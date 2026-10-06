# -*- coding: utf-8 -*-
"""
ARAB STORE — app.py
======================
سيرفر الموقع (Backend). بيخدم صفحات الموقع (site/) + REST API كامل.
ما بيعيد كتابة منطق البوت — بيستورد lod.py ويستخدم نفس دواله مباشرة
(نفس قاعدة بيانات products.db، نفس حساب الأسعار، نفس التحقق من
الإيداع التلقائي، نفس عملية الشراء من مزودي API).

تشغيل محلي:
    pip install -r requirements.txt
    python app.py
    → الموقع: http://localhost:5000
"""
import os
import json
import re
import hmac
import secrets
import string
import sqlite3
import uuid
import threading
import time
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import lod  # ← كل منطق البوت (قاعدة البيانات، الشراء، الإيداع، إلخ)

# =============================================================
# إعدادات عامة
# =============================================================
SECRET_KEY = os.environ.get("ARAB_SECRET_KEY")
if not SECRET_KEY:
    # قيمة ثابتة افتراضية (بدل ما تتغيّر عشوائياً كل إعادة تشغيل) — حتى تسجيل الدخول
    # يضل محفوظ عند المستخدمين مهما أعدنا تشغيل السيرفر. لأعلى أمان بالإنتاج الحقيقي،
    # فيك تحدد ARAB_SECRET_KEY بمتغيرات البيئة بقيمتك الخاصة وهاد رح ياخذ الأولوية دايماً.
    SECRET_KEY = "arab-store-fixed-key-9f3a7c2e1b6d4508a2c9e7f01d3b6a84"
    print("ℹ️  ARAB_SECRET_KEY غير محدد بمتغيرات البيئة — يتم استخدام قيمة ثابتة افتراضية (تسجيل الدخول بيضل محفوظ).")
    print("    لأعلى أمان بالإنتاج، تقدر تحدد قيمتك الخاصة: ARAB_SECRET_KEY=قيمتك_الخاصة python app.py")

ADMIN_PANEL_PASSWORD = os.environ.get("ARAB_ADMIN_PASSWORD", "aboudy231")  # ⚠️ غيّرها!
if ADMIN_PANEL_PASSWORD == "aboudy231":
    print("⚠️  تحذير أمني: كلمة مرور لوحة الأدمن لسا الافتراضية (aboudy231) — غيّرها عبر ARAB_ADMIN_PASSWORD قبل النشر الحقيقي.")
WEB_ID_OFFSET = 9_000_000_000_000  # نطاق آيدي خاص بحسابات الموقع غير المربوطة بتيليجرام بعد
TOKEN_MAX_AGE = 60 * 60 * 24 * 30  # شهر
ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp", "gif"}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 ميغا

app = Flask(__name__, static_folder="site", static_url_path="")
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE
serializer = URLSafeTimedSerializer(SECRET_KEY)
admin_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="admin")
UPLOAD_DIR = os.path.join(app.static_folder, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ===== حماية من الطلبات الكثيفة (Rate Limiting) =====
# حد عام معقول لكل عناوين الـ IP، وحدود أشد على تسجيل الدخول/التسجيل لمنع
# محاولات تخمين كلمات السر (Brute-force). تخزين العدّاد بالذاكرة (كافي لسيرفر
# واحد)؛ لو صار عندك أكتر من سيرفر لازم storage_uri="redis://..." بدل الذاكرة.
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per hour", "40 per minute"],
    storage_uri="memory://",
)


# =============================================================
# تهيئة جداول الموقع الإضافية (فوق نفس قاعدة بيانات البوت)
# =============================================================
def init_web_tables():
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS web_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            site_user_id INTEGER UNIQUE,
            telegram_user_id INTEGER,
            api_key TEXT UNIQUE,
            allowed_ips TEXT DEFAULT '',
            api_enabled INTEGER DEFAULT 0,
            preferred_currency TEXT DEFAULT 'USD',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS link_codes (
            code TEXT PRIMARY KEY,
            web_user_id INTEGER NOT NULL,
            expires_at TIMESTAMP NOT NULL
        )""")
        try:
            c.execute("ALTER TABLE sections ADD COLUMN image TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # العمود موجود مسبقاً
        try:
            c.execute("ALTER TABLE web_users ADD COLUMN api_enabled INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # العمود موجود مسبقاً (لقاعدة بيانات قديمة)
        try:
            c.execute("ALTER TABLE web_users ADD COLUMN preferred_currency TEXT DEFAULT 'USD'")
        except sqlite3.OperationalError:
            pass
        # ===== بلد المستخدم ورقم هاتفه (تُطلب عند التسجيل) =====
        try:
            c.execute("ALTER TABLE web_users ADD COLUMN country TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE web_users ADD COLUMN phone TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE auto_deposit_methods ADD COLUMN gateway_type TEXT DEFAULT 'verify'")
        except sqlite3.OperationalError:
            pass  # العمود موجود مسبقاً
        try:
            c.execute("ALTER TABLE deposit_requests ADD COLUMN invoice_ref TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # العمود موجود مسبقاً
        try:
            c.execute("ALTER TABLE categories ADD COLUMN margin_percent REAL DEFAULT NULL")
        except sqlite3.OperationalError:
            pass  # العمود موجود مسبقاً
        # ===== كمية المخزون لكل فئة (NULL = غير محدودة، رقم = يتناقص مع كل عملية شراء) =====
        try:
            c.execute("ALTER TABLE categories ADD COLUMN stock_qty INTEGER DEFAULT NULL")
        except sqlite3.OperationalError:
            pass
        # ===== عملة إدخال المبلغ لكل طريقة إيداع (usd = المستخدم يكتب دولار، syp = يكتب ليرة سورية) =====
        try:
            c.execute("ALTER TABLE deposit_methods ADD COLUMN input_currency TEXT DEFAULT 'usd'")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE auto_deposit_methods ADD COLUMN input_currency TEXT DEFAULT 'usd'")
        except sqlite3.OperationalError:
            pass
        # ===== معرّفات عامة ثابتة (public_id) للمنتجات والفئات — لعملاء API الخارجيين =====
        try:
            c.execute("ALTER TABLE products ADD COLUMN public_id TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE categories ADD COLUMN public_id TEXT")
        except sqlite3.OperationalError:
            pass
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_products_public_id ON products(public_id)")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_public_id ON categories(public_id)")
        # ترحيل تلقائي: أي منتج/فئة قديمة بدون public_id (من قبل هالتحديث) بتاخذ وحدة جديدة
        c.execute("SELECT id FROM products WHERE public_id IS NULL OR public_id = ''")
        for (pid,) in c.fetchall():
            c.execute("UPDATE products SET public_id = ? WHERE id = ?", (gen_public_id("prd"), pid))
        c.execute("SELECT id FROM categories WHERE public_id IS NULL OR public_id = ''")
        for (cid,) in c.fetchall():
            c.execute("UPDATE categories SET public_id = ? WHERE id = ?", (gen_public_id("cat"), cid))
        # ===== دعم التكرار (idempotency) وحقول مخصّصة لطلبات الـ API الرسمية =====
        try:
            c.execute("ALTER TABLE api_orders ADD COLUMN order_uuid TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE api_orders ADD COLUMN custom_params TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE shop_orders ADD COLUMN order_uuid TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE shop_orders ADD COLUMN custom_params TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        c.execute("""CREATE TABLE IF NOT EXISTS banner_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT DEFAULT '',
            kind TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read)")
        # ترحيل تلقائي: لو كان موجود بانر قديم (نظام صورة واحدة)، ننقله للجدول الجديد كأول صورة
        old_banner = None
        try:
            c.execute("SELECT value FROM settings WHERE key = 'banner_image'")
            row = c.fetchone()
            old_banner = row[0] if row else None
        except sqlite3.OperationalError:
            pass
        if old_banner:
            c.execute("SELECT COUNT(*) FROM banner_images")
            if c.fetchone()[0] == 0:
                c.execute("INSERT INTO banner_images (image, sort_order) VALUES (?, 0)", (old_banner,))


def save_upload(file_storage):
    """يحفظ صورة مرفوعة بمجلد site/uploads ويرجع رابطها العام."""
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in ALLOWED_IMAGE_EXT:
        return None
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(UPLOAD_DIR, secure_filename(filename)))
    return f"/uploads/{filename}"


def gen_api_key():
    return "ALSH-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(28))


def gen_public_id(prefix=None):
    """معرّف عام ثابت وفريد (رقم فقط، مثل 52134) يولّد تلقائياً مرة وحدة عند الإنشاء
    ولا يتغير أبداً بعدها — آمن للمشاركة مع عملاء API/شركاء يربطون منتجاتهم بمنتجاتك.
    رقم فقط (بدون بادئة حرفية) لأن كثير من أنظمة الربط الخارجية (بوتات/مواقع شركاء)
    بتتوقع رقم صرف بالـID وبترفض أي رمز فيه حروف."""
    with lod.get_db() as conn:
        c = conn.cursor()
        for _ in range(20):
            candidate = str(secrets.randbelow(90000) + 10000)  # رقم من 5 خانات: 10000-99999
            c.execute("SELECT 1 FROM products WHERE public_id = ? UNION SELECT 1 FROM categories WHERE public_id = ?",
                       (candidate, candidate))
            if not c.fetchone():
                return candidate
    # احتياط نادر جداً لو انشغلت كل الأرقام (يستخدم مجال أوسع لضمان عدم التعارض)
    return str(secrets.randbelow(9000000) + 1000000)


# =============================================================
# أدوات مساعدة للمستخدم/التوكن
# =============================================================
def get_web_user_by_email(email):
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, name, email, password_hash, site_user_id, telegram_user_id, api_key, allowed_ips, api_enabled, preferred_currency, country, phone
                     FROM web_users WHERE email = ?""", (email.lower().strip(),))
        return c.fetchone()


def get_web_user_by_id(web_id):
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, name, email, password_hash, site_user_id, telegram_user_id, api_key, allowed_ips, api_enabled, preferred_currency, country, phone
                     FROM web_users WHERE id = ?""", (web_id,))
        return c.fetchone()


def get_web_user_by_api_key(api_key):
    if not api_key:
        return None
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, name, email, password_hash, site_user_id, telegram_user_id, api_key, allowed_ips, api_enabled, preferred_currency, country, phone
                     FROM web_users WHERE api_key = ? AND api_enabled = 1""", (api_key,))
        return c.fetchone()


def effective_user_id(web_row):
    """آيدي المستخدم الفعلي بقاعدة بيانات البوت (تيليجرام إذا مربوط، وإلا آيدي الموقع)."""
    return web_row[5] if web_row[5] else web_row[4]


def user_public_dict(web_row):
    uid = effective_user_id(web_row)
    balance_syp = lod.get_user_balance(uid)
    rate = lod.get_exchange_rate()
    tier = lod.get_user_discount_tier(uid)
    return {
        "id": web_row[0],
        "name": web_row[1],
        "email": web_row[2],
        "telegram_linked": bool(web_row[5]),
        "balance_syp": balance_syp,
        "balance_usd": round(balance_syp / rate, 2) if rate else 0,
        "api_enabled": bool(web_row[8]),
        "preferred_currency": (web_row[9] or "USD").upper() if len(web_row) > 9 else "USD",
        "country": (web_row[10] or "") if len(web_row) > 10 else "",
        "phone": (web_row[11] or "") if len(web_row) > 11 else "",
        "discount_tier_name": tier[1] if tier else "",
        "discount_percent": tier[2] if tier else 0,
        # صلاحيات الإدارة — الواجهة بتعتمد عليها لإظهار زر "لوحة الأدمن"
        "is_owner": is_owner_email(web_row[2]),
        "is_admin": is_admin_email(web_row[2]),
    }


# البريد الرئيسي للمالك — بيدخل مباشرة كأدمن كامل الصلاحيات
OWNER_EMAILS = {"aboudyhassoun3@gmail.com"}


def is_owner_email(email):
    return (email or "").strip().lower() in OWNER_EMAILS


def is_admin_email(email):
    """أدمن = المالك، أو بريد مضاف بجدول web_admins، أو مستخدم عليه is_admin بالبوت."""
    email = (email or "").strip().lower()
    if not email:
        return False
    if email in OWNER_EMAILS:
        return True
    try:
        return email in _get_web_admin_emails()
    except Exception:
        return False


def get_optional_web_user():
    """متل require_auth بس ما بترفض الطلب لو مافي توكن — مفيدة للـ endpoints العامة
    (متل عرض المنتجات) يلي بدها تطبّق خصم المستخدم لو مسجّل دخول بدون ما تصير محمية بالكامل."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1]
    try:
        data = serializer.loads(token, max_age=TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    return get_web_user_by_id(data.get("web_id"))


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"message": "سجّل دخولك أولاً"}), 401
        token = auth.split(" ", 1)[1]
        try:
            data = serializer.loads(token, max_age=TOKEN_MAX_AGE)
        except (BadSignature, SignatureExpired):
            return jsonify({"message": "جلستك انتهت، سجّل دخولك من جديد"}), 401
        web_row = get_web_user_by_id(data.get("web_id"))
        if not web_row:
            return jsonify({"message": "الحساب غير موجود"}), 401
        request.web_user = web_row
        return f(*args, **kwargs)
    return wrapper


def _decode_admin_token():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1]
    try:
        return admin_serializer.loads(token, max_age=60 * 60 * 12)
    except (BadSignature, SignatureExpired):
        return None


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        payload = _decode_admin_token()
        if not payload:
            return jsonify({"message": "دخول غير مصرح"}), 401
        request.admin_payload = payload
        return f(*args, **kwargs)
    return wrapper


def require_owner(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        payload = _decode_admin_token()
        if not payload:
            return jsonify({"message": "دخول غير مصرح"}), 401
        if not payload.get("owner"):
            return jsonify({"message": "هذا الإجراء مسموح للمالك فقط"}), 403
        request.admin_payload = payload
        return f(*args, **kwargs)
    return wrapper


def _ensure_web_admins_table():
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS web_admins (
            email TEXT PRIMARY KEY,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")


def _get_web_admin_emails():
    _ensure_web_admins_table()
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT email FROM web_admins")
        return {r[0].lower() for r in c.fetchall()}


# =============================================================
# 1) المصادقة (تسجيل / دخول / الحساب / كود ربط تيليجرام)
# =============================================================
@app.post("/api/auth/register")
@limiter.limit("8 per hour")
def auth_register():
    body = request.get_json(force=True, silent=True) or {}
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    country = (body.get("country") or "").strip()
    phone = re.sub(r"[^\d+]", "", (body.get("phone") or "").strip())

    if not name or not email or len(password) < 6:
        return jsonify({"message": "تأكد من الاسم والإيميل وكلمة مرور لا تقل عن 6 أحرف"}), 400
    if not country:
        return jsonify({"message": "اختر البلد"}), 400
    if len(phone) < 6:
        return jsonify({"message": "أدخل رقم هاتف صحيح"}), 400
    if get_web_user_by_email(email):
        return jsonify({"message": "هذا الإيميل مسجّل مسبقاً"}), 409

    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO web_users (name, email, password_hash, country, phone) VALUES (?, ?, ?, ?, ?)",
                   (name, email, generate_password_hash(password), country, phone))
        web_id = c.lastrowid
        site_user_id = WEB_ID_OFFSET + web_id
        c.execute("UPDATE web_users SET site_user_id = ? WHERE id = ?",
                   (site_user_id, web_id))
        # إنشاء صف رصيد بقاعدة بيانات البوت لنفس المستخدم
        c.execute("INSERT OR IGNORE INTO users (user_id, balance, is_admin, blocked) VALUES (?, 0, 0, 0)",
                   (site_user_id,))

    web_row = get_web_user_by_id(web_id)
    token = serializer.dumps({"web_id": web_id})
    lod.notify_admin("👤 مستخدم جديد سجّل بالموقع",
                     f"الاسم: {name}\nالإيميل: {email}\nالبلد: {country}\nالهاتف: {phone}\n🆔 {site_user_id}")
    return jsonify({"token": token, "user": user_public_dict(web_row)})


@app.post("/api/auth/login")
@limiter.limit("10 per minute")
def auth_login():
    body = request.get_json(force=True, silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    web_row = get_web_user_by_email(email)
    if not web_row or not check_password_hash(web_row[3], password):
        return jsonify({"message": "الإيميل أو كلمة المرور غير صحيحة"}), 401

    token = serializer.dumps({"web_id": web_row[0]})
    return jsonify({"token": token, "user": user_public_dict(web_row)})


@app.get("/api/auth/me")
@require_auth
def auth_me():
    return jsonify({"user": user_public_dict(request.web_user)})


@app.post("/api/auth/link-code")
@require_auth
def auth_link_code():
    web_row = request.web_user
    if web_row[5]:
        return jsonify({"message": "حسابك مربوط ببوت تيليجرام مسبقاً"}), 400
    code = "".join(secrets.choice(string.digits) for _ in range(6))
    expires_at = datetime.now() + timedelta(minutes=15)
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO link_codes (code, web_user_id, expires_at) VALUES (?, ?, ?)",
                   (code, web_row[0], expires_at))
    bot_username = lod.get_bot_username()
    deep_link = f"https://t.me/{bot_username}?start=link_{code}" if bot_username else None
    return jsonify({"code": code, "expires_in_minutes": 15, "deep_link": deep_link,
                     "instructions": "افتح بوت تيليجرام وأرسل: /link " + code})


@app.post("/api/auth/update-profile")
@require_auth
def auth_update_profile():
    b = request.get_json(force=True, silent=True) or {}
    name = (b.get("name") or "").strip()
    email = (b.get("email") or "").strip().lower()
    if not name or not email:
        return jsonify({"message": "الاسم والبريد مطلوبين"}), 400
    web_id = request.web_user[0]
    existing = get_web_user_by_email(email)
    if existing and existing[0] != web_id:
        return jsonify({"message": "هذا البريد مستخدم من حساب آخر"}), 409
    with lod.get_db() as conn:
        conn.cursor().execute("UPDATE web_users SET name=?, email=? WHERE id=?", (name, email, web_id))
    return jsonify({"message": "تم الحفظ"})

@app.post("/api/auth/currency")
@require_auth
def auth_update_currency():
    currency = ((request.get_json(force=True, silent=True) or {}).get("currency") or "").upper()
    if currency not in ("USD", "SYP"):
        return jsonify({"message": "العملة غير مدعومة"}), 400
    with lod.get_db() as conn:
        conn.cursor().execute("UPDATE web_users SET preferred_currency = ? WHERE id = ?",
                              (currency, request.web_user[0]))
    return jsonify({"message": "تم حفظ عملة الشراء", "currency": currency})


@app.post("/api/auth/change-password")
@require_auth
def auth_change_password():
    b = request.get_json(force=True, silent=True) or {}
    old_pw = b.get("old_password", "")
    new_pw = b.get("new_password", "")
    if len(new_pw) < 6:
        return jsonify({"message": "كلمة المرور الجديدة لازم تكون 6 أحرف على الأقل"}), 400
    w = request.web_user
    if not check_password_hash(w[3], old_pw):
        return jsonify({"message": "كلمة المرور الحالية غير صحيحة"}), 401
    with lod.get_db() as conn:
        conn.cursor().execute("UPDATE web_users SET password_hash=? WHERE id=?",
                               (generate_password_hash(new_pw), w[0]))
    return jsonify({"message": "تم تغيير كلمة المرور"})


@app.post("/api/auth/forgot-password")
@limiter.limit("6 per hour")
def auth_forgot_password():
    b = request.get_json(force=True, silent=True) or {}
    email = (b.get("email") or "").strip().lower()
    w = get_web_user_by_email(email)
    if not w:
        return jsonify({"message": "هذا البريد غير مسجّل"}), 404
    uid = w[5]
    if not uid:
        return jsonify({"message": "حسابك غير مربوط ببوت تيليجرام، تواصل مع الدعم عبر تيليجرام لاستعادة كلمة المرور"}), 400
    code = "".join(secrets.choice(string.digits) for _ in range(6))
    expires_at = datetime.now() + timedelta(minutes=30)
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO link_codes (code, web_user_id, expires_at) VALUES (?, ?, ?)",
                   ("reset_" + code, w[0], expires_at))
    try:
        lod.send_message(uid, f"🔑 كود إعادة تعيين كلمة المرور:\n\n<b>{code}</b>\n\nصالح 30 دقيقة. لا تشاركه مع أحد.")
    except Exception:
        pass
    return jsonify({"message": "تم إرسال كود التحقق عبر تيليجرام"})


@app.post("/api/auth/reset-password")
def auth_reset_password():
    b = request.get_json(force=True, silent=True) or {}
    code = (b.get("code") or "").strip()
    new_pw = b.get("new_password", "")
    if len(new_pw) < 6:
        return jsonify({"message": "كلمة المرور لازم تكون 6 أحرف على الأقل"}), 400
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT web_user_id FROM link_codes WHERE code=? AND expires_at > datetime('now')", ("reset_" + code,))
        row = c.fetchone()
        if not row:
            return jsonify({"message": "الكود غير صحيح أو منتهي الصلاحية"}), 400
        c.execute("UPDATE web_users SET password_hash=? WHERE id=?",
                   (generate_password_hash(new_pw), row[0]))
        c.execute("DELETE FROM link_codes WHERE code=?", ("reset_" + code,))
    return jsonify({"message": "تم تعيين كلمة مرور جديدة"})


# =============================================================
# 2) تصفّح المتجر (عام - بدون تسجيل دخول)
# =============================================================
def get_setting(key, default=""):
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = c.fetchone()
        return row[0] if row else default


def set_setting(key, value):
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


# =============================================================
# وضع الصيانة (Maintenance Mode)
# =============================================================
def get_maintenance_status():
    """يرجع (enabled, ends_at_iso, seconds_left). يوقف الصيانة تلقائياً لما ينتهي الوقت."""
    enabled = get_setting("maintenance_enabled", "false") == "true"
    ends_at_str = get_setting("maintenance_ends_at", "")
    if not enabled or not ends_at_str:
        return False, None, 0
    try:
        ends_at = datetime.fromisoformat(ends_at_str)
    except ValueError:
        return False, None, 0
    seconds_left = int((ends_at - datetime.now()).total_seconds())
    if seconds_left <= 0:
        set_setting("maintenance_enabled", "false")
        return False, None, 0
    return True, ends_at_str, seconds_left


@app.get("/api/maintenance-status")
def maintenance_status():
    enabled, ends_at, seconds_left = get_maintenance_status()
    return jsonify({"enabled": enabled, "ends_at": ends_at, "seconds_left": seconds_left})


@app.get("/api/admin/maintenance")
@require_admin
def admin_get_maintenance():
    enabled, ends_at, seconds_left = get_maintenance_status()
    return jsonify({"enabled": enabled, "ends_at": ends_at, "seconds_left": seconds_left})


@app.post("/api/admin/maintenance")
@require_admin
def admin_set_maintenance():
    b = request.get_json(force=True, silent=True) or {}
    enabled = bool(b.get("enabled"))
    if enabled:
        hours = float(b.get("hours") or 1)
        ends_at = datetime.now() + timedelta(hours=hours)
        set_setting("maintenance_enabled", "true")
        set_setting("maintenance_ends_at", ends_at.isoformat())
    else:
        set_setting("maintenance_enabled", "false")
    return jsonify({"message": "تم الحفظ"})


# الأمسار المسموحة أثناء وضع الصيانة (تسجيل الدخول + كل مسارات الأدمن + حالة الصيانة نفسها)
_MAINTENANCE_ALLOWED_PREFIXES = ("/api/auth/", "/api/admin/", "/api/maintenance-status")

@app.before_request
def block_during_maintenance():
    path = request.path
    if not path.startswith("/api/"):
        return None  # الملفات الثابتة (HTML/CSS/JS) بتفلتر بالواجهة نفسها
    if path.startswith(_MAINTENANCE_ALLOWED_PREFIXES):
        return None
    enabled, _, _ = get_maintenance_status()
    if enabled:
        return jsonify({"message": "الموقع في فترة الصيانة حالياً، نعمل على تحديثات أفضل", "maintenance": True}), 503
    return None


# =============================================================
CONTACT_SETTING_KEYS = (
    "support_whatsapp_number", "support_whatsapp_url",
    "support_telegram_url", "whatsapp_channel_url", "telegram_channel_url",
)


def _contact_settings():
    """أرقام وروابط التواصل التي تظهر داخل زر السماعة العائم بالموقع."""
    number = (get_setting("support_whatsapp_number", "") or "").strip()
    wa_url = (get_setting("support_whatsapp_url", "") or "").strip()
    if not wa_url and number:
        wa_url = "https://wa.me/" + re.sub(r"[^\d]", "", number)
    tg_user = lod.get_support_username()
    return {
        "whatsapp_number": number,
        "whatsapp_url": wa_url,
        "telegram_url": (get_setting("support_telegram_url", "") or "").strip() or (f"https://t.me/{tg_user}" if tg_user else ""),
        "whatsapp_channel_url": (get_setting("whatsapp_channel_url", "") or "").strip(),
        "telegram_channel_url": (get_setting("telegram_channel_url", "") or "").strip(),
    }


@app.get("/api/store/settings")
def store_settings():
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT image FROM banner_images ORDER BY sort_order ASC, id ASC")
        banner_images = [r[0] for r in c.fetchall()]
    return jsonify({
        "exchange_rate": lod.get_exchange_rate(),
        "support_username": lod.get_support_username(),
        "banner_images": banner_images,
        "logo_image": get_setting("logo_image", ""),
        "welcome_popup_enabled": get_setting("welcome_popup_enabled", "false") == "true",
        "welcome_popup_text": get_setting("welcome_popup_text", ""),
        "ai_image_api_url": get_setting("ai_image_api_url", ""),
        "ai_image_api_key": get_setting("ai_image_api_key", ""),
        "ai_image_prompt_template": get_setting("ai_image_prompt_template", DEFAULT_AI_PROMPT_TEMPLATE),
        "dev_logo": get_setting("dev_logo", ""),
        "contact": _contact_settings(),
    })


@app.get("/api/store/sections")
def store_sections():
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, name, color, emoji, image FROM sections
                     WHERE is_active = 1 ORDER BY sort_order ASC, id ASC""")
        rows = c.fetchall()
    return jsonify([{"id": r[0], "name": r[1], "color": r[2], "emoji": r[3], "image": r[4] or ""} for r in rows])


@app.get("/api/store/subsections")
def store_subsections():
    """يرجع الأقسام الفرعية المفعّلة التابعة لقسم رئيسي معيّن"""
    section_id = request.args.get("section_id", type=int)
    if not section_id:
        return jsonify({"message": "section_id مطلوب"}), 400
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, section_id, name, emoji, image FROM subsections
                     WHERE section_id = ? AND is_active = 1 ORDER BY sort_order ASC, id ASC""", (section_id,))
        rows = c.fetchall()
    return jsonify([{"id": r[0], "section_id": r[1], "name": r[2], "emoji": r[3], "image": r[4] or ""} for r in rows])


@app.get("/api/store/products")
def store_products():
    section = request.args.get("section", "")
    subsection_id = request.args.get("subsection_id", type=int)
    if subsection_id:
        with lod.get_db() as conn:
            c = conn.cursor()
            c.execute("""SELECT id, name, emoji, image FROM products
                         WHERE subsection_id = ? ORDER BY sort_order ASC, id ASC""", (subsection_id,))
            rows = c.fetchall()
        return jsonify([{"id": r[0], "name": r[1], "emoji": r[2], "image": r[3] or ""} for r in rows])
    if not section:
        return jsonify({"message": "section أو subsection_id مطلوب"}), 400
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, name, emoji, image FROM products
                     WHERE category = ? AND (subsection_id IS NULL OR subsection_id = 0)
                     ORDER BY sort_order ASC, id ASC""", (section,))
        rows = c.fetchall()
    return jsonify([{"id": r[0], "name": r[1], "emoji": r[2], "image": r[3] or ""} for r in rows])


@app.get("/api/store/product/<int:product_id>")
def store_product_detail(product_id):
    p = lod.get_product_by_id(product_id)  # id, name, category, emoji, description, image
    if not p:
        return jsonify({"message": "المنتج غير موجود"}), 404
    return jsonify({"id": p[0], "name": p[1], "category": p[2], "emoji": p[3], "image": p[5] or ""})


@app.get("/api/store/categories")
def store_categories():
    product_id = request.args.get("product_id", type=int)
    if not product_id:
        return jsonify({"message": "product_id مطلوب"}), 400
    rate = lod.get_exchange_rate()

    discount_percent = 0
    web_row = get_optional_web_user()
    if web_row:
        _, discount_percent = lod.get_user_discount(effective_user_id(web_row))

    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, name, price, type, min_qty, max_qty, image, stock_qty, COALESCE(NULLIF(unit_qty, 0), 1),
                            COALESCE(requires_id, 1)
                     FROM categories WHERE product_id = ?""", (product_id,))
        rows = c.fetchall()

    result = []
    for r in rows:
        base_price = r[2]
        final_price = base_price * (1 - discount_percent / 100) if discount_percent else base_price
        stock_qty = r[7]
        item = {
            "id": r[0], "name": r[1], "price_usd": round(final_price, 4), "price_syp": round(final_price * rate),
            "type": r[3], "min_qty": r[4], "max_qty": r[5], "image": r[6] or "",
            "stock_qty": stock_qty, "unit_qty": r[8], "available": (stock_qty is None or stock_qty > 0),
            "requires_id": bool(r[9]),
        }
        if discount_percent:
            item["original_price_usd"] = base_price
            item["discount_percent"] = discount_percent
        result.append(item)
    return jsonify(result)


# =============================================================
# 2.5) الإشعارات
# =============================================================
@app.get("/api/notifications")
@require_auth
def notifications_list():
    uid = effective_user_id(request.web_user)
    rows = lod.get_notifications(uid, limit=30)
    unread = lod.count_unread_notifications(uid)
    return jsonify({
        "unread": unread,
        "items": [{
            "id": r[0], "title": r[1], "message": r[2], "kind": r[3],
            "is_read": bool(r[4]), "created_at": r[5]
        } for r in rows]
    })


@app.post("/api/notifications/mark-read")
@require_auth
def notifications_mark_read():
    uid = effective_user_id(request.web_user)
    lod.mark_notifications_read(uid)
    return jsonify({"message": "تم"})


# =============================================================
# 3) المحفظة + الإيداع
# =============================================================
@app.get("/api/wallet")
@require_auth
def wallet_summary():
    return jsonify({"user": user_public_dict(request.web_user)})


@app.get("/api/wallet/transactions")
@require_auth
def wallet_transactions():
    uid = effective_user_id(request.web_user)
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT type, amount, description, created_at FROM user_transactions
                     WHERE user_id = ? ORDER BY created_at DESC LIMIT 100""", (uid,))
        rows = c.fetchall()
    return jsonify([{"type": r[0], "amount": r[1], "description": r[2], "date": r[3]} for r in rows])


@app.get("/api/wallet/deposit-history")
@require_auth
def wallet_deposit_history():
    uid = effective_user_id(request.web_user)
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT method_title, amount_usd, amount_syp, status, created_at
                     FROM deposit_requests WHERE user_id = ? ORDER BY created_at DESC LIMIT 30""", (uid,))
        rows = c.fetchall()
    return jsonify([{"method_title": r[0], "amount_usd": r[1], "amount_syp": r[2],
                      "status": r[3], "date": r[4]} for r in rows])


@app.get("/api/wallet/deposit-methods")
def wallet_deposit_methods():
    auto = lod.get_all_auto_deposit_methods()    # id, title, description, code, rate, token, url, image, gateway_type
    manual = lod.get_all_deposit_methods()        # id, title, description, code, rate, image
    return jsonify({
        "auto": [{"id": m[0], "title": m[1], "description": m[2], "code": m[3], "image": m[7] or "",
                   "gateway_type": m[8] if len(m) > 8 else "verify",
                   "input_currency": m[9] if len(m) > 9 else "usd"} for m in auto],
        "manual": [{"id": m[0], "title": m[1], "description": m[2], "code": m[3], "image": m[5] or "",
                     "input_currency": m[6] if len(m) > 6 else "usd"} for m in manual],
    })


@app.post("/api/wallet/deposit")
@require_auth
def wallet_deposit():
    web_row = request.web_user
    uid = effective_user_id(web_row)
    body = request.get_json(force=True, silent=True) or {}
    method_id = body.get("method_id")
    kind = body.get("kind")  # 'auto' | 'manual'
    amount_entered = float(body.get("amount_usd") or 0)  # القيمة الخام يلي كتبها المستخدم (دولار أو ليرة حسب عملة الطريقة)
    code = (body.get("transaction_code") or "").strip()

    if amount_entered <= 0 or not code or kind not in ("auto", "manual"):
        return jsonify({"message": "تأكد من المبلغ وكود العملية"}), 400

    rate = lod.get_exchange_rate()

    if kind == "auto":
        method = lod.get_auto_deposit_method_by_id(method_id)
        if not method:
            return jsonify({"message": "طريقة الإيداع غير موجودة"}), 404
        _, title, _, _, _, api_token, api_url, _, gateway_type = method[:9]
        input_currency = method[9] if len(method) > 9 else "usd"
        if input_currency == "syp":
            amount_syp = amount_entered
            amount_usd = round(amount_syp / rate, 4) if rate else 0
        else:
            amount_usd = amount_entered
            amount_syp = amount_usd * rate
        if gateway_type == "invoice":
            return jsonify({"message": "هذه الطريقة تعمل عبر إنشاء فاتورة، استخدم /wallet/deposit/create-invoice"}), 400
        ok = lod.verify_auto_deposit(api_token, api_url, code, amount_syp)
        if not ok:
            return jsonify({"message": "لم يتم العثور على عملية مطابقة لهذا الكود، تأكد منه وحاول مجدداً"}), 400

        new_balance = lod.update_user_balance(uid, amount_syp)
        with lod.get_db() as conn:
            c = conn.cursor()
            c.execute("""INSERT INTO user_transactions (user_id, type, amount, description)
                         VALUES (?, 'deposit', ?, ?)""", (uid, amount_syp, f"إيداع تلقائي عبر {title} (الموقع)"))
        lod.add_deposit_request(uid, web_row[2], web_row[1], title, amount_usd, amount_syp, code)
        return jsonify({"message": "تم الإيداع بنجاح", "new_balance_syp": new_balance})

    else:
        method = lod.get_deposit_method_by_id(method_id)
        if not method:
            return jsonify({"message": "طريقة الإيداع غير موجودة"}), 404
        title = method[1]
        input_currency = method[6] if len(method) > 6 else "usd"
        if input_currency == "syp":
            amount_syp = amount_entered
            amount_usd = round(amount_syp / rate, 4) if rate else 0
        else:
            amount_usd = amount_entered
            amount_syp = amount_usd * rate
        req_id = lod.add_deposit_request(uid, web_row[2], web_row[1], title, amount_usd, amount_syp, code)
        # نفس تنبيه الأدمن المستخدم بالبوت تماماً (نفس الأزرار)
        keyboard = {"inline_keyboard": [[
            {"text": "🟢 قبول الإيداع", "callback_data": lod.safe_callback_data(f"accept_deposit_{req_id}"), "color": "success"},
            {"text": "🔴 رفض الإيداع", "callback_data": lod.safe_callback_data(f"reject_deposit_{req_id}"), "color": "danger"},
        ]]}
        lod.send_message(lod.ADMIN_CHAT_ID,
                          f"💳 طلب إيداع جديد من الموقع\n"
                          f"👤 {web_row[1]} ({web_row[2]})\n"
                          f"💰 {amount_usd}$ ({amount_syp:,.0f} ل.س)\n"
                          f"🏷️ {title}\n🔑 الكود: {code}", reply_markup=keyboard)
        return jsonify({"message": "تم إرسال طلب الإيداع، بانتظار مراجعة الدعم", "request_id": req_id})


@app.post("/api/wallet/deposit/create-invoice")
@require_auth
def wallet_deposit_create_invoice():
    """
    لطرق الإيداع من نوع 'فاتورة' (مثل شام كاش): يولّد رابط دفع جاهز
    وينشئ طلب إيداع 'pending' بانتظار تأكيد المزوّد عبر webhook.
    """
    web_row = request.web_user
    uid = effective_user_id(web_row)
    body = request.get_json(force=True, silent=True) or {}
    method_id = body.get("method_id")
    currency = (body.get("currency") or "USD").upper()
    amount = float(body.get("amount") or 0)
    if amount <= 0 or currency not in ("USD", "SYP"):
        return jsonify({"message": "أدخل مبلغ صحيح وعملة مدعومة (USD/SYP)"}), 400

    method = lod.get_auto_deposit_method_by_id(method_id)
    if not method:
        return jsonify({"message": "طريقة الإيداع غير موجودة"}), 404
    _, title, _, _, _, api_token, api_url, _, gateway_type = method
    if gateway_type != "invoice":
        return jsonify({"message": "هذه الطريقة لا تدعم إنشاء الفاتورة"}), 400

    rate = lod.get_exchange_rate()
    amount_usd = amount if currency == "USD" else round(amount / rate, 2)
    amount_syp = amount_usd * rate

    invoice_ref = f"NZ-{uid}-{int(datetime.now().timestamp())}"
    callback_url = request.url_root.rstrip('/') + "/api/webhooks/deposit-invoice"
    payment_url, error = lod.create_gateway_invoice(api_token, api_url, amount, currency, invoice_ref, callback_url)
    if not payment_url:
        return jsonify({"message": error or "تعذّر إنشاء الفاتورة، حاول لاحقاً"}), 502

    req_id = lod.add_deposit_request(uid, web_row[2], web_row[1], title, amount_usd, amount_syp, invoice_ref)
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE deposit_requests SET invoice_ref = ? WHERE id = ?", (invoice_ref, req_id))
    return jsonify({"message": "تم إنشاء الفاتورة", "payment_url": payment_url, "invoice_ref": invoice_ref})


@app.post("/api/webhooks/deposit-invoice")
def webhook_deposit_invoice():
    """
    نقطة استدعاء (Webhook) يستدعيها مزوّد الدفع (شام كاش) بعد إتمام أو فشل عملية
    الفاتورة. علّي: وجّه رابط الـ callback من إعدادات شام كاش لهذا المسار،
    وتأكد من ضبط شكل الحمولة (body) هون ليطابق اللي بيرسله مزوّدك فعلياً.

    الحمولة المتوقعة حالياً: { "reference": invoice_ref, "status": "paid" | "failed", "token": api_token }
    """
    body = request.get_json(force=True, silent=True) or {}
    invoice_ref = body.get("reference") or body.get("invoice_ref") or ""
    status = (body.get("status") or "").lower()
    token = body.get("token") or request.headers.get("X-Api-Key") or ""
    if not invoice_ref:
        return jsonify({"message": "reference مطلوب"}), 400
    if not token:
        return jsonify({"message": "token مطلوب"}), 401

    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, method_title FROM deposit_requests WHERE invoice_ref = ? AND status = 'pending'", (invoice_ref,))
        row = c.fetchone()
        if not row:
            return jsonify({"message": "لا يوجد طلب إيداع مطابق أو تمت معالجته مسبقاً"}), 404
        req_id, method_title = row
        c.execute("SELECT api_token FROM auto_deposit_methods WHERE title = ?", (method_title,))
        method_row = c.fetchone()

    # ===== تحقق إلزامي من التوكن قبل تأكيد أي إيداع — بدونه أي طرف يعرف invoice_ref فيه يزوّر تأكيد الدفع =====
    expected_token = method_row[0] if method_row else None
    if not expected_token or not hmac.compare_digest(str(token), str(expected_token)):
        return jsonify({"message": "توكن غير صحيح"}), 401

    if status in ("paid", "success", "completed"):
        lod.accept_deposit_request(req_id)
        return jsonify({"message": "تم تأكيد الإيداع"})
    else:
        lod.reject_deposit_request(req_id)
        return jsonify({"message": "تم تسجيل فشل الإيداع"})


# =============================================================
# 4) الطلبات (عرض + إنشاء)
# =============================================================
def serialize_orders(uid):
    """
    يوحّد حالات الطلبات (يدوية وتلقائية) إلى 3 حالات موحّدة للعرض:
    accepted (مقبول) / pending (بانتظار) / rejected (مرفوض)
    raw_status تبقى محفوظة للمنطق الداخلي (تحديث، إعادة محاولة...)
    """
    UNIFY = {
        # shop_orders
        "accepted": "accepted", "pending": "pending", "rejected": "rejected",
        # api_orders
        "completed": "accepted", "processing": "pending", "failed": "rejected",
        "timeout": "rejected",
    }
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, product_name, category_name, price, player_id, qty, status, created_at
                     FROM shop_orders WHERE user_id = ?""", (uid,))
        shop = [{"id": r[0], "source": "shop", "product_name": r[1], "category_name": r[2], "price_syp": r[3],
                  "player_id": r[4], "qty": r[5], "raw_status": r[6],
                  "status": UNIFY.get(r[6], r[6]), "date": r[7]} for r in c.fetchall()]
        c.execute("""SELECT id, product_name, category_name, price, player_id, qty, status, created_at
                     FROM api_orders WHERE user_id = ?""", (uid,))
        api_o = [{"id": r[0], "source": "api", "product_name": r[1], "category_name": r[2], "price_syp": r[3],
                   "player_id": r[4], "qty": r[5], "raw_status": r[6],
                   "status": UNIFY.get(r[6], r[6]), "date": r[7]} for r in c.fetchall()]
    return sorted(shop + api_o, key=lambda o: o["date"], reverse=True)


@app.get("/api/orders")
@require_auth
def orders_list():
    uid = effective_user_id(request.web_user)
    return jsonify(serialize_orders(uid))


def place_order(uid, category_id, player_id, qty, username="", full_name="", currency="SYP"):
    """نفس منطق الشراء بالبوت بالضبط: خصم → (API أو يدوي) → استرجاع عند الرفض."""
    category = lod.get_category_by_id(category_id)
    if not category:
        return False, {"message": "الفئة غير موجودة"}, 404
    cat_id, product_id, cat_name, price_usd, cat_type, min_qty, max_qty = category
    qty = max(min_qty, min(max_qty, int(qty or 1)))

    # هل هالفئة بتطلب ايدي لاعب أصلاً؟ (في منتجات ما بتحتاج ايدي)
    needs_id = lod.category_requires_id(category_id)
    player_id = (player_id or "").strip()
    if needs_id and not player_id:
        return False, {"message": "ايدي اللاعب مطلوب لهذا المنتج"}, 400
    if not needs_id and not player_id:
        player_id = "—"

    rate = lod.get_exchange_rate()
    discount_name, discount_percent = lod.get_user_discount(uid)
    price_usd_final = price_usd * (1 - discount_percent / 100) if discount_percent else price_usd
    unit_qty = lod.get_category_unit_qty(category_id)
    total_usd = lod.compute_total_price(price_usd_final, qty, unit_qty)
    price_syp = total_usd * rate

    product = lod.get_product_by_id(product_id)
    product_name = product[1] if product else "غير معروف"

    # فحص وخصم المخزون بشكل ذرّي أولاً (قبل خصم الرصيد) — يمنع بيع نفس القطعة مرتين
    stock_ok = lod.try_decrement_stock(cat_id, qty)
    if not stock_ok:
        return False, {"message": "الكمية المطلوبة غير متوفرة بالمخزون حالياً"}, 400

    # خصم ذرّي (atomic) — الفحص والخصم بأمر SQL واحد، يمنع تكرار الخصم لو وصل طلبين بنفس اللحظة
    ok_deduct, _ = lod.try_deduct_balance(uid, price_syp)
    if not ok_deduct:
        lod.restore_stock(cat_id, qty)  # نرجع المخزون لأن الشراء ما تم فعلياً
        return False, {"message": "رصيدك غير كافٍ لإتمام هذا الطلب"}, 400
    lod.add_notification(uid, "🛒 تم إنشاء طلبك", f"طلب «{product_name} - {cat_name}» قيد المعالجة", "info")

    linked = lod.get_linked_by_category(category_id)
    if linked:
        api_product_id, provider_id = linked[3], linked[8]
        p_token, p_url = linked[10], linked[11]
        result = lod.buy_from_api(api_product_id, player_id, qty, api_token=p_token, api_base_url=p_url)

        if result.get("error") or result.get("status") != "OK":
            lod.update_user_balance(uid, price_syp)  # استرجاع
            lod.restore_stock(cat_id, qty)  # استرجاع المخزون كمان لأن المزوّد رفض الطلب
            return False, {"message": "تم رفض الطلب من المزوّد، تم استرجاع رصيدك", "detail": str(result)}, 400

        data_res = result.get("data", {})
        order_id = data_res.get("order_id", "")
        replay_text = lod.extract_replay_text(data_res)
        api_price_usd = linked[7] or 0
        cost_usd_total = lod.compute_total_price(api_price_usd, qty, unit_qty)
        order_db_id = lod.save_api_order(uid, 0, order_id, product_name, cat_name, price_syp,
                                          player_id, qty, replay_text, provider_id,
                                          cost_usd=cost_usd_total, price_usd=total_usd)

        lod.notify_admin("🧾 طلب API جديد من الموقع",
                          f"👤 {full_name} ({username})\n🆔 {uid}\n"
                          f"🔶 المنتج: {product_name}\n🔶 الفئة: {cat_name}\n"
                          f"🔶 الكمية: {qty}\n🔶 السعر: {price_syp:,.2f} ليرة\n"
                          f"🔶 الايدي: {player_id}\n🔖 رقم الطلب: {order_db_id}")

        # تشغيل مراقبة الطلب بالخلفية (نفس منطق البوت بالضبط)
        threading.Thread(
            target=lod.monitor_api_order_web,
            args=(order_db_id, uid, price_syp),
            kwargs={"api_token": p_token, "api_base_url": p_url},
            daemon=True
        ).start()

        return True, {"message": "تم إنشاء طلبك بنجاح", "order_id": order_db_id, "status": "processing",
                       "price_syp": price_syp, "price_usd": total_usd, "currency": currency}, 200
    else:
        with lod.get_db() as conn:
            c = conn.cursor()
            c.execute("""INSERT INTO shop_orders (user_id, product_name, category_name, price, player_id, qty, status, price_usd)
                         VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
                       (uid, product_name, cat_name, price_syp, player_id, qty, total_usd))
            order_db_id = c.lastrowid

        keyboard = {"inline_keyboard": [[
            {"text": "🟢 قبول الشحن", "callback_data": lod.safe_callback_data(f"accept_order_{order_db_id}"), "color": "success"},
            {"text": "🔴 رفض الشحن", "callback_data": lod.safe_callback_data(f"reject_order_{order_db_id}"), "color": "danger"},
        ]]}
        lod.send_message(lod.ADMIN_CHAT_ID,
                          f"🔶 طلب شحن جديد من الموقع 🔶\n👤 {full_name} ({username})\n🆔 {uid}\n"
                          f"----------------------------\n🔶 المنتج: {product_name}\n🔶 الفئة: {cat_name}\n"
                          f"🔶 السعر: {price_syp:,.2f} ليرة\n🔶 الكمية: {qty}\n🔶 ايدي اللاعب: {player_id}",
                          reply_markup=keyboard)
        return True, {"message": "تم إنشاء طلبك بنجاح، بانتظار المراجعة", "order_id": order_db_id,
                       "status": "pending", "price_syp": price_syp, "price_usd": total_usd, "currency": currency}, 200


@app.post("/api/orders")
@require_auth
def orders_create():
    web_row = request.web_user
    uid = effective_user_id(web_row)
    body = request.get_json(force=True, silent=True) or {}
    preferred_currency = (web_row[9] or "USD").upper() if len(web_row) > 9 else "USD"
    requested_currency = (body.get("currency") or preferred_currency).upper()
    if requested_currency != preferred_currency:
        return jsonify({"message": "عملة الطلب لا تطابق العملة المحفوظة في إعدادات حسابك"}), 400
    ok, payload, code = place_order(uid, body.get("category_id"), body.get("player_id"),
                                     body.get("qty", 1), web_row[2], web_row[1], requested_currency)
    return jsonify(payload), code

# =============================================================
# 5) إدارة API الخاص بالمستخدم + نقطة الطلب الخارجية (Reseller API)
# ملاحظة: تفعيل/تعطيل/تجديد مفتاح API يتم فقط من لوحة تحكم الأدمن.
# المستخدم نفسه يتحكم فقط بعناوين IP المسموحة لمفتاحه.
# =============================================================
@app.get("/api/user/api")
@require_auth
def user_api_info():
    w = request.web_user
    if not w[8]:
        return jsonify({"message": "API غير مفعّل لحسابك، تواصل مع الإدارة لتفعيله"}), 403
    return jsonify({"api_key": w[6], "allowed_ips": w[7] or ""})


@app.post("/api/user/api/ips")
@require_auth
def user_api_ips():
    w = request.web_user
    if not w[8]:
        return jsonify({"message": "API غير مفعّل لحسابك"}), 403
    body = request.get_json(force=True, silent=True) or {}
    ips = (body.get("allowed_ips") or "").strip()
    with lod.get_db() as conn:
        conn.cursor().execute("UPDATE web_users SET allowed_ips = ? WHERE id = ?", (ips, w[0]))
    return jsonify({"message": "تم الحفظ"})


@app.post("/api/v1/order")
def external_order():
    """نقطة طلب خارجية لعملاء الـ API (نظام Reseller) — المصادقة عبر مفتاح API."""
    auth = request.headers.get("Authorization", "")
    api_key = auth.split(" ", 1)[1] if auth.startswith("Bearer ") else request.args.get("api_key", "")
    web_row = get_web_user_by_api_key(api_key)
    if not web_row:
        return jsonify({"status": "error", "message": "مفتاح API غير صحيح"}), 401

    allowed_ips = [ip.strip() for ip in (web_row[7] or "").split(",") if ip.strip()]
    if allowed_ips and request.remote_addr not in allowed_ips:
        return jsonify({"status": "error", "message": "عنوان IP غير مسموح"}), 403

    body = request.get_json(force=True, silent=True) or request.form
    uid = effective_user_id(web_row)
    ok, payload, code = place_order(uid, body.get("category_id") or body.get("product_id"),
                                     body.get("player_id"), body.get("qty", 1), web_row[2], web_row[1])
    payload["status"] = "OK" if ok else "error"
    return jsonify(payload), code


@app.get("/api/v1/products")
def external_products_list():
    """يرجع كل الأقسام والمنتجات وفئاتها (مع category_id المطلوب لإنشاء طلب) — للمصادقة بمفتاح API."""
    auth = request.headers.get("Authorization", "")
    api_key = auth.split(" ", 1)[1] if auth.startswith("Bearer ") else request.args.get("api_key", "")
    web_row = get_web_user_by_api_key(api_key)
    if not web_row:
        return jsonify({"status": "error", "message": "مفتاح API غير صحيح"}), 401

    rate = lod.get_exchange_rate()
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT p.id, p.name, p.category, c.id, c.name, c.price, c.min_qty, c.max_qty
                     FROM products p JOIN categories c ON c.product_id = p.id
                     ORDER BY p.category, p.id, c.id""")
        rows = c.fetchall()

    out = {}
    for pid, pname, section, cid, cname, price_usd, min_qty, max_qty in rows:
        key = f"{section}::{pname}::{pid}"
        out.setdefault(key, {"product_id": pid, "product_name": pname, "section": section, "categories": []})
        out[key]["categories"].append({
            "category_id": cid, "name": cname,
            "price_usd": price_usd, "price_syp": round(price_usd * rate),
            "min_qty": min_qty, "max_qty": max_qty,
        })
    return jsonify({"status": "OK", "products": list(out.values())})


@app.get("/api/v1/order/<int:order_id>")
def external_order_status(order_id):
    """فحص حالة طلب سابق (مكتمل/قيد التنفيذ/مرفوض) — للمصادقة بمفتاح API."""
    auth = request.headers.get("Authorization", "")
    api_key = auth.split(" ", 1)[1] if auth.startswith("Bearer ") else request.args.get("api_key", "")
    web_row = get_web_user_by_api_key(api_key)
    if not web_row:
        return jsonify({"status": "error", "message": "مفتاح API غير صحيح"}), 401
    uid = effective_user_id(web_row)

    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT status, product_name, category_name, price, player_id, qty
                     FROM api_orders WHERE id = ? AND user_id = ?""", (order_id, uid))
        row = c.fetchone()
        if not row:
            c.execute("""SELECT status, product_name, category_name, price, player_id, qty
                         FROM shop_orders WHERE id = ? AND user_id = ?""", (order_id, uid))
            row = c.fetchone()
    if not row:
        return jsonify({"status": "error", "message": "الطلب غير موجود"}), 404
    status, pname, cname, price, player_id, qty = row
    return jsonify({"status": "OK", "order_status": status, "product_name": pname,
                     "category_name": cname, "price_syp": price, "player_id": player_id, "qty": qty})


# =============================================================
# 5.5) واجهة API الرسمية (client/api) — مطابقة تماماً لصفحة api-docs.html
# نفس منطق /api/v1 (إعادة استخدام place_order وباقي المنطق)، بس بمسارات/ترويسة/
# أشكال استجابة موحّدة مع التوثيق المعروض للشركاء الخارجيين + أكواد الأخطاء الرسمية.
# =============================================================
CLIENT_API_ERRORS = {
    120: "رمز API مطلوب!",
    121: "خطأ في الرمز المميز",
    122: "غير مسموح باستخدام واجهة برمجة التطبيقات (API)",
    123: "عنوان IP غير مسموح به",
    130: "الموقع قيد الصيانة",
    100: "رصيد غير كافٍ",
    105: "الكمية غير متوفرة",
    106: "الكمية غير مسموح بها",
    112: "الكمية صغيرة جداً",
    113: "الكمية كبيرة جداً",
    114: "معلمة غير معروفة/غير صالحة",
    500: "خطأ غير معروف",
}


def client_api_err(code, http=400, extra=None):
    payload = {"status": code, "msg": CLIENT_API_ERRORS.get(code, "خطأ غير معروف")}
    if extra:
        payload.update(extra)
    return jsonify(payload), http


def client_api_auth():
    """مصادقة موحّدة لكل مسارات client/api عبر ترويسة api-token. يرجع (web_row, None) أو (None, error_response)."""
    token = request.headers.get("api-token", "")
    if not token:
        return None, client_api_err(120, 401)
    web_row = get_web_user_by_api_key(token)
    if not web_row:
        return None, client_api_err(121, 401)
    if not web_row[8]:  # api_enabled
        return None, client_api_err(122, 403)
    allowed_ips = [ip.strip() for ip in (web_row[7] or "").split(",") if ip.strip()]
    if allowed_ips and request.remote_addr not in allowed_ips:
        return None, client_api_err(123, 403)
    enabled, _, _ = get_maintenance_status()
    if enabled:
        return None, client_api_err(130, 503)
    return web_row, None


def _map_client_status(raw_status, source=None):
    if raw_status in ("completed", "accepted", "accept"):
        return "accept"
    if raw_status in ("failed", "rejected", "timeout", "decline"):
        return "decline"
    return "processing"


def _category_to_client_product(cat_row, product_name, product_public_id):
    """cat_row = (id, name, price, type, min_qty, max_qty, public_id)"""
    cid, cname, price, ctype, min_qty, max_qty, public_id = cat_row
    return {
        "id": public_id,
        "name": cname,
        "price": price,
        "params": ["Enter Player ID"],
        "category_name": product_name,
        "available": True,
        "qty_values": {"min": min_qty, "max": max_qty},
        "product_type": ctype,
        "parent_id": product_public_id,
    }


@app.get("/client/api/profile")
def client_api_profile():
    web_row, err = client_api_auth()
    if err:
        return err
    uid = effective_user_id(web_row)
    rate = lod.get_exchange_rate()
    balance_syp = lod.get_user_balance(uid)
    balance_usd = round(balance_syp / rate, 3) if rate else 0
    return jsonify({"status": "OK", "balance": str(balance_usd), "email": web_row[2]})


@app.get("/api/products/catalog")
@require_auth
def products_catalog():
    """قائمة كل المنتجات (الفئات القابلة للشراء) مع public_id — لصفحة 'منتجات API' داخل الموقع.
    يستخدم جلسة الموقع العادية (وليس مفتاح API) لأنها صفحة تصفّح داخل لوحة المستخدم."""
    q = (request.args.get("q") or "").strip().lower()
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT c.id, c.name, c.price, c.type, c.min_qty, c.max_qty, c.public_id,
                            p.name, p.public_id
                     FROM categories c JOIN products p ON p.id = c.product_id
                     ORDER BY p.category, p.id, c.id""")
        rows = c.fetchall()

    out = []
    for cid, cname, price, ctype, min_qty, max_qty, cpub, pname, ppub in rows:
        if q and q not in cname.lower() and q not in pname.lower() and q not in (cpub or "").lower():
            continue
        out.append(_category_to_client_product((cid, cname, price, ctype, min_qty, max_qty, cpub), pname, ppub))
    return jsonify(out)


@app.get("/client/api/products")
def client_api_products():
    web_row, err = client_api_auth()
    if err:
        return err
    products_filter = request.args.get("products_id", "")
    base_only = request.args.get("base") == "1"
    ids_filter = [x.strip() for x in products_filter.split(",") if x.strip()] if products_filter else None

    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT c.id, c.name, c.price, c.type, c.min_qty, c.max_qty, c.public_id,
                            p.name, p.public_id
                     FROM categories c JOIN products p ON p.id = c.product_id""")
        rows = c.fetchall()

    out = []
    for cid, cname, price, ctype, min_qty, max_qty, cpub, pname, ppub in rows:
        if ids_filter and cpub not in ids_filter:
            continue
        if base_only:
            out.append({"id": cpub, "name": cname})
        else:
            out.append(_category_to_client_product((cid, cname, price, ctype, min_qty, max_qty, cpub), pname, ppub))
    return jsonify(out)


@app.get("/client/api/content/<category_id>")
def client_api_content(category_id):
    web_row, err = client_api_auth()
    if err:
        return err
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, public_id FROM products WHERE public_id = ?", (category_id,))
        prod = c.fetchone()
        if not prod:
            return client_api_err(114, 404)
        pid, pname, ppub = prod
        c.execute("""SELECT id, name, price, type, min_qty, max_qty, public_id
                     FROM categories WHERE product_id = ?""", (pid,))
        cats = c.fetchall()
    return jsonify({
        "status": "OK",
        "categories": [{"id": ppub, "name": pname}],
        "products": [_category_to_client_product(row, pname, ppub) for row in cats],
    })


@app.route("/client/api/newOrder/<product_id>", methods=["GET", "POST"])
@app.route("/client/api/newOrder/<product_id>/params", methods=["GET", "POST"])
def client_api_new_order(product_id):
    web_row, err = client_api_auth()
    if err:
        return err
    uid = effective_user_id(web_row)

    body = (request.get_json(force=True, silent=True) or request.form.to_dict()) if request.method == "POST" else request.args.to_dict()
    qty = body.get("qty", 1)
    player_id = body.get("playerId", body.get("player_id", ""))
    order_uuid = (body.get("order_uuid") or "").strip()
    extra_params = {k: v for k, v in body.items() if k not in ("qty", "playerId", "player_id", "order_uuid")}

    # التحقق من التكرار (idempotency) — نفس order_uuid يرجع نفس نتيجة الطلب الأصلي دون تكراره
    if order_uuid:
        with lod.get_db() as conn:
            c = conn.cursor()
            c.execute("""SELECT id, status, price, player_id, custom_params FROM api_orders
                         WHERE order_uuid = ? AND user_id = ?""", (order_uuid, uid))
            existing = c.fetchone()
            if not existing:
                c.execute("""SELECT id, status, price, player_id, custom_params FROM shop_orders
                             WHERE order_uuid = ? AND user_id = ?""", (order_uuid, uid))
                existing = c.fetchone()
        if existing:
            eid, estatus, eprice, eplayer, ecustom = existing
            return jsonify({"status": "OK", "data": {
                "order_id": f"ID_{eid}", "status": _map_client_status(estatus),
                "price": eprice, "data": json.loads(ecustom) if ecustom else {"playerId": eplayer},
                "replay_api": [],
            }})

    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM categories WHERE public_id = ?", (product_id,))
        row = c.fetchone()
    if not row:
        return client_api_err(114, 404)

    ok, payload, code = place_order(uid, row[0], player_id, qty, web_row[2], web_row[1])
    if not ok:
        msg = payload.get("message", "")
        if "غير كافٍ" in msg:
            return client_api_err(100, 400)
        if "الكمية" in msg:
            return client_api_err(106, 400)
        return client_api_err(500, 400, {"detail": msg})

    order_db_id = payload["order_id"]
    custom_json = json.dumps({"playerId": player_id, **extra_params}, ensure_ascii=False)
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM api_orders WHERE id = ?", (order_db_id,))
        table = "api_orders" if c.fetchone() else "shop_orders"
        c.execute(f"UPDATE {table} SET order_uuid = ?, custom_params = ? WHERE id = ?",
                   (order_uuid or None, custom_json, order_db_id))

    rate = lod.get_exchange_rate()
    price_usd = round(payload["price_syp"] / rate, 5) if rate else payload["price_syp"]
    return jsonify({"status": "OK", "data": {
        "order_id": f"ID_{order_db_id}", "status": _map_client_status(payload["status"]),
        "price": price_usd, "data": {"playerId": player_id, **extra_params}, "replay_api": [],
    }})


@app.get("/client/api/check")
def client_api_check():
    web_row, err = client_api_auth()
    if err:
        return err
    uid = effective_user_id(web_row)
    use_uuid = request.args.get("uuid") == "1"
    raw_param = request.args.get("orders", "[]")
    try:
        ids_raw = json.loads(raw_param)
    except Exception:
        ids_raw = [x.strip() for x in raw_param.strip("[]").split(",") if x.strip()]

    results = []
    with lod.get_db() as conn:
        c = conn.cursor()
        for raw in ids_raw:
            row, src = None, None
            if use_uuid:
                c.execute("""SELECT id, product_name, price, player_id, qty, status, created_at, custom_params
                             FROM api_orders WHERE order_uuid = ? AND user_id = ?""", (raw, uid))
                row = c.fetchone(); src = "api"
                if not row:
                    c.execute("""SELECT id, product_name, price, player_id, qty, status, created_at, custom_params
                                 FROM shop_orders WHERE order_uuid = ? AND user_id = ?""", (raw, uid))
                    row = c.fetchone(); src = "shop"
            else:
                oid = str(raw).replace("ID_", "")
                if oid.isdigit():
                    c.execute("""SELECT id, product_name, price, player_id, qty, status, created_at, custom_params
                                 FROM api_orders WHERE id = ? AND user_id = ?""", (int(oid), uid))
                    row = c.fetchone(); src = "api"
                    if not row:
                        c.execute("""SELECT id, product_name, price, player_id, qty, status, created_at, custom_params
                                     FROM shop_orders WHERE id = ? AND user_id = ?""", (int(oid), uid))
                        row = c.fetchone(); src = "shop"
            if not row:
                continue
            oid, pname, price, player_id, qty, status, created_at, custom = row
            results.append({
                "order_id": f"ID_{oid}", "quantity": qty,
                "data": json.loads(custom) if custom else {"playerId": player_id},
                "created_at": created_at, "product_name": pname, "price": price,
                "status": _map_client_status(status), "replay_api": [],
            })
    return jsonify({"status": "OK", "data": results})


# =============================================================
# 6) لوحة تحكم الأدمن (محمية بكلمة مرور بسيطة عبر متغيّر بيئة)
# =============================================================
@app.post("/api/admin/login")
@limiter.limit("6 per minute")
def admin_login():
    body = request.get_json(force=True, silent=True) or {}
    if body.get("password") != ADMIN_PANEL_PASSWORD:
        return jsonify({"message": "كلمة مرور خاطئة"}), 401
    return jsonify({"token": admin_serializer.dumps({"admin": True, "owner": True, "email": "owner"})})


@app.post("/api/auth/admin-auto-login")
@require_auth
def admin_auto_login():
    web_user = request.web_user
    email = (web_user[2] or "").lower() if web_user else ""
    if not email:
        return jsonify({"message": "غير مصرح"}), 403
    is_owner = is_owner_email(email)
    if not is_owner and not is_admin_email(email):
        return jsonify({"message": "غير مصرح"}), 403
    return jsonify({"token": admin_serializer.dumps({"admin": True, "owner": is_owner, "email": email})})


@app.get("/api/admin/stats")
@require_admin
def admin_stats():
    today_start = datetime.now().strftime("%Y-%m-%d 00:00:00")
    today_end = datetime.now().strftime("%Y-%m-%d 23:59:59")
    today = lod.get_profit_summary(start_date=today_start, end_date=today_end)
    margin_percent = round((today["total_profit_usd"] / today["total_sales_usd"]) * 100, 1) if today["total_sales_usd"] else 0
    return jsonify({
        "total_users": lod.get_total_users_count(),
        "total_balance_syp": lod.get_total_balance(),
        "total_orders": lod.get_total_orders(),
        "exchange_rate": lod.get_exchange_rate(),
        "today_sales_usd": today["total_sales_usd"],
        "today_orders": today["total_orders"],
        "today_profit_usd": today["total_profit_usd"],
        "today_margin_percent": margin_percent,
    })


@app.get("/api/admin/alerts-count")
@require_admin
def admin_alerts_count():
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM deposit_requests WHERE status = 'pending'")
        pending_deposits = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM shop_orders WHERE status = 'pending'")
        pending_shop_orders = c.fetchone()[0]
    return jsonify({
        "pending_deposits": pending_deposits,
        "pending_shop_orders": pending_shop_orders,
        "total": pending_deposits + pending_shop_orders,
    })


# ----- جدول الأرباح (مبيعات + تكلفة + ربح) -----
@app.get("/api/admin/profits")
@require_admin
def admin_profits():
    """
    استعلامات اختيارية: start (YYYY-MM-DD), end (YYYY-MM-DD), limit, offset
    """
    start = request.args.get("start") or None
    end = request.args.get("end") or None
    limit = request.args.get("limit", default=500, type=int)
    offset = request.args.get("offset", default=0, type=int)
    if end:
        end = end + " 23:59:59"
    orders = lod.get_profit_orders(start_date=start, end_date=end, limit=limit, offset=offset)
    summary = lod.get_profit_summary(start_date=start, end_date=end)
    return jsonify({"summary": summary, "orders": orders})


@app.get("/api/admin/orders")
@require_admin
def admin_orders():
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, user_id, product_name, category_name, price, player_id, qty, status, created_at
                     FROM shop_orders ORDER BY created_at DESC LIMIT 200""")
        rows = c.fetchall()
        c.execute("""SELECT id, user_id, product_name, category_name, price, player_id, qty, status, created_at
                     FROM api_orders ORDER BY created_at DESC LIMIT 200""")
        api_rows = c.fetchall()
    out = [{"id": r[0], "ref": f"S{r[0]}", "source": "يدوي", "user_id": r[1], "product_name": r[2],
            "category_name": r[3], "price_syp": r[4], "player_id": r[5], "qty": r[6],
            "status": r[7], "date": r[8]} for r in rows]
    out += [{"id": r[0], "ref": f"A{r[0]}", "source": "مزود", "user_id": r[1], "product_name": r[2],
             "category_name": r[3], "price_syp": r[4], "player_id": r[5], "qty": r[6],
             "status": r[7], "date": r[8]} for r in api_rows]
    out.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
    return jsonify(out[:300])


@app.get("/api/admin/deposits")
@require_admin
def admin_deposits():
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, user_id, username, full_name, method_title, amount_usd, amount_syp,
                     transaction_code, status, created_at FROM deposit_requests
                     ORDER BY created_at DESC LIMIT 200""")
        rows = c.fetchall()
    return jsonify([{"id": r[0], "user_id": r[1], "username": r[2], "full_name": r[3], "method_title": r[4],
                      "amount_usd": r[5], "amount_syp": r[6], "code": r[7], "status": r[8], "date": r[9]} for r in rows])




@app.get("/api/admin/users")
@require_admin
def admin_users():
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT w.id, w.name, w.email, w.telegram_user_id, w.site_user_id, w.api_enabled, w.api_key
                     FROM web_users w ORDER BY w.id DESC LIMIT 300""")
        rows = c.fetchall()
    out = []
    for r in rows:
        uid = r[3] or r[4]
        tier = lod.get_user_discount_tier(uid)
        out.append({"web_id": r[0], "name": r[1], "email": r[2], "telegram_linked": bool(r[3]),
                     "balance_syp": lod.get_user_balance(uid), "blocked": lod.is_blocked(uid),
                     "api_enabled": bool(r[5]), "api_key": r[6] or "",
                     "discount_tier_id": tier[0] if tier else 0,
                     "discount_tier_name": tier[1] if tier else "",
                     "discount_percent": tier[2] if tier else 0})
    return jsonify(out)


@app.get("/api/admin/users/<int:web_id>/details")
@require_admin
def admin_user_details(web_id):
    w = get_web_user_by_id(web_id)
    if not w:
        return jsonify({"message": "غير موجود"}), 404
    uid = effective_user_id(w)
    rate = lod.get_exchange_rate() or 1

    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, product_name, category_name, price, price_usd, cost_usd, qty, status, created_at
                     FROM shop_orders WHERE user_id = ?
                     UNION ALL
                     SELECT id, product_name, category_name, price, price_usd, cost_usd, qty, status, created_at
                     FROM api_orders WHERE user_id = ?
                     ORDER BY created_at DESC LIMIT 500""", (uid, uid))
        all_orders = c.fetchall()

    total_orders = len(all_orders)
    total_spent_usd = 0.0
    total_profit_usd = 0.0
    recent = []
    for o in all_orders:
        oid, pname, cname, price_syp, price_usd, cost_usd, qty, status, created_at = o
        usd = price_usd if price_usd else (price_syp / rate if rate else 0)
        cost = cost_usd or 0
        if status in ("accepted", "completed"):
            total_spent_usd += usd
            total_profit_usd += (usd - cost)
        if len(recent) < 30:
            recent.append({
                "id": oid, "product_name": pname, "category_name": cname,
                "price_usd": round(usd, 4), "qty": qty, "status": status, "date": created_at,
            })

    return jsonify({
        "name": w[1], "email": w[2],
        "balance_usd": round(lod.get_user_balance(uid) / rate, 2) if rate else 0,
        "total_orders": total_orders,
        "total_spent_usd": round(total_spent_usd, 2),
        "total_profit_usd": round(total_profit_usd, 4),
        "recent_orders": recent,
    })


@app.get("/api/admin/discount-tiers")
@require_admin
def admin_discount_tiers():
    tiers = lod.get_all_discount_tiers()
    return jsonify([{"id": t[0], "name": t[1], "percent": t[2], "sort_order": t[3]} for t in tiers])


@app.post("/api/admin/discount-tiers")
@require_admin
def admin_add_discount_tier():
    b = request.get_json(force=True, silent=True) or {}
    name = (b.get("name") or "").strip()
    if not name:
        return jsonify({"message": "اسم الرتبة مطلوب"}), 400
    try:
        percent = float(b.get("percent") or 0)
    except (TypeError, ValueError):
        return jsonify({"message": "نسبة الخصم غير صحيحة"}), 400
    if percent < 0 or percent > 100:
        return jsonify({"message": "نسبة الخصم يجب أن تكون بين 0 و100"}), 400
    sort_order = int(b.get("sort_order") or 0)
    tier_id = lod.add_discount_tier(name, percent, sort_order)
    return jsonify({"message": "تمت إضافة الرتبة", "id": tier_id})


@app.put("/api/admin/discount-tiers/<int:tier_id>")
@require_admin
def admin_update_discount_tier(tier_id):
    if not lod.get_discount_tier_by_id(tier_id):
        return jsonify({"message": "الرتبة غير موجودة"}), 404
    b = request.get_json(force=True, silent=True) or {}
    name = b.get("name")
    percent = b.get("percent")
    sort_order = b.get("sort_order")
    if percent is not None:
        try:
            percent = float(percent)
        except (TypeError, ValueError):
            return jsonify({"message": "نسبة الخصم غير صحيحة"}), 400
        if percent < 0 or percent > 100:
            return jsonify({"message": "نسبة الخصم يجب أن تكون بين 0 و100"}), 400
    lod.update_discount_tier(tier_id, name=name, percent=percent,
                              sort_order=int(sort_order) if sort_order is not None else None)
    return jsonify({"message": "تم التعديل"})


@app.delete("/api/admin/discount-tiers/<int:tier_id>")
@require_admin
def admin_delete_discount_tier(tier_id):
    if not lod.get_discount_tier_by_id(tier_id):
        return jsonify({"message": "الرتبة غير موجودة"}), 404
    lod.delete_discount_tier(tier_id)
    return jsonify({"message": "تم حذف الرتبة"})


@app.post("/api/admin/users/<int:web_id>/discount-tier")
@require_admin
def admin_set_user_discount_tier(web_id):
    w = get_web_user_by_id(web_id)
    if not w:
        return jsonify({"message": "غير موجود"}), 404
    b = request.get_json(force=True, silent=True) or {}
    tier_id = int(b.get("tier_id") or 0)
    if tier_id == 0:
        lod.remove_user_discount(effective_user_id(w))
        with lod.get_db() as conn:
            conn.cursor().execute("UPDATE users SET discount_tier_id = 0 WHERE user_id = ?", (effective_user_id(w),))
        return jsonify({"message": "تمت إزالة رتبة المستخدم"})
    if not lod.get_discount_tier_by_id(tier_id):
        return jsonify({"message": "الرتبة غير موجودة"}), 404
    lod.set_user_discount_tier(effective_user_id(w), tier_id)
    return jsonify({"message": "تم تعيين الرتبة"})


@app.post("/api/admin/users/<int:web_id>/balance")
@require_admin
def admin_adjust_user_balance(web_id):
    w = get_web_user_by_id(web_id)
    if not w:
        return jsonify({"message": "غير موجود"}), 404
    b = request.get_json(force=True, silent=True) or {}
    action = b.get("action")  # "add" أو "deduct"
    amount = float(b.get("amount") or 0)
    if amount <= 0 or action not in ("add", "deduct"):
        return jsonify({"message": "أدخل مبلغ صحيح ونوع العملية (إضافة/خصم)"}), 400

    uid = effective_user_id(w)
    if action == "add":
        lod.add_user_balance(uid, amount)
        lod.add_notification(uid, "✅ تمت إضافة رصيد", f"تمت إضافة {amount:,.0f} ل.س لرصيدك من الإدارة", "success")
    else:
        lod.deduct_user_balance(uid, amount)
        lod.add_notification(uid, "⚠️ تم خصم رصيد", f"تم خصم {amount:,.0f} ل.س من رصيدك من الإدارة", "danger")
    lod.notify_admin("💰 تعديل رصيد مستخدم",
                      f"المستخدم: {w[1]} ({w[2]})\nالعملية: {'إضافة' if action == 'add' else 'خصم'}\n"
                      f"المبلغ: {amount:,.0f} ل.س")
    return jsonify({"message": "تم تحديث الرصيد", "new_balance_syp": lod.get_user_balance(uid)})


@app.post("/api/admin/users/<int:web_id>/block")
@require_admin
def admin_block_user(web_id):
    w = get_web_user_by_id(web_id)
    if not w:
        return jsonify({"message": "غير موجود"}), 404
    lod.block_user(effective_user_id(w))
    return jsonify({"message": "تم الحظر"})


@app.post("/api/admin/users/<int:web_id>/unblock")
@require_admin
def admin_unblock_user(web_id):
    w = get_web_user_by_id(web_id)
    if not w:
        return jsonify({"message": "غير موجود"}), 404
    lod.unblock_user(effective_user_id(w))
    return jsonify({"message": "تم رفع الحظر"})


@app.post("/api/admin/users/<int:web_id>/api/enable")
@require_admin
def admin_enable_user_api(web_id):
    """يفتح API لمستخدم محدد: يولّد مفتاحاً إذا لم يكن موجوداً ويفعّله."""
    w = get_web_user_by_id(web_id)
    if not w:
        return jsonify({"message": "غير موجود"}), 404
    api_key = w[6] or gen_api_key()
    with lod.get_db() as conn:
        conn.cursor().execute("UPDATE web_users SET api_key = ?, api_enabled = 1 WHERE id = ?",
                               (api_key, web_id))
    return jsonify({"message": "تم تفعيل API للمستخدم", "api_key": api_key})


@app.post("/api/admin/users/<int:web_id>/api/disable")
@require_admin
def admin_disable_user_api(web_id):
    w = get_web_user_by_id(web_id)
    if not w:
        return jsonify({"message": "غير موجود"}), 404
    with lod.get_db() as conn:
        conn.cursor().execute("UPDATE web_users SET api_enabled = 0 WHERE id = ?", (web_id,))
    return jsonify({"message": "تم تعطيل API للمستخدم"})


@app.post("/api/admin/users/<int:web_id>/api/regenerate")
@require_admin
def admin_regenerate_user_api(web_id):
    w = get_web_user_by_id(web_id)
    if not w:
        return jsonify({"message": "غير موجود"}), 404
    new_key = gen_api_key()
    with lod.get_db() as conn:
        conn.cursor().execute("UPDATE web_users SET api_key = ? WHERE id = ?", (new_key, web_id))
    return jsonify({"message": "تم توليد مفتاح جديد", "api_key": new_key})


# =============================================================
# 7) إدارة كاملة للمتجر: منتجات / فئات / أقسام / طرق إيداع / مزودين / إعدادات / مشرفين
# =============================================================

# ----- رفع الصور -----
@app.post("/api/admin/upload")
@require_admin
def admin_upload():
    f = request.files.get("file")
    url = save_upload(f)
    if not url:
        return jsonify({"message": "صيغة غير مدعومة (png/jpg/jpeg/webp/gif فقط)"}), 400
    return jsonify({"url": url})


# ----- المنتجات والفئات -----
@app.get("/api/admin/products")
@require_admin
def admin_products():
    products = lod.get_all_products_admin()  # id, name, category, emoji, description, image, subsection_id, sort_order
    with lod.get_db() as conn:
        c = conn.cursor()
        out = []
        for p in products:
            c.execute("SELECT COUNT(*) FROM categories WHERE product_id = ?", (p[0],))
            cnt = c.fetchone()[0]
            sub_name = ""
            if p[6]:
                c.execute("SELECT name FROM subsections WHERE id = ?", (p[6],))
                row = c.fetchone()
                sub_name = row[0] if row else ""
            c.execute("SELECT public_id FROM products WHERE id = ?", (p[0],))
            pub_row = c.fetchone()
            out.append({"id": p[0], "name": p[1], "category": p[2], "emoji": p[3],
                         "image": p[5] or "", "subsection_id": p[6] or 0, "subsection_name": sub_name,
                         "sort_order": p[7], "categories_count": cnt, "public_id": pub_row[0] if pub_row else ""})
    return jsonify(out)


@app.post("/api/admin/products")
@require_admin
def admin_add_product():
    b = request.get_json(force=True, silent=True) or {}
    if not b.get("name") or not b.get("category"):
        return jsonify({"message": "اسم المنتج والقسم مطلوبين"}), 400
    pid = lod.add_product(b["name"], b["category"], b.get("emoji", ""),
                           subsection_id=b.get("subsection_id", 0) or 0)
    public_id = gen_public_id("prd")
    with lod.get_db() as conn:
        conn.cursor().execute("UPDATE products SET public_id = ? WHERE id = ?", (public_id, pid))
    return jsonify({"message": "تمت الإضافة", "id": pid, "public_id": public_id})


@app.delete("/api/admin/products/<int:product_id>")
@require_admin
def admin_delete_product(product_id):
    lod.delete_product(product_id)
    return jsonify({"message": "تم الحذف"})


@app.post("/api/admin/products/<int:product_id>/image")
@require_admin
def admin_set_product_image(product_id):
    url = save_upload(request.files.get("file"))
    if not url:
        return jsonify({"message": "صيغة غير مدعومة"}), 400
    lod.update_product_image(product_id, url)
    return jsonify({"message": "تم تحديث الصورة", "url": url})


@app.get("/api/admin/products/<int:product_id>/categories")
@require_admin
def admin_product_categories(product_id):
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, name, price, type, min_qty, max_qty, image, public_id, stock_qty, COALESCE(NULLIF(unit_qty, 0), 1),
                            COALESCE(requires_id, 1)
                     FROM categories WHERE product_id = ?""", (product_id,))
        rows = c.fetchall()
    return jsonify([{"id": r[0], "name": r[1], "price_usd": r[2], "type": r[3],
                      "min_qty": r[4], "max_qty": r[5], "image": r[6] or "", "public_id": r[7] or "",
                      "stock_qty": r[8], "unit_qty": r[9], "requires_id": bool(r[10])} for r in rows])


@app.post("/api/admin/products/<int:product_id>/categories")
@require_admin
def admin_add_category(product_id):
    b = request.get_json(force=True, silent=True) or {}
    if not b.get("name") or b.get("price") in (None, ""):
        return jsonify({"message": "اسم الفئة والسعر مطلوبين"}), 400
    min_qty = max(1, int(b.get("min_qty", 1) or 1))
    max_qty = max(min_qty, int(b.get("max_qty", min_qty) or min_qty))
    unit_qty = max(1, int(b.get("unit_qty", 1) or 1))
    cid = lod.add_category(product_id, b["name"], float(b["price"]), b.get("type", "default"),
                            min_qty, max_qty, unit_qty)
    public_id = gen_public_id("cat")
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE categories SET public_id = ? WHERE id = ?", (public_id, cid))
        requires_id = 0 if str(b.get("requires_id", True)).lower() in ("false", "0", "no") else 1
        c.execute("UPDATE categories SET requires_id = ? WHERE id = ?", (requires_id, cid))
        stock_val = b.get("stock_qty")
        if stock_val not in (None, ""):
            c.execute("UPDATE categories SET stock_qty = ? WHERE id = ?", (int(stock_val), cid))
    return jsonify({"message": "تمت الإضافة", "id": cid, "public_id": public_id})


@app.delete("/api/admin/categories/<int:category_id>")
@require_admin
def admin_delete_category(category_id):
    lod.delete_category(category_id)
    return jsonify({"message": "تم الحذف"})


# ===== [إضافة جديدة] نظام التسعير الذكي =====
@app.get("/api/admin/categories/all-pricing")
@require_admin
def admin_categories_all_pricing():
    rows = lod.get_all_categories_pricing()
    return jsonify([{
        "id": r[0], "name": r[1], "price_usd": r[2], "margin_percent": r[3],
        "product_name": r[4] or "—", "provider_id": r[5] or 0, "provider_name": r[6] or "",
        "cost_usd": r[7], "linked": bool(r[5]),
    } for r in rows])


@app.post("/api/admin/categories/apply-margin")
@require_admin
def admin_categories_apply_margin():
    b = request.get_json(force=True, silent=True) or {}
    category_ids = b.get("category_ids") or []
    margin_percent = b.get("margin_percent")
    if margin_percent is None or float(margin_percent) < 0:
        return jsonify({"message": "أدخل نسبة هامش صحيحة"}), 400
    if not category_ids:
        return jsonify({"message": "حدد فئة واحدة على الأقل"}), 400
    result = lod.apply_margin_to_categories(category_ids, float(margin_percent))
    msg = f"تم تحديث {len(result['updated'])} فئة"
    if result["skipped_not_linked"]:
        msg += f"، و{len(result['skipped_not_linked'])} فئة اتحفظ فيها الهامش بس ما تحدّث سعرها لأنها مش مربوطة بمزوّد بعد"
    return jsonify({"message": msg, **result})


@app.post("/api/admin/categories/<int:category_id>/image")
@require_admin
def admin_set_category_image(category_id):
    url = save_upload(request.files.get("file"))
    if not url:
        return jsonify({"message": "صيغة غير مدعومة"}), 400
    lod.update_category_image(category_id, url)
    return jsonify({"message": "تم تحديث الصورة", "url": url})


# ----- الأقسام -----
@app.get("/api/admin/sections")
@require_admin
def admin_sections():
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, color, emoji, is_active, image, sort_order FROM sections ORDER BY sort_order ASC, id ASC")
        rows = c.fetchall()
        out = []
        for r in rows:
            c.execute("SELECT COUNT(*) FROM products WHERE category = ?", (r[1],))
            cnt = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM subsections WHERE section_id = ?", (r[0],))
            sub_cnt = c.fetchone()[0]
            out.append({"id": r[0], "name": r[1], "color": r[2], "emoji": r[3],
                         "active": bool(r[4]), "image": r[5] or "", "sort_order": r[6],
                         "products_count": cnt, "subsections_count": sub_cnt})
    return jsonify(out)


@app.post("/api/admin/sections/reorder")
@require_admin
def admin_reorder_sections():
    b = request.get_json(force=True, silent=True) or {}
    ids = b.get("ids", [])
    if not isinstance(ids, list) or not ids:
        return jsonify({"message": "ids مطلوبة (لائحة من معرّفات الأقسام بالترتيب الجديد)"}), 400
    lod.reorder_sections(ids)
    return jsonify({"message": "تم تحديث الترتيب"})


@app.post("/api/admin/sections")
@require_admin
def admin_add_section():
    b = request.get_json(force=True, silent=True) or {}
    if not b.get("name"):
        return jsonify({"message": "اسم القسم مطلوب"}), 400
    ok = lod.add_section(b["name"], b.get("color", "success"), b.get("emoji", ""))
    if not ok:
        return jsonify({"message": "تعذّر إضافة القسم (ربما الاسم مستخدم)"}), 400
    return jsonify({"message": "تمت الإضافة"})


@app.delete("/api/admin/sections/<int:section_id>")
@require_admin
def admin_delete_section(section_id):
    lod.delete_section(section_id)
    return jsonify({"message": "تم الحذف"})


@app.post("/api/admin/sections/<int:section_id>/image")
@require_admin
def admin_set_section_image(section_id):
    url = save_upload(request.files.get("file"))
    if not url:
        return jsonify({"message": "صيغة غير مدعومة"}), 400
    with lod.get_db() as conn:
        conn.cursor().execute("UPDATE sections SET image = ? WHERE id = ?", (url, section_id))
    return jsonify({"message": "تم تحديث الصورة", "url": url})


# ----- الأقسام الفرعية -----
@app.get("/api/admin/sections/<int:section_id>/subsections")
@require_admin
def admin_subsections(section_id):
    rows = lod.get_subsections_by_section(section_id)
    with lod.get_db() as conn:
        c = conn.cursor()
        out = []
        for r in rows:
            sid, sec_id, name, emoji, image, is_active, sort_order = r
            c.execute("SELECT COUNT(*) FROM products WHERE subsection_id = ?", (sid,))
            cnt = c.fetchone()[0]
            out.append({"id": sid, "section_id": sec_id, "name": name, "emoji": emoji,
                         "image": image or "", "active": bool(is_active), "sort_order": sort_order,
                         "products_count": cnt})
    return jsonify(out)


@app.post("/api/admin/sections/<int:section_id>/subsections")
@require_admin
def admin_add_subsection(section_id):
    b = request.get_json(force=True, silent=True) or {}
    if not b.get("name"):
        return jsonify({"message": "اسم القسم الفرعي مطلوب"}), 400
    new_id = lod.add_subsection(section_id, b["name"], b.get("emoji", ""))
    return jsonify({"message": "تمت الإضافة", "id": new_id})


@app.put("/api/admin/subsections/<int:subsection_id>")
@require_admin
def admin_update_subsection(subsection_id):
    b = request.get_json(force=True, silent=True) or {}
    lod.update_subsection(subsection_id, name=b.get("name"), emoji=b.get("emoji"),
                           is_active=b.get("active"))
    return jsonify({"message": "تم التحديث"})


@app.delete("/api/admin/subsections/<int:subsection_id>")
@require_admin
def admin_delete_subsection(subsection_id):
    lod.delete_subsection(subsection_id)
    return jsonify({"message": "تم الحذف"})


@app.post("/api/admin/subsections/<int:subsection_id>/image")
@require_admin
def admin_set_subsection_image(subsection_id):
    url = save_upload(request.files.get("file"))
    if not url:
        return jsonify({"message": "صيغة غير مدعومة"}), 400
    lod.update_subsection_image(subsection_id, url)
    return jsonify({"message": "تم تحديث الصورة", "url": url})


@app.post("/api/admin/sections/<int:section_id>/subsections/reorder")
@require_admin
def admin_reorder_subsections(section_id):
    b = request.get_json(force=True, silent=True) or {}
    ids = b.get("ids", [])
    if not isinstance(ids, list) or not ids:
        return jsonify({"message": "ids مطلوبة"}), 400
    lod.reorder_subsections(ids)
    return jsonify({"message": "تم تحديث الترتيب"})


@app.get("/api/admin/subsections/<int:subsection_id>/products")
@require_admin
def admin_subsection_products(subsection_id):
    rows = lod.get_products_by_subsection(subsection_id)
    return jsonify([{"id": r[0], "name": r[1], "category": r[2], "emoji": r[3],
                      "description": r[4], "image": r[5] or "", "subsection_id": r[6]} for r in rows])


@app.post("/api/admin/products/reorder")
@require_admin
def admin_reorder_products():
    b = request.get_json(force=True, silent=True) or {}
    ids = b.get("ids", [])
    if not isinstance(ids, list) or not ids:
        return jsonify({"message": "ids مطلوبة"}), 400
    lod.reorder_products(ids)
    return jsonify({"message": "تم تحديث الترتيب"})


# ----- طرق الإيداع (تلقائي + يدوي) -----
@app.get("/api/admin/deposit-methods")
@require_admin
def admin_deposit_methods():
    auto = lod.get_all_auto_deposit_methods()   # id, title, description, code, rate, token, url, image, gateway_type
    manual = lod.get_all_deposit_methods()       # id, title, description, code, rate, image
    return jsonify({
        "auto": [{"id": m[0], "title": m[1], "description": m[2], "code": m[3], "exchange_rate": m[4],
                   "api_url": m[6], "image": m[7] or "", "gateway_type": m[8] if len(m) > 8 else "verify"} for m in auto],
        "manual": [{"id": m[0], "title": m[1], "description": m[2], "code": m[3], "exchange_rate": m[4],
                     "image": m[5] or ""} for m in manual],
    })


@app.post("/api/admin/deposit-methods/manual")
@require_admin
def admin_add_manual_method():
    b = request.get_json(force=True, silent=True) or {}
    if not b.get("title"):
        return jsonify({"message": "اسم الطريقة مطلوب"}), 400
    mid = lod.add_deposit_method(b["title"], b.get("description", ""), b.get("code", ""),
                                  float(b.get("exchange_rate") or lod.get_exchange_rate()),
                                  b.get("input_currency", "usd"))
    return jsonify({"message": "تمت الإضافة", "id": mid})


@app.delete("/api/admin/deposit-methods/manual/<int:method_id>")
@require_admin
def admin_delete_manual_method(method_id):
    lod.delete_deposit_method(method_id)
    return jsonify({"message": "تم الحذف"})


@app.post("/api/admin/deposit-methods/auto")
@require_admin
def admin_add_auto_method():
    b = request.get_json(force=True, silent=True) or {}
    if not b.get("title") or not b.get("api_token") or not b.get("api_url"):
        return jsonify({"message": "الاسم ومفتاح API ورابط API مطلوبين"}), 400
    gateway_type = b.get("gateway_type") or "verify"
    if gateway_type not in ("verify", "invoice"):
        gateway_type = "verify"
    mid = lod.add_auto_deposit_method(b["title"], b.get("description", ""), b.get("code", ""),
                                       float(b.get("exchange_rate") or lod.get_exchange_rate()),
                                       b["api_token"], b["api_url"], gateway_type, b.get("input_currency", "usd"))
    return jsonify({"message": "تمت الإضافة", "id": mid})


@app.put("/api/admin/deposit-methods/auto/<int:method_id>")
@require_admin
def admin_update_auto_method(method_id):
    b = request.get_json(force=True, silent=True) or {}
    existing = lod.get_auto_deposit_method_by_id(method_id)
    if not existing:
        return jsonify({"message": "الطريقة غير موجودة"}), 404
    gateway_type = b.get("gateway_type") or (existing[8] if len(existing) > 8 else "verify")
    if gateway_type not in ("verify", "invoice"):
        gateway_type = "verify"
    input_currency = b.get("input_currency") or (existing[9] if len(existing) > 9 else "usd")
    lod.update_auto_deposit_method(
        method_id,
        b.get("title", existing[1]), b.get("description", existing[2]), b.get("code", existing[3]),
        float(b.get("exchange_rate") or existing[4]),
        b.get("api_token", existing[5]), b.get("api_url", existing[6]),
        gateway_type, input_currency
    )
    return jsonify({"message": "تم التحديث"})


@app.delete("/api/admin/deposit-methods/auto/<int:method_id>")
@require_admin
def admin_delete_auto_method(method_id):
    lod.delete_auto_deposit_method(method_id)
    return jsonify({"message": "تم الحذف"})


@app.post("/api/admin/deposit-methods/manual/<int:method_id>/image")
@require_admin
def admin_set_manual_method_image(method_id):
    url = save_upload(request.files.get("file"))
    if not url:
        return jsonify({"message": "صيغة غير مدعومة"}), 400
    lod.update_deposit_method_image(method_id, url)
    return jsonify({"message": "تم تحديث صورة الطريقة", "url": url})


@app.post("/api/admin/deposit-methods/auto/<int:method_id>/image")
@require_admin
def admin_set_auto_method_image(method_id):
    url = save_upload(request.files.get("file"))
    if not url:
        return jsonify({"message": "صيغة غير مدعومة"}), 400
    lod.update_auto_deposit_method_image(method_id, url)
    return jsonify({"message": "تم تحديث صورة الطريقة", "url": url})


# ----- مزوّدو API -----
@app.get("/api/admin/providers")
@require_admin
def admin_providers():
    rows = lod.get_all_api_providers()  # id, name, api_token, api_url
    out = []
    with lod.get_db() as conn:
        c = conn.cursor()
        for r in rows:
            c.execute("SELECT COUNT(*) FROM linked_products WHERE provider_id = ?", (r[0],))
            cnt = c.fetchone()[0]
            out.append({"id": r[0], "name": r[1], "api_url": r[3], "linked_products": cnt})
    return jsonify(out)


@app.get("/api/admin/categories/<int:category_id>/link")
@require_admin
def admin_get_category_link(category_id):
    """يرجّع معلومات ربط الفئة بمزوّد API الحالي (إن وجد)."""
    link = lod.get_linked_by_category(category_id)
    if not link:
        return jsonify({"linked": False})
    # ترتيب الأعمدة من get_linked_by_category: lp.* ثم p_token, p_url
    # lp.* = id, product_id, category_id, api_product_id, product_name, category_name, api_name, api_price, provider_id, created_at
    return jsonify({
        "linked": True, "link_id": link[0], "api_product_id": link[3],
        "api_name": link[6] or "", "api_price": link[7] or 0, "provider_id": link[8],
    })


@app.post("/api/admin/categories/<int:category_id>/link")
@require_admin
def admin_link_category(category_id):
    """ربط فئة معيّنة بمنتج عند مزوّد API خارجي — نفس العملية يلي كانت بس عبر البوت،
    هلق صارت متاحة من لوحة تحكم الموقع مباشرة."""
    b = request.get_json(force=True, silent=True) or {}
    provider_id = b.get("provider_id")
    api_product_id = b.get("api_product_id")
    if not provider_id or not api_product_id:
        return jsonify({"message": "المزوّد ومعرّف المنتج بالـAPI مطلوبين"}), 400

    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, product_id FROM categories WHERE id = ?", (category_id,))
        cat = c.fetchone()
        if not cat:
            return jsonify({"message": "الفئة غير موجودة"}), 404
        cat_name, product_id = cat[1], cat[2]
        c.execute("SELECT name FROM products WHERE id = ?", (product_id,))
        prow = c.fetchone()
        product_name = prow[0] if prow else ""

        # إزالة أي ربط سابق لنفس الفئة قبل إضافة الربط الجديد (فئة واحدة = ربط واحد فعّال)
        c.execute("DELETE FROM linked_products WHERE category_id = ?", (category_id,))
        c.execute("""INSERT INTO linked_products (product_id, category_id, api_product_id, product_name,
                                                    category_name, api_name, api_price, provider_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                   (product_id, category_id, api_product_id, product_name, cat_name,
                    b.get("api_name", ""), float(b.get("api_price", 0) or 0), int(provider_id)))
    return jsonify({"message": "تم ربط الفئة بالمزوّد ✅"})


@app.delete("/api/admin/categories/<int:category_id>/link")
@require_admin
def admin_unlink_category(category_id):
    with lod.get_db() as conn:
        conn.cursor().execute("DELETE FROM linked_products WHERE category_id = ?", (category_id,))
    return jsonify({"message": "تم إلغاء الربط"})


@app.post("/api/admin/providers")
@require_admin
def admin_add_provider():
    b = request.get_json(force=True, silent=True) or {}
    if not b.get("name") or not b.get("api_token") or not b.get("api_url"):
        return jsonify({"message": "كل الحقول مطلوبة"}), 400
    pid = lod.add_api_provider(b["name"], b["api_token"], b["api_url"])
    return jsonify({"message": "تمت الإضافة", "id": pid})


@app.delete("/api/admin/providers/<int:provider_id>")
@require_admin
def admin_delete_provider(provider_id):
    lod.delete_api_provider(provider_id)
    return jsonify({"message": "تم الحذف"})


# ----- إعدادات عامة -----
@app.get("/api/admin/settings")
@require_admin
def admin_get_settings():
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, image FROM banner_images ORDER BY sort_order ASC, id ASC")
        banner_images = [{"id": r[0], "image": r[1]} for r in c.fetchall()]
    return jsonify({
        "exchange_rate": lod.get_exchange_rate(),
        "welcome_message": lod.welcome_message,
        "support_username": lod.get_support_username(),
        "banner_images": banner_images,
        "logo_image": get_setting("logo_image", ""),
        "app_icon": get_setting("app_icon", ""),
        "welcome_popup_enabled": get_setting("welcome_popup_enabled", "false") == "true",
        "welcome_popup_text": get_setting("welcome_popup_text", ""),
        "dev_logo": get_setting("dev_logo", ""),
        "ai_image_api_url": get_setting("ai_image_api_url", ""),
        "ai_image_api_key": get_setting("ai_image_api_key", ""),
        "ai_image_prompt_template": get_setting("ai_image_prompt_template", DEFAULT_AI_PROMPT_TEMPLATE),
        "ai_image_prompt_product": get_setting("ai_image_prompt_product", ""),
        "ai_image_prompt_section": get_setting("ai_image_prompt_section", ""),
        "admin_notify_chat_ids": get_setting("admin_notify_chat_ids", ""),
        "contact": _contact_settings(),
    })


@app.post("/api/admin/settings/banner-image")
@require_admin
def admin_add_banner_image():
    """يضيف صورة جديدة لسلايدر البانر (لا يحل محل الصور الموجودة، حد أقصى 5 صور)."""
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM banner_images")
        if c.fetchone()[0] >= 5:
            return jsonify({"message": "الحد الأقصى 5 صور للبانر، احذف صورة قبل إضافة جديدة"}), 400
    url = save_upload(request.files.get("file"))
    if not url:
        return jsonify({"message": "صيغة غير مدعومة"}), 400
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM banner_images")
        next_order = c.fetchone()[0]
        c.execute("INSERT INTO banner_images (image, sort_order) VALUES (?, ?)", (url, next_order))
        new_id = c.lastrowid
    return jsonify({"message": "تمت إضافة صورة البانر", "id": new_id, "url": url})


@app.delete("/api/admin/settings/banner-image/<int:image_id>")
@require_admin
def admin_remove_banner_image(image_id):
    with lod.get_db() as conn:
        conn.cursor().execute("DELETE FROM banner_images WHERE id = ?", (image_id,))
    return jsonify({"message": "تمت إزالة الصورة"})


@app.post("/api/admin/settings")
@require_admin
def admin_update_settings():
    b = request.get_json(force=True, silent=True) or {}
    if b.get("exchange_rate"):
        lod.set_exchange_rate(float(b["exchange_rate"]))
    if b.get("welcome_message"):
        lod.set_welcome_message(b["welcome_message"])
    if b.get("support_username"):
        lod.set_support_username(b["support_username"])
    if "welcome_popup_enabled" in b:
        set_setting("welcome_popup_enabled", "true" if b["welcome_popup_enabled"] else "false")
    if "welcome_popup_text" in b:
        set_setting("welcome_popup_text", b["welcome_popup_text"] or "")
    for ai_key in ("ai_image_api_url", "ai_image_api_key", "ai_image_prompt_template",
                   "ai_image_prompt_product", "ai_image_prompt_section"):
        if ai_key in b:
            set_setting(ai_key, b[ai_key] or "")
    # ===== أرقام/روابط التواصل وقنوات الأخبار (تظهر بزر السماعة العائم) =====
    for ck in CONTACT_SETTING_KEYS:
        if ck in b:
            set_setting(ck, (b[ck] or "").strip())
    if "admin_notify_chat_ids" in b:
        set_setting("admin_notify_chat_ids", (b["admin_notify_chat_ids"] or "").strip())
        lod.reload_admin_notify_targets()
    return jsonify({"message": "تم حفظ الإعدادات"})


@app.post("/api/admin/settings/notify-test")
@require_admin
def admin_notify_test():
    """يرسل إشعار تجريبي لكل جهات الإدارة على تيليجرام للتأكد من وصول الإشعارات."""
    lod.reload_admin_notify_targets()
    targets = lod.get_admin_notify_targets()
    ok = lod.notify_admin("🔔 اختبار إشعارات الأدمن", "إذا وصلتك هالرسالة فإشعارات الأدمن شغّالة ✅")
    if not ok:
        return jsonify({"message": "لم تصل الرسالة لأي جهة — تأكد أن البوت عضو بالمجموعة أو أن الأدمن ضغط /start بالبوت",
                        "targets": targets}), 502
    return jsonify({"message": "تم إرسال إشعار تجريبي ✅", "targets": targets})


# ----- صلاحيات الأدمن -----
@app.get("/api/admin/admins")
@require_admin
def admin_list_admins():
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE is_admin = 1")
        ids = [r[0] for r in c.fetchall()]
    if lod.MAIN_ADMIN_ID not in ids:
        ids.insert(0, lod.MAIN_ADMIN_ID)
    return jsonify([{"user_id": uid, "main": uid == lod.MAIN_ADMIN_ID} for uid in ids])


@app.post("/api/admin/admins")
@require_admin
def admin_add_admin_route():
    b = request.get_json(force=True, silent=True) or {}
    try:
        uid = int(b.get("user_id"))
    except (TypeError, ValueError):
        return jsonify({"message": "آيدي تيليجرام غير صحيح"}), 400
    lod.add_admin(uid)
    return jsonify({"message": "تمت الإضافة"})


@app.delete("/api/admin/admins/<int:user_id>")
@require_admin
def admin_remove_admin_route(user_id):
    if not lod.remove_admin(user_id):
        return jsonify({"message": "لا يمكن إزالة المشرف الرئيسي"}), 400
    return jsonify({"message": "تمت الإزالة"})


# ----- أدمن الموقع (Web Admins) — يعطي صلاحية كاملة للوحة الأدمن لحساب موقع -----
@app.get("/api/admin/web-admins")
@require_admin
def admin_list_web_admins():
    _ensure_web_admins_table()
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT email, added_at FROM web_admins ORDER BY added_at DESC")
        rows = c.fetchall()
    payload = getattr(request, "admin_payload", {}) or {}
    admins = [{"email": e, "added_at": str(a) if a else "", "owner": False, "removable": True} for (e, a) in rows]
    for owner_email in OWNER_EMAILS:
        admins.insert(0, {"email": owner_email, "added_at": "—", "owner": True, "removable": False})
    return jsonify({"admins": admins, "is_owner": bool(payload.get("owner"))})


@app.post("/api/admin/web-admins")
@require_owner
def admin_add_web_admin():
    body = request.get_json(force=True, silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"message": "أدخل بريد إلكتروني صحيح"}), 400
    if email in OWNER_EMAILS:
        return jsonify({"message": "هذا البريد هو المالك الرئيسي مسبقاً"}), 400
    _ensure_web_admins_table()
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO web_admins (email) VALUES (?)", (email,))
    return jsonify({"message": "تمت إضافة الأدمن ✅"})


@app.delete("/api/admin/web-admins/<path:email>")
@require_owner
def admin_remove_web_admin(email):
    email = (email or "").strip().lower()
    if email in OWNER_EMAILS:
        return jsonify({"message": "لا يمكن حذف المالك الرئيسي"}), 400
    _ensure_web_admins_table()
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM web_admins WHERE email = ?", (email,))
    return jsonify({"message": "تمت الإزالة"})





# =============================================================
# 2) مراقبة حالة الطلبات تلقائياً (يعمل في الخلفية)
# =============================================================
def _poll_pending_orders():
    """
    خيط (thread) يعمل بالخلفية — يفحص كل 60 ثانية طلبات API التي لا تزال
    "processing" ويحدّث حالتها باستخدام نفس check_order_status المستخدم بالبوت.
    """
    while True:
        try:
            with lod.get_db() as conn:
                c = conn.cursor()
                c.execute("""SELECT o.id, o.order_id, o.user_id, o.price,
                                    p.api_token, p.api_url
                             FROM api_orders o
                             LEFT JOIN api_providers p ON o.provider_id = p.id
                             WHERE o.status = 'processing'
                             ORDER BY o.created_at ASC LIMIT 50""")
                pending = c.fetchall()

            for row in pending:
                db_id, ext_order_id, uid, price, api_token, api_url = row
                if not ext_order_id:
                    continue
                try:
                    result = lod.check_order_status(ext_order_id, api_token=api_token, api_base_url=api_url)
                    if result is None or result == "wait":
                        continue
                    if isinstance(result, dict):
                        new_status = result.get("status", "")
                        replay = result.get("_replay_text", "") or result.get("api_response", "")
                        if new_status in ("completed", "failed"):
                            lod.update_api_order_status(db_id, new_status, str(replay))
                            if new_status == "failed" and price:
                                lod.update_user_balance(uid, price)  # استرجاع الرصيد
                except Exception:
                    pass
        except Exception:
            pass

        # ===== فحص فواتير الدفع (SAM API) المعلّقة — احتياطي عن الـ webhook =====
        try:
            with lod.get_db() as conn:
                c = conn.cursor()
                c.execute("""SELECT dr.id, dr.invoice_ref, m.api_token
                             FROM deposit_requests dr
                             JOIN auto_deposit_methods m ON m.title = dr.method_title
                             WHERE dr.status = 'pending' AND dr.invoice_ref != '' AND m.gateway_type = 'invoice'
                             ORDER BY dr.id ASC LIMIT 50""")
                pending_invoices = c.fetchall()
            for req_id, invoice_ref, api_token in pending_invoices:
                status = lod.check_invoice_status(invoice_ref, api_token)
                if status == "paid":
                    lod.accept_deposit_request(req_id)
                elif status in ("failed", "expired"):
                    lod.reject_deposit_request(req_id)
        except Exception as e:
            print(f"[invoice-poll] error: {e}")

        time.sleep(60)


def start_order_monitor():
    t = threading.Thread(target=_poll_pending_orders, daemon=True)
    t.start()


def _daily_price_sync_loop():
    """
    خيط بالخلفية يشتغل مرة كل 24 ساعة: يمر على كل فئة إلها هامش ربح محدد
    ومربوطة بمزوّد API، ويجيب سعر المزوّد الحالي، ويعيد حساب سعر البيع
    (تكلفة × (1 + الهامش%))، وبيحدّثه تلقائياً — هيك لو رفع المزوّد سعرو
    بيرتفع سعرك لحاله بنفس اليوم بدون ما تحتاج تدخل يدوي.
    """
    while True:
        try:
            time.sleep(24 * 60 * 60)  # مرة كل 24 ساعة
            results = lod.sync_all_margin_prices()
            if results:
                ok_count = sum(1 for r in results if r["ok"])
                print(f"[price-sync] تم تحديث {ok_count}/{len(results)} فئة بنجاح")
        except Exception as e:
            print(f"[price-sync] error: {e}")


def start_price_sync_monitor():
    t = threading.Thread(target=_daily_price_sync_loop, daemon=True)
    t.start()


# ===== API endpoint: طلب تحديث يدوي فوري لطلب واحد =====
@app.get("/api/orders/<int:order_id>/refresh")
@require_auth
def refresh_order(order_id):
    uid = effective_user_id(request.web_user)
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT o.id, o.order_id, o.status, o.product_name, o.category_name,
                            o.price, o.player_id, o.qty, o.api_response, o.created_at,
                            p.api_token, p.api_url
                     FROM api_orders o
                     LEFT JOIN api_providers p ON o.provider_id = p.id
                     WHERE o.id = ? AND o.user_id = ?""", (order_id, uid))
        row = c.fetchone()
    if not row:
        with lod.get_db() as conn2:
            c2 = conn2.cursor()
            c2.execute("SELECT id, status FROM shop_orders WHERE id = ? AND user_id = ?", (order_id, uid))
            row2 = c2.fetchone()
        if row2:
            return jsonify({"status": row2[1], "changed": False, "note": "طلب يدوي"})
        return jsonify({"message": "الطلب غير موجود"}), 404

    db_id, ext_id, status = row[0], row[1], row[2]
    api_token, api_url = row[10], row[11]

    if status != "processing":
        return jsonify({"status": status, "changed": False})

    try:
        result = lod.check_order_status(ext_id, api_token=api_token, api_base_url=api_url)
        if isinstance(result, dict):
            new_status = result.get("status", status)
            replay = result.get("_replay_text", "") or ""
            if new_status in ("completed", "failed"):
                lod.update_api_order_status(db_id, new_status, str(replay))
                if new_status == "failed" and row[5]:
                    lod.update_user_balance(uid, row[5])
                return jsonify({"status": new_status, "changed": True, "replay": replay})
    except Exception as e:
        return jsonify({"status": status, "changed": False, "error": str(e)})

    return jsonify({"status": status, "changed": False})


# ===== تفاصيل طلب واحد كاملة =====
@app.get("/api/orders/<int:order_id>/detail")
@require_auth
def order_detail(order_id):
    uid = effective_user_id(request.web_user)
    rate = lod.get_exchange_rate()
    with lod.get_db() as conn:
        c = conn.cursor()
        # نبحث بالطلبات المربوطة بـ API أولاً
        c.execute("""SELECT 'api' as src, o.id, o.order_id, o.product_name, o.category_name,
                            o.price, o.player_id, o.qty, o.api_response, o.status, o.created_at, o.completed_at
                     FROM api_orders o WHERE o.id = ? AND o.user_id = ?""", (order_id, uid))
        row = c.fetchone()
        if not row:
            c.execute("""SELECT 'shop' as src, id, '' as ext_id, product_name, category_name,
                                price, player_id, qty, '' as api_response, status, created_at, completed_at
                         FROM shop_orders WHERE id = ? AND user_id = ?""", (order_id, uid))
            row = c.fetchone()

    if not row:
        return jsonify({"message": "الطلب غير موجود"}), 404

    # حساب مدة الاستجابة الفعلية = الفرق بين وقت الإنشاء ووقت الرد (إن وُجد)
    response_time_text = None
    created_raw, completed_raw = row[10], row[11]
    if created_raw and completed_raw:
        try:
            fmt = "%Y-%m-%d %H:%M:%S"
            t0 = datetime.strptime(str(created_raw)[:19], fmt)
            t1 = datetime.strptime(str(completed_raw)[:19], fmt)
            delta_seconds = max(0, int((t1 - t0).total_seconds()))
            if delta_seconds < 60:
                response_time_text = f"{delta_seconds} ثانية"
            elif delta_seconds < 3600:
                response_time_text = f"{delta_seconds // 60} دقيقة"
            else:
                h, rem = divmod(delta_seconds, 3600)
                response_time_text = f"{h} ساعة و{rem // 60} دقيقة"
        except Exception:
            response_time_text = None

    UNIFY = {
        "accepted": "accepted", "pending": "pending", "rejected": "rejected",
        "completed": "accepted", "processing": "pending", "failed": "rejected", "timeout": "rejected",
    }
    raw_status = row[9]
    return jsonify({
        "source": row[0], "id": row[1], "ext_order_id": row[2],
        "product_name": row[3], "category_name": row[4],
        "price_syp": row[5], "price_usd": round(row[5] / rate, 2) if rate else 0,
        "player_id": row[6], "qty": row[7],
        "api_response": row[8] or "",
        "status": UNIFY.get(raw_status, raw_status), "raw_status": raw_status, "date": row[10],
        "response_time_text": response_time_text,  # None إذا الطلب لسا قيد التنفيذ (ما رد عليه بعد)
    })


# =============================================================
# 3) تعديل المنتجات / الفئات / الأقسام / طرق الإيداع
# =============================================================

@app.put("/api/admin/products/<int:product_id>")
@require_admin
def admin_edit_product(product_id):
    b = request.get_json(force=True, silent=True) or {}
    with lod.get_db() as conn:
        c = conn.cursor()
        if b.get("name"):
            c.execute("UPDATE products SET name = ? WHERE id = ?", (b["name"], product_id))
        if b.get("category"):
            c.execute("UPDATE products SET category = ? WHERE id = ?", (b["category"], product_id))
        if b.get("emoji") is not None:
            c.execute("UPDATE products SET emoji = ? WHERE id = ?", (b["emoji"], product_id))
        if "subsection_id" in b:
            c.execute("UPDATE products SET subsection_id = ? WHERE id = ?", (b.get("subsection_id") or 0, product_id))
    return jsonify({"message": "تم التعديل"})


@app.put("/api/admin/categories/<int:category_id>")
@require_admin
def admin_edit_category(category_id):
    b = request.get_json(force=True, silent=True) or {}
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT min_qty, max_qty FROM categories WHERE id = ?", (category_id,))
        current = c.fetchone()
        if not current:
            return jsonify({"message": "الفئة غير موجودة"}), 404
        next_min = int(b.get("min_qty", current[0]) or 1)
        next_max = int(b.get("max_qty", current[1]) or 1)
        if next_min < 1 or next_max < next_min:
            return jsonify({"message": "يجب أن يكون الحد الأدنى 1 على الأقل وألا يتجاوز الحد الأقصى"}), 400
        if b.get("name"):
            c.execute("UPDATE categories SET name = ? WHERE id = ?", (b["name"], category_id))
        if b.get("price") is not None:
            c.execute("UPDATE categories SET price = ? WHERE id = ?", (float(b["price"]), category_id))
        if b.get("min_qty") is not None:
            c.execute("UPDATE categories SET min_qty = ? WHERE id = ?", (int(b["min_qty"]), category_id))
        if b.get("max_qty") is not None:
            c.execute("UPDATE categories SET max_qty = ? WHERE id = ?", (int(b["max_qty"]), category_id))
        if b.get("unit_qty") is not None:
            c.execute("UPDATE categories SET unit_qty = ? WHERE id = ?", (max(1, int(b["unit_qty"])), category_id))
        if "requires_id" in b:
            c.execute("UPDATE categories SET requires_id = ? WHERE id = ?",
                      (0 if str(b["requires_id"]).lower() in ("false", "0", "no") else 1, category_id))
        if "stock_qty" in b:
            val = b["stock_qty"]
            stock_val = None if val in (None, "", "null") else int(val)
            c.execute("UPDATE categories SET stock_qty = ? WHERE id = ?", (stock_val, category_id))
    return jsonify({"message": "تم التعديل"})


@app.put("/api/admin/sections/<int:section_id>")
@require_admin
def admin_edit_section(section_id):
    b = request.get_json(force=True, silent=True) or {}
    with lod.get_db() as conn:
        c = conn.cursor()
        if b.get("name"):
            c.execute("UPDATE sections SET name = ? WHERE id = ?", (b["name"], section_id))
        if b.get("emoji") is not None:
            c.execute("UPDATE sections SET emoji = ? WHERE id = ?", (b["emoji"], section_id))
        if "active" in b:
            c.execute("UPDATE sections SET is_active = ? WHERE id = ?", (1 if b["active"] else 0, section_id))
    return jsonify({"message": "تم التعديل"})


@app.put("/api/admin/deposit-methods/manual/<int:method_id>")
@require_admin
def admin_edit_manual_method(method_id):
    b = request.get_json(force=True, silent=True) or {}
    with lod.get_db() as conn:
        c = conn.cursor()
        if b.get("title"):
            c.execute("UPDATE deposit_methods SET title = ? WHERE id = ?", (b["title"], method_id))
        if b.get("description") is not None:
            c.execute("UPDATE deposit_methods SET description = ? WHERE id = ?", (b["description"], method_id))
        if b.get("exchange_rate") is not None:
            c.execute("UPDATE deposit_methods SET exchange_rate = ? WHERE id = ?", (float(b["exchange_rate"]), method_id))
    return jsonify({"message": "تم التعديل"})





# =============================================================
# 5) نظام الإحالة والخصومات
# =============================================================

@app.get("/api/user/referral")
@require_auth
def user_referral():
    uid = effective_user_id(request.web_user)
    ref = lod.get_referral_settings()  # tuple: (enabled, amount)
    enabled = ref[0] if ref else False
    amount = ref[1] if ref else 0
    count = lod.get_referral_count(uid)
    name, discount = lod.get_user_discount(uid)
    rate = lod.get_exchange_rate()
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT SUM(reward_amount) FROM referrals WHERE referrer_id = ?", (uid,))
        earned_syp = (c.fetchone()[0] or 0)
    return jsonify({
        "referral_enabled": bool(enabled),
        "reward_amount_syp": float(amount),
        "reward_amount_usd": round(float(amount) / rate, 2) if rate else 0,
        "my_referral_count": count,
        "earned_syp": earned_syp,
        "earned_usd": round(earned_syp / rate, 2) if rate else 0,
        "my_code": str(uid),
        "discount_name": name,
        "discount_percent": discount,
    })


# =============================================================
# لوغو الموقع
# =============================================================
@app.post("/api/admin/settings/logo")
@require_admin
def admin_set_logo():
    url = save_upload(request.files.get("file"))
    if not url:
        return jsonify({"message": "صيغة غير مدعومة"}), 400
    set_setting("logo_image", url)
    return jsonify({"message": "تم تحديث اللوغو", "url": url})


@app.post("/api/admin/settings/dev-logo")
@require_admin
def admin_set_dev_logo():
    """لوغو المطوّر الظاهر أسفل القائمة الجانبية فوق (برمجة وتصميم)."""
    url = save_upload(request.files.get("file"))
    if not url:
        return jsonify({"message": "صيغة غير مدعومة"}), 400
    set_setting("dev_logo", url)
    return jsonify({"message": "تم رفع لوغو المطوّر", "url": url})


@app.delete("/api/admin/settings/dev-logo")
@require_admin
def admin_remove_dev_logo():
    set_setting("dev_logo", "")
    return jsonify({"message": "تمت إزالة لوغو المطوّر"})


@app.delete("/api/admin/settings/logo")
@require_admin
def admin_remove_logo():
    set_setting("logo_image", "")
    return jsonify({"message": "تمت إزالة اللوغو"})


# =============================================================
# قبول / رفض طلبات الإيداع من لوحة الويب
# =============================================================
@app.post("/api/admin/deposits/<int:req_id>/accept")
@require_admin
def admin_accept_deposit(req_id):
    ok, uid, amount = lod.accept_deposit_request(req_id)
    if not ok:
        return jsonify({"message": "الطلب غير موجود أو تمت معالجته مسبقاً"}), 404
    # إشعار المستخدم عبر تيليجرام لو كان مربوطاً
    try:
        rate = lod.get_exchange_rate()
        lod.send_message(uid, f"✅ تم قبول إيداعك بنجاح!\n💰 المبلغ: {amount:,.0f} ل.س ({round(amount/rate,2)}$)\n⚡ رصيدك الحالي: {lod.get_user_balance(uid):,.0f} ل.س")
    except Exception:
        pass
    return jsonify({"message": "تم القبول وإضافة الرصيد", "user_id": uid, "amount_syp": amount})


@app.post("/api/admin/deposits/<int:req_id>/reject")
@require_admin
def admin_reject_deposit(req_id):
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM deposit_requests WHERE id = ? AND status='pending'", (req_id,))
        row = c.fetchone()
    lod.reject_deposit_request(req_id)
    if row:
        try:
            lod.send_message(row[0], "❌ تم رفض طلب الإيداع.\nللاستفسار تواصل مع الدعم.")
        except Exception:
            pass
    return jsonify({"message": "تم الرفض"})


# =============================================================
# قبول / رفض / شحن طلبات المتجر (shop_orders) من لوحة الويب
# =============================================================
@app.get("/api/admin/shop-orders")
@require_admin
def admin_shop_orders():
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, user_id, product_name, category_name, price,
                            player_id, qty, status, created_at
                     FROM shop_orders ORDER BY created_at DESC LIMIT 200""")
        rows = c.fetchall()
    return jsonify([{
        "id": r[0], "user_id": r[1], "product_name": r[2], "category_name": r[3],
        "price_syp": r[4], "player_id": r[5], "qty": r[6], "status": r[7], "date": r[8]
    } for r in rows])


@app.post("/api/admin/shop-orders/<int:order_id>/accept")
@require_admin
def admin_accept_shop_order(order_id):
    """قبول طلب يدوي (بدون شحن API) — إشعار العميل بالقبول"""
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT user_id, product_name, category_name, price, player_id, qty
                     FROM shop_orders WHERE id = ? AND status = 'pending'""", (order_id,))
        o = c.fetchone()
        if not o:
            return jsonify({"message": "الطلب غير موجود أو تمت معالجته"}), 404
        uid, pname, cname, price, player_id, qty = o
        c.execute("UPDATE shop_orders SET status = 'accepted', completed_at = ? WHERE id = ?", (datetime.utcnow(), order_id))

    rate = lod.get_exchange_rate()
    price_usd = round(price / rate, 2) if rate else 0
    try:
        lod.send_message(uid,
            f"✅ تم اكتمال طلبك بنجاح!\n\n"
            f"▪️ المنتج: {pname}\n▪️ الفئة: {cname}\n"
            f"▪️ الكمية: {qty or 1}\n▪️ آيدي اللاعب: {player_id}\n"
            f"▪️ السعر: {price:,.0f} ل.س ({price_usd}$)\n\nشكراً ❤️")
    except Exception:
        pass
    lod.add_notification(uid, "✅ تم شحن طلبك", f"تم تنفيذ طلب «{pname}» بنجاح", "success")
    return jsonify({"message": "تم قبول الطلب وإشعار العميل"})


@app.post("/api/admin/shop-orders/<int:order_id>/reject")
@require_admin
def admin_reject_shop_order(order_id):
    """رفض طلب يدوي — استرجاع الرصيد وإشعار العميل"""
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, price, product_name FROM shop_orders WHERE id = ? AND status='pending'", (order_id,))
        o = c.fetchone()
        if not o:
            return jsonify({"message": "الطلب غير موجود أو تمت معالجته"}), 404
        uid, price, pname = o
        c.execute("UPDATE shop_orders SET status = 'rejected', completed_at = ? WHERE id = ?", (datetime.utcnow(), order_id))

    lod.update_user_balance(uid, price)  # استرجاع الرصيد
    try:
        lod.send_message(uid,
            f"❌ تم رفض طلبك ({pname}).\n"
            f"💰 تم استرجاع {price:,.0f} ل.س لمحفظتك.\nللاستفسار تواصل مع الدعم.")
    except Exception:
        pass
    lod.add_notification(uid, "❌ تم رفض طلبك", f"تم رفض طلبك ({pname}) وإعادة {price:,.0f} ل.س لمحفظتك", "danger")
    return jsonify({"message": "تم رفض الطلب واسترجاع الرصيد"})


@app.post("/api/admin/shop-orders/<int:order_id>/execute")
@require_admin
def admin_execute_shop_order(order_id):
    """
    شحن طلب يدوي عبر مزوّد API مباشرة من لوحة التحكم.
    body: { provider_id: int, api_product_id: str, cost_usd: float }
    """
    b = request.get_json(force=True, silent=True) or {}
    provider_id = b.get("provider_id")
    api_product_id = b.get("api_product_id")
    cost_usd = float(b.get("cost_usd") or 0)
    if not provider_id or not api_product_id:
        return jsonify({"message": "provider_id وapi_product_id مطلوبين"}), 400

    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT user_id, product_name, category_name, price, player_id, qty, price_usd
                     FROM shop_orders WHERE id = ? AND status IN ('pending','accepted')""", (order_id,))
        o = c.fetchone()
        if not o:
            return jsonify({"message": "الطلب غير موجود أو تمت معالجته"}), 404
        uid, pname, cname, price, player_id, qty, price_usd = o

        c.execute("SELECT api_token, api_url FROM api_providers WHERE id = ?", (provider_id,))
        prow = c.fetchone()
        if not prow:
            return jsonify({"message": "المزوّد غير موجود"}), 404
        api_token, api_url = prow

    result = lod.buy_from_api(api_product_id, player_id, qty or 1,
                               api_token=api_token, api_base_url=api_url)
    if result.get("error") or result.get("status") not in ("OK", "ok", "success", "SUCCESS", "processing"):
        return jsonify({"message": "رفضه المزوّد: " + str(result), "raw": result}), 400

    data_res = result.get("data", {})
    ext_order_id = data_res.get("order_id", "") or str(result.get("order_id", ""))
    replay = lod.extract_replay_text(data_res) or ""

    # تحويل الطلب من shop_orders إلى api_orders لمتابعة الحالة تلقائياً
    new_api_id = lod.save_api_order(uid, 0, ext_order_id, pname, cname, price,
                                     player_id, qty or 1, replay, provider_id,
                                     cost_usd=cost_usd, price_usd=price_usd or 0)
    with lod.get_db() as conn:
        conn.cursor().execute("UPDATE shop_orders SET status = 'accepted' WHERE id = ?", (order_id,))

    try:
        lod.send_message(uid,
            f"⚡ جاري شحن طلبك الآن!\n▪️ {pname} — {cname}\n▪️ آيدي: {player_id}\nرح نبلغك فور الانتهاء ✅")
    except Exception:
        pass
    return jsonify({"message": "تم إرسال الطلب للمزوّد بنجاح", "api_order_id": new_api_id, "ext_order_id": ext_order_id})


# =============================================================
# جلب منتجات مزوّد API (لربط الطلب اليدوي بمنتج المزوّد)
# =============================================================
@app.post("/api/admin/providers/<int:provider_id>/import-catalog")
@require_admin
def admin_import_provider_catalog(provider_id):
    b = request.get_json(force=True, silent=True) or {}
    margin_percent = b.get("margin_percent")
    if margin_percent is None or float(margin_percent) < 0:
        return jsonify({"message": "أدخل نسبة هامش ربح صحيحة"}), 400
    result, error = lod.import_provider_catalog(provider_id, float(margin_percent))
    if error:
        return jsonify({"message": error}), 400
    return jsonify({
        "message": f"تم استيراد {result['categories_created']} فئة ({result['products_created']} منتج جديد) "
                    f"بقسم «{result['section_name']}»"
                    + (f"، وتخطّينا {result['categories_skipped']} عنصر (مربوط مسبقاً أو سعره غير صالح)" if result['categories_skipped'] else ""),
        **result,
    })


@app.get("/api/admin/providers/<int:provider_id>/products")
@require_admin
def admin_provider_products(provider_id):
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT api_token, api_url FROM api_providers WHERE id = ?", (provider_id,))
        row = c.fetchone()
    if not row:
        return jsonify({"message": "المزوّد غير موجود"}), 404
    try:
        products = lod.get_all_api_products(api_token=row[0], api_base_url=row[1])
        if not products:
            return jsonify([])
        # نوحّد الشكل — أي بنية يرجعها المزوّد
        out = []
        for p in products:
            if isinstance(p, dict):
                price_val = p.get("price") or p.get("cost") or p.get("rate") or p.get("amount") or 0
                try:
                    price_val = float(price_val)
                except (TypeError, ValueError):
                    price_val = 0
                out.append({
                    "id": str(p.get("id") or p.get("product_id") or ""),
                    "name": p.get("name") or p.get("product_name") or str(p),
                    "price": price_val,
                })
            else:
                out.append({"id": str(p), "name": str(p), "price": 0})
        return jsonify(out)
    except Exception as e:
        return jsonify({"message": str(e)}), 500


# =============================================================
# سجل العمليات للمستخدم (طلبات + رصيد + إشعارات)
# =============================================================
@app.get("/api/user/activity")
@require_auth
def user_activity():
    """سجل موحّد: كل الطلبات + تغييرات الرصيد + إشعارات النظام مع الوقت والحالة."""
    uid = effective_user_id(request.web_user)
    items = []
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, product_name, category_name, price, qty, status, created_at, player_id
                     FROM shop_orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 200""", (uid,))
        for r in c.fetchall():
            items.append({"kind": "order", "ref": f"S{r[0]}", "title": f"{r[1]} - {r[2]}",
                          "detail": f"الكمية: {r[4]} | الايدي: {r[7] or '—'}",
                          "amount_syp": r[3], "status": r[5], "date": r[6], "source": "يدوي"})
        c.execute("""SELECT id, product_name, category_name, price, qty, status, created_at, player_id, order_id
                     FROM api_orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 200""", (uid,))
        for r in c.fetchall():
            items.append({"kind": "order", "ref": f"A{r[0]}", "title": f"{r[1]} - {r[2]}",
                          "detail": f"الكمية: {r[4]} | الايدي: {r[7] or '—'} | مرجع المزود: {r[8] or '—'}",
                          "amount_syp": r[3], "status": r[5], "date": r[6], "source": "مزود"})
        c.execute("""SELECT type, amount, description, created_at FROM user_transactions
                     WHERE user_id = ? ORDER BY created_at DESC LIMIT 200""", (uid,))
        for r in c.fetchall():
            items.append({"kind": "balance", "ref": "", "title": r[0] or "حركة رصيد",
                          "detail": r[2] or "", "amount_syp": r[1], "status": "done", "date": r[3], "source": "المحفظة"})
        c.execute("""SELECT method_title, amount_usd, amount_syp, status, created_at
                     FROM deposit_requests WHERE user_id = ? ORDER BY created_at DESC LIMIT 200""", (uid,))
        for r in c.fetchall():
            items.append({"kind": "deposit", "ref": "", "title": f"طلب إيداع - {r[0]}",
                          "detail": f"${float(r[1] or 0):.2f}", "amount_syp": r[2],
                          "status": r[3], "date": r[4], "source": "إيداع"})
        c.execute("""SELECT title, message, kind, created_at FROM notifications
                     WHERE user_id = ? ORDER BY created_at DESC LIMIT 200""", (uid,))
        for r in c.fetchall():
            items.append({"kind": "notification", "ref": "", "title": r[0], "detail": r[1] or "",
                          "amount_syp": None, "status": r[2] or "info", "date": r[3], "source": "النظام"})

    items.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
    return jsonify(items[:400])


# =============================================================
# توليد صور بالذكاء الاصطناعي (للمنتجات/الأقسام/الفئات)
# =============================================================
DEFAULT_AI_PROMPT_TEMPLATE = (
    "Premium mobile game top-up store card thumbnail for \"{name}\", centered product artwork, "
    "dark navy background with subtle red neon glow, glossy 3D coins and gems, clean modern layout, "
    "consistent branded style, sharp studio lighting, no text, square 1:1"
)


def _ai_settings():
    return {
        "url": get_setting("ai_image_api_url", ""),
        "key": get_setting("ai_image_api_key", ""),
        "template": get_setting("ai_image_prompt_template", DEFAULT_AI_PROMPT_TEMPLATE),
    }


def _save_remote_image(image_url):
    """ينزّل الصورة من رابط مؤقت ويحفظها محلياً بمجلد uploads (الروابط من المزود بتنتهي صلاحيتها)."""
    import requests as _rq
    resp = _rq.get(image_url, timeout=90)
    resp.raise_for_status()
    ctype = (resp.headers.get("content-type") or "").lower()
    ext = "png"
    for cand in ("jpeg", "jpg", "webp", "gif", "png"):
        if cand in ctype:
            ext = "jpg" if cand == "jpeg" else cand
            break
    filename = f"ai_{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as fh:
        fh.write(resp.content)
    return f"/uploads/{filename}"


@app.post("/api/admin/ai-image/generate")
@require_admin
def admin_ai_image_generate():
    """ينشئ صورة تلقائياً حسب اسم المنتج/القسم/الفئة بنفس الستايل الموحّد."""
    from urllib.parse import quote
    import requests as _rq

    b = request.get_json(force=True, silent=True) or {}
    name = (b.get("name") or "").strip()
    kind = (b.get("kind") or "product").strip()
    if not name:
        return jsonify({"message": "الاسم مطلوب لتوليد الصورة"}), 400

    cfg = _ai_settings()
    if not cfg["url"]:
        return jsonify({"message": "رابط API الذكاء الاصطناعي غير محدد بإعدادات لوحة الأدمن"}), 400

    kind_label = {"product": "game product", "section": "store category",
                  "subsection": "store sub-category", "category": "top-up package"}.get(kind, "product")
    # قالب خاص بالمنتج وآخر خاص بالقسم/القسم الفرعي، وإذا فاضي منستعمل القالب العام
    if kind in ("section", "subsection"):
        template = (get_setting("ai_image_prompt_section", "") or "").strip() or cfg["template"]
    else:
        template = (get_setting("ai_image_prompt_product", "") or "").strip() or cfg["template"]
    prompt = template.replace("{name}", name).replace("{kind}", kind_label)
    if (b.get("prompt") or "").strip():
        prompt = b["prompt"].strip().replace("{name}", name).replace("{kind}", kind_label)

    url = cfg["url"]
    if "{prompt}" in url:
        endpoint = url.replace("{prompt}", quote(prompt))
    elif url.rstrip().endswith("prompt="):
        endpoint = url.rstrip() + quote(prompt)
    else:
        endpoint = url + ("&" if "?" in url else "?") + "prompt=" + quote(prompt)
    if cfg["key"] and "key=" not in endpoint:
        endpoint += "&key=" + quote(cfg["key"])

    try:
        resp = _rq.get(endpoint, timeout=120)
        ctype = (resp.headers.get("content-type") or "").lower()
        if resp.status_code >= 400:
            return jsonify({"message": f"فشل التوليد ({resp.status_code})", "detail": resp.text[:300]}), 502
        if ctype.startswith("image/"):
            filename = f"ai_{uuid.uuid4().hex}.png"
            with open(os.path.join(UPLOAD_DIR, filename), "wb") as fh:
                fh.write(resp.content)
            return jsonify({"url": f"/uploads/{filename}", "prompt": prompt})
        data = resp.json()
        remote = data.get("url") or data.get("image_url") or data.get("image")
        if not remote and isinstance(data.get("data"), list) and data["data"]:
            first = data["data"][0]
            if isinstance(first, dict):
                remote = first.get("url") or first.get("image_url")
        if not remote:
            return jsonify({"message": "المزوّد لم يرجّع صورة", "detail": str(data)[:300]}), 502
        return jsonify({"url": _save_remote_image(remote), "prompt": prompt})
    except Exception as e:
        return jsonify({"message": f"تعذّر توليد الصورة: {e}"}), 502


@app.post("/api/admin/ai-image/apply")
@require_admin
def admin_ai_image_apply():
    """يثبّت الصورة المولّدة بعد تأكيد الأدمن على العنصر المطلوب."""
    b = request.get_json(force=True, silent=True) or {}
    kind, target_id, url = b.get("kind"), b.get("id"), b.get("url")
    if not url or not target_id:
        return jsonify({"message": "بيانات ناقصة"}), 400
    target_id = int(target_id)
    if kind == "product":
        lod.update_product_image(target_id, url)
    elif kind == "category":
        lod.update_category_image(target_id, url)
    elif kind == "section":
        lod.update_section_image(target_id, url)
    elif kind == "subsection":
        lod.update_subsection_image(target_id, url)
    else:
        return jsonify({"message": "نوع غير مدعوم"}), 400
    return jsonify({"message": "تم اعتماد الصورة ✅", "url": url})


# =============================================================
# تصدير قائمة منتجات المزوّد كاملة كملف
# =============================================================
@app.get("/api/admin/providers/<int:provider_id>/products/export")
@require_admin
def admin_provider_products_export(provider_id):
    import csv
    import io
    from flask import Response

    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT name, api_token, api_url FROM api_providers WHERE id = ?", (provider_id,))
        row = c.fetchone()
    if not row:
        return jsonify({"message": "المزوّد غير موجود"}), 404
    try:
        products = lod.get_all_api_products(api_token=row[1], api_base_url=row[2]) or []
    except Exception as e:
        return jsonify({"message": str(e)}), 502

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "name", "price", "category", "provider"])
    for p in products:
        if isinstance(p, dict):
            pid = p.get("id") or p.get("product_id") or ""
            pname = p.get("name") or p.get("product_name") or ""
            pprice = p.get("price") or p.get("cost") or p.get("rate") or p.get("amount") or 0
            pcat = p.get("category") or p.get("game") or p.get("group") or ""
        else:
            pid, pname, pprice, pcat = str(p), str(p), 0, ""
        writer.writerow([pid, pname, pprice, pcat, row[0]])

    csv_bytes = ("\ufeff" + buf.getvalue()).encode("utf-8")
    return Response(csv_bytes, mimetype="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="provider_{provider_id}_products.csv"'
    })


# =============================================================
# قبول/رفض الطلبات من لوحة الأدمن (حتى المرتبطة بمزوّد)
# =============================================================
def _order_tables(order_ref):
    return "api_orders" if str(order_ref).upper().startswith("A") else "shop_orders"


@app.post("/api/admin/orders/<order_ref>/status")
@require_admin
def admin_set_order_status(order_ref):
    """تجاوز يدوي للأدمن: قبول أو رفض أي طلب حتى لو مرتبط بمزوّد API (مع استرجاع الرصيد عند الرفض)."""
    b = request.get_json(force=True, silent=True) or {}
    action = (b.get("action") or "").lower()
    if action not in ("accept", "reject"):
        return jsonify({"message": "الإجراء غير صحيح"}), 400

    table = _order_tables(order_ref)
    try:
        order_id = int(str(order_ref).lstrip("SsAa"))
    except ValueError:
        return jsonify({"message": "رقم الطلب غير صحيح"}), 400

    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute(f"SELECT user_id, product_name, category_name, price, status FROM {table} WHERE id = ?", (order_id,))
        row = c.fetchone()
        if not row:
            return jsonify({"message": "الطلب غير موجود"}), 404
        uid, product_name, cat_name, price_syp, status = row
        if status in ("accepted", "rejected"):
            return jsonify({"message": "تمت معالجة هذا الطلب مسبقاً"}), 400
        new_status = "accepted" if action == "accept" else "rejected"
        c.execute(f"UPDATE {table} SET status = ? WHERE id = ?", (new_status, order_id))

    if action == "reject":
        lod.update_user_balance(uid, float(price_syp or 0))
        lod.add_notification(uid, "❌ تم رفض طلبك",
                              f"طلب «{product_name} - {cat_name}» تم رفضه وتم استرجاع {float(price_syp or 0):,.2f} ليرة لرصيدك",
                              "error")
    else:
        lod.add_notification(uid, "✅ تم تنفيذ طلبك",
                              f"طلب «{product_name} - {cat_name}» تم قبوله وتنفيذه بنجاح", "success")

    lod.notify_admin("🛠️ تحديث حالة طلب من لوحة الموقع",
                      f"الطلب: {order_ref}\nالحالة الجديدة: {new_status}\nالمستخدم: {uid}\n"
                      f"المنتج: {product_name} - {cat_name}")
    return jsonify({"message": "تم تحديث حالة الطلب"})


# =============================================================
# تقديم ملفات الموقع الثابتة (site/)
# =============================================================
@app.get("/")
def serve_index():
    return send_from_directory(app.static_folder, "store.html")


def _get_app_icon_url():
    """أيقونة PWA: تفضّل الأيقونة المخصصة، وإلا تستخدم اللوغو المرفوع أصلاً كحل احتياطي."""
    return get_setting("app_icon", "") or get_setting("logo_image", "") or ""


@app.get("/manifest.json")
def pwa_manifest():
    """
    ملف PWA Manifest — بيخلي "إضافة إلى الشاشة الرئيسية" تظهر بأيقونة واسم
    احترافيين (متل أي تطبيق حقيقي) بدل الأيقونة الافتراضية الفارغة من المتصفح.
    """
    icon_url = _get_app_icon_url()
    site_name = get_setting("site_name", "ARAB STORE")
    icons = []
    if icon_url:
        icons = [
            {"src": icon_url, "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": icon_url, "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ]
    return jsonify({
        "name": site_name,
        "short_name": site_name,
        "start_url": "/store.html",
        "display": "standalone",
        "background_color": "#0b0d14",
        "theme_color": "#e63946",
        "icons": icons,
    })


@app.get("/site-icon")
def site_icon():
    """يحوّل دايماً لآخر أيقونة رفعها الأدمن — هيك أي مكان بالموقع بيشير لـ /site-icon
    بيتحدّث تلقائياً بدون ما نغيّر رابط بكل صفحة."""
    icon_url = _get_app_icon_url()
    if not icon_url:
        return "", 404
    return redirect(icon_url)


@app.get("/favicon.ico")
def favicon_fallback():
    """بعض المتصفحات (خصوصاً بسجل التصفح/الاقتراحات) بتطلب /favicon.ico مباشرة
    بغض النظر عن وسم <link rel="icon">، فمنحوّلها لنفس الأيقونة كحل احتياطي."""
    icon_url = _get_app_icon_url()
    if not icon_url:
        return "", 404
    return redirect(icon_url)
    return redirect(icon_url)


@app.post("/api/admin/settings/app-icon")
@require_admin
def admin_set_app_icon():
    """رفع أيقونة التطبيق (يفضّل صورة مربعة 512x512 بصيغة PNG بخلفية شفافة أو صلبة)."""
    url = save_upload(request.files.get("file"))
    if not url:
        return jsonify({"message": "صيغة غير مدعومة"}), 400
    set_setting("app_icon", url)
    return jsonify({"message": "تم رفع أيقونة التطبيق", "url": url})


@app.delete("/api/admin/settings/app-icon")
@require_admin
def admin_remove_app_icon():
    set_setting("app_icon", "")
    return jsonify({"message": "تمت إزالة الأيقونة، رجعت للافتراضية"})


# =============================================================
# 7) النسخ الاحتياطي / الاسترجاع / حذف كل البيانات (للمالك فقط)
# =============================================================
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)


def _dump_db_to(path):
    src = sqlite3.connect(lod.DB_PATH, timeout=30)
    try:
        dst = sqlite3.connect(path)
        try:
            with dst:
                src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return path


def _create_backup_file():
    """نسخة كاملة: قاعدة البيانات + كل صور مجلد uploads داخل ملف zip واحد،
    حتى لا تختفي الصور عند الاسترجاع."""
    import zipfile
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    zip_path = os.path.join(BACKUP_DIR, f"backup-{ts}.zip")
    tmp_db = os.path.join(BACKUP_DIR, f".tmp-{uuid.uuid4().hex}.db")
    _dump_db_to(tmp_db)
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp_db, "database.db")
            if os.path.isdir(UPLOAD_DIR):
                for root, _dirs, files in os.walk(UPLOAD_DIR):
                    for fn in files:
                        full = os.path.join(root, fn)
                        rel = os.path.relpath(full, UPLOAD_DIR)
                        zf.write(full, os.path.join("uploads", rel))
    finally:
        try:
            os.remove(tmp_db)
        except Exception:
            pass
    return zip_path


@app.get("/api/admin/backups")
@require_admin
def admin_list_backups():
    items = []
    for name in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if not (name.endswith(".db") or name.endswith(".zip")):
            continue
        full = os.path.join(BACKUP_DIR, name)
        items.append({
            "name": name,
            "size_kb": round(os.path.getsize(full) / 1024, 1),
            "created_at": datetime.fromtimestamp(os.path.getmtime(full)).strftime("%Y-%m-%d %H:%M"),
            "download_url": "/admin/backups/" + name + "/download",
        })
    return jsonify({"backups": items})


@app.post("/api/admin/backups")
@require_owner
def admin_create_backup():
    try:
        path = _create_backup_file()
    except Exception as e:
        return jsonify({"message": f"تعذّر إنشاء النسخة: {e}"}), 500
    name = os.path.basename(path)
    return jsonify({"message": "تم إنشاء نسخة احتياطية ✅", "name": name,
                    "download_url": "/admin/backups/" + name + "/download"})


def _safe_backup_path(name):
    name = secure_filename(name or "")
    if not (name.endswith(".db") or name.endswith(".zip")):
        return None
    path = os.path.join(BACKUP_DIR, name)
    if not os.path.isfile(path):
        return None
    return path


@app.get("/api/admin/backups/<name>/download")
def admin_download_backup(name):
    """تحميل ملف نسخة احتياطية. التوكن بيجي كـ query (?token=) لأن التحميل بيصير
    عبر رابط مباشر مو عبر fetch بترويسة Authorization."""
    token = request.args.get("token", "")
    try:
        payload = admin_serializer.loads(token, max_age=60 * 60 * 12)
    except (BadSignature, SignatureExpired):
        return jsonify({"message": "دخول غير مصرح"}), 401
    if not payload.get("owner"):
        return jsonify({"message": "هذا الإجراء مسموح للمالك فقط"}), 403
    path = _safe_backup_path(name)
    if not path:
        return jsonify({"message": "الملف غير موجود"}), 404
    return send_from_directory(BACKUP_DIR, os.path.basename(path), as_attachment=True)


@app.delete("/api/admin/backups/<name>")
@require_owner
def admin_delete_backup(name):
    path = _safe_backup_path(name)
    if not path:
        return jsonify({"message": "الملف غير موجود"}), 404
    os.remove(path)
    return jsonify({"message": "تم حذف النسخة"})


def _restore_uploads_from_zip(zf):
    """يرجّع كل الصور لمجلد uploads حتى تظهر الصور بعد الاسترجاع بشكل طبيعي."""
    import zipfile
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    for member in zf.namelist():
        if not member.startswith("uploads/") or member.endswith("/"):
            continue
        rel = os.path.normpath(member[len("uploads/"):])
        if rel.startswith("..") or os.path.isabs(rel):
            continue  # حماية من مسارات خبيثة
        target = os.path.join(UPLOAD_DIR, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with zf.open(member) as srcf, open(target, "wb") as out:
            out.write(srcf.read())


def _restore_from_file(source_path):
    """يستبدل قاعدة البيانات الحالية بمحتوى ملف نسخة احتياطية (مع أخذ نسخة أمان قبلها).
    يدعم النسخ الجديدة (zip فيها قاعدة البيانات + الصور) والنسخ القديمة (.db فقط)."""
    import zipfile
    if zipfile.is_zipfile(source_path):
        tmp_db = os.path.join(BACKUP_DIR, f".restore-{uuid.uuid4().hex}.db")
        with zipfile.ZipFile(source_path) as zf:
            names = zf.namelist()
            db_member = "database.db" if "database.db" in names else next(
                (n for n in names if n.endswith(".db")), None)
            if not db_member:
                raise ValueError("النسخة لا تحتوي على قاعدة بيانات")
            with zf.open(db_member) as srcf, open(tmp_db, "wb") as out:
                out.write(srcf.read())
            _restore_uploads_from_zip(zf)
        try:
            _restore_from_file(tmp_db)
        finally:
            try:
                os.remove(tmp_db)
            except Exception:
                pass
        return
    check = sqlite3.connect(source_path)
    try:
        check.execute("SELECT count(*) FROM sqlite_master")
    finally:
        check.close()
    try:
        _create_backup_file()  # نسخة أمان قبل الاستبدال
    except Exception:
        pass
    src = sqlite3.connect(source_path)
    try:
        dst = sqlite3.connect(lod.DB_PATH, timeout=30)
        try:
            with dst:
                src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    # بعد الاسترجاع منتأكد إنو بنية الجداول كاملة (مرة وحدة) ومنعيد تحميل الإعدادات
    lod.reset_schema_marker()
    lod.init_db(force=True)
    init_web_tables()
    lod.mark_schema_current()


@app.post("/api/admin/restore")
@require_owner
def admin_restore_backup():
    name = (request.form.get("name") or "").strip()
    if name:
        path = _safe_backup_path(name)
        if not path:
            return jsonify({"message": "النسخة غير موجودة"}), 404
        try:
            _restore_from_file(path)
        except Exception as e:
            return jsonify({"message": f"فشل الاسترجاع: {e}"}), 400
        return jsonify({"message": "تم استرجاع النسخة الاحتياطية ✅"})

    up = request.files.get("file")
    if not up or not up.filename:
        return jsonify({"message": "ارفع ملف نسخة احتياطية (.zip أو .db)"}), 400
    ext = "zip" if up.filename.lower().endswith(".zip") else "db"
    tmp_path = os.path.join(BACKUP_DIR, f"upload-{uuid.uuid4().hex}.{ext}")
    up.save(tmp_path)
    try:
        _restore_from_file(tmp_path)
    except Exception as e:
        return jsonify({"message": f"الملف غير صالح: {e}"}), 400
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
    return jsonify({"message": "تم استرجاع النسخة الاحتياطية ✅"})


# الجداول التي تُمسح عند "حذف كل البيانات" (البنية بتضل موجودة)
WIPE_TABLES = [
    "shop_orders", "api_orders", "manual_orders", "deposit_requests", "transactions",
    "notifications", "link_codes", "referrals", "web_users", "users",
]
WIPE_TABLES_FULL = WIPE_TABLES + [
    "related_products", "categories", "products", "sections", "banner_images",
    "api_providers", "deposit_methods", "auto_deposit_methods", "discount_tiers",
    "web_admins", "required_channels",
]


@app.post("/api/admin/wipe-data")
@require_owner
def admin_wipe_data():
    """حذف كل البيانات من داخل الموقع. لازم تأكيد نصي صريح.
    scope = 'users' (المستخدمين والطلبات والمعاملات فقط) أو 'all' (كل شي)."""
    body = request.get_json(force=True, silent=True) or {}
    if (body.get("confirm") or "").strip() != "حذف":
        return jsonify({"message": "اكتب كلمة (حذف) للتأكيد"}), 400
    scope = body.get("scope") or "users"
    tables = WIPE_TABLES_FULL if scope == "all" else WIPE_TABLES

    backup_name = None
    try:
        backup_name = os.path.basename(_create_backup_file())  # نسخة أمان قبل الحذف
    except Exception:
        pass

    cleared, skipped = [], []
    with lod.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = {r[0] for r in c.fetchall()}
        for t in tables:
            if t not in existing:
                skipped.append(t)
                continue
            c.execute(f"DELETE FROM {t}")
            cleared.append(t)
        try:
            c.execute("DELETE FROM sqlite_sequence")
        except sqlite3.OperationalError:
            pass
        # نرجّع المشرف الرئيسي للبوت حتى ما يضيع الوصول
        c.execute("INSERT OR IGNORE INTO users (user_id, is_admin, balance) VALUES (?, 1, 0)",
                  (lod.MAIN_ADMIN_ID,))
    try:
        with lod.get_db() as conn:
            conn.execute("VACUUM")
    except Exception:
        pass
    lod._load_runtime_settings()
    return jsonify({
        "message": "تم حذف البيانات ✅" + (f" (نسخة أمان: {backup_name})" if backup_name else ""),
        "cleared": cleared, "skipped": skipped, "backup": backup_name,
    })


# =============================================================
# تشغيل بوت تيليجرام بالخلفية (مع الموقع بنفس العملية)
# =============================================================
_bot_thread = None
_bot_lock = threading.Lock()


def start_bot_thread():
    """يشغّل بوت تيليجرام بخيط خلفي مع الموقع.
    - ينطفي بوضع ARAB_ENABLE_BOT=0
    - أي خطأ بالبوت ما بيأثر إطلاقاً على الموقع (كله داخل try/except)
    - قفل ملف بسيط يمنع تشغيل أكتر من نسخة (تفادي خطأ 409 من تيليجرام)
    """
    global _bot_thread
    if os.environ.get("ARAB_ENABLE_BOT", "1") != "1":
        print("ℹ️  بوت تيليجرام معطّل (ARAB_ENABLE_BOT=0).")
        return
    with _bot_lock:
        if _bot_thread and _bot_thread.is_alive():
            return
        lock_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bot.lock")
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(fd, str(os.getpid()).encode())
        except FileExistsError:
            try:
                with open(lock_path) as f:
                    old_pid = int((f.read() or "0").strip() or 0)
                os.kill(old_pid, 0)  # النسخة القديمة لسا شغّالة
                print("ℹ️  نسخة أخرى من البوت شغّالة مسبقاً — تم تخطي تشغيله هنا.")
                return
            except Exception:
                try:
                    os.remove(lock_path)
                    fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                    os.write(fd, str(os.getpid()).encode())
                except Exception:
                    print("ℹ️  تعذّر أخذ قفل البوت — الموقع بيكمل شغل عادي.")
                    return
        except Exception:
            fd = None
        finally:
            try:
                if fd:
                    os.close(fd)
            except Exception:
                pass

        def runner():
            while True:
                try:
                    lod.main()
                except Exception as e:
                    print(f"⚠️  خطأ ببوت تيليجرام (الموقع ما بيتأثر): {e}")
                    time.sleep(10)
                else:
                    time.sleep(5)

        _bot_thread = threading.Thread(target=runner, daemon=True, name="telegram-bot")
        _bot_thread.start()
        print("🤖 بوت تيليجرام يعمل بالخلفية مع الموقع.")


@app.get("/api/admin/bot-status")
@require_admin
def admin_bot_status():
    return jsonify({
        "running": bool(_bot_thread and _bot_thread.is_alive()),
        "enabled_env": os.environ.get("ARAB_ENABLE_BOT", "1") == "1",
    })


# =============================================================
# تشغيل
# =============================================================
# =============================================================
# تهيئة قاعدة البيانات — لازم تصير بمستوى الموديول (مش جوا if __name__=="__main__")
# لأنو gunicorn (وأي WSGI server تاني) بيستورد app.py كموديول عادي، ما بيشغّله كسكربت مباشر،
# فأي كود جوا "if __name__=='__main__'" ما رح يشتغل إطلاقاً مع gunicorn — يعني كل تحديثات
# قاعدة البيانات (أعمدة جديدة، جداول جديدة...) ما كانت رح تنطبق أبداً بالنشر الحقيقي.
# =============================================================
# التهيئة بتصير مرة وحدة بس (أول تشغيل أو بعد تحديث إصدار البنية) — بعدها منتخطّاها.
_needs_web_init = not lod.schema_is_current()
lod.init_db()
if _needs_web_init:
    init_web_tables()
    lod.mark_schema_current()
    print("✅ تم تجهيز قاعدة البيانات (مرة وحدة).")
else:
    print("✅ قاعدة البيانات مهيّأة مسبقاً — تم تخطي التهيئة.")
start_order_monitor()
start_price_sync_monitor()
start_bot_thread()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("DEBUG") == "1"
    if not debug_mode:
        print("⚠️  تنبيه: عم تشغّل سيرفر Flask التطويري مباشرة (python app.py).")
        print("    هذا غير مناسب للإنتاج الحقيقي (بطيء، وما بيتحمّل أكتر من طلب بنفس اللحظة بأمان).")
        print("    للنشر الحقيقي، استخدم gunicorn بدلاً من هذا الأمر:")
        print("        gunicorn -w 1 --threads 4 -b 0.0.0.0:" + str(port) + " app:app")
        print("    (عامل واحد فقط لأن قاعدة البيانات SQLite وخيط المراقبة بالخلفية")
        print("     ما بيتحمّلوا أكتر من نسخة شغالة بنفس الوقت — استخدم --threads للتوازي بدل -w)")
        print("    (راجع ملف README.md لتفاصيل تشغيله كخدمة systemd دائمة)")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
