import requests
import json
import uuid
import time
import sqlite3
import traceback
import re
import threading
import os
import urllib3
from datetime import datetime
from contextlib import contextmanager

# إيقاف تحذيرات SSL (لدعم المزودين الذين لا يملكون شهادة صالحة)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# إعدادات البوت
BOT_TOKEN = "8786107427:AAG_qpVtGZsiLfcZK1NS8ZXOCey8ATMsPng"
MAIN_ADMIN_ID = 7839905310
ADMIN_CHAT_ID = -1003920958698

# متغيرات عامة
API_TOKEN = "ge32K9fUlESMQxtAt6Bb3Mu74utcJOB7mno3gd9IJ1o_cQzuWRknlWcBnAAZfd6E"
API_BASE_URL = "https://api.shams4store.com/"
user_states = {}
last_update_id = 0
pending_orders = {}
manual_order_msg_ids = {}  # order_db_id -> (target_user_id, pending_msg_id)
admins = set([MAIN_ADMIN_ID])
bot_enabled = True
# نفس القيمة المستخدمة بـ app.py لحساب معرّف حسابات الموقع المؤقتة (قبل ربطها بتيليجرام)
WEB_ID_OFFSET = 9_000_000_000_000
button_mode = 'reply'
support_username = "aboudy2312"

@contextmanager
def get_db():
    last_error = None
    conn = None
    for attempt in range(5):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=30000")
            break  # نجح الاتصال — منطلع من حلقة إعادة المحاولة ومنكمل تحت
        except sqlite3.OperationalError as e:
            last_error = e
            if conn:
                try:
                    conn.close()
                except:
                    pass
                conn = None
            if "locked" in str(e) and attempt < 4:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise
    else:
        raise last_error

    # ملاحظة مهمة: إعادة المحاولة (retry) تخص فقط خطوة الاتصال بالأعلى.
    # بعد ما نسلّم الاتصال للمستدعي (yield) ما منقدر نحاول نعيد التسليم مرة تانية بنفس
    # استدعاء المولّد (generator) — هاد ممنوع أساساً بقواعد @contextmanager ويسبب كراش
    # "generator didn't stop after throw()" لو صار خطأ "database is locked" أثناء الكتابة
    # الفعلية (مش أثناء الاتصال). لهيك من هون وطالع أي خطأ بيترجع فوراً للمستدعي بعد rollback.
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def load_api_settings():
    global API_TOKEN, API_BASE_URL
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = 'api_token'")
        result = c.fetchone()
        if result:
            API_TOKEN = result[0]
        else:
            c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('api_token', ?)", (API_TOKEN,))

        c.execute("SELECT value FROM settings WHERE key = 'api_base_url'")
        result = c.fetchone()
        if result:
            API_BASE_URL = result[0]
        else:
            c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('api_base_url', ?)", (API_BASE_URL,))

def set_api_token(token):
    global API_TOKEN
    API_TOKEN = token
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE settings SET value = ? WHERE key = 'api_token'", (token,))

def set_api_base_url(url):
    global API_BASE_URL
    API_BASE_URL = url
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE settings SET value = ? WHERE key = 'api_base_url'", (url,))

# ===== إصدار بنية قاعدة البيانات =====
# تهيئة/ترحيل الجداول بتصير مرة وحدة بس (أول تشغيل، أو بعد أي تحديث بيرفع هالرقم).
# بعدها كل إقلاع للسيرفر/البوت بيتخطّى كل أوامر CREATE/ALTER — أسرع وما بيلمس البيانات.
SCHEMA_VERSION = "2026-07-26.1"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "products.db")
_SCHEMA_MARKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".db_schema_version")


def schema_is_current():
    """هل بنية قاعدة البيانات مهيّأة مسبقاً بنفس الإصدار الحالي؟"""
    try:
        if not os.path.exists(DB_PATH):
            return False
        with open(_SCHEMA_MARKER, "r", encoding="utf-8") as f:
            return f.read().strip() == SCHEMA_VERSION
    except Exception:
        return False


def mark_schema_current():
    try:
        with open(_SCHEMA_MARKER, "w", encoding="utf-8") as f:
            f.write(SCHEMA_VERSION)
    except Exception:
        pass


def reset_schema_marker():
    """يُستعمل بعد استرجاع نسخة احتياطية — حتى تتأكد البنية مرة وحدة بعدها."""
    try:
        if os.path.exists(_SCHEMA_MARKER):
            os.remove(_SCHEMA_MARKER)
    except Exception:
        pass


def init_db(force=False):
    """ينشئ الجداول ويطبّق الترحيلات أول مرة فقط، وبيحمّل الإعدادات كل مرة.
    بيرجع True إذا فعلاً صار إنشاء/ترحيل هالمرة."""
    if not force and schema_is_current():
        _load_runtime_settings()
        return False
    _create_schema()
    _load_runtime_settings()
    mark_schema_current()
    return True


def _create_schema():
    global welcome_message
    with get_db() as conn:
        c = conn.cursor()

        c.execute('''CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            emoji TEXT DEFAULT '',
            description TEXT DEFAULT '',
            image TEXT DEFAULT ''
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            type TEXT DEFAULT 'default',
            min_qty INTEGER DEFAULT 1,
            max_qty INTEGER DEFAULT 1,
            unit_qty INTEGER DEFAULT 1,
            image TEXT DEFAULT ''
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            color TEXT DEFAULT 'success',
            emoji TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0
        )''')

        # الأقسام الفرعية: قسم رئيسي -> أقسام فرعية -> منتجات -> فئات/أسعار
        c.execute('''CREATE TABLE IF NOT EXISTS subsections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            emoji TEXT DEFAULT '',
            image TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS deposit_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            code TEXT NOT NULL,
            exchange_rate REAL NOT NULL,
            image TEXT DEFAULT ''
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS auto_deposit_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            code TEXT NOT NULL,
            exchange_rate REAL NOT NULL,
            api_token TEXT NOT NULL,
            api_url TEXT DEFAULT '',
            image TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            value TEXT
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            blocked INTEGER DEFAULT 0,
            discount_name TEXT DEFAULT '',
            discount_percent REAL DEFAULT 0,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT DEFAULT '',
            kind TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute("CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read)")

        c.execute('''CREATE TABLE IF NOT EXISTS deposit_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            full_name TEXT,
            method_title TEXT,
            amount_usd REAL,
            amount_syp REAL,
            transaction_code TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # جدول مزودي الـ API (يدعم حتى 10000 مزود)
        c.execute('''CREATE TABLE IF NOT EXISTS api_providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            api_token TEXT NOT NULL,
            api_url TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS linked_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            api_product_id INTEGER NOT NULL,
            product_name TEXT,
            category_name TEXT,
            api_name TEXT,
            api_price REAL,
            provider_id INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # جدول المنتجات المرتبطة للعرض (عرض المنتجات المرتبطة)
        c.execute('''CREATE TABLE IF NOT EXISTS related_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            provider_id INTEGER NOT NULL DEFAULT 0,
            api_product_id INTEGER NOT NULL,
            product_name TEXT,
            category_name TEXT,
            api_name TEXT,
            api_price REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS api_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            linked_id INTEGER NOT NULL,
            order_id TEXT,
            product_name TEXT,
            category_name TEXT,
            price REAL,
            player_id TEXT,
            qty INTEGER DEFAULT 1,
            api_response TEXT,
            status TEXT DEFAULT 'processing',
            provider_id INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS shop_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_name TEXT,
            category_name TEXT,
            price REAL,
            player_id TEXT,
            qty INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS user_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT,
            amount REAL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS category_description (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT UNIQUE,
            description TEXT DEFAULT ''
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS required_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_username TEXT UNIQUE NOT NULL
        )''')

        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('exchange_rate', '10000')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('bot_enabled', 'true')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('welcome_message', '⚡ أهلاً بك في بوت الشحن ⚡')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('api_token', 'a6ee3450a4b8f6a89bd8b1d2712f38b877ecd24c00608a9c')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('api_base_url', 'https://api.sahl-cash.com/')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('button_mode', 'reply')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('support_username', 'aboudy2312')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('referral_enabled', 'false')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('referral_amount', '1000')")
        c.execute("INSERT OR IGNORE INTO users (user_id, is_admin, balance) VALUES (?, 1, 0)", (MAIN_ADMIN_ID,))

        # جدول الإحالات
        c.execute('''CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL,
            reward_amount REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # جدول رتب الخصم (VIP1...VIPMAX) — النسب يحددها الأدمن بنفسه من لوحة التحكم
        c.execute('''CREATE TABLE IF NOT EXISTS discount_tiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            percent REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        # رتبة افتراضية "VIP1" بدون خصم (0%) — تمثل كل الزبائن بدون أي رتبة مخصّصة
        c.execute("SELECT COUNT(*) FROM discount_tiers")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO discount_tiers (name, percent, sort_order) VALUES ('VIP1', 0, 0)")

        # لا توجد أقسام افتراضية - يضيفها الأدمن من لوحة التحكم
        pass

    # ترقيات الأعمدة
    for migration in [
        "ALTER TABLE deposit_methods ADD COLUMN image TEXT DEFAULT ''",
        "ALTER TABLE categories ADD COLUMN image TEXT DEFAULT ''",
        "ALTER TABLE categories ADD COLUMN unit_qty INTEGER DEFAULT 1",
        "ALTER TABLE categories ADD COLUMN requires_id INTEGER DEFAULT 1",
        "ALTER TABLE linked_products ADD COLUMN provider_id INTEGER DEFAULT 0",
        "ALTER TABLE api_orders ADD COLUMN provider_id INTEGER DEFAULT 0",
        "ALTER TABLE sections ADD COLUMN image TEXT DEFAULT ''",
        "ALTER TABLE api_providers ADD COLUMN products_endpoint TEXT DEFAULT ''",
        "ALTER TABLE api_providers ADD COLUMN order_endpoint TEXT DEFAULT ''",
        "ALTER TABLE api_providers ADD COLUMN check_endpoint TEXT DEFAULT ''",
        "ALTER TABLE api_providers ADD COLUMN auth_header TEXT DEFAULT 'api-token'",
        "ALTER TABLE sections ADD COLUMN sort_order INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN subsection_id INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN sort_order INTEGER DEFAULT 0",
        "ALTER TABLE shop_orders ADD COLUMN cost_usd REAL DEFAULT 0",
        "ALTER TABLE shop_orders ADD COLUMN price_usd REAL DEFAULT 0",
        "ALTER TABLE shop_orders ADD COLUMN completed_at TIMESTAMP",
        "ALTER TABLE api_orders ADD COLUMN cost_usd REAL DEFAULT 0",
        "ALTER TABLE api_orders ADD COLUMN price_usd REAL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN discount_tier_id INTEGER DEFAULT 0",
        """CREATE TABLE IF NOT EXISTS subsections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            emoji TEXT DEFAULT '',
            image TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL,
            reward_amount REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
    ]:
        try:
            with get_db() as conn:
                conn.cursor().execute(migration)
        except:
            pass

    # حماية إضافية: منع تسجيل نفس المُحال (referred_id) أكثر من مرة (يمنع مكافأة إحالة مضاعفة
    # لو وصل طلبين متزامنين لنفس اللحظة بالضبط)
    try:
        with get_db() as conn:
            conn.cursor().execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_referrals_referred_once ON referrals(referred_id)")
    except sqlite3.IntegrityError:
        pass  # يوجد بيانات قديمة مكررة — يُفضّل تنظيفها يدوياً لاحقاً، لا نوقف تشغيل النظام لأجلها
    except Exception:
        pass

    # ترحيل إعدادات API الحالية إلى جدول المزودين إذا كانت موجودة
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM api_providers")
            count = c.fetchone()[0]
            if count == 0:
                c.execute("SELECT value FROM settings WHERE key = 'api_token'")
                r1 = c.fetchone()
                c.execute("SELECT value FROM settings WHERE key = 'api_base_url'")
                r2 = c.fetchone()
                if r1 and r2 and r1[0] and r2[0]:
                    c.execute("INSERT INTO api_providers (name, api_token, api_url) VALUES (?, ?, ?)",
                              ("المزود الافتراضي", r1[0], r2[0]))
    except:
        pass


def _load_runtime_settings():
    """يحمّل الإعدادات من قاعدة البيانات للذاكرة (بيشتغل كل إقلاع)."""
    load_api_settings()
    load_admins()
    load_bot_status()
    load_welcome_message()
    load_button_mode()
    load_support_username()

# ===== إدارة مزودي API =====

def add_api_provider(name, api_token, api_url):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO api_providers (name, api_token, api_url) VALUES (?, ?, ?)",
                  (name, api_token, api_url))
        return c.lastrowid

def get_all_api_providers():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, api_token, api_url FROM api_providers")
        return c.fetchall()

def get_api_provider_by_id(provider_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, api_token, api_url FROM api_providers WHERE id = ?", (provider_id,))
        return c.fetchone()

def delete_api_provider(provider_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM api_providers WHERE id = ?", (provider_id,))

def update_api_provider(provider_id, name, api_token, api_url):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE api_providers SET name=?, api_token=?, api_url=? WHERE id=?",
                  (name, api_token, api_url, provider_id))

# ===== المنتجات المرتبطة للعرض =====

def add_related_product(product_id, category_id, provider_id, api_product_id, api_name, api_price):
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO related_products
            (product_id, category_id, provider_id, api_product_id,
             product_name, category_name, api_name, api_price)
            VALUES (?,
                    ?,
                    ?,
                    ?,
                    (SELECT name FROM products WHERE id=?),
                    (SELECT name FROM categories WHERE id=?),
                    ?,
                    ?)''',
                  (product_id, category_id, provider_id, api_product_id,
                   product_id, category_id, api_name, api_price))
        return c.lastrowid

def get_related_products_by_category(category_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT rp.id, rp.provider_id, rp.api_product_id,
                            rp.api_name, rp.api_price,
                            ap.name as provider_name
                     FROM related_products rp
                     LEFT JOIN api_providers ap ON ap.id = rp.provider_id
                     WHERE rp.category_id = ?""", (category_id,))
        return c.fetchall()

def delete_related_product(related_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM related_products WHERE id = ?", (related_id,))

def get_all_related_products():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT rp.id, rp.product_name, rp.category_name,
                            rp.api_name, rp.api_price,
                            ap.name as provider_name
                     FROM related_products rp
                     LEFT JOIN api_providers ap ON ap.id = rp.provider_id
                     ORDER BY rp.product_name, rp.category_name""")
        return c.fetchall()

# ===== إعدادات عامة =====

def load_welcome_message():
    global welcome_message
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key = 'welcome_message'")
            result = c.fetchone()
            if result:
                welcome_message = result[0]
    except:
        pass

def set_welcome_message(msg):
    global welcome_message
    welcome_message = msg
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE settings SET value = ? WHERE key = 'welcome_message'", (msg,))

def load_button_mode():
    global button_mode
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key = 'button_mode'")
            result = c.fetchone()
            if result:
                button_mode = result[0]
    except:
        pass

def set_button_mode(mode):
    global button_mode
    button_mode = mode
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE settings SET value = ? WHERE key = 'button_mode'", (mode,))

def load_support_username():
    global support_username
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key = 'support_username'")
            result = c.fetchone()
            if result:
                support_username = result[0]
    except:
        pass

def set_support_username(username):
    global support_username
    username = username.lstrip('@').strip()
    support_username = username
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE settings SET value = ? WHERE key = 'support_username'", (username,))

def get_support_username():
    return support_username

# ===== نظام الإحالة =====

def get_referral_settings():
    """يجلب إعدادات الإحالة: هل مفعلة ومبلغ المكافأة"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = 'referral_enabled'")
        r1 = c.fetchone()
        c.execute("SELECT value FROM settings WHERE key = 'referral_amount'")
        r2 = c.fetchone()
        enabled = (r1[0].lower() == 'true') if r1 else False
        amount = float(r2[0]) if r2 else 1000.0
    return enabled, amount

def set_referral_enabled(enabled):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE settings SET value = ? WHERE key = 'referral_enabled'", ('true' if enabled else 'false',))

def set_referral_amount(amount):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE settings SET value = ? WHERE key = 'referral_amount'", (str(amount),))

def process_referral(referrer_id, referred_id):
    """يعالج الإحالة: يتحقق أنها لم تُسجَّل قبلاً ويضيف الرصيد"""
    try:
        ref_enabled, ref_amount = get_referral_settings()
        if not ref_enabled:
            return False
        if referrer_id == referred_id:
            return False
        with get_db() as conn:
            c = conn.cursor()
            # تحقق من أنه لم يتم تسجيل هذه الإحالة من قبل
            c.execute("SELECT id FROM referrals WHERE referred_id = ?", (referred_id,))
            if c.fetchone():
                return False
            # سجّل الإحالة
            c.execute("INSERT INTO referrals (referrer_id, referred_id, reward_amount) VALUES (?, ?, ?)",
                      (referrer_id, referred_id, ref_amount))
            # أضف الرصيد للمحيل
            c.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (referrer_id,))
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (ref_amount, referrer_id))
            c.execute("INSERT INTO user_transactions (user_id, type, amount, description) VALUES (?, 'referral', ?, ?)",
                      (referrer_id, ref_amount, f'مكافأة إحالة مستخدم {referred_id}'))
        return True
    except Exception as e:
        print(f"[process_referral] error: {e}")
        return False

def get_referral_count(user_id):
    """يجلب عدد الإحالات الناجحة لمستخدم"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
        return c.fetchone()[0]

def load_bot_status():
    global bot_enabled
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key = 'bot_enabled'")
            result = c.fetchone()
            if result:
                bot_enabled = result[0].lower() == 'true'
    except:
        pass

def set_bot_status(enabled):
    global bot_enabled
    bot_enabled = enabled
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE settings SET value = ? WHERE key = 'bot_enabled'", ('true' if enabled else 'false',))

def load_admins():
    global admins
    admins = set([MAIN_ADMIN_ID])
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT user_id FROM users WHERE is_admin = 1")
            for row in c.fetchall():
                admins.add(row[0])
    except:
        pass

def is_admin(user_id):
    return user_id in admins or user_id == MAIN_ADMIN_ID

def add_admin(user_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
        if c.rowcount == 0:
            c.execute("INSERT INTO users (user_id, is_admin, balance) VALUES (?, 1, 0)", (user_id,))
    load_admins()

def remove_admin(user_id):
    if user_id == MAIN_ADMIN_ID:
        return False
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (user_id,))
    load_admins()
    return True

def add_user_balance(user_id, amount):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        c.execute("INSERT INTO user_transactions (user_id, type, amount, description) VALUES (?, 'add', ?, 'تمت الإضافة بواسطة الأدمن')", (user_id, amount))

def deduct_user_balance(user_id, amount):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
        c.execute("UPDATE users SET balance = MAX(0, balance - ?) WHERE user_id = ?", (amount, user_id))
        c.execute("INSERT INTO user_transactions (user_id, type, amount, description) VALUES (?, 'deduct', ?, 'تم الخصم بواسطة الأدمن')", (user_id, amount))

def get_user_stats(user_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COALESCE(SUM(price), 0) FROM shop_orders WHERE user_id = ? AND status = 'accepted'", (user_id,))
        total_shop = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(amount_syp), 0) FROM deposit_requests WHERE user_id = ? AND status = 'accepted'", (user_id,))
        total_deposit = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM shop_orders WHERE user_id = ?", (user_id,))
        total_orders = c.fetchone()[0]
        c.execute("SELECT amount_syp, method_title, created_at FROM deposit_requests WHERE user_id = ? AND status = 'accepted' ORDER BY created_at DESC LIMIT 3", (user_id,))
        last_deposits = c.fetchall()
        c.execute("SELECT product_name, category_name, price, created_at FROM shop_orders WHERE user_id = ? AND status = 'accepted' ORDER BY created_at DESC LIMIT 3", (user_id,))
        last_products = c.fetchall()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance_row = c.fetchone()
        balance = balance_row[0] if balance_row else 0
        c.execute("SELECT discount_name, discount_percent FROM users WHERE user_id = ?", (user_id,))
        discount_row = c.fetchone()
        discount_name = discount_row[0] if discount_row and discount_row[0] else ""
        discount_percent = discount_row[1] if discount_row else 0
    return {
        "total_shop": total_shop,
        "total_deposit": total_deposit,
        "total_orders": total_orders,
        "last_deposits": last_deposits,
        "last_products": last_products,
        "balance": balance,
        "discount_name": discount_name,
        "discount_percent": discount_percent
    }

def block_user(user_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (user_id, blocked) VALUES (?, 0)", (user_id,))
        c.execute("UPDATE users SET blocked = 1 WHERE user_id = ?", (user_id,))

def unblock_user(user_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET blocked = 0 WHERE user_id = ?", (user_id,))

def is_blocked(user_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT blocked FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        return result and result[0] == 1

def get_exchange_rate():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = 'exchange_rate'")
        result = c.fetchone()
        if result:
            return float(result[0])
    return 10000.0

def set_exchange_rate(rate):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE settings SET value = ? WHERE key = 'exchange_rate'", (str(rate),))

def get_user_balance(user_id):
    if is_blocked(user_id):
        return 0
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        if result:
            return result[0]
    return 0.0

def update_user_balance(user_id, amount):
    """يحدّث الرصيد بأمر SQL واحد ذرّي (atomic) — يمنع ضياع التحديثات (lost update)
    لما يوصل طلبين لنفس المستخدم بنفس اللحظة تقريباً (تزامن/concurrency).
    يرجّع الرصيد الجديد. لا يسمح للرصيد إنه ينزل تحت الصفر."""
    if is_blocked(user_id):
        return get_user_balance(user_id)
    with get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
        c.execute("UPDATE users SET balance = MAX(0, balance + ?) WHERE user_id = ?", (amount, user_id))
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
    return row[0] if row else 0.0


def try_decrement_stock(category_id, qty):
    """خصم كمية من مخزون الفئة بأمر SQL ذرّي واحد (نفس أسلوب try_deduct_balance) —
    ينجح فقط إذا كانت الكمية متوفرة فعلياً وقت التنفيذ، يمنع بيع نفس القطعة مرتين
    لو وصل طلبين بنفس اللحظة. NULL = مخزون غير محدود (دايماً بينجح)."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_qty FROM categories WHERE id = ?", (category_id,))
        row = c.fetchone()
        if not row or row[0] is None:
            return True  # مخزون غير محدود، ما في داعي لخصم
        c.execute("UPDATE categories SET stock_qty = stock_qty - ? WHERE id = ? AND stock_qty >= ?",
                   (qty, category_id, qty))
        return c.rowcount > 0


def restore_stock(category_id, qty):
    """استرجاع كمية للمخزون (عند فشل/رفض الطلب بعد ما كان انخصم)."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_qty FROM categories WHERE id = ?", (category_id,))
        row = c.fetchone()
        if row and row[0] is not None:
            c.execute("UPDATE categories SET stock_qty = stock_qty + ? WHERE id = ?", (qty, category_id))


def try_deduct_balance(user_id, amount):
    """خصم آمن من التزامن: الفحص والخصم يصيرو بنفس أمر SQL (WHERE balance >= amount)،
    فما فيه احتمال إنو طلبين متزامنين ياخدو نفس اللحظة إنو الرصيد كافي وينخصم مرتين.
    يرجّع (نجح: bool, الرصيد الحالي بعد المحاولة: float)."""
    if is_blocked(user_id):
        return False, 0.0
    with get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
        c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
                   (amount, user_id, amount))
        success = c.rowcount > 0
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
    return success, (row[0] if row else 0.0)

# ===== [إضافة جديدة - نظام إشعارات موحّد للموقع والبوت] =====
def add_notification(user_id, title, message="", kind="info"):
    """يسجّل إشعار لمستخدم معيّن (تُقرأ لاحقاً من صفحة الموقع عبر جرس الإشعارات)،
    وإذا كان حساب المستخدم مربوط فعلياً ببوت تيليجرام (user_id حقيقي، مش معرّف موقع مؤقت)
    يبعتلو نفس الإشعار كرسالة تيليجرام مباشرة كمان — بدون أي تعديل إضافي بأماكن الاستدعاء."""
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO notifications (user_id, title, message, kind) VALUES (?, ?, ?, ?)",
                      (user_id, title, message, kind))
    except Exception as e:
        print(f"add_notification error: {e}")

    # user_id أصغر من WEB_ID_OFFSET يعني حساب تيليجرام حقيقي مربوط فعلياً (وليس معرّف موقع مؤقت)
    if user_id and user_id < WEB_ID_OFFSET:
        try:
            text = f"{title}\n\n{message}" if message else title
            send_message(user_id, text)
        except Exception as e:
            print(f"add_notification telegram forward error: {e}")

def broadcast_notification(title, message="", kind="info"):
    """يسجّل الإشعار لكل الحسابات، ويرسله أيضاً للحسابات المرتبطة بتيليجرام."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE blocked = 0")
        user_ids = [row[0] for row in c.fetchall()]
    for target_user_id in user_ids:
        add_notification(target_user_id, title, message, kind)

_admin_notify_targets_cache = None
_admin_notify_targets_at = 0.0


def get_setting_value(key, default=""):
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = c.fetchone()
            return row[0] if row and row[0] is not None else default
    except Exception:
        return default


def reload_admin_notify_targets():
    global _admin_notify_targets_cache
    _admin_notify_targets_cache = None


def get_admin_notify_targets():
    """كل الوجهات التي يجب أن تصلها إشعارات الأدمن على تيليجرام:
    مجموعة الإدارة + المالك + أي أدمن مسجّل + أي آيدي إضافي من إعدادات الموقع."""
    global _admin_notify_targets_cache, _admin_notify_targets_at
    if _admin_notify_targets_cache is not None and (time.time() - _admin_notify_targets_at) < 60:
        return _admin_notify_targets_cache
    targets = []
    def _add(v):
        try:
            v = int(str(v).strip())
        except Exception:
            return
        if v and v not in targets:
            targets.append(v)
    _add(ADMIN_CHAT_ID)
    _add(MAIN_ADMIN_ID)
    for extra in re.split(r"[,\s]+", get_setting_value("admin_notify_chat_ids", "") or ""):
        _add(extra)
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT user_id FROM users WHERE is_admin = 1")
            for (uid,) in c.fetchall():
                _add(uid)
    except Exception:
        pass
    _admin_notify_targets_cache = targets
    _admin_notify_targets_at = time.time()
    return targets


def notify_admin(title, message="", kind="info"):
    """يرسل إشعاراً على تيليجرام لكل جهات الإدارة (مجموعة الإدارة + المالك + الأدمنية)."""
    text = f"<b>{title}</b>\n\n{message}" if message else f"<b>{title}</b>"
    delivered = False
    for chat_id in get_admin_notify_targets():
        try:
            res = send_message(chat_id, text)
            if res and res.get("ok"):
                delivered = True
            else:
                print(f"notify_admin failed for {chat_id}: {res}")
        except Exception as e:
            print(f"notify_admin error ({chat_id}): {e}")
    return delivered

def category_requires_id(category_id):
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT requires_id FROM categories WHERE id = ?", (category_id,))
            row = c.fetchone()
            if not row or row[0] is None:
                return True
            return bool(int(row[0]))
    except Exception:
        return True

def get_notifications(user_id, limit=30):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, title, message, kind, is_read, created_at FROM notifications
                     WHERE user_id = ? ORDER BY created_at DESC LIMIT ?""", (user_id, limit))
        return c.fetchall()

def count_unread_notifications(user_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,))
        return c.fetchone()[0]

def mark_notifications_read(user_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (user_id,))


def add_deposit_request(user_id, username, full_name, method_title, amount_usd, amount_syp, transaction_code):
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO deposit_requests
            (user_id, username, full_name, method_title, amount_usd, amount_syp, transaction_code, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')''',
                  (user_id, username, full_name, method_title, amount_usd, amount_syp, transaction_code))
        return c.lastrowid

def accept_deposit_request(request_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, amount_syp FROM deposit_requests WHERE id = ? AND status = 'pending'", (request_id,))
        result = c.fetchone()
        if result:
            user_id, amount_syp = result
            c.execute("UPDATE deposit_requests SET status = 'accepted' WHERE id = ?", (request_id,))
            # نضمن وجود صف المستخدم أولاً، لأن UPDATE وحده لا يعمل شيئاً إن لم يكن الصف موجوداً
            # (هذا يحمي من ضياع مبلغ الإيداع بصمت في حال لم يُنشأ صف المستخدم مسبقاً)
            c.execute("INSERT OR IGNORE INTO users (user_id, balance, is_admin, blocked) VALUES (?, 0, 0, 0)", (user_id,))
            # تحديث ذرّي (atomic) — لا نقرأ الرصيد ونعيد كتابته يدوياً، حتى لا يضيع خصم متزامن
            # (مثلاً المستخدم يشتري بنفس لحظة قبول الإيداع) بسبب الكتابة فوق قيمة قديمة.
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount_syp, user_id))
            c.execute("INSERT INTO user_transactions (user_id, type, amount, description) VALUES (?, 'deposit', ?, 'تم ايداع عن طريق البوت')", (user_id, amount_syp))
        else:
            user_id, amount_syp = None, None
    # الإشعار بعد إغلاق الاتصال (commit) — منعاً لتزاحم اتصال جديد وسط معاملة لسا مفتوحة
    if user_id:
        add_notification(user_id, "✅ تم قبول الإيداع", f"تمت إضافة {amount_syp:,.0f} ل.س لرصيدك", "success")
        return True, user_id, amount_syp
    return False, None, None

def reject_deposit_request(request_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM deposit_requests WHERE id = ?", (request_id,))
        row = c.fetchone()
        c.execute("UPDATE deposit_requests SET status = 'rejected' WHERE id = ?", (request_id,))
    if row:
        add_notification(row[0], "❌ تم رفض الإيداع", "تعذّر تأكيد عملية الإيداع، تواصل مع الدعم لمزيد من التفاصيل", "danger")

# ===== [إضافة جديدة - ربط حساب الموقع ببوت تيليجرام] =====
# هاي الدالة وحدها مضافة لدعم موقع ARAB STORE، ما عدّلنا أي دالة قديمة.
# بتتأكد من كود الربط بجدول link_codes (يصنعه سيرفر الموقع)، وبتدمج
# رصيد/طلبات/إيداعات حساب الموقع المؤقت مع حساب تيليجرام الحقيقي.
def web_link_telegram_account(code, telegram_user_id, username, full_name):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT web_user_id FROM link_codes WHERE code = ? AND expires_at > datetime('now')", (code,))
        row = c.fetchone()
        if not row:
            return False, "كود الربط غير صحيح أو منتهي الصلاحية"
        web_id = row[0]  # هذا هو web_users.id الحقيقي (المفتاح الأساسي بجدول حسابات الموقع)
        site_user_id = WEB_ID_OFFSET + web_id  # المعرّف المؤقت المستخدم بجدول users قبل الربط (نفس معادلة app.py)

        # تأكيد وجود صف للمستخدم التليجرامي الحقيقي (وتسجيله إذا لم يكن موجوداً)
        c.execute("INSERT OR IGNORE INTO users (user_id, balance, is_admin, blocked) VALUES (?, 0, 0, 0)", (telegram_user_id,))

        # دمج الرصيد من حساب الموقع المؤقت (إن وجد) إلى الحساب الحقيقي
        c.execute("SELECT balance, discount_tier_id, discount_name, discount_percent FROM users WHERE user_id = ?", (site_user_id,))
        site_row = c.fetchone()
        site_balance = site_row[0] if site_row else 0
        site_tier_id = site_row[1] if site_row else 0
        site_discount_name = site_row[2] if site_row else ""
        site_discount_percent = site_row[3] if site_row else 0
        if site_balance:
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (site_balance, telegram_user_id))
        # نقل الرتبة والخصم إذا كان حساب الموقع عنده رتبة مخصّصة
        if site_tier_id:
            c.execute("UPDATE users SET discount_tier_id = ?, discount_name = ?, discount_percent = ? WHERE user_id = ?",
                       (site_tier_id, site_discount_name, site_discount_percent, telegram_user_id))

        # نقل سجل الطلبات والإيداعات والمعاملات لحساب تيليجرام الحقيقي
        for table in ("shop_orders", "deposit_requests", "user_transactions", "api_orders"):
            try:
                c.execute(f"UPDATE {table} SET user_id = ? WHERE user_id = ?", (telegram_user_id, site_user_id))
            except sqlite3.OperationalError:
                pass  # الجدول غير موجود بهذا الاسم بهذا الإصدار - تجاهل بأمان

        # حذف حساب الموقع المؤقت بعد الدمج
        c.execute("DELETE FROM users WHERE user_id = ?", (site_user_id,))
        c.execute("DELETE FROM link_codes WHERE code = ?", (code,))

        # الإصلاح الأهم: كان هذا السطر يقارن web_users.id الخام بعمود site_user_id
        # (الذي يخزّن WEB_ID_OFFSET + id، رقم مختلف تماماً)، فما كان يطابق أي صف أبداً —
        # ولهيك telegram_user_id ما كان ينحفظ إطلاقاً رغم نجاح الربط ظاهرياً.
        c.execute("UPDATE web_users SET telegram_user_id = ? WHERE id = ?",
                   (telegram_user_id, web_id))

        return True, telegram_user_id

def import_provider_catalog(provider_id, margin_percent):
    """
    [إضافة جديدة] استيراد تلقائي لكل كتالوج مزوّد API دفعة وحدة: يخلق قسم فرعي
    خاص بالاستيراد + منتج لكل مجموعة (لو المزوّد بيرجّع حقل تصنيف) + فئة لكل
    عنصر، ويربطها فوراً بالمزوّد، ويطبّق هامش الربح المحدد على السعر النهائي
    (سعر البيع = تكلفة المزوّد × (1 + الهامش%))، ويسجّل الهامش عالفئة حتى تنعاد
    مزامنتها يومياً متل باقي نظام التسعير الذكي.
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, api_token, api_url FROM api_providers WHERE id = ?", (provider_id,))
        prov = c.fetchone()
    if not prov:
        return None, "المزوّد غير موجود"
    _, provider_name, api_token, api_url = prov

    raw_items = get_all_api_products(api_token=api_token, api_base_url=api_url)
    if not raw_items:
        return None, "تعذّر جلب كتالوج المزوّد أو هو فارغ"

    # قسم رئيسي مخصص للاستيراد التلقائي (يُعاد استخدامه لو استوردت من نفس المزوّد مرة تانية بدل ما يتكرر)
    section_name = f"مستوردة - {provider_name}"
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM sections WHERE name = ?", (section_name,))
        row = c.fetchone()
        if row:
            section_id = row[0]
        else:
            c.execute("INSERT INTO sections (name, color, emoji) VALUES (?, 'success', '📦')", (section_name,))
            section_id = c.lastrowid

        c.execute("SELECT id FROM subsections WHERE section_id = ? AND name = ?", (section_id, "الكل"))
        row = c.fetchone()
        if row:
            subsection_id = row[0]
        else:
            c.execute("INSERT INTO subsections (section_id, name) VALUES (?, 'الكل')", (section_id,))
            subsection_id = c.lastrowid

    # تجميع العناصر حسب أي حقل تصنيف متوفر عند المزوّد (لو ما في، الكل تحت منتج واحد باسم المزوّد)
    GROUP_FIELDS = ("category", "category_name", "game", "game_name", "group", "group_name", "type", "service", "service_name")
    groups = {}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        group_name = None
        for f in GROUP_FIELDS:
            v = item.get(f)
            if v and isinstance(v, str) and v.strip():
                group_name = v.strip()
                break
        group_name = group_name or provider_name
        groups.setdefault(group_name, []).append(item)

    with get_db() as conn:
        c = conn.cursor()
        # الفئات المربوطة أصلاً بنفس المزوّد (لتفادي تكرار الاستيراد لو الزر انضغط أكتر من مرة)
        c.execute("SELECT api_product_id FROM linked_products WHERE provider_id = ?", (provider_id,))
        already_linked = {str(r[0]) for r in c.fetchall()}

    products_created = 0
    categories_created = 0
    categories_skipped = 0

    # اتصال واحد مشترك لكل عملية الاستيراد (بدل فتح اتصال جديد لكل عنصر — أسرع بكتير لكتالوجات كبيرة)
    with get_db() as conn:
        c = conn.cursor()
        for group_name, items in groups.items():
            c.execute("SELECT id FROM products WHERE name = ? AND subsection_id = ?", (group_name, subsection_id))
            row = c.fetchone()
            if row:
                product_id = row[0]
            else:
                c.execute("INSERT INTO products (name, category, emoji, description, image, subsection_id, sort_order) VALUES (?, ?, '', '', '', ?, 0)",
                          (group_name, group_name, subsection_id))
                product_id = c.lastrowid
                products_created += 1

            for item in items:
                api_product_id = str(item.get("id") or item.get("product_id") or "")
                if not api_product_id or api_product_id in already_linked:
                    categories_skipped += 1
                    continue
                name = item.get("name") or item.get("product_name") or api_product_id
                cost_usd = item.get("price") or item.get("cost") or item.get("rate") or item.get("amount") or 0
                try:
                    cost_usd = float(cost_usd)
                except (TypeError, ValueError):
                    cost_usd = 0
                if cost_usd <= 0:
                    categories_skipped += 1
                    continue

                sell_price = round(cost_usd * (1 + margin_percent / 100), 4)
                c.execute("INSERT INTO categories (product_id, name, price, type, min_qty, max_qty, margin_percent) VALUES (?, ?, ?, 'api', 1, 1, ?)",
                          (product_id, name, sell_price, margin_percent))
                category_id = c.lastrowid
                c.execute("DELETE FROM linked_products WHERE category_id = ?", (category_id,))
                c.execute('''INSERT INTO linked_products
                    (product_id, category_id, api_product_id, product_name, category_name, api_name, api_price, provider_id)
                    VALUES (?,?,?,?,?,?,?,?)''',
                    (product_id, category_id, api_product_id, group_name, name, name, cost_usd, provider_id))
                already_linked.add(api_product_id)
                categories_created += 1

    if products_created or categories_created:
        broadcast_notification(
            "🆕 تحديث كتالوج المتجر",
            f"تمت إضافة {products_created} منتج و{categories_created} فئة جديدة من {provider_name}",
            "info",
        )

    return {
        "section_id": section_id, "section_name": section_name,
        "products_created": products_created, "categories_created": categories_created,
        "categories_skipped": categories_skipped,
    }, None


def link_product(product_id, category_id, api_product_id, api_name, api_price, provider_id=0):
    with get_db() as conn:
        c = conn.cursor()
        # احذف أي ربط قديم لنفس الفئة حتى لا يبقى صف قديم بدون مزود
        c.execute("DELETE FROM linked_products WHERE category_id = ?", (category_id,))
        c.execute('''INSERT INTO linked_products
            (product_id, category_id, api_product_id, product_name, category_name, api_name, api_price, provider_id)
            VALUES (?,?,?,
                    (SELECT name FROM products WHERE id=?),
                    (SELECT name FROM categories WHERE id=?),
                    ?,?,?)''',
                  (product_id, category_id, api_product_id, product_id, category_id, api_name, api_price, provider_id))
        return c.lastrowid

def unlink_product(linked_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM linked_products WHERE id = ?", (linked_id,))

def get_linked_products():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT lp.id, lp.product_id, lp.category_id, lp.api_product_id,
                            lp.product_name, lp.category_name, lp.api_name, lp.api_price,
                            lp.created_at, lp.provider_id,
                            COALESCE(ap.name, 'مزود غير محدد') as provider_name
                     FROM linked_products lp
                     LEFT JOIN api_providers ap ON ap.id = lp.provider_id""")
        return c.fetchall()

def get_linked_by_category(category_id):
    with get_db() as conn:
        c = conn.cursor()
        # ORDER BY id DESC لضمان استخدام آخر ربط (الأحدث) وليس صف قديم بدون مزود
        c.execute("""SELECT lp.*, COALESCE(ap.api_token, '') as p_token,
                            COALESCE(ap.api_url, '') as p_url
                     FROM linked_products lp
                     LEFT JOIN api_providers ap ON ap.id = lp.provider_id
                     WHERE lp.category_id = ?
                     ORDER BY lp.id DESC LIMIT 1""", (category_id,))
        return c.fetchone()

def save_api_order(user_id, linked_id, order_id, product_name, category_name, price, player_id, qty, api_response, provider_id=0, cost_usd=0, price_usd=0):
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO api_orders
            (user_id, linked_id, order_id, product_name, category_name, price, player_id, qty, api_response, status, provider_id, cost_usd, price_usd)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'processing', ?, ?, ?)''',
                  (user_id, linked_id, order_id, product_name, category_name, price, player_id, qty, api_response, provider_id, cost_usd, price_usd))
        return c.lastrowid

def update_api_order_status(order_db_id, status, api_response=None):
    with get_db() as conn:
        c = conn.cursor()
        utc_now = datetime.utcnow()
        if api_response:
            c.execute("UPDATE api_orders SET status = ?, api_response = ?, completed_at = ? WHERE id = ?",
                      (status, api_response, utc_now, order_db_id))
        else:
            c.execute("UPDATE api_orders SET status = ?, completed_at = ? WHERE id = ?",
                      (status, utc_now, order_db_id))
    if status in ("completed", "failed"):
        try:
            with get_db() as conn:
                c = conn.cursor()
                c.execute("SELECT user_id, product_name FROM api_orders WHERE id = ?", (order_db_id,))
                row = c.fetchone()
            if row:
                uid, pname = row
                if status == "completed":
                    add_notification(uid, "✅ تم شحن طلبك", f"تم تنفيذ طلب «{pname}» بنجاح", "success")
                else:
                    add_notification(uid, "❌ فشل تنفيذ الطلب", f"تعذّر تنفيذ طلب «{pname}»، تواصل مع الدعم", "danger")
        except Exception as e:
            print(f"notify update_api_order_status error: {e}")

def get_api_order_by_id(order_db_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM api_orders WHERE id = ?", (order_db_id,))
        return c.fetchone()

def extract_replay_text(order_data):
    """
    يستخرج نص الملاحظات/الرد من order_data بشكل موحّد.
    يدعم: replay_api, notes, note, message, description, comment
    """
    for field in ["replay_api", "notes", "note", "message", "description", "comment"]:
        val = order_data.get(field)
        if val and str(val).strip() not in ["null", "None", ""]:
            return str(val).strip()
    return ""


def check_order_status(order_id, api_token=None, api_base_url=None):
    """
    التحقق من حالة الطلب - يدعم أي مزود في العالم.
    يجرب عدة endpoints ويفهم أي هيكل رد.
    """
    SUCCESS_KEYWORDS = ["تم", "شحن", "نجاح", "مكتمل", "تنفيذ",
                        "completed", "success", "done", "ok", "تم بنجاح"]
    FAIL_KEYWORDS    = ["مرفوض", "فشل", "الغاء", "خطأ", "غير صحيح",
                        "reject", "fail", "error", "cancel", "invalid", "wrong"]

    def parse_order_dict(order_data):
        if not isinstance(order_data, dict):
            return None
        current_status = str(order_data.get("status", "")).lower()
        replay_text    = extract_replay_text(order_data)
        replay_lower   = replay_text.lower()

        if replay_text:
            if any(kw in replay_lower for kw in SUCCESS_KEYWORDS):
                order_data["status"] = "completed"
                order_data["_replay_text"] = replay_text
                return order_data
            if any(kw in replay_lower for kw in FAIL_KEYWORDS):
                order_data["status"] = "failed"
                order_data["_replay_text"] = replay_text
                return order_data

        if current_status in ["wait", "pending", "processing", "in_progress",
                               "queued", "waiting", "inprogress", "in progress",
                               "running", "started"]:
            return "wait"
        elif current_status in ["completed", "complete", "ok", "success", "done",
                                 "accept", "accepted", "finish", "finished",
                                 "delivered", "active", "charged", "true", "1"]:
            order_data["status"] = "completed"
            order_data["_replay_text"] = replay_text
            return order_data
        elif current_status in ["reject", "rejected", "canceled", "cancelled",
                                 "fail", "failed", "error", "refunded", "refund",
                                 "invalid", "wrong", "false", "0"]:
            order_data["status"] = "failed"
            order_data["_replay_text"] = replay_text
            return order_data
        else:
            order_data["_replay_text"] = replay_text
            return order_data

    def try_parse_result(result):
        """يحاول تحليل الرد بأي هيكل"""
        if result is None or not isinstance(result, dict):
            return None
        if result.get("error") is True:
            return None

        # حالة 1: {"status":"OK","data":{...} أو [...]}
        if result.get("status") == "OK" and "data" in result:
            order_data = result["data"]
            if isinstance(order_data, list) and order_data:
                order_data = order_data[0]
            parsed = parse_order_dict(order_data)
            if parsed is not None:
                return parsed

        # حالة 2: {"data":{...}} بدون "OK"
        if "data" in result:
            order_data = result["data"]
            if isinstance(order_data, list) and order_data:
                order_data = order_data[0]
            parsed = parse_order_dict(order_data)
            if parsed is not None:
                return parsed

        # حالة 3: {"order":{...}}
        if "order" in result:
            parsed = parse_order_dict(result["order"])
            if parsed is not None:
                return parsed

        # حالة 4: رد مباشر هو بيانات الطلب
        if "status" in result and ("order_id" in result or "id" in result):
            if "order_id" not in result and "id" in result:
                result["order_id"] = result["id"]
            parsed = parse_order_dict(result)
            if parsed is not None:
                return parsed

        # حالة 5: {"result":{...}} أو {"response":{...}}
        for key in ("result", "response", "order_status"):
            if key in result:
                parsed = parse_order_dict(result[key])
                if parsed is not None:
                    return parsed

        return None

    # endpoints للتحقق من حالة الطلب
    check_endpoints = [
        f"client/api/check?orders={order_id}",
        f"api/orders/{order_id}",
        f"api/order/{order_id}",
        f"orders/{order_id}",
        f"order/{order_id}",
        f"api/v1/orders/{order_id}",
        f"api/orders?order_id={order_id}",
        f"api/order/status?order_id={order_id}",
        f"api/check?order_id={order_id}",
        f"client/order/status?order_id={order_id}",
    ]

    for ep in check_endpoints:
        try:
            result = api_request(ep, api_token=api_token, api_base_url=api_base_url)
            parsed = try_parse_result(result)
            if parsed is not None:
                return parsed
        except Exception:
            continue

    return None

def buy_from_api(api_product_id, player_id, qty=1, api_token=None, api_base_url=None):
    """
    يطلب شراء من المزود - يجرب عدة endpoints وأساليب حتى ينجح.
    يدعم GET و POST وأشكال params مختلفة.
    """
    order_uuid = str(uuid.uuid4())

    # قائمة endpoint + method + params المحتملة
    attempts = [
        # --- الطراز الكلاسيكي (shams4store / sahl-cash) ---
        ("GET",  f"client/api/newOrder/{api_product_id}/params",
         {"qty": qty, "playerId": player_id, "order_uuid": order_uuid}),
        # --- POST body ---
        ("POST", "client/api/orders",
         None, {"product_id": api_product_id, "player_id": player_id, "quantity": qty, "order_uuid": order_uuid}),
        ("POST", "api/orders",
         None, {"product_id": api_product_id, "player_id": player_id, "quantity": qty}),
        ("POST", "api/order",
         None, {"service": api_product_id, "link": player_id, "quantity": qty}),
        ("POST", "order",
         None, {"service": api_product_id, "link": player_id, "quantity": qty}),
        ("POST", "api/v1/orders",
         None, {"product_id": api_product_id, "user_id": player_id, "qty": qty}),
        # --- GET مع query params مختلفة ---
        ("GET",  f"client/api/newOrder/{api_product_id}",
         {"qty": qty, "playerId": player_id}),
        ("GET",  f"api/order/create",
         {"product_id": api_product_id, "player_id": player_id, "quantity": qty}),
        ("GET",  f"api/orders/new",
         {"service": api_product_id, "link": player_id, "quantity": qty}),
    ]

    for attempt in attempts:
        if len(attempt) == 3:
            method, ep, params = attempt
            body = None
        else:
            method, ep, params, body = attempt
        try:
            result = api_request(ep, params=params, api_token=api_token,
                                 api_base_url=api_base_url, method=method, body=body)
            if not isinstance(result, dict):
                continue
            if result.get("error") is True:
                # اتصال فشل كلياً (ConnectionError) → لا نكمل
                if "message" in result and ("ConnectionError" in result["message"]
                                            or "Timeout" in result["message"]):
                    return result
                continue

            # أي رد صالح من API (حتى لو status = reject) → ارجعه
            # المهم أن الرد وصل من السيرفر
            status_val = str(result.get("status", "")).lower()
            has_data = "data" in result or "order" in result or "order_id" in result
            has_ok = status_val in ["ok", "success", "true", "accepted", "created", "1",
                                    "reject", "rejected", "failed", "error", "wait", "pending"]

            if has_data or has_ok or "id" in result:
                # حوّل الرد إلى الهيكل المتوقع {"status":"OK","data":{...}}
                if "data" not in result:
                    # استخرج بيانات الطلب
                    order_data = {}
                    for k in ("order", "order_id", "orderId", "id", "status",
                              "replay_api", "notes", "message"):
                        if k in result:
                            order_data[k] = result[k]
                    if not order_data:
                        order_data = result.copy()
                    if "order_id" not in order_data and "id" in order_data:
                        order_data["order_id"] = order_data["id"]
                    # إذا ما في status في order_data وفي result
                    if "status" not in order_data and "status" in result:
                        order_data["status"] = result["status"]
                    result = {"status": "OK", "data": order_data}
                else:
                    if isinstance(result.get("data"), dict):
                        data_d = result["data"]
                        if "order_id" not in data_d and "id" in data_d:
                            data_d["order_id"] = data_d["id"]
                    result["status"] = "OK"
                return result
        except Exception:
            continue

    return {"error": True, "message": "فشل في إرسال الطلب لجميع endpoints"}

def monitor_api_order_web(order_db_id, user_id, price_syp, api_token=None, api_base_url=None,
                          check_interval=2, max_wait=600):
    """
    نسخة مطابقة لـ monitor_api_order بس بدون أي اعتماد على تيليجرام (لا send_message
    ولا chat_id) — تستخدم من background thread بالموقع (app.py) بعد كل طلب API ناجح.

    نفس منطق البوت بالضبط:
      - تفحص حالة الطلب كل check_interval ثانية
      - إذا تجاوزت max_wait ثانية بدون نتيجة نهائية → "timeout" + استرجاع الرصيد
      - إذا "completed" → لا استرجاع (الطلب نجح)
      - إذا "failed"    → استرجاع الرصيد فوراً
      - إذا "wait"      → تستمر بالمراقبة
    """
    start_time = time.time()
    none_count = 0
    max_none = 20  # فشل اتصال متكرر متتالي
    first_check = True

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait:
            update_api_order_status(order_db_id, "timeout")
            update_user_balance(user_id, price_syp)
            add_notification(user_id, "⌛ انتهت مهلة الطلب", "تم إرجاع المبلغ إلى رصيدك تلقائياً", "danger")
            return

        time.sleep(0 if first_check else check_interval)
        first_check = False

        order = get_api_order_by_id(order_db_id)
        if not order:
            return  # الطلب حُذف أو غير موجود — توقف
        order_id_ext = order[3]
        current_status = order[10] if len(order) > 10 else None
        # إذا تغيّرت الحالة بالفعل (مثلاً عبر /refresh اليدوي بنفس اللحظة) → توقف
        if current_status not in (None, "processing"):
            return

        try:
            order_data = check_order_status(order_id_ext, api_token=api_token, api_base_url=api_base_url)
        except Exception:
            order_data = None

        if order_data is None:
            none_count += 1
            if none_count >= max_none:
                # تعذّر الوصول للمزوّد بشكل متكرر — لا نسترجع تلقائياً (قد يكون الطلب نجح
                # والمشكلة بالاتصال فقط)، نوقف المراقبة ونترك /refresh اليدوي كخيار أخير
                return
            continue
        none_count = 0

        if order_data == "wait":
            continue

        status = str(order_data.get("status", "")).lower()
        replay_text = order_data.get("_replay_text", "") or ""

        if status == "completed":
            update_api_order_status(order_db_id, "completed", replay_text)
            return
        elif status == "failed":
            update_api_order_status(order_db_id, "failed", replay_text)
            update_user_balance(user_id, price_syp)
            add_notification(user_id, "💰 تم استرجاع المبلغ", "أعيد مبلغ الطلب الفاشل إلى رصيدك", "info")
            return
        # أي حالة أخرى (processing/غيرها) → استمر بالمراقبة


def edit_or_send(chat_id, pending_msg_id, text):
    """يحرّر رسالة الانتظار إن توفّر معرّفها، وإلا يرسل رسالة جديدة"""
    if pending_msg_id:
        try:
            edit_message(chat_id, pending_msg_id, text)
            return
        except Exception:
            pass
    send_message(chat_id, text)

def monitor_api_order(order_db_id, user_id, chat_id, start_time, price_syp, api_token=None, api_base_url=None, pending_msg_id=None):
    """مراقبة حالة الطلب مع مهلة زمنية وإشعارات صحيحة"""
    order = get_api_order_by_id(order_db_id)
    if not order:
        return

    order_id = order[3]
    product_name = order[4]
    category_name = order[5]
    player_id = order[7]
    qty = order[9] if order[9] else 1

    user_info = get_telegram_user_info(user_id)
    balance = get_user_balance(user_id)

    processing_msg = (
        f"<b>جار معالجة طلب اوتوماتيكي عبر Api 🟣:</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<b>♕🟡 اللعبة: {product_name}</b>\n"
        f"<b>♕🟡 المنتج: {category_name}</b>\n"
        f"<b>♕🟡 السعر: {price_syp:,.2f} ليرة</b>\n"
        f"<b>♕🟡 ايدي الاعب: {player_id}</b>\n"
        f"<b>♕🟡 رد نظام: {order[8]}</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<b>◽ المستخدم: {user_info['name']}</b>\n"
        f"<b>◽ ايديه: {user_id}</b>\n"
        f"<b>◽ اليوزر: {user_info['username']}</b>\n"
        f"<b>◽ رصيده الان: {balance:,.2f} ليرة</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━</b>"
    )
    send_message(ADMIN_CHAT_ID, processing_msg)

    check_interval = 2   # فحص كل 2 ثانية
    max_wait = 600       # 10 دقائق كحد أقصى
    none_count = 0
    max_none = 20        # إذا فشل الاتصال 20 مرة متتالية
    first_check = True   # أول فحص يكون فوري بدون sleep

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait:
            # انتهت المهلة - نرفض الطلب ونسترد الرصيد
            update_api_order_status(order_db_id, "timeout")
            update_user_balance(user_id, price_syp)
            new_balance = get_user_balance(user_id)
            elapsed_time = time.time() - start_time
            timeout_msg = (
                f"تم رفض طلبك من المزود❌:\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔴⚡ المنتج: {product_name}\n"
                f"🔴⚡ الفئة: {category_name}\n"
                f"🔴⚡ السعر: {price_syp:,.2f} ليرة\n"
                f"🔴⚡ الايدي: {player_id}\n"
                f"🔴⚡ الكمية: {qty}\n"
                f"🔴⚡ الوقت المستغرق: {elapsed_time:.2f} ثانية\n"
                f"🔴⚡ رد النظام: انتهت مهلة الانتظار\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 تم استرداد رصيدك: {price_syp:,.2f} ليرة\n"
                f"💰 رصيدك الحالي: {new_balance:,.2f} ليرة"
            )
            edit_or_send(chat_id, pending_msg_id, timeout_msg)
            send_message(ADMIN_CHAT_ID,
                         f"⏰ انتهت مهلة طلب API:\n"
                         f"المستخدم: {user_info['name']} ({user_id})\n"
                         f"المنتج: {product_name} - {category_name}\n"
                         f"order_id: {order_id}\n"
                         f"تم استرداد: {price_syp:,.2f} ليرة")
            return

        time.sleep(0 if first_check else check_interval)
        first_check = False

        order_data = check_order_status(order_id, api_token=api_token, api_base_url=api_base_url)

        if order_data == "wait":
            none_count = 0
            continue

        if order_data is None:
            none_count += 1
            if none_count >= max_none:
                # فشل الاتصال كثيراً - نسترد الرصيد ونبلّغ الجميع
                update_api_order_status(order_db_id, "unknown")
                update_user_balance(user_id, price_syp)
                new_balance = get_user_balance(user_id)
                elapsed_time = time.time() - start_time
                unknown_msg = (
                    f"تم رفض طلبك من المزود❌:\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔴⚡ المنتج: {product_name}\n"
                    f"🔴⚡ الفئة: {category_name}\n"
                    f"🔴⚡ السعر: {price_syp:,.2f} ليرة\n"
                    f"🔴⚡ الايدي: {player_id}\n"
                    f"🔴⚡ الكمية: {qty}\n"
                    f"🔴⚡ الوقت المستغرق: {elapsed_time:.2f} ثانية\n"
                    f"🔴⚡ رد النظام: تعذّر التحقق من الطلب\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 تم استرداد رصيدك: {price_syp:,.2f} ليرة\n"
                    f"💰 رصيدك الحالي: {new_balance:,.2f} ليرة"
                )
                edit_or_send(chat_id, pending_msg_id, unknown_msg)
                send_message(ADMIN_CHAT_ID,
                             f"⚠️ تعذّر التحقق من حالة الطلب:\n"
                             f"order_id: {order_id}\n"
                             f"المستخدم: {user_info['name']} ({user_id})\n"
                             f"المنتج: {product_name} - {category_name}\n"
                             f"تم استرداد رصيد المستخدم: {price_syp:,.2f} ليرة\n"
                             f"يرجى التحقق يدوياً إذا نُفّذ الطلب.")
                return
            continue

        if isinstance(order_data, dict):
            status = order_data.get("status", "")
            # يدعم _replay_text (المُستخلص من أي حقل) أو replay_api مباشرة
            replay_text = order_data.get("_replay_text") or extract_replay_text(order_data) or "لا يوجد"
            none_count = 0

            if status in ["completed", "success", "OK", "done", "accept", "accepted"]:
                update_api_order_status(order_db_id, "completed", json.dumps(order_data))
                elapsed_time = time.time() - start_time

                _elapsed_h = int(elapsed_time // 3600)
                _elapsed_m = int((elapsed_time % 3600) // 60)
                _elapsed_s = int(elapsed_time % 60)
                _price_usd_auto = price_syp / get_exchange_rate() if get_exchange_rate() > 0 else 0
                success_msg = (
                    f"✅ تم اكتمال طلبك بنجاح!\n\n"
                    f"▪️ اللعبة: {product_name}\n"
                    f"▪️ الحزمة: {category_name}\n"
                    f"▪️ الكمية: {qty}\n"
                    f"▪️ ID اللاعب: {player_id}\n"
                    f"▪️ رقم الطلب: {order_db_id}\n"
                    f"▪️ السعر: {price_syp:,.0f} ل.س ({_price_usd_auto:.2f}$)\n"
                    f"▪️ الوقت المستغرق: {_elapsed_h} ساعات و {_elapsed_m} دقائق و {_elapsed_s} ثانية\n\n"
                    f"شكراً لاستخدامك خدماتنا ❤️"
                )
                edit_or_send(chat_id, pending_msg_id, success_msg)

                channel_success_msg = (
                    f"<b>🎉 طلب تم اكتماله عبر API 🎉:</b>\n"
                    f"<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
                    f"<b>🟢⚡ اللعبة: {product_name}</b>\n"
                    f"<b>🟢⚡ المنتج: {category_name}</b>\n"
                    f"<b>🟢⚡ السعر: {price_syp:,.2f} ليرة</b>\n"
                    f"<b>🟢⚡ الايدي الاعب: {player_id}</b>\n"
                    f"<b>🟢⚡ رد نظام: <code>{replay_text}</code></b>\n"
                    f"<b>🟢⚡ الوقت: {elapsed_time:.1f} ثانية</b>\n"
                    f"<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
                    f"<b>◽ المستخدم: {user_info['name']}</b>\n"
                    f"<b>◽ ايديه: {user_id}</b>\n"
                    f"<b>◽ اليوزر: {user_info['username']}</b>\n"
                    f"<b>◽ رصيده: {get_user_balance(user_id):,.2f} ليرة</b>\n"
                    f"<b>━━━━━━━━━━━━━━━━━━━━</b>"
                )
                send_message(ADMIN_CHAT_ID, channel_success_msg)
                return

            elif status in ["reject", "rejected", "canceled", "fail", "failed", "error", "refunded"]:
                update_api_order_status(order_db_id, "rejected", json.dumps(order_data))
                elapsed_time = time.time() - start_time
                update_user_balance(user_id, price_syp)
                new_balance = get_user_balance(user_id)

                reject_msg = (
                    f"❌ عذراً، تعذر إكمال طلبك\n\n"
                    f"⚡المنتج: {product_name}\n"
                    f"⚡️ الحزمة: {category_name}\n"
                    f"⚡️ الكمية: {qty}\n"
                    f"⚡️ السعر: {price_syp:,.0f} ل.س\n"
                    f"⚡️ اللاعب: {player_id} ⚡\n"
                    f"⚡️ رقم الطلب: {order_db_id}\n"
                    f"⚡️ حالة الطلب: رفض ❌\n"
                    f"⚡️ السبب: {replay_text}\n\n"
                    f"تم استعادة رصيدك تلقائياً.\n"
                    f"الرصيد الحالي: {new_balance:,.0f} ل.س"
                )
                edit_or_send(chat_id, pending_msg_id, reject_msg)

                channel_reject_msg = (
                    f"<b>تم رفض الطلب من API❌:</b>\n"
                    f"<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
                    f"<b>🔴⚡ المنتج: {product_name}</b>\n"
                    f"<b>🔴⚡ الفئة: {category_name}</b>\n"
                    f"<b>🔴⚡ السعر: {price_syp:,.2f} ليرة</b>\n"
                    f"<b>🔴⚡ الايدي: {player_id}</b>\n"
                    f"<b>🔴⚡ رد النظام: <code>{replay_text}</code></b>\n"
                    f"<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
                    f"<b>◽ المستخدم: {user_info['name']}</b>\n"
                    f"<b>◽ ايديه: {user_id}</b>\n"
                    f"<b>◽ رصيده: {new_balance:,.2f} ليرة</b>\n"
                    f"<b>━━━━━━━━━━━━━━━━━━━━</b>"
                )
                send_message(ADMIN_CHAT_ID, channel_reject_msg)
                return
            # حالة غير معروفة - استمر في الانتظار

def add_product(name, category, emoji="", description="", image="", subsection_id=0):
    with get_db() as conn:
        c = conn.cursor()
        sort_order = 0
        if subsection_id:
            c.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM products WHERE subsection_id = ?", (subsection_id,))
            sort_order = c.fetchone()[0]
        c.execute("INSERT INTO products (name, category, emoji, description, image, subsection_id, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (name, category, emoji, description, image, subsection_id, sort_order))
        product_id = c.lastrowid
    broadcast_notification("🆕 منتج جديد", f"تمت إضافة «{name}» إلى قسم {category}", "info")
    return product_id

def update_product_subsection(product_id, subsection_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE products SET subsection_id = ? WHERE id = ?", (subsection_id, product_id))

def reorder_products(ordered_ids):
    with get_db() as conn:
        c = conn.cursor()
        for idx, pid in enumerate(ordered_ids):
            c.execute("UPDATE products SET sort_order = ? WHERE id = ?", (idx, pid))

def update_product_description(product_id, description):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE products SET description = ? WHERE id = ?", (description, product_id))

def update_product_image(product_id, image):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE products SET image = ? WHERE id = ?", (image, product_id))

def get_product_image(product_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT image FROM products WHERE id = ?", (product_id,))
        result = c.fetchone()
        return result[0] if result else ""

def get_product_description(product_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT description FROM products WHERE id = ?", (product_id,))
        result = c.fetchone()
        return result[0] if result else ""

def get_products_by_category(category):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, emoji FROM products WHERE category = ?", (category,))
        return c.fetchall()

def get_all_products():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, category, emoji, description, image FROM products")
        return c.fetchall()

def get_all_products_admin():
    """نسخة موسّعة لإدارة الويب: تتضمن subsection_id و sort_order"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, name, category, emoji, description, image, subsection_id, sort_order
                     FROM products ORDER BY sort_order ASC, id ASC""")
        return c.fetchall()

# ----- تقارير الأرباح -----
def get_profit_orders(start_date=None, end_date=None, limit=500, offset=0):
    """يدمج shop_orders (المكتملة 'accepted') و api_orders (المكتملة 'completed') بتقرير مبيعات/أرباح موحّد"""
    with get_db() as conn:
        c = conn.cursor()
        rate = get_exchange_rate() or 1
        params = []
        date_filter = ""
        if start_date:
            date_filter += " AND created_at >= ?"
            params.append(start_date)
        if end_date:
            date_filter += " AND created_at <= ?"
            params.append(end_date)

        c.execute(f"""SELECT id, 'shop' as src, user_id, product_name, category_name, price, price_usd, cost_usd, status, created_at
                      FROM shop_orders WHERE status = 'accepted' {date_filter}
                      UNION ALL
                      SELECT id, 'api' as src, user_id, product_name, category_name, price, price_usd, cost_usd, status, created_at
                      FROM api_orders WHERE status = 'completed' {date_filter}
                      ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                  params + params + [limit, offset])
        rows = c.fetchall()

        result = []
        for r in rows:
            oid, src, user_id, pname, cname, price_syp, price_usd, cost_usd, status, created_at = r
            price_usd = price_usd if price_usd else (price_syp / rate if rate else 0)
            cost_usd = cost_usd or 0
            profit_usd = price_usd - cost_usd
            result.append({
                "id": oid, "source": src, "user_id": user_id, "product_name": pname,
                "category_name": cname, "price_syp": price_syp, "price_usd": round(price_usd, 3),
                "cost_usd": round(cost_usd, 3), "profit_usd": round(profit_usd, 3),
                "status": status, "created_at": created_at
            })
        return result

def get_profit_summary(start_date=None, end_date=None):
    """إجمالي المبيعات / التكلفة / الربح خلال فترة معيّنة"""
    with get_db() as conn:
        c = conn.cursor()
        rate = get_exchange_rate() or 1
        params = []
        date_filter = ""
        if start_date:
            date_filter += " AND created_at >= ?"
            params.append(start_date)
        if end_date:
            date_filter += " AND created_at <= ?"
            params.append(end_date)

        total_sales_usd = 0.0
        total_cost_usd = 0.0
        total_orders = 0

        c.execute(f"""SELECT price, price_usd, cost_usd FROM shop_orders
                      WHERE status = 'accepted' {date_filter}""", params)
        for price_syp, price_usd, cost_usd in c.fetchall():
            total_sales_usd += price_usd if price_usd else (price_syp / rate if rate else 0)
            total_cost_usd += cost_usd or 0
            total_orders += 1

        c.execute(f"""SELECT price, price_usd, cost_usd FROM api_orders
                      WHERE status = 'completed' {date_filter}""", params)
        for price_syp, price_usd, cost_usd in c.fetchall():
            total_sales_usd += price_usd if price_usd else (price_syp / rate if rate else 0)
            total_cost_usd += cost_usd or 0
            total_orders += 1

        return {
            "total_orders": total_orders,
            "total_sales_usd": round(total_sales_usd, 2),
            "total_cost_usd": round(total_cost_usd, 2),
            "total_profit_usd": round(total_sales_usd - total_cost_usd, 2),
        }

def get_product_by_id(product_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, category, emoji, description, image FROM products WHERE id = ?", (product_id,))
        return c.fetchone()

def delete_product(product_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM categories WHERE product_id = ?", (product_id,))
        c.execute("DELETE FROM products WHERE id = ?", (product_id,))

def add_category(product_id, name, price, cat_type='default', min_qty=1, max_qty=1, unit_qty=1):
    min_qty = max(1, int(min_qty or 1))
    max_qty = max(min_qty, int(max_qty or min_qty))
    unit_qty = max(1, int(unit_qty or 1))
    with get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO categories (product_id, name, price, type, min_qty, max_qty, unit_qty) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (product_id, name, float(price), cat_type, min_qty, max_qty, unit_qty))
        return c.lastrowid

def get_categories_by_product(product_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, price, type, min_qty, max_qty FROM categories WHERE product_id = ?", (product_id,))
        return c.fetchall()

def get_category_by_id(category_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, product_id, name, price, type, min_qty, max_qty FROM categories WHERE id = ?", (category_id,))
        return c.fetchone()

def get_category_unit_qty(category_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COALESCE(NULLIF(unit_qty, 0), 1) FROM categories WHERE id = ?", (category_id,))
        row = c.fetchone()
        return max(1, int(row[0])) if row else 1

def compute_total_price(price_per_unit, qty, unit_qty=1):
    """السعر المدخل هو سعر الحزمة الأساسية (مثلاً كل 100)، وليس دائماً سعر القطعة."""
    return float(price_per_unit) * int(qty) / max(1, int(unit_qty or 1))


# ===== [إضافة جديدة] نظام التسعير الذكي: هامش ربح + مزامنة سعر المزوّد =====
def get_all_categories_pricing():
    """قائمة مسطّحة بكل فئات كل المنتجات، مع حالة الربط بمزوّد والهامش الحالي."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT c.id, c.name, c.price, c.margin_percent, p.name as product_name,
                            lp.provider_id, COALESCE(ap.name, '') as provider_name, lp.api_price
                     FROM categories c
                     LEFT JOIN products p ON p.id = c.product_id
                     LEFT JOIN linked_products lp ON lp.category_id = c.id
                     LEFT JOIN api_providers ap ON ap.id = lp.provider_id
                     ORDER BY p.name, c.name""")
        return c.fetchall()


def set_category_margin(category_id, margin_percent):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE categories SET margin_percent = ? WHERE id = ?", (margin_percent, category_id))


def refresh_category_price_from_provider(category_id):
    """
    يجيب السعر الحالي (التكلفة) من المزوّد لفئة مربوطة، ويطبّق الهامش المخزّن
    عليها، ويحدّث سعر البيع. يرجع (success: bool, new_price_usd أو رسالة خطأ).
    """
    cat = get_category_by_id(category_id)
    if not cat:
        return False, "الفئة غير موجودة"
    margin = None
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT margin_percent FROM categories WHERE id = ?", (category_id,))
        row = c.fetchone()
        margin = row[0] if row else None
    if margin is None:
        return False, "ما في هامش ربح محدد لهاي الفئة"

    linked = get_linked_by_category(category_id)
    if not linked:
        return False, "الفئة غير مربوطة بأي مزوّد API"

    api_product_id = linked[3]
    provider_id = linked[8]
    p_token, p_url = linked[10], linked[11]
    fresh = get_api_product_by_id(api_product_id, api_token=p_token, api_base_url=p_url)
    if not fresh:
        return False, "تعذّر جلب السعر الحالي من المزوّد"

    cost_usd = float(fresh.get("price", 0) or 0)
    if cost_usd <= 0:
        return False, "المزوّد رجّع سعر غير صالح"

    new_price_usd = round(cost_usd * (1 + margin / 100), 4)
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE categories SET price = ? WHERE id = ?", (new_price_usd, category_id))
        c.execute("UPDATE linked_products SET api_price = ? WHERE category_id = ?", (cost_usd, category_id))
    return True, new_price_usd


def apply_margin_to_categories(category_ids, margin_percent):
    """يطبّق هامش ربح على مجموعة فئات دفعة وحدة، ويعيد حساب سعرها فوراً لو كانت مربوطة."""
    updated, skipped_not_linked, failed = [], [], []
    for cid in category_ids:
        set_category_margin(cid, margin_percent)
        ok, result = refresh_category_price_from_provider(cid)
        if ok:
            updated.append({"category_id": cid, "new_price_usd": result})
        elif result == "الفئة غير مربوطة بأي مزوّد API":
            skipped_not_linked.append(cid)
        else:
            failed.append({"category_id": cid, "error": result})
    return {"updated": updated, "skipped_not_linked": skipped_not_linked, "failed": failed}


def sync_all_margin_prices():
    """يشتغل دورياً (مرة يومياً) — يحدّث سعر كل فئة إلها هامش ربح محدد ومربوطة بمزوّد."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM categories WHERE margin_percent IS NOT NULL")
        ids = [r[0] for r in c.fetchall()]
    results = []
    for cid in ids:
        ok, result = refresh_category_price_from_provider(cid)
        results.append({"category_id": cid, "ok": ok, "result": result})
    return results

def delete_category(category_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM categories WHERE id = ?", (category_id,))

def update_category_image(category_id, image):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE categories SET image = ? WHERE id = ?", (image, category_id))

def get_category_image_by_id(category_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT image FROM categories WHERE id = ?", (category_id,))
        result = c.fetchone()
        return result[0] if result else ""

def add_deposit_method(title, description, code, exchange_rate, input_currency='usd'):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO deposit_methods (title, description, code, exchange_rate, input_currency) VALUES (?, ?, ?, ?, ?)",
                  (title, description, code, float(exchange_rate), input_currency))
        return c.lastrowid

def get_all_deposit_methods():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, title, description, code, exchange_rate, image, input_currency FROM deposit_methods")
        return c.fetchall()

def get_deposit_method_by_id(method_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, title, description, code, exchange_rate, image, input_currency FROM deposit_methods WHERE id = ?", (method_id,))
        return c.fetchone()

def update_deposit_method(method_id, title, description, code, exchange_rate):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE deposit_methods SET title = ?, description = ?, code = ?, exchange_rate = ? WHERE id = ?",
                  (title, description, code, float(exchange_rate), method_id))

def delete_deposit_method(method_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM deposit_methods WHERE id = ?", (method_id,))

def add_auto_deposit_method(title, description, code, exchange_rate, api_token, api_url='', gateway_type='verify', input_currency='usd'):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO auto_deposit_methods (title, description, code, exchange_rate, api_token, api_url, gateway_type, input_currency) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (title, description, code, float(exchange_rate), api_token, api_url, gateway_type, input_currency))
        return c.lastrowid

def get_all_auto_deposit_methods():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, title, description, code, exchange_rate, api_token, api_url, image, gateway_type, input_currency FROM auto_deposit_methods")
        return c.fetchall()

def get_auto_deposit_method_by_id(method_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, title, description, code, exchange_rate, api_token, api_url, image, gateway_type, input_currency FROM auto_deposit_methods WHERE id = ?", (method_id,))
        return c.fetchone()

def delete_auto_deposit_method(method_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM auto_deposit_methods WHERE id = ?", (method_id,))

def update_auto_deposit_method(method_id, title, description, code, exchange_rate, api_token, api_url, gateway_type=None, input_currency=None):
    with get_db() as conn:
        c = conn.cursor()
        if gateway_type is None:
            c.execute(
                "UPDATE auto_deposit_methods SET title=?, description=?, code=?, exchange_rate=?, api_token=?, api_url=? WHERE id=?",
                (title, description, code, float(exchange_rate), api_token, api_url, method_id)
            )
        else:
            c.execute(
                "UPDATE auto_deposit_methods SET title=?, description=?, code=?, exchange_rate=?, api_token=?, api_url=?, gateway_type=? WHERE id=?",
                (title, description, code, float(exchange_rate), api_token, api_url, gateway_type, method_id)
            )
        if input_currency is not None:
            c.execute("UPDATE auto_deposit_methods SET input_currency=? WHERE id=?", (input_currency, method_id))

SAM_API_BASE = "https://www.sam-api.pro/api"

def create_gateway_invoice(api_token, api_url, amount, currency, invoice_ref, callback_url=None):
    """
    ينشئ فاتورة دفع عبر SAM API (نظام الفواتير الموثّق فعلياً بـ sam-api.pro/api-docs).

    Endpoints مؤكدة من التوثيق الرسمي:
        POST {SAM_API_BASE}/v1/invoices        → إنشاء الفاتورة
        GET  {SAM_API_BASE}/pay/{invoiceId}     → صفحة/بيانات الدفع (هي رابط الدفع نفسه)
        POST {SAM_API_BASE}/pay/{invoiceId}/verify → التحقق من إتمام الدفع

    ⚠️ ملاحظة مهمة: التوثيق يعرض أسماء المسارات بوضوح، بس ما بيوضح أسماء حقول
    الـ body بالتفصيل (لازم تفتح كل endpoint بالتوثيق وتضغط عليه ليوسّع ويطلعلك
    شكل الطلب/الرد بالضبط). الحقول تحت (amount, currency, reference, webhook_url)
    هي التسميات الشائعة بمعظم أنظمة الفوترة المشابهة — إذا رجّع SAM API خطأ
    VALIDATION_ERROR، ابعتلي سكرين شوت من الـ body الموسّع بالتوثيق لنصحح التسميات.
    """
    try:
        if not api_token:
            return None, "لا يوجد مفتاح API (token) مضبوط لهذه الطريقة"
        headers = {
            "Authorization": "Bearer " + api_token,
            "X-Api-Key": api_token,
            "Content-Type": "application/json",
        }
        body = {"amount": amount, "currency": currency, "reference": invoice_ref}
        if callback_url:
            body["webhook_url"] = callback_url

        r = requests.post(SAM_API_BASE + "/v1/invoices", headers=headers, json=body, timeout=20)
        if r.status_code in (200, 201):
            data = r.json()
            invoice_id = data.get("invoiceId") or data.get("invoice_id") or data.get("id")
            payment_url = data.get("payment_url") or data.get("url")
            if not payment_url and invoice_id:
                # التوثيق يوضّح GET /pay/{invoiceId} كصفحة الدفع نفسها
                payment_url = f"{SAM_API_BASE}/pay/{invoice_id}"
            if payment_url:
                return payment_url, None
            return None, "رد SAM API ما فيه invoiceId ولا payment_url — راجع شكل الرد بالتوثيق"

        error_code = None
        try:
            error_code = r.json().get("error_code") or r.json().get("code")
        except Exception:
            pass
        friendly = _SAM_ERROR_MESSAGES.get(error_code, f"HTTP {r.status_code}")
        return None, f"فشل إنشاء الفاتورة: {friendly}"
    except Exception as e:
        return None, f"تعذّر الاتصال بـ SAM API: {e}"


def check_invoice_status(invoice_id, api_token):
    """
    يتحقق من حالة فاتورة SAM API عبر POST /pay/{invoiceId}/verify (بديل احتياطي
    عن الـ webhook، بالحالة يلي السيرفر ما إلو دومين/SSL عام يوصلو الـ webhook).
    يرجع 'paid' / 'pending' / 'failed' / 'expired' / None (خطأ اتصال).
    """
    try:
        headers = {"Authorization": "Bearer " + api_token, "X-Api-Key": api_token}
        r = requests.post(f"{SAM_API_BASE}/pay/{invoice_id}/verify", headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            status = (data.get("status") or "").lower()
            if status in ("paid", "success", "completed"):
                return "paid"
            if status in ("expired",):
                return "expired"
            if status in ("failed", "rejected"):
                return "failed"
            return "pending"
        if r.status_code == 410:
            return "expired"
        return None
    except Exception as e:
        print(f"[check_invoice_status] error: {e}")
        return None

_SAM_ERROR_MESSAGES = {
    "MISSING_API_KEY": "مفتاح الـ API مفقود",
    "INVALID_API_KEY": "مفتاح الـ API غير صالح",
    "VALIDATION_ERROR": "بيانات الطلب غير صحيحة",
    "INVALID_IDENTIFIER": "تنسيق معرّف المحفظة غير مطابق للمزوّد المحدد",
    "NOT_FOUND": "المحفظة أو الفاتورة غير موجودة",
    "EXPIRED": "انتهت صلاحية الفاتورة",
    "WALLET_SESSION_EXPIRED": "انتهت جلسة ربط المحفظة بـ SAM API — لازم تعيد ربطها من لوحة sam-api.pro",
    "WALLET_UPSTREAM_ERROR": "تعذّر اتصال SAM API بمزوّد المحفظة (شام كاش/سيرياتيل)",
    "PROVIDER_ERROR": "رفض المزوّد الطلب",
}

# مانع إزعاج: ما منبعت تنبيه أدمن لنفس الخطأ أكتر من مرة كل ساعة
_last_sam_alert_at = {}

def _alert_admin_sam_error(api_url, error_code, http_status):
    """ينبّه الأدمن مباشرة عبر تيليجرام لو صار خطأ تشغيلي حرج بـ SAM API (يعطّل الإيداع التلقائي بالكامل)."""
    critical = error_code in ("WALLET_SESSION_EXPIRED", "MISSING_API_KEY", "INVALID_API_KEY", "WALLET_UPSTREAM_ERROR")
    if not critical:
        return
    key = api_url + "|" + str(error_code)
    now = datetime.now()
    last = _last_sam_alert_at.get(key)
    if last and (now - last).total_seconds() < 3600:
        return
    _last_sam_alert_at[key] = now
    friendly = _SAM_ERROR_MESSAGES.get(error_code, error_code)
    try:
        send_message(ADMIN_CHAT_ID,
            f"🚨 <b>عطل بالإيداع التلقائي (SAM API)</b>\n"
            f"الخطأ: <code>{error_code}</code> (HTTP {http_status})\n"
            f"التفصيل: {friendly}\n"
            f"⚠️ كل عمليات الإيداع التلقائي عبر هالطريقة معطّلة لحد ما تصلحها من لوحة sam-api.pro")
    except Exception as e:
        print(f"[verify_auto_deposit] فشل إرسال تنبيه الأدمن: {e}")


def verify_auto_deposit(api_token, api_url, transaction_code, amount_syp, wallet_address=None):
    """
    التحقق من الإيداع مع دعم SAM API (ShamCash و SyriaTelCash) والمزودين العاديين.

    SAM API Base: https://www.sam-api.pro/api
    Authentication: Authorization: Bearer {token}  أو  X-Api-Key: {token}

    ShamCash:    api_url = https://www.sam-api.pro/api/v1/wallets/shamcash/{walletAddress}
    SyriaTel:    api_url = https://www.sam-api.pro/api/v1/wallets/syriatel/{phoneOrCode}

    الفحص يتم عبر GET {api_url}/transactions
    ثم البحث في النتائج عن transaction_code (يُقارن بحقول: id, transactionId, ref, code, transferId)
    """
    try:
        if not api_url or not api_token:
            return False

        # SAM API يقبل كلا الطريقتين للمصادقة
        headers = {
            "Authorization": "Bearer " + api_token,
            "X-Api-Key": api_token,
            "Content-Type": "application/json"
        }

        # ===== دعم SAM API: ShamCash و SyriaTelCash (/v1/wallets/) =====
        if '/wallets/' in api_url:
            base = api_url.rstrip('/')

            # الخطوة 1: جلب قائمة المعاملات من /transactions
            trans_url = base + '/transactions'
            try:
                r = requests.get(trans_url, headers=headers, timeout=15)
                if r.status_code == 200:
                    data_r = r.json()

                    # SAM API يرجع: {"data": [...]} أو قائمة مباشرة
                    transactions = []
                    if isinstance(data_r, list):
                        transactions = data_r
                    elif isinstance(data_r, dict):
                        transactions = (data_r.get('data') or
                                        data_r.get('transactions') or
                                        data_r.get('result') or
                                        data_r.get('items') or [])

                    if isinstance(transactions, list):
                        tx_code_str = str(transaction_code).strip()
                        for tx in transactions:
                            if not isinstance(tx, dict):
                                continue
                            # حقول المعرف المحتملة في SAM API
                            possible_ids = [
                                str(tx.get('id', '')),
                                str(tx.get('transactionId', '')),
                                str(tx.get('transaction_id', '')),
                                str(tx.get('transferId', '')),
                                str(tx.get('transfer_id', '')),
                                str(tx.get('ref', '')),
                                str(tx.get('reference', '')),
                                str(tx.get('code', '')),
                                str(tx.get('orderRef', '')),
                            ]
                            # إذا وجدنا تطابق في أي حقل -> تم التحقق
                            if tx_code_str in possible_ids:
                                return True
                    # الـ API يعمل (200) لكن رقم العملية مش موجود بالكشف — طبيعي، مو عطل
                    print(f"[verify_auto_deposit] لم يتم العثور على رقم العملية {transaction_code} بكشف الحساب")
                else:
                    # ===== خطأ حقيقي: نقرأ رمز الخطأ من SAM API لمعرفة السبب بالضبط =====
                    error_code = http_status_note = None
                    try:
                        err_body = r.json()
                        error_code = err_body.get("error_code") or err_body.get("code") or err_body.get("error")
                    except Exception:
                        pass
                    error_code = error_code or f"HTTP_{r.status_code}"
                    friendly = _SAM_ERROR_MESSAGES.get(error_code, "خطأ غير معروف من SAM API")
                    print(f"[verify_auto_deposit] {error_code} (HTTP {r.status_code}) — {friendly}")
                    _alert_admin_sam_error(base, error_code, r.status_code)
            except requests.RequestException as e:
                print(f"[verify_auto_deposit] تعذّر الاتصال بـ SAM API: {e}")
                _alert_admin_sam_error(base, "CONNECTION_ERROR", 0)

            # لم يتم إيجاد رقم العملية (أو صار خطأ)
            return False

        # ===== مزود عادي (الطريقة القديمة) =====
        params = {
            "transaction_id": transaction_code,
            "code": transaction_code,
            "amount": amount_syp
        }
        r = requests.get(api_url, headers=headers, params=params, timeout=15)
        if r.status_code == 200:
            result = r.json()
            return (result.get("success") is True or
                    result.get("status") in ["success", "OK", "verified", "valid", "done"] or
                    result.get("verified") is True or
                    result.get("result") == "success")
    except Exception as e:
        print(f"[verify_auto_deposit] خطأ عام: {e}")
    return False

def update_deposit_method_image(method_id, image):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE deposit_methods SET image = ? WHERE id = ?", (image, method_id))

def update_auto_deposit_method_image(method_id, image):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE auto_deposit_methods SET image = ? WHERE id = ?", (image, method_id))

def get_category_description(category_name):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT description FROM category_description WHERE category_name = ?", (category_name,))
        result = c.fetchone()
        if result and result[0]:
            return result[0]
    return f"🔶 قائمة {category_name} المتاحة:"

def set_category_description(category_name, description):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO category_description (category_name, description) VALUES (?, ?)", (category_name, description))

def get_all_sections():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, color, emoji, is_active FROM sections WHERE is_active = 1 ORDER BY sort_order ASC, id ASC")
        return c.fetchall()

def get_all_sections_admin():
    """نسخة موسّعة لاستخدام لوحة التحكم (الويب) فقط - تتضمن sort_order وكل الأقسام (مفعّلة أو لا)"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, color, emoji, is_active, sort_order FROM sections ORDER BY sort_order ASC, id ASC")
        return c.fetchall()

def add_section(name, color='success', emoji=''):
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO sections (name, color, emoji) VALUES (?, ?, ?)", (name, color, emoji))
            c.execute("INSERT INTO category_description (category_name, description) VALUES (?, ?)", (name, f"🔶 قائمة {name} المتاحة:"))
        return True
    except:
        return False

def delete_section(section_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM sections WHERE id = ?", (section_id,))
        result = c.fetchone()
        if result:
            section_name = result[0]
            c.execute("SELECT id FROM subsections WHERE section_id = ?", (section_id,))
            sub_ids = [r[0] for r in c.fetchall()]
            for sub_id in sub_ids:
                c.execute("DELETE FROM products WHERE subsection_id = ?", (sub_id,))
            c.execute("DELETE FROM subsections WHERE section_id = ?", (section_id,))
            c.execute("DELETE FROM products WHERE category = ?", (section_name,))
            c.execute("DELETE FROM sections WHERE id = ?", (section_id,))
            c.execute("DELETE FROM category_description WHERE category_name = ?", (section_name,))

def reorder_sections(ordered_ids):
    """ordered_ids: لائحة آيديات الأقسام بالترتيب الجديد المطلوب"""
    with get_db() as conn:
        c = conn.cursor()
        for idx, sid in enumerate(ordered_ids):
            c.execute("UPDATE sections SET sort_order = ? WHERE id = ?", (idx, sid))

# ----- الأقسام الفرعية -----
def get_subsections_by_section(section_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, section_id, name, emoji, image, is_active, sort_order
                     FROM subsections WHERE section_id = ? ORDER BY sort_order ASC, id ASC""", (section_id,))
        return c.fetchall()

def get_all_subsections():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, section_id, name, emoji, image, is_active, sort_order
                     FROM subsections ORDER BY sort_order ASC, id ASC""")
        return c.fetchall()

def get_subsection_by_id(subsection_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, section_id, name, emoji, image, is_active, sort_order
                     FROM subsections WHERE id = ?""", (subsection_id,))
        return c.fetchone()

def add_subsection(section_id, name, emoji='', image=''):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM subsections WHERE section_id = ?", (section_id,))
        next_order = c.fetchone()[0]
        c.execute("""INSERT INTO subsections (section_id, name, emoji, image, sort_order)
                     VALUES (?, ?, ?, ?, ?)""", (section_id, name, emoji, image, next_order))
        return c.lastrowid

def update_subsection(subsection_id, name=None, emoji=None, is_active=None):
    with get_db() as conn:
        c = conn.cursor()
        if name is not None:
            c.execute("UPDATE subsections SET name = ? WHERE id = ?", (name, subsection_id))
        if emoji is not None:
            c.execute("UPDATE subsections SET emoji = ? WHERE id = ?", (emoji, subsection_id))
        if is_active is not None:
            c.execute("UPDATE subsections SET is_active = ? WHERE id = ?", (1 if is_active else 0, subsection_id))

def update_subsection_image(subsection_id, image):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE subsections SET image = ? WHERE id = ?", (image, subsection_id))

def delete_subsection(subsection_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM products WHERE subsection_id = ?", (subsection_id,))
        c.execute("DELETE FROM subsections WHERE id = ?", (subsection_id,))

def reorder_subsections(ordered_ids):
    with get_db() as conn:
        c = conn.cursor()
        for idx, sid in enumerate(ordered_ids):
            c.execute("UPDATE subsections SET sort_order = ? WHERE id = ?", (idx, sid))

def get_products_by_subsection(subsection_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, name, category, emoji, description, image, subsection_id
                     FROM products WHERE subsection_id = ? ORDER BY sort_order ASC, id ASC""", (subsection_id,))
        return c.fetchall()

def update_section_color(section_id, color):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE sections SET color = ? WHERE id = ?", (color, section_id))

def update_section_name(section_id, new_name):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM sections WHERE id = ?", (section_id,))
        result = c.fetchone()
        if result:
            old_name = result[0]
            c.execute("UPDATE products SET category = ? WHERE category = ?", (new_name, old_name))
            c.execute("UPDATE sections SET name = ? WHERE id = ?", (new_name, section_id))
            c.execute("UPDATE category_description SET category_name = ? WHERE category_name = ?", (new_name, old_name))

def get_section_by_id(section_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, color, emoji FROM sections WHERE id = ?", (section_id,))
        return c.fetchone()

def get_section_color(section_name):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT color FROM sections WHERE name = ?", (section_name,))
        result = c.fetchone()
        if result:
            return result[0]
    return "success"

def get_section_image_by_name(section_name):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT image FROM sections WHERE name = ?", (section_name,))
        result = c.fetchone()
        return result[0] if result and result[0] else ""

def get_section_image_by_id(section_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT image FROM sections WHERE id = ?", (section_id,))
        result = c.fetchone()
        return result[0] if result and result[0] else ""

def update_section_image(section_id, image):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE sections SET image = ? WHERE id = ?", (image, section_id))

def add_required_channel(channel_username):
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO required_channels (channel_username) VALUES (?)", (channel_username,))
        return True
    except:
        return False

def get_all_required_channels():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, channel_username FROM required_channels")
        return c.fetchall()

def delete_required_channel(channel_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM required_channels WHERE id = ?", (channel_id,))

def check_user_subscribed(user_id):
    channels = get_all_required_channels()
    if not channels:
        return True
    for channel in channels:
        channel_id = channel[1]
        if not channel_id.startswith('@'):
            channel_id = '@' + channel_id
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
            data = {"chat_id": channel_id, "user_id": user_id}
            r = requests.post(url, json=data, timeout=10)
            result = r.json()
            if result.get("ok"):
                status = result.get("result", {}).get("status")
                if status not in ["member", "administrator", "creator"]:
                    return False
            else:
                return False
        except:
            return False
    return True

def get_all_users():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        return [u[0] for u in c.fetchall()]

def get_total_users_count():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        result = c.fetchone()
        return result[0] if result else 0

def get_total_balance():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COALESCE(SUM(balance), 0) FROM users")
        return c.fetchone()[0]

def get_total_orders():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM shop_orders WHERE status = 'accepted'")
        return c.fetchone()[0]

# ===== إحصائيات المبيعات الذكية =====

def get_sales_analytics():
    """إحصائيات شاملة للمبيعات: أكثر منتج، أكثر مستخدم، إيرادات اليوم والأسبوع والشهر"""
    with get_db() as conn:
        c = conn.cursor()

        # إيرادات اليوم
        c.execute("""SELECT COALESCE(SUM(price), 0) FROM shop_orders
                     WHERE status='accepted'
                     AND DATE(created_at) = DATE('now')""")
        revenue_today = c.fetchone()[0] or 0

        # إيرادات هذا الأسبوع
        c.execute("""SELECT COALESCE(SUM(price), 0) FROM shop_orders
                     WHERE status='accepted'
                     AND DATE(created_at) >= DATE('now', '-7 days')""")
        revenue_week = c.fetchone()[0] or 0

        # إيرادات هذا الشهر
        c.execute("""SELECT COALESCE(SUM(price), 0) FROM shop_orders
                     WHERE status='accepted'
                     AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')""")
        revenue_month = c.fetchone()[0] or 0

        # إجمالي الإيرادات (كل الوقت)
        c.execute("SELECT COALESCE(SUM(price), 0) FROM shop_orders WHERE status='accepted'")
        revenue_total = c.fetchone()[0] or 0

        # أكثر 5 منتجات مبيعاً (product_name + category_name مجتمعة)
        c.execute("""SELECT product_name, category_name, COUNT(*) as cnt, SUM(price) as total
                     FROM shop_orders WHERE status='accepted'
                     GROUP BY product_name, category_name
                     ORDER BY cnt DESC LIMIT 5""")
        top_products = c.fetchall()

        # أكثر 5 مستخدمين شراءً
        c.execute("""SELECT user_id, COUNT(*) as cnt, SUM(price) as total
                     FROM shop_orders WHERE status='accepted'
                     GROUP BY user_id
                     ORDER BY cnt DESC LIMIT 5""")
        top_users = c.fetchall()

        # عدد الطلبات اليوم
        c.execute("""SELECT COUNT(*) FROM shop_orders
                     WHERE status='accepted'
                     AND DATE(created_at) = DATE('now')""")
        orders_today = c.fetchone()[0] or 0

        # عدد الطلبات هذا الشهر
        c.execute("""SELECT COUNT(*) FROM shop_orders
                     WHERE status='accepted'
                     AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')""")
        orders_month = c.fetchone()[0] or 0

        # أكثر 5 منتجات مبيعاً من API orders أيضاً
        c.execute("""SELECT product_name, category_name, COUNT(*) as cnt, SUM(price) as total
                     FROM api_orders WHERE status='completed'
                     GROUP BY product_name, category_name
                     ORDER BY cnt DESC LIMIT 5""")
        top_api_products = c.fetchall()

        # إيرادات API اليوم
        c.execute("""SELECT COALESCE(SUM(price), 0) FROM api_orders
                     WHERE status='completed'
                     AND DATE(created_at) = DATE('now')""")
        api_revenue_today = c.fetchone()[0] or 0

        # إيرادات API الشهر
        c.execute("""SELECT COALESCE(SUM(price), 0) FROM api_orders
                     WHERE status='completed'
                     AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')""")
        api_revenue_month = c.fetchone()[0] or 0

        # إجمالي API
        c.execute("SELECT COALESCE(SUM(price), 0) FROM api_orders WHERE status='completed'")
        api_revenue_total = c.fetchone()[0] or 0

    return {
        "revenue_today": revenue_today + api_revenue_today,
        "revenue_week": revenue_week,
        "revenue_month": revenue_month + api_revenue_month,
        "revenue_total": revenue_total + api_revenue_total,
        "orders_today": orders_today,
        "orders_month": orders_month,
        "top_products": top_products,
        "top_api_products": top_api_products,
        "top_users": top_users,
    }

def format_sales_analytics_msg():
    """يبني رسالة لوحة الإحصائيات كاملة"""
    s = get_sales_analytics()
    exchange_rate = get_exchange_rate()

    def syp(v):
        return f"{v:,.0f}"
    def usd(v):
        return f"{(v/exchange_rate):.2f}" if exchange_rate > 0 else "0"

    lines = [
        "📊 <b>لوحة إحصائيات المبيعات</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        "💰 <b>الإيرادات:</b>",
        f"  📅 اليوم:   <b>{syp(s['revenue_today'])} ل.س</b>  (~{usd(s['revenue_today'])}$)",
        f"  📆 الشهر:  <b>{syp(s['revenue_month'])} ل.س</b>  (~{usd(s['revenue_month'])}$)",
        f"  🏆 الكل:   <b>{syp(s['revenue_total'])} ل.س</b>  (~{usd(s['revenue_total'])}$)",
        "",
        "📦 <b>الطلبات:</b>",
        f"  📅 اليوم:   <b>{s['orders_today']}</b> طلب",
        f"  📆 الشهر:  <b>{s['orders_month']}</b> طلب",
        "",
    ]

    # أكثر منتجات
    all_top = {}
    for row in s['top_products'] + s['top_api_products']:
        key = f"{row[0]} | {row[1]}"
        if key not in all_top:
            all_top[key] = [0, 0]
        all_top[key][0] += row[2]
        all_top[key][1] += row[3]
    top_sorted = sorted(all_top.items(), key=lambda x: x[1][0], reverse=True)[:5]

    if top_sorted:
        lines.append("🔥 <b>أكثر المنتجات مبيعاً:</b>")
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, (name, (cnt, total)) in enumerate(top_sorted):
            lines.append(f"  {medals[i]} {name}  ←  <b>{cnt}</b> مبيعة  |  <b>{syp(total)}</b> ل.س")
        lines.append("")

    if s['top_users']:
        lines.append("👑 <b>أكثر المستخدمين شراءً:</b>")
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, (uid, cnt, total) in enumerate(s['top_users']):
            lines.append(f"  {medals[i]} <code>{uid}</code>  ←  <b>{cnt}</b> طلب  |  <b>{syp(total)}</b> ل.س")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🕐 آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    return "\n".join(lines)


def get_user_discount(user_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT discount_name, discount_percent FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        if result and result[1] > 0:
            return result[0], result[1]
    return "", 0

def set_user_discount(user_id, discount_name, discount_percent):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET discount_name = ?, discount_percent = ? WHERE user_id = ?", (discount_name, discount_percent, user_id))
        if c.rowcount == 0:
            c.execute("INSERT INTO users (user_id, discount_name, discount_percent) VALUES (?, ?, ?)", (user_id, discount_name, discount_percent))

def remove_user_discount(user_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET discount_name = '', discount_percent = 0 WHERE user_id = ?", (user_id,))


# =============================================================
# رتب الخصم (VIP1...VIPMAX) — نسبها يحددها الأدمن بنفسه
# =============================================================
def get_all_discount_tiers():
    """id, name, percent, sort_order"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, percent, sort_order FROM discount_tiers ORDER BY sort_order, id")
        return c.fetchall()

def get_discount_tier_by_id(tier_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, percent, sort_order FROM discount_tiers WHERE id = ?", (tier_id,))
        return c.fetchone()

def add_discount_tier(name, percent, sort_order=0):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO discount_tiers (name, percent, sort_order) VALUES (?, ?, ?)", (name, percent, sort_order))
        return c.lastrowid

def update_discount_tier(tier_id, name=None, percent=None, sort_order=None):
    with get_db() as conn:
        c = conn.cursor()
        if name is not None:
            c.execute("UPDATE discount_tiers SET name = ? WHERE id = ?", (name, tier_id))
        if percent is not None:
            c.execute("UPDATE discount_tiers SET percent = ? WHERE id = ?", (percent, tier_id))
            # نزامن discount_percent لكل مستخدم بهاد الرتبة فوراً (place_order وكود البوت بيقرؤوا منها مباشرة)
            c.execute("UPDATE users SET discount_percent = ? WHERE discount_tier_id = ?", (percent, tier_id))
        if sort_order is not None:
            c.execute("UPDATE discount_tiers SET sort_order = ? WHERE id = ?", (sort_order, tier_id))

def delete_discount_tier(tier_id):
    with get_db() as conn:
        c = conn.cursor()
        # أي مستخدم بهاد الرتبة يرجع لحالة "بدون رتبة" (0% خصم) بدل ما يبقى مربوط برتبة محذوفة
        c.execute("UPDATE users SET discount_tier_id = 0, discount_name = '', discount_percent = 0 WHERE discount_tier_id = ?", (tier_id,))
        c.execute("DELETE FROM discount_tiers WHERE id = ?", (tier_id,))

def set_user_discount_tier(user_id, tier_id):
    """يعيّن رتبة لمستخدم، ويزامن discount_name/discount_percent تلقائياً للتوافق مع البوت و place_order()."""
    tier = get_discount_tier_by_id(tier_id)
    if not tier:
        return False
    _, name, percent, _ = tier
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET discount_tier_id = ?, discount_name = ?, discount_percent = ? WHERE user_id = ?",
                   (tier_id, name, percent, user_id))
        if c.rowcount == 0:
            c.execute("INSERT INTO users (user_id, discount_tier_id, discount_name, discount_percent) VALUES (?, ?, ?, ?)",
                       (user_id, tier_id, name, percent))
    return True

def get_user_discount_tier(user_id):
    """يرجع (tier_id, tier_name, percent) للمستخدم — None لو ما إله رتبة مخصّصة."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""SELECT u.discount_tier_id, t.name, t.percent
                     FROM users u LEFT JOIN discount_tiers t ON u.discount_tier_id = t.id
                     WHERE u.user_id = ?""", (user_id,))
        row = c.fetchone()
        if row and row[0]:
            return row
    return None

def get_all_users_with_discount():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, discount_name, discount_percent FROM users WHERE discount_percent > 0")
        return c.fetchall()

def broadcast_to_all(message, admin_id):
    users = get_all_users()
    success = 0
    failed = 0
    for user_id in users:
        try:
            send_message(user_id, message)
            success += 1
        except:
            failed += 1
        time.sleep(0.05)
    return success, failed, len(users)

def broadcast_to_user(user_id, message):
    try:
        send_message(user_id, message)
        return True
    except:
        return False

def tg_api(method, data=None, retries=3):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    for i in range(retries):
        try:
            if data:
                r = requests.post(url, json=data, timeout=15)
            else:
                r = requests.get(url, timeout=15)
            try:
                result = r.json()
                if not result.get("ok"):
                    print(f"tg_api [{method}] error: {result.get('error_code')} - {result.get('description')}")
                return result
            except Exception:
                print(f"tg_api: non-JSON response for {method}: {r.text[:200]}")
                return None
        except requests.exceptions.ConnectionError as e:
            print(f"tg_api attempt {i+1} connection error: {e}")
            time.sleep(3)
        except requests.exceptions.Timeout as e:
            print(f"tg_api attempt {i+1} timeout: {e}")
            time.sleep(2)
        except requests.exceptions.RequestException as e:
            print(f"tg_api attempt {i+1} failed: {e}")
            time.sleep(2)
    print(f"tg_api: all retries failed for {method} ❌")
    return None


_BOT_USERNAME_CACHE = {"value": None}

def get_bot_username():
    """يرجع يوزرنيم البوت (مع كاش بالذاكرة) لبناء روابط deep-link متل ربط الحساب."""
    if _BOT_USERNAME_CACHE["value"]:
        return _BOT_USERNAME_CACHE["value"]
    try:
        info = tg_api("getMe")
        username = (info or {}).get("result", {}).get("username")
        if username:
            _BOT_USERNAME_CACHE["value"] = username
            return username
    except Exception as e:
        print(f"get_bot_username error: {e}")
    return None


def safe_callback_data(data):
    """يضمن أن callback_data لا يتجاوز 64 بايت كما يشترط Telegram"""
    encoded = data.encode('utf-8')
    if len(encoded) <= 64:
        return data
    # اختصر الـ data إذا كانت أطول من المسموح
    return encoded[:64].decode('utf-8', errors='ignore')

def send_message(chat_id, text, reply_markup=None, photo=None):
    # صور الموقع غالباً روابط محلية مثل /uploads/... لا يستطيع Telegram جلبها.
    # البوت يعرض الكتالوج نصياً دائماً حتى لا تتعطل الأزرار بسبب صورة غير صالحة.
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    result = tg_api("sendMessage", data)
    if result and not result.get("ok"):
        data.pop("parse_mode", None)
        result = tg_api("sendMessage", data)
    return result

def edit_message(chat_id, message_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    result = tg_api("editMessageText", data)
    if result and not result.get("ok"):
        data.pop("parse_mode", None)
        result = tg_api("editMessageText", data)
    return result

def answer_callback(callback_id):
    return tg_api("answerCallbackQuery", {"callback_query_id": callback_id})

def delete_message(chat_id, message_id):
    return tg_api("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

def _unwrap_api_response(raw):
    """
    يحوّل أي هيكل رد API إلى البيانات الفعلية.
    يدعم:
      - raw نفسه (list أو dict مباشر)
      - {"status":"OK/success/true", "data": ...}
      - {"result": ...}
      - {"response": ...}
      - {"items": ...}
      - {"products": ...}
      - {"orders": ...}
    """
    if raw is None:
        return None
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        # إذا كان الرد يحمل خطأ واضح
        if raw.get("error") is True:
            return raw
        # حاول استخراج البيانات من حقول شائعة
        for key in ("data", "result", "response", "items", "products", "orders", "Data", "Result"):
            val = raw.get(key)
            if val is not None:
                return val
        return raw
    return raw


def api_request(endpoint, params=None, api_token=None, api_base_url=None,
                method="GET", body=None):
    """
    طلب API عالمي - يشتغل مع أي مزود في العالم.

    يجرب تلقائياً عدة طرق مصادقة:
      1. Header: api-token
      2. Header: Authorization: Bearer
      3. Header: token
      4. Query param: api_key / token / key
    """
    token = api_token if (api_token is not None and api_token != '') else API_TOKEN
    base  = api_base_url if (api_base_url is not None and api_base_url != '') else API_BASE_URL

    if base and not base.endswith('/'):
        base = base + '/'

    # إذا كان endpoint يحمل http كامل لا نضيف الـ base
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        url = endpoint
    else:
        url = base + endpoint

    auth_attempts = [
        # (headers, extra_params)
        ({"api-token": token, "Content-Type": "application/json"}, {}),
        ({"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, {}),
        ({"token": token, "Content-Type": "application/json"}, {}),
        ({"X-Api-Key": token, "Content-Type": "application/json"}, {}),
        ({}, {"api_key": token}),
        ({}, {"token": token}),
        ({}, {"key": token}),
    ]

    last_result = None
    for headers, extra_params in auth_attempts:
        merged_params = {}
        if params:
            merged_params.update(params)
        if extra_params:
            merged_params.update(extra_params)
        try:
            if method.upper() == "POST":
                r = requests.post(url, headers=headers,
                                  params=merged_params if merged_params else None,
                                  json=body, timeout=30)
            else:
                r = requests.get(url, headers=headers,
                                 params=merged_params if merged_params else None,
                                 timeout=30)

            if r.status_code == 200:
                try:
                    return r.json()
                except Exception:
                    return {"error": True, "status": 200, "text": r.text[:500]}

            if r.status_code == 401:
                # هذه المصادقة مش صح، جرب التالية
                try:
                    last_result = r.json()
                except Exception:
                    last_result = {"error": True, "status": 401}
                continue

            # أي كود آخر (400, 404, 500...) → أرجع الرد كما هو
            try:
                return r.json()
            except Exception:
                return {"error": True, "status": r.status_code, "text": r.text[:500]}

        except requests.exceptions.SSLError as e:
            # SSL error: جرب بدون verify
            try:
                if method.upper() == "POST":
                    r = requests.post(url, headers=headers,
                                      params=merged_params if merged_params else None,
                                      json=body, timeout=30, verify=False)
                else:
                    r = requests.get(url, headers=headers,
                                     params=merged_params if merged_params else None,
                                     timeout=30, verify=False)
                if r.status_code == 200:
                    try:
                        return r.json()
                    except Exception:
                        pass
            except Exception:
                pass
            last_result = {"error": True, "message": f"SSL: {str(e)}"}
            continue
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            return {"error": True, "message": str(e)}
        except Exception as e:
            last_result = {"error": True, "message": str(e)}
            continue

    return last_result or {"error": True, "message": "فشلت جميع طرق المصادقة"}

def get_profile(api_token=None, api_base_url=None):
    """
    يجلب بروفايل المزود - يدعم أي هيكل رد.
    يجرب عدة endpoints شائعة حتى ينجح.
    """
    endpoints = [
        "client/api/profile",
        "api/profile",
        "profile",
        "client/profile",
        "api/user",
        "user",
        "api/account",
        "account",
        "api/balance",
        "balance",
        "api/v1/profile",
        "v1/profile",
        "api/me",
        "me",
    ]
    for ep in endpoints:
        try:
            result = api_request(ep, api_token=api_token, api_base_url=api_base_url)
            if not isinstance(result, dict):
                continue
            if result.get("error") is True:
                continue
            # استخرج البيانات الفعلية
            data = _unwrap_api_response(result)
            if not isinstance(data, dict):
                data = result

            # ابحث عن أي حقل يدل على نجاح الربط
            balance_keys = ["balance", "Balance", "credit", "Credit", "wallet", "funds", "amount"]
            has_balance = any(k in data for k in balance_keys) or any(k in result for k in balance_keys)
            status_ok = str(result.get("status", "")).lower() in ["ok", "success", "true", "1", "active"]
            has_email = "email" in data or "email" in result
            has_name = "name" in data or "username" in data or "name" in result or "username" in result

            if has_balance or status_ok or has_email or has_name:
                # وحّد الرد: أرجع dict يحتوي على balance و email على الأقل
                merged = {}
                merged.update(result)
                merged.update(data)
                # حوّل balance إلى أي مفتاح شائع
                for k in balance_keys:
                    if k in merged:
                        merged["balance"] = merged[k]
                        break
                if "balance" not in merged:
                    merged["balance"] = "غير محدد"
                if "email" not in merged:
                    merged["email"] = merged.get("username") or merged.get("name") or "غير محدد"
                return merged
        except Exception:
            continue
    return None

def get_all_api_products(api_token=None, api_base_url=None):
    """
    يجلب جميع منتجات المزود - يشتغل مع كل المزودين في العالم.
    يجرب عدة endpoints ويدعم أي هيكل رد.
    """
    endpoints = [
        "client/api/products",
        "api/products",
        "products",
        "client/products",
        "api/services",
        "services",
        "api/v1/products",
        "v1/products",
        "api/items",
        "items",
        "api/catalog",
        "catalog",
    ]

    def extract_products(raw):
        """يستخرج قائمة المنتجات من أي هيكل رد"""
        if raw is None:
            return []
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        if isinstance(raw, dict):
            if raw.get("error") is True:
                return []
            # جرب حقول شائعة
            for key in ("data", "products", "services", "items", "result",
                        "results", "response", "catalog", "list", "Data",
                        "Products", "Services", "Items"):
                val = raw.get(key)
                if isinstance(val, list):
                    return [item for item in val if isinstance(item, dict)]
                if isinstance(val, dict):
                    # قد يكون {"data": {"products": [...]}}
                    for k2 in ("products", "services", "items", "list"):
                        v2 = val.get(k2)
                        if isinstance(v2, list):
                            return [item for item in v2 if isinstance(item, dict)]
        return []

    for ep in endpoints:
        try:
            result = api_request(ep, api_token=api_token, api_base_url=api_base_url)
            products = extract_products(result)
            if products:
                # تأكد من وجود حقل id أو ID في كل منتج (normalize)
                normalized = []
                for p in products:
                    if "id" not in p:
                        for alt in ("ID", "product_id", "productId", "service_id", "serviceId"):
                            if alt in p:
                                p["id"] = p[alt]
                                break
                    if "name" not in p:
                        for alt in ("Name", "title", "Title", "product_name", "service_name"):
                            if alt in p:
                                p["name"] = p[alt]
                                break
                    normalized.append(p)
                return normalized
        except Exception:
            continue
    return []

def search_api_products(search_term, api_token=None, api_base_url=None):
    """يبحث في منتجات المزود باسم المنتج"""
    all_products = get_all_api_products(api_token=api_token, api_base_url=api_base_url)
    matches = []
    for item in all_products:
        name = item.get("name", "").lower()
        if search_term.lower() in name:
            matches.append(item)
    return matches

def get_api_product_by_id(api_product_id, api_token=None, api_base_url=None):
    """
    يجلب منتج محدد بالـ ID من المزود.
    يعمل مع جميع المزودين (Techno Rex والمبرمجين العاديين):
    - أولاً: يجرب endpoint الفلتر المباشر (سريع مع Techno Rex)
    - ثانياً: يجلب كل المنتجات ويبحث بالـ ID (يشتغل مع الكل)
    - لا يرجع أول منتج أبداً كاحتياط لأنه سبب المشكلة
    """
    # المرحلة 1: نجرب جلب المنتج بفلتر الـ ID مباشرة
    result = api_request(
        f"client/api/products?products_id={api_product_id}",
        api_token=api_token, api_base_url=api_base_url
    )
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and str(item.get("id")) == str(api_product_id):
                return item  # تطابق بالـ ID ← المنتج الصحيح

    # المرحلة 2: الفلتر ما اشتغل ← نجلب كل المنتجات ونبحث بالـ ID
    all_products = get_all_api_products(api_token=api_token, api_base_url=api_base_url)
    for item in all_products:
        if str(item.get("id")) == str(api_product_id):
            return item  # وجدنا التطابق الصحيح

    # ما لقينا أي منتج بهاد الـ ID ← نرجع None بدل أول منتج غلط
    return None

def get_telegram_user_info(user_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChat"
    data = {"chat_id": user_id}
    try:
        r = requests.post(url, json=data, timeout=10)
        result = r.json()
        if result.get("ok"):
            chat = result.get("result", {})
            first_name = chat.get("first_name", "")
            last_name = chat.get("last_name", "")
            username = chat.get("username", "")
            full_name = f"{first_name} {last_name}".strip()
            return {
                "name": full_name if full_name else first_name,
                "user_id": user_id,
                "username": f"@{username}" if username else "لا يوجد"
            }
    except:
        pass
    return {"name": "مستخدم", "user_id": user_id, "username": "لا يوجد"}

def get_user_orders(user_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT product_name, category_name, price, player_id, qty, status, created_at FROM shop_orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        return c.fetchall()

def get_user_deposits(user_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT method_title, amount_syp, transaction_code, status, created_at FROM deposit_requests WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        return c.fetchall()

def register_new_user(user_id, username, full_name):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        exists = c.fetchone()
        if not exists:
            c.execute("INSERT INTO users (user_id, balance, is_admin, blocked) VALUES (?, 0, 0, 0)", (user_id,))
            welcome_msg = (f"<b>عضو جديد انضم لبوتك الفاخر:</b>\n"
                           f"<b>الاسم: {full_name}</b>\n"
                           f"<b>الايدي: {user_id}</b>\n"
                           f"<b>يوزر: {username}</b>\n"
                           f"<b>شرفت ونورت البوت 🎉❤</b>")
            send_message(ADMIN_CHAT_ID, welcome_msg)
            return True
    return False

# ===== لوحات المفاتيح =====

def get_main_keyboard(is_admin_user=False):
    keyboard = []
    sections = get_all_sections()
    row = []
    for section in sections:
        sec_id, sec_name, color, emoji, is_active = section
        button = {"text": sec_name, "style": color}
        row.append(button)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([
        {"text": "تعبئة رصيد 🏦", "style": "primary"},
        {"text": "الحساب والمعلومات 🗂️", "style": "primary"}
    ])
    keyboard.append([{"text": "حساب الإدارة 💬", "style": "danger"}])
    if is_admin_user:
        keyboard.append([{"text": "🛡️ لوحة التحكم"}])
    return {"keyboard": keyboard, "resize_keyboard": True, "one_time_keyboard": False}

def get_main_inline_keyboard(is_admin_user=False):
    keyboard = {"inline_keyboard": []}
    sections = get_all_sections()
    row = []
    for section in sections:
        sec_id, sec_name, color, emoji, is_active = section
        row.append({"text": sec_name, "callback_data": safe_callback_data(f"inline_section_{sec_id}"), "color": color})
        if len(row) == 2:
            keyboard["inline_keyboard"].append(row)
            row = []
    if row:
        keyboard["inline_keyboard"].append(row)
    keyboard["inline_keyboard"].append([
        {"text": "تعبئة رصيد 🏦", "callback_data": "inline_deposit"},
        {"text": "الحساب والمعلومات 🗂️", "callback_data": "inline_account"}
    ])
    keyboard["inline_keyboard"].append([{"text": "حساب الإدارة 💬", "callback_data": "inline_support"}])
    if is_admin_user:
        keyboard["inline_keyboard"].append([{"text": "🛡️ لوحة التحكم", "callback_data": "inline_admin_panel"}])
    return keyboard

def send_main_menu(chat_id, user_id):
    is_admin_user = is_admin(user_id)
    if button_mode == 'inline':
        keyboard = get_main_inline_keyboard(is_admin_user)
        send_message(chat_id, welcome_message, reply_markup=keyboard)
    else:
        # وضع الـ reply keyboard: نرسل الكيبورد دائماً مع رسالة الترحيب
        kb = get_main_keyboard(is_admin_user)
        # نرسل رسالة منفصلة لتهيئة الكيبورد أولاً إذا كان المستخدم جديداً
        send_message(chat_id, welcome_message, reply_markup=kb)

def get_products_buttons(category):
    products = get_products_by_category(category)
    if not products:
        return None, f"🚫 لا توجد منتجات في {category}"
    section_color = get_section_color(category)
    keyboard = {"inline_keyboard": []}
    row = []
    for product in products:
        product_id, product_name, emoji = product
        display_name = f"{emoji} {product_name}" if emoji else product_name
        row.append({"text": display_name, "callback_data": safe_callback_data(f"show_product_{product_id}"), "style": section_color})
        if len(row) == 2:
            keyboard["inline_keyboard"].append(row)
            row = []
    if row:
        keyboard["inline_keyboard"].append(row)
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع للقائمة", "callback_data": "back_main"}])
    description = get_category_description(category)
    return keyboard, description

def get_categories_buttons(product_id, product_name):
    categories = get_categories_by_product(product_id)
    if not categories:
        return None, f"🚫 لا توجد فئات لهذا المنتج: {product_name}"
    keyboard = {"inline_keyboard": []}
    for cat in categories:
        cat_id, cat_name, price_usd, cat_type, min_qty, max_qty = cat
        if cat_type == 'counter':
            display_text = f"{cat_name} (عداد)"
        elif cat_type == 'limited':
            display_text = f"{cat_name} (كمية محددة)"
        else:
            display_text = cat_name
        keyboard["inline_keyboard"].append([{"text": display_text, "callback_data": safe_callback_data(f"category_{cat_id}")}])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "back_to_products"}])
    product_description = get_product_description(product_id)
    msg = product_description if product_description else f"📦 {product_name}:"
    return keyboard, msg

def get_deposit_methods_buttons():
    manual_methods = get_all_deposit_methods()
    auto_methods = get_all_auto_deposit_methods()
    if not manual_methods and not auto_methods:
        return None, "🚫 لا توجد طرق إيداع حالياً"
    keyboard = {"inline_keyboard": []}
    for method in manual_methods:
        method_id, title = method[0], method[1]
        keyboard["inline_keyboard"].append([{"text": title, "callback_data": safe_callback_data(f"deposit_{method_id}")}])
    for method in auto_methods:
        mid, title = method[0], method[1]
        keyboard["inline_keyboard"].append([{"text": f"⚡ {title} (تلقائي)", "callback_data": safe_callback_data(f"auto_deposit_{mid}")}])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "back_main"}])
    return keyboard, "💰 اختر طريقة الإيداع:"

def get_deposit_method_details(method_id):
    method = get_deposit_method_by_id(method_id)
    if not method:
        return None, None
    mid, title, description, code, exchange_rate = method[0], method[1], method[2], method[3], method[4]
    image = method[5] if len(method) > 5 else ""
    msg = f"{description}\n--------------------------------\n<code>{code}</code>\n--------------------------------\n"
    msg += f"كل 1$ = {exchange_rate:,.2f} ليرة سورية\n--------------------------------\nارسل قيمة المبلغ بالليرة السورية:"
    return msg, image

def get_auto_deposit_method_details(method_id):
    method = get_auto_deposit_method_by_id(method_id)
    if not method:
        return None, None, None, None
    mid, title, description, code, exchange_rate, api_token, api_url, image, gateway_type = method
    msg = f"{description}\n--------------------------------\n<code>{code}</code>\n--------------------------------\n"
    msg += f"كل 1$ = {exchange_rate:,.2f} ليرة سورية\n--------------------------------\nارسل قيمة المبلغ بالليرة السورية:"
    return msg, image, api_token, api_url

def get_check_subscription_keyboard():
    channels = get_all_required_channels()
    keyboard = {"inline_keyboard": []}
    for channel in channels:
        ch_id, ch_username = channel
        keyboard["inline_keyboard"].append([{"text": ch_username, "url": f"https://t.me/{ch_username.replace('@', '')}"}])
    keyboard["inline_keyboard"].append([{"text": "🔄 تحقق الاشتراك", "callback_data": "check_sub", "color": "success"}])
    return keyboard

# ===== لوحات التحكم للأدمن =====

def get_admin_main_keyboard():
    return {"inline_keyboard": [
        [{"text": "📂 إدارة الأقسام", "callback_data": "sections_management"},
         {"text": "🔐 إدارة API", "callback_data": "admin_api"}],
        [{"text": "📦 إدارة المنتجات", "callback_data": "admin_products"}],
        [{"text": "💳 إدارة الايداعات", "callback_data": "deposit_management"},
         {"text": "👥 إدارة المستخدمين", "callback_data": "user_management"}],
        [{"text": "🎁 إدارة الخصومات", "callback_data": "discount_management"}],
        [{"text": "💲 تعديل الأسعار", "callback_data": "edit_prices_menu"}],
        [{"text": "📢 إدارة الاشتراك الاجباري", "callback_data": "subscription_management"}],
        [{"text": "📣 الاذاعة", "callback_data": "broadcast_menu"},
         {"text": "⚙️ الاعدادات الاساسية", "callback_data": "basic_settings"}],
        [{"text": "🔄 الاعدادات العامة", "callback_data": "general_settings"}],
        [{"text": "💰 تعديل سعر صرف", "callback_data": "edit_exchange_rate"}],
        [{"text": "📊 إحصائيات المبيعات", "callback_data": "sales_analytics"}],
        [{"text": "🔙 رجوع", "callback_data": "back_main"}]
    ]}

def get_admin_products_keyboard():
    return {"inline_keyboard": [
        [{"text": "➕ إضافة منتج", "callback_data": "add_product"},
         {"text": "🗑 حذف منتج", "callback_data": "delete_product_menu"}],
        [{"text": "📂 إضافة فئة", "callback_data": "add_category_menu"},
         {"text": "🗑 حذف فئة", "callback_data": "delete_category_menu"}],
        [{"text": "🖼️ صور المنتجات", "callback_data": "manage_images"},
         {"text": "🖼️ صور الفئات", "callback_data": "manage_category_images_prod"}],
        [{"text": "📝 وصف المنتجات", "callback_data": "product_description_menu"},
         {"text": "📝 وصف الأقسام", "callback_data": "manage_description"}],
        [{"text": "➕ إضافة فئة عداد", "callback_data": "add_counter_category"},
         {"text": "➕ فئة (كمية محددة)", "callback_data": "add_limited_category"}],
        [{"text": "🔙 رجوع", "callback_data": "back_admin"}]
    ]}

def get_sections_management_keyboard():
    sections = get_all_sections()
    keyboard = {"inline_keyboard": []}
    keyboard["inline_keyboard"].append([{"text": "➕ إضافة قسم", "callback_data": "add_section"}])
    for section in sections:
        sec_id, sec_name, color, emoji, is_active = section
        has_img = "🖼️✅" if get_section_image_by_id(sec_id) else "🖼️➕"
        keyboard["inline_keyboard"].append([
            {"text": f"✏️ {sec_name}", "callback_data": safe_callback_data(f"rename_section_{sec_id}")},
            {"text": f"🗑 حذف", "callback_data": safe_callback_data(f"delete_section_{sec_id}")},
            {"text": f"🎨 لون", "callback_data": safe_callback_data(f"color_section_{sec_id}")},
            {"text": f"{has_img} صورة", "callback_data": safe_callback_data(f"section_img_{sec_id}")}
        ])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "back_admin"}])
    return keyboard, "📂 إدارة الأقسام:"

def get_color_selection_keyboard(section_id):
    return {"inline_keyboard": [
        [{"text": "🟢 اخضر", "callback_data": safe_callback_data(f"set_color_{section_id}_success")}],
        [{"text": "🔴 احمر", "callback_data": safe_callback_data(f"set_color_{section_id}_danger")}],
        [{"text": "🔵 ازرق", "callback_data": safe_callback_data(f"set_color_{section_id}_primary")}],
        [{"text": "🔙 رجوع", "callback_data": "sections_management"}]
    ]}

def get_products_for_image_menu():
    products = get_all_products()
    if not products:
        return None, "🚫 لا توجد منتجات"
    keyboard = {"inline_keyboard": []}
    for product in products:
        product_id, name, category, emoji, desc, img = product
        display_name = f"{emoji} {name}" if emoji else name
        has_img = "✅" if img else "➕"
        keyboard["inline_keyboard"].append([{"text": f"{has_img} {display_name} ({category})", "callback_data": safe_callback_data(f"image_product_{product_id}")}])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "admin_products"}])
    return keyboard, "🖼️ اختر المنتج لإضافة/تعديل صورته:"

def get_categories_for_image_menu(back_target="admin_products"):
    products = get_all_products()
    if not products:
        return None, "🚫 لا توجد منتجات"
    keyboard = {"inline_keyboard": []}
    for product in products:
        product_id = product[0]
        name = product[1]
        emoji = product[3]
        cats = get_categories_by_product(product_id)
        for cat in cats:
            cat_id = cat[0]
            cat_name = cat[1]
            display = f"{emoji} {name}" if emoji else name
            cat_img = get_category_image_by_id(cat_id)
            has_img = "✅" if cat_img else "➕"
            keyboard["inline_keyboard"].append([{"text": f"{has_img} {display} - {cat_name}", "callback_data": safe_callback_data(f"cat_img_{cat_id}")}])
    if not keyboard["inline_keyboard"]:
        return None, "🚫 لا توجد فئات"
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": back_target}])
    return keyboard, "🖼️ اختر الفئة لإضافة/تعديل صورتها:"

def get_delete_category_menu():
    products = get_all_products()
    if not products:
        return None, "🚫 لا توجد منتجات"
    keyboard = {"inline_keyboard": []}
    for product in products:
        product_id, name, category, emoji, desc, img = product
        categories = get_categories_by_product(product_id)
        for cat in categories:
            cat_id, cat_name, price_usd, cat_type, min_qty, max_qty = cat
            keyboard["inline_keyboard"].append([{"text": f"🗑 {name} - {cat_name}", "callback_data": safe_callback_data(f"delete_category_{cat_id}")}])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "admin_products"}])
    return keyboard, "اختر الفئة لحذفها:"

def get_products_for_category_menu():
    products = get_all_products()
    if not products:
        return None, "🚫 لا توجد منتجات"
    keyboard = {"inline_keyboard": []}
    for product in products:
        product_id, name, category, emoji, desc, img = product
        display_name = f"{emoji} {name}" if emoji else name
        keyboard["inline_keyboard"].append([{"text": f"{display_name} ({category})", "callback_data": safe_callback_data(f"select_product_{product_id}")}])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "admin_products"}])
    return keyboard, "اختر المنتج:"

def get_delete_products_menu():
    products = get_all_products()
    if not products:
        return None, "🚫 لا توجد منتجات"
    keyboard = {"inline_keyboard": []}
    for product in products:
        product_id, name, category, emoji, desc, img = product
        display_name = f"{emoji} {name}" if emoji else name
        keyboard["inline_keyboard"].append([{"text": f"🗑 {display_name} ({category})", "callback_data": safe_callback_data(f"delete_product_{product_id}")}])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "admin_products"}])
    return keyboard, "اختر المنتج لحذفه:"

def get_products_for_product_desc_menu():
    products = get_all_products()
    if not products:
        return None, "🚫 لا توجد منتجات"
    keyboard = {"inline_keyboard": []}
    for product in products:
        product_id, name, category, emoji, desc, img = product
        display_name = f"{emoji} {name}" if emoji else name
        keyboard["inline_keyboard"].append([{"text": f"📝 {display_name} ({category})", "callback_data": safe_callback_data(f"desc_product_{product_id}")}])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "admin_products"}])
    return keyboard, "اختر المنتج لإضافة وصف له:"

def get_description_management_keyboard():
    sections = get_all_sections()
    keyboard = {"inline_keyboard": []}
    for section in sections:
        sec_id, sec_name, color, emoji, is_active = section
        keyboard["inline_keyboard"].append([{"text": f"📝 {sec_name}", "callback_data": safe_callback_data(f"desc_section_{sec_id}")}])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "admin_products"}])
    return keyboard

def get_link_products_menu():
    keyboard = {"inline_keyboard": []}
    sections = get_all_sections()
    for section in sections:
        sec_id, sec_name, color, emoji, is_active = section
        keyboard["inline_keyboard"].append([{"text": f"📁 {sec_name}", "callback_data": safe_callback_data(f"link_section_{sec_id}")}])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "admin_api"}])
    return keyboard, "اختر القسم لربط المنتجات:"

def get_unlink_products_menu():
    linked = get_linked_products()
    if not linked:
        return None, "🚫 لا توجد منتجات مرتبطة"
    keyboard = {"inline_keyboard": []}
    for link in linked:
        link_id = link[0]
        product_name = link[4] or "منتج محذوف"
        category_name = link[5] or "فئة محذوفة"
        provider_name = link[10] if len(link) > 10 and link[10] else "مزود"
        # نقصر النص لضمان أن callback_data لا يتجاوز 64 بايت
        short_product = (product_name[:10] + "…") if len(product_name) > 10 else product_name
        short_cat = (category_name[:10] + "…") if len(category_name) > 10 else category_name
        short_prov = (provider_name[:8] + "…") if len(provider_name) > 8 else provider_name
        btn_text = f"🔓 {short_product} | {short_cat} [{short_prov}]"
        cb_data = f"do_unlink_{link_id}"  # callback_data قصير دائماً (رقم فقط)
        keyboard["inline_keyboard"].append([{"text": btn_text, "callback_data": cb_data}])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "admin_api"}])
    return keyboard, f"🔗 المنتجات المرتبطة ({len(linked)}):\nاضغط على منتج لفك ربطه:"

def get_providers_select_keyboard(action_prefix, extra_data=""):
    """لوحة اختيار المزود لعمليات الربط"""
    providers = get_all_api_providers()
    if not providers:
        return None, "🚫 لا يوجد مزودين. أضف مزوداً أولاً من إدارة API."
    keyboard = {"inline_keyboard": []}
    for p in providers:
        pid, pname, ptoken, purl = p
        sep = "_" if extra_data else ""
        keyboard["inline_keyboard"].append([
            {"text": f"🔌 {pname}", "callback_data": safe_callback_data(f"{action_prefix}{pid}{sep}{extra_data}")}
        ])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "admin_api"}])
    return keyboard, "🔌 اختر المزود:"

def get_providers_management_keyboard():
    providers = get_all_api_providers()
    count = len(providers)
    remaining = 10000 - count
    keyboard = {"inline_keyboard": []}

    if remaining > 0:
        keyboard["inline_keyboard"].append([
            {"text": f"➕ إضافة مزود جديد  ({remaining} متبقي)", "callback_data": "add_provider"}
        ])
    else:
        keyboard["inline_keyboard"].append([
            {"text": "🔴 الحد الأقصى (10000/10000) — احذف مزوداً للإضافة", "callback_data": "providers_management"}
        ])

    for p in providers:
        pid, pname, ptoken, purl = p
        short_url = purl.replace("https://", "").replace("http://", "").rstrip("/")
        short_url = (short_url[:22] + "…") if len(short_url) > 22 else short_url
        keyboard["inline_keyboard"].append([
            {"text": f"🔌 {pname}", "callback_data": safe_callback_data(f"test_provider_{pid}")},
            {"text": "🔬 اختبار", "callback_data": safe_callback_data(f"test_provider_{pid}")}
        ])
        keyboard["inline_keyboard"].append([
            {"text": f"✏️ تعديل الاسم", "callback_data": safe_callback_data(f"edit_provider_{pid}")},
            {"text": f"🗑 حذف", "callback_data": safe_callback_data(f"delete_provider_{pid}")}
        ])

    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع لإدارة API", "callback_data": "admin_api"}])

    msg_lines = [
        "🔐 <b>إدارة مزودي API</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📊 المزودون النشطون: <b>{count}/10000</b>",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    if providers:
        for i, p in enumerate(providers, 1):
            pid, pname, ptoken, purl = p
            short_url = purl.replace("https://", "").replace("http://", "").rstrip("/")
            short_url = (short_url[:30] + "…") if len(short_url) > 30 else short_url
            masked_token = (ptoken[:6] + "…" + ptoken[-4:]) if ptoken and len(ptoken) > 10 else "غير محدد"
            msg_lines.append(f"<b>{i}. {pname}</b>")
            msg_lines.append(f"   🌐 {short_url}")
            msg_lines.append(f"   🔑 {masked_token}")
    else:
        msg_lines.append("⚠️ لا يوجد مزودون. أضف مزوداً للبدء.")

    msg_lines.append("━━━━━━━━━━━━━━━━━━━━")
    msg_lines.append("💡 اضغط على اسم المزود لاختباره")
    return keyboard, "\n".join(msg_lines)

def get_related_products_admin_keyboard():
    """لوحة إدارة المنتجات المرتبطة"""
    keyboard = {"inline_keyboard": [
        [{"text": "➕ إضافة منتج مرتبط", "callback_data": "add_related_product"}],
        [{"text": "🗑 حذف منتج مرتبط", "callback_data": "delete_related_product_menu"}],
        [{"text": "📋 عرض جميع المرتبطة", "callback_data": "list_related_products"}],
        [{"text": "🔙 رجوع", "callback_data": "admin_api"}]
    ]}
    return keyboard, "📋 إدارة عرض المنتجات المرتبطة:"

def get_user_management_keyboard():
    return {"inline_keyboard": [
        [{"text": "🟢 اضافة رصيد", "callback_data": "add_balance"}],
        [{"text": "🔴 خصم رصيد", "callback_data": "deduct_balance"}],
        [{"text": "👑 اضافة ادمن", "callback_data": "add_admin"}],
        [{"text": "🗑 حذف ادمن", "callback_data": "remove_admin"}],
        [{"text": "🔍 كشف مستخدم", "callback_data": "user_info"}],
        [{"text": "🚫 حظر عضو", "callback_data": "block_user"},
         {"text": "🔓 فك حظر", "callback_data": "unblock_user"}],
        [{"text": "📊 احصائية عامة", "callback_data": "general_stats"}],
        [{"text": "🔙 رجوع", "callback_data": "back_admin"}]
    ]}

def get_discount_management_keyboard():
    return {"inline_keyboard": [
        [{"text": "🎁 اضافة خصم لمستخدم", "callback_data": "add_discount"}],
        [{"text": "🗑 حذف خصم لمستخدم", "callback_data": "remove_discount"}],
        [{"text": "👥 عرض المستخدمين (المميزين)", "callback_data": "list_discount_users"}],
        [{"text": "🔙 رجوع", "callback_data": "back_admin"}]
    ]}

def get_subscription_management_keyboard():
    channels = get_all_required_channels()
    keyboard = {"inline_keyboard": []}
    keyboard["inline_keyboard"].append([{"text": "➕ اضافة قناة اشتراك", "callback_data": "add_channel"}])
    for channel in channels:
        ch_id, ch_username = channel
        keyboard["inline_keyboard"].append([{"text": f"🗑 حذف {ch_username}", "callback_data": safe_callback_data(f"delete_channel_{ch_id}")}])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "back_admin"}])
    return keyboard, "📢 إدارة الاشتراك الاجباري:"

def get_broadcast_keyboard():
    return {"inline_keyboard": [
        [{"text": "📢 اذاعة عامة", "callback_data": "broadcast_all"}],
        [{"text": "👤 اذاعة لمستخدم", "callback_data": "broadcast_user"}],
        [{"text": "🔙 رجوع", "callback_data": "back_admin"}]
    ]}

def get_deposit_management_keyboard():
    return {"inline_keyboard": [
        [{"text": "➕ إضافة طريقة ايداع (يدوي)", "callback_data": "add_deposit"},
         {"text": "⚡ إضافة طريقة ايداع (تلقائي)", "callback_data": "add_auto_deposit"}],
        [{"text": "✏️ تعديل طريقة يدوي", "callback_data": "edit_deposit"},
         {"text": "✏️ تعديل طريقة تلقائي", "callback_data": "edit_auto_deposit_menu"}],
        [{"text": "🗑 حذف طريقة ايداع (يدوي)", "callback_data": "delete_deposit"},
         {"text": "🗑 حذف طريقة ايداع (تلقائي)", "callback_data": "delete_auto_deposit_menu"}],
        [{"text": "🖼️ صور طرق الايداع", "callback_data": "manage_deposit_images"}],
        [{"text": "🔙 رجوع", "callback_data": "back_admin"}]
    ]}

def get_auto_deposit_methods_for_delete():
    methods = get_all_auto_deposit_methods()
    if not methods:
        return None, "🚫 لا توجد طرق ايداع تلقائي"
    keyboard = {"inline_keyboard": []}
    for method in methods:
        mid, title = method[0], method[1]
        keyboard["inline_keyboard"].append([{"text": f"🗑 {title}", "callback_data": safe_callback_data(f"delete_auto_method_{mid}")}])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "deposit_management"}])
    return keyboard, "اختر طريقة الإيداع التلقائي لحذفها:"

def get_auto_deposit_methods_for_edit():
    methods = get_all_auto_deposit_methods()
    if not methods:
        return None, "🚫 لا توجد طرق ايداع تلقائي للتعديل"
    keyboard = {"inline_keyboard": []}
    for method in methods:
        mid, title = method[0], method[1]
        keyboard["inline_keyboard"].append([{"text": f"✏️ {title}", "callback_data": safe_callback_data(f"edit_auto_method_{mid}")}])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "deposit_management"}])
    return keyboard, "اختر طريقة الإيداع التلقائي لتعديلها:"

def get_deposit_methods_for_image_menu():
    manual = get_all_deposit_methods()
    auto = get_all_auto_deposit_methods()
    if not manual and not auto:
        return None, "🚫 لا توجد طرق إيداع"
    keyboard = {"inline_keyboard": []}
    for m in manual:
        mid, title = m[0], m[1]
        keyboard["inline_keyboard"].append([{"text": f"🖼️ {title} (يدوي)", "callback_data": safe_callback_data(f"dep_img_{mid}")}])
    for m in auto:
        mid, title = m[0], m[1]
        keyboard["inline_keyboard"].append([{"text": f"🖼️ {title} (تلقائي)", "callback_data": safe_callback_data(f"auto_dep_img_{mid}")}])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "deposit_management"}])
    return keyboard, "اختر طريقة الإيداع لإضافة/تعديل صورتها:"

def get_deposit_methods_for_edit():
    methods = get_all_deposit_methods()
    if not methods:
        return None, "🚫 لا توجد طرق إيداع"
    keyboard = {"inline_keyboard": []}
    for method in methods:
        method_id, title = method[0], method[1]
        keyboard["inline_keyboard"].append([{"text": f"✏️ {title}", "callback_data": safe_callback_data(f"edit_method_{method_id}")}])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "deposit_management"}])
    return keyboard, "اختر طريقة الإيداع لتعديلها:"

def get_deposit_methods_for_delete():
    methods = get_all_deposit_methods()
    if not methods:
        return None, "🚫 لا توجد طرق إيداع"
    keyboard = {"inline_keyboard": []}
    for method in methods:
        method_id, title = method[0], method[1]
        keyboard["inline_keyboard"].append([{"text": f"🗑 {title}", "callback_data": safe_callback_data(f"delete_method_{method_id}")}])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "deposit_management"}])
    return keyboard, "اختر طريقة الإيداع لحذفها:"

def get_general_settings_keyboard():
    status_text = "🟢 تشغيل" if bot_enabled else "🔴 ايقاف"
    btn_mode_text = "🔲 تحويل إلى أزرار شفافة" if button_mode == 'reply' else "⌨️ تحويل إلى كيبورد عادي"
    uname = get_support_username()
    return {"inline_keyboard": [
        [{"text": f"{status_text} البوت", "callback_data": "toggle_bot"}],
        [{"text": "✏️ تغيير رسالة الترحيب", "callback_data": "change_welcome"}],
        [{"text": btn_mode_text, "callback_data": "toggle_button_type"}],
        [{"text": f"💬 يوزر الدعم: @{uname}", "callback_data": "change_support_username"}],
        [{"text": "🔙 رجوع", "callback_data": "back_admin"}]
    ]}

def get_basic_settings_keyboard():
    ref_enabled, ref_amount = get_referral_settings()
    ref_status = "🟢 مفعّل" if ref_enabled else "🔴 معطّل"
    return {"inline_keyboard": [
        [{"text": "✏️ تعديل اسماء الاقسام", "callback_data": "rename_sections"}],
        [{"text": f"🔗 نظام الإحالة ({ref_status})", "callback_data": "referral_settings"}],
        [{"text": "🔙 رجوع", "callback_data": "back_admin"}]
    ]}

def get_rename_sections_menu():
    sections = get_all_sections()
    if not sections:
        return None, "🚫 لا توجد اقسام"
    keyboard = {"inline_keyboard": []}
    for section in sections:
        sec_id, sec_name, color, emoji, is_active = section
        keyboard["inline_keyboard"].append([{"text": f"✏️ {sec_name}", "callback_data": safe_callback_data(f"rename_section_{sec_id}")}])
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "basic_settings"}])
    return keyboard, "اختر القسم لتعديل اسمه:"

def get_edit_prices_menu():
    products = get_all_products()
    if not products:
        return None, "🚫 لا توجد منتجات أو فئات"
    keyboard = {"inline_keyboard": []}
    exchange_rate = get_exchange_rate()
    has_categories = False
    for product in products:
        product_id, name, category, emoji, desc, img = product
        display_name = f"{emoji} {name}" if emoji else name
        categories = get_categories_by_product(product_id)
        for cat in categories:
            cat_id, cat_name, price_usd, cat_type, min_qty, max_qty = cat
            has_categories = True
            price_syp = price_usd * exchange_rate
            keyboard["inline_keyboard"].append([
                {"text": f"✏️ {display_name} | {cat_name} | {price_usd:.2f}$ | {price_syp:,.0f}ل.س",
                 "callback_data": safe_callback_data(f"editprice_{cat_id}")}
            ])
    if not has_categories:
        return None, "🚫 لا توجد فئات لتعديل أسعارها"
    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع للوحة التحكم", "callback_data": "back_admin"}])
    msg = (
        f"💲 <b>تعديل أسعار الفئات</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💱 سعر الصرف الحالي: <b>{exchange_rate:,.0f}</b> ل.س/دولار\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"اضغط على أي فئة لتعديل سعرها:"
    )
    return keyboard, msg

# ===== معالجة الرسائل =====

def handle_message(chat_id, user_id, text):
    user_info = get_telegram_user_info(user_id)
    register_new_user(user_id, user_info["username"], user_info["name"])

    if not bot_enabled and user_id != MAIN_ADMIN_ID and not is_admin(user_id):
        send_message(chat_id, "⚠️ الــبــوت مــتــوقــف حــالــيًــا عــن الــعــمــل .⚠️")
        return

    if is_blocked(user_id) and user_id != MAIN_ADMIN_ID:
        send_message(chat_id, "🚫 تم حظرك من استخدام البوت")
        return

    if not check_user_subscribed(user_id) and user_id != MAIN_ADMIN_ID and not is_admin(user_id):
        send_message(chat_id, "⚠️ عذرا عليك الاشتراك بالقنوات التالية:", reply_markup=get_check_subscription_keyboard())
        return

    # ===== [إضافة جديدة] أمر ربط حساب موقع ARAB STORE بحساب تيليجرام =====
    if text.strip().startswith("/link"):
        parts = text.strip().split()
        if len(parts) == 2:
            ok, info = web_link_telegram_account(parts[1], user_id, user_info["username"], user_info["name"])
            if ok:
                send_message(chat_id, "✅ تم ربط حسابك بالموقع بنجاح! رصيدك وطلباتك صارت موحّدة بين البوت والموقع.")
            else:
                send_message(chat_id, f"❌ {info}")
        else:
            send_message(chat_id, "📎 أرسل الكود هيك: <code>/link 123456</code>\nرح تلاقي الكود بصفحة المحفظة بالموقع.")
        return

    if user_id in user_states:
        state = user_states[user_id]

        if state.get("action") == "waiting_api_token":
            set_api_token(text)
            user_states[user_id]["action"] = "waiting_api_base_url"
            send_message(chat_id, "✅ تم حفظ التوكن\n📎 ارسل رابط الـ API:")
            return

        elif state.get("action") == "waiting_api_base_url":
            set_api_base_url(text)
            del user_states[user_id]
            send_message(chat_id, "✅ تم وضع المصدر بنجاح✅")
            return

        # ===== إضافة مزود جديد =====
        elif state.get("action") == "waiting_provider_name":
            user_states[user_id]["provider_name"] = text
            user_states[user_id]["action"] = "waiting_provider_token"
            send_message(chat_id, "🔑 ارسل توكن API للمزود:")
            return

        elif state.get("action") == "waiting_provider_token":
            user_states[user_id]["provider_token"] = text
            user_states[user_id]["action"] = "waiting_provider_url"
            send_message(chat_id, "🔗 ارسل رابط API للمزود (مثال: https://api.example.com/):")
            return

        elif state.get("action") == "waiting_provider_url":
            pname = user_states[user_id]["provider_name"]
            ptoken = user_states[user_id]["provider_token"]
            purl = text.strip()
            providers = get_all_api_providers()
            if len(providers) >= 10000:
                send_message(chat_id, "❌ وصلت الحد الأقصى (10000 مزود). احذف مزوداً لإضافة جديد.")
            else:
                pid = add_api_provider(pname, ptoken, purl)
                send_message(chat_id, f"✅ تم إضافة المزود بنجاح!\n🔌 الاسم: {pname}\n🆔 رقم المزود: {pid}")
            del user_states[user_id]
            return

        # ===== تعديل مزود =====
        elif state.get("action") == "waiting_edit_provider_name":
            user_states[user_id]["new_name"] = text
            user_states[user_id]["action"] = "waiting_edit_provider_token"
            send_message(chat_id, "🔑 ارسل التوكن الجديد (أو أرسل - للإبقاء على الحالي):")
            return

        elif state.get("action") == "waiting_edit_provider_token":
            pid = user_states[user_id]["provider_id"]
            provider = get_api_provider_by_id(pid)
            if text.strip() != "-":
                user_states[user_id]["new_token"] = text
            else:
                user_states[user_id]["new_token"] = provider[2] if provider else ""
            user_states[user_id]["action"] = "waiting_edit_provider_url"
            send_message(chat_id, "🔗 ارسل الرابط الجديد (أو أرسل - للإبقاء على الحالي):")
            return

        elif state.get("action") == "waiting_edit_provider_url":
            pid = user_states[user_id]["provider_id"]
            provider = get_api_provider_by_id(pid)
            if text.strip() != "-":
                new_url = text.strip()
            else:
                new_url = provider[3] if provider else ""
            update_api_provider(pid, user_states[user_id]["new_name"],
                                user_states[user_id]["new_token"], new_url)
            send_message(chat_id, f"✅ تم تعديل المزود بنجاح!")
            del user_states[user_id]
            return

        # ===== ربط المنتج بمزود محدد =====
        elif state.get("action") == "waiting_api_product_id":
            try:
                api_product_id = int(text)
                product_id = state.get("product_id")
                category_id = state.get("category_id")
                product_name = state.get("product_name")
                category_name = state.get("category_name")
                provider_id = state.get("provider_id", 0)

                # نحضّر بيانات المزود
                p_token, p_url = None, None
                if provider_id:
                    provider = get_api_provider_by_id(provider_id)
                    if provider:
                        p_token = provider[2]
                        p_url = provider[3]

                api_product = get_api_product_by_id(api_product_id, api_token=p_token, api_base_url=p_url)
                if api_product:
                    api_name = api_product.get("name", "غير معروف")
                    api_price = api_product.get("price", 0)
                    link_product(product_id, category_id, api_product_id, api_name, api_price, provider_id)
                    provider_name = "غير محدد"
                    if provider_id:
                        prov = get_api_provider_by_id(provider_id)
                        if prov:
                            provider_name = prov[1]
                    msg = (f"✅ تم ربط المنتج بنجاح:\n"
                           f"📦 المنتج: {product_name}\n"
                           f"🏷️ الفئة: {category_name}\n"
                           f"🔗 الفئة API: {api_name}\n"
                           f"💰 السعر API: {float(api_price):.2f}$\n"
                           f"🔌 المزود: {provider_name}\n"
                           f"⚡ يمكن الآن للمستخدمين الشحن تلقائياً🎉")
                    send_message(chat_id, msg)
                else:
                    send_message(chat_id, "❌ لا يوجد منتج بهذا الرقم في API")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ الرقم غير صحيح، أرسل رقم المنتج من API")
            return

        # ===== إضافة منتج مرتبط للعرض =====
        elif state.get("action") == "waiting_related_api_product_id":
            try:
                api_product_id = int(text)
                product_id = state.get("product_id")
                category_id = state.get("category_id")
                provider_id = state.get("provider_id", 0)

                p_token, p_url = None, None
                if provider_id:
                    provider = get_api_provider_by_id(provider_id)
                    if provider:
                        p_token = provider[2]
                        p_url = provider[3]

                api_product = get_api_product_by_id(api_product_id, api_token=p_token, api_base_url=p_url)
                if api_product:
                    api_name = api_product.get("name", "غير معروف")
                    api_price = api_product.get("price", 0)
                    add_related_product(product_id, category_id, provider_id, api_product_id, api_name, api_price)
                    provider_name = "غير محدد"
                    if provider_id:
                        prov = get_api_provider_by_id(provider_id)
                        if prov:
                            provider_name = prov[1]
                    msg = (f"✅ تم إضافة المنتج المرتبط للعرض:\n"
                           f"🔗 اسم API: {api_name}\n"
                           f"💰 سعر API: {float(api_price):.2f}$\n"
                           f"🔌 المزود: {provider_name}")
                    send_message(chat_id, msg)
                else:
                    send_message(chat_id, "❌ لا يوجد منتج بهذا الرقم في API")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ الرقم غير صحيح")
            return

        elif state.get("action") == "waiting_search_term":
            search_term = text
            provider_id = state.get("provider_id", 0)
            p_token, p_url = None, None
            if provider_id:
                provider = get_api_provider_by_id(provider_id)
                if provider:
                    p_token = provider[2]
                    p_url = provider[3]
            results = search_api_products(search_term, api_token=p_token, api_base_url=p_url)
            if results:
                for product in results[:10]:
                    product_id = product.get("id", "?")
                    name = product.get("name", "غير معروف")
                    price = product.get("price", 0)
                    product_type = product.get("product_type", "غير معروف")
                    available = product.get("available", False)
                    available_text = "✅ متاح" if available else "❌ غير متاح"
                    params = ", ".join(product.get("params", []))
                    msg = (f"🔶 اسم المنتج: {name}\n"
                           f"🔶 سعر المنتج: {float(price):.2f}$\n"
                           f"<code>🔷 ايدي المنتج: {product_id}</code>\n"
                           f"🔷 نوع المنتج: {product_type}\n"
                           f"🔶 حالة المنتج: {available_text}\n"
                           f"🔶 متطلبات: {params}\n"
                           f"━━━━━━━━━━━━━━━━━━━━\n")
                    send_message(chat_id, msg)
            else:
                send_message(chat_id, "❌ لا توجد منتجات مطابقة للبحث")
            del user_states[user_id]
            return

        elif state.get("action") == "waiting_category_name":
            user_states[user_id]["category_name"] = text
            cat_type = state.get("cat_type", "default")
            if cat_type == 'counter':
                user_states[user_id]["action"] = "waiting_counter_min_qty"
                send_message(chat_id, "📊 ارسل الحد الادنى للكمية:")
            elif cat_type == 'limited':
                user_states[user_id]["action"] = "waiting_limited_min_qty"
                send_message(chat_id, "📊 ارسل الحد الادنى للكمية:")
            else:
                user_states[user_id]["action"] = "waiting_category_price"
                send_message(chat_id, "💰 اكتب سعر الفئة بدولار:")
            return

        elif state.get("action") == "waiting_category_price":
            try:
                price = float(text.replace(',', '.').replace(' ', ''))
                product_id = state.get("product_id")
                category_name = state.get("category_name")
                cat_type = state.get("cat_type", "default")
                min_qty = state.get("min_qty", 1)
                max_qty = state.get("max_qty", 1)
                add_category(product_id, category_name, price, cat_type, min_qty, max_qty)
                send_message(chat_id, f"✅ تم اضافة {category_name} بسعر {price:.2f}$")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ السعر غير صحيح، أرسل رقم فقط مثل 5.99")
            return

        elif state.get("action") == "waiting_counter_min_qty":
            try:
                min_qty = int(text)
                user_states[user_id]["min_qty"] = min_qty
                user_states[user_id]["action"] = "waiting_counter_max_qty"
                send_message(chat_id, "📊 ارسل الحد الاعلى للكمية:")
            except:
                send_message(chat_id, "❌ الرقم غير صحيح")
            return

        elif state.get("action") == "waiting_counter_max_qty":
            try:
                max_qty = int(text)
                if max_qty < user_states[user_id]["min_qty"]:
                    send_message(chat_id, "❌ الحد الاعلى يجب ان يكون اكبر من الحد الادنى")
                    return
                user_states[user_id]["max_qty"] = max_qty
                user_states[user_id]["action"] = "waiting_counter_price"
                send_message(chat_id, "💰 قم بتعيين سعر الكمية الواحدة دولار:")
            except:
                send_message(chat_id, "❌ الرقم غير صحيح")
            return

        elif state.get("action") == "waiting_counter_price":
            try:
                price = float(text.replace(',', '.').replace(' ', ''))
                product_id = user_states[user_id]["product_id"]
                category_name = user_states[user_id]["category_name"]
                min_qty = user_states[user_id]["min_qty"]
                max_qty = user_states[user_id]["max_qty"]
                add_category(product_id, category_name, price, 'counter', min_qty, max_qty)
                send_message(chat_id, f"✅ تم اضافة فئة العداد بنجاح\n📊 {category_name}\n💰 سعر الواحدة: {price:.2f}$\n📈 الحد الادنى: {min_qty}\n📉 الحد الاعلى: {max_qty}")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ السعر غير صحيح")
            return

        elif state.get("action") == "waiting_limited_min_qty":
            try:
                min_qty = int(text)
                user_states[user_id]["min_qty"] = min_qty
                user_states[user_id]["action"] = "waiting_limited_max_qty"
                send_message(chat_id, "📊 ارسل الحد الاعلى للكمية:")
            except:
                send_message(chat_id, "❌ الرقم غير صحيح")
            return

        elif state.get("action") == "waiting_limited_max_qty":
            try:
                max_qty = int(text)
                if max_qty < user_states[user_id]["min_qty"]:
                    send_message(chat_id, "❌ الحد الاعلى يجب أن يكون أكبر من الحد الادنى")
                    return
                user_states[user_id]["max_qty"] = max_qty
                user_states[user_id]["action"] = "waiting_limited_price"
                send_message(chat_id, "💰 اكتب سعر الفئة (للوحدة الواحدة) بالدولار:")
            except:
                send_message(chat_id, "❌ الرقم غير صحيح")
            return

        elif state.get("action") == "waiting_limited_price":
            try:
                price = float(text.replace(',', '.').replace(' ', ''))
                product_id = user_states[user_id]["product_id"]
                category_name = user_states[user_id]["category_name"]
                min_qty = user_states[user_id]["min_qty"]
                max_qty = user_states[user_id]["max_qty"]
                add_category(product_id, category_name, price, 'limited', min_qty, max_qty)
                send_message(chat_id, f"✅ تم إضافة فئة الكمية المحددة\n📊 {category_name}\n💰 سعر الواحدة: {price:.2f}$\n📈 {min_qty}-{max_qty}")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ السعر غير صحيح")
            return

        elif state.get("action") == "waiting_player_id":
            player_id = text
            category_id = state.get("category_id")
            cat_type = state.get("cat_type", "default")

            category = get_category_by_id(category_id)
            if not category:
                send_message(chat_id, "❌ خطأ في الفئة")
                del user_states[user_id]
                return

            cat_id, product_id, cat_name, price_usd, cat_type, min_qty, max_qty = category
            exchange_rate = get_exchange_rate()
            product = get_product_by_id(product_id)

            discount_name, discount_percent = get_user_discount(user_id)
            price_before_discount_usd = price_usd
            if discount_percent > 0:
                price_usd = price_usd * (1 - discount_percent / 100)

            price_before_discount_syp = price_before_discount_usd * exchange_rate
            price_after_discount_syp = price_usd * exchange_rate

            if cat_type in ('counter', 'limited'):
                user_states[user_id] = {
                    "action": "waiting_qty",
                    "category_id": category_id,
                    "product_id": product_id,
                    "product_name": product[1] if product else "غير معروف",
                    "cat_name": cat_name,
                    "price_usd": price_usd,
                    "price_usd_before": price_before_discount_usd,
                    "player_id": player_id,
                    "min_qty": min_qty,
                    "max_qty": max_qty,
                    "cat_type": cat_type
                }
                msg = (f"<b>⚡ المنتج: {product[1] if product else 'غير معروف'}</b>\n"
                       f"<b>⚡ الفئة: {cat_name}</b>\n"
                       f"<b>🔷 سعر الواحدة بدولار: {price_before_discount_usd:.2f}$</b>\n")
                if discount_percent > 0:
                    msg += f"<b>🔷 سعر الواحدة بعد الخصم: {price_usd:.2f}$</b>\n"
                msg += (f"<b>🔷 سعر الواحدة بليرة: {price_before_discount_syp:,.2f} ليرة</b>\n"
                        f"<b>⚡ الحد الادنى: {min_qty}</b>\n"
                        f"<b>⚡ الحد الاعلى: {max_qty}</b>\n"
                        f"<b>🔶 ارسل الكمية المراد شحنها 🔶:</b>")
                send_message(chat_id, msg)
                return

            price_syp = price_usd * exchange_rate
            balance = get_user_balance(user_id)
            linked = get_linked_by_category(category_id)

            pending_orders[user_id] = {
                "category_id": category_id,
                "product_id": product_id,
                "product_name": product[1] if product else "غير معروف",
                "cat_name": cat_name,
                "price_usd": price_usd,
                "price_usd_before": price_before_discount_usd,
                "price_syp": price_syp,
                "price_syp_before": price_before_discount_syp,
                "player_id": player_id,
                "qty": 1,
                "start_time": time.time(),
                "linked": linked is not None,
                "api_product_id": linked[3] if linked else None,
                "provider_id": linked[8] if linked and len(linked) > 8 else 0,
                "provider_token": linked[10] if linked and len(linked) > 10 else None,
                "provider_url": linked[11] if linked and len(linked) > 11 else None,
                "discount_percent": discount_percent,
                "discount_name": discount_name
            }

            msg = (f"<b>❄️ تاكيد عملية الشراء ❄️</b>\n\n"
                   f"<b>🔷 المنتج: {product[1] if product else 'غير معروف'}</b>\n\n"
                   f"<b>🔷 الفئة: {cat_name}</b>\n\n"
                   f"<b>🔷 السعر الاصلي بالدولار: {price_before_discount_usd:.2f}$</b>\n")
            if discount_percent > 0:
                msg += f"<b>🔷 السعر بعد الخصم بالدولار: {price_usd:.2f}$</b>\n"
            msg += f"<b>🔷 السعر الاصلي بليرة: {price_before_discount_syp:,.2f} ليرة</b>\n"
            if discount_percent > 0:
                msg += f"<b>🔷 السعر بعد الخصم بليرة: {price_syp:,.2f} ليرة</b>\n\n"
                msg += f"<b>🎁 الخصم: {discount_name} {discount_percent}%</b>\n\n"
            else:
                msg += f"<b>🔷 السعر بليرة: {price_syp:,.2f} ليرة</b>\n\n"
            msg += (f"<b>🔷 رصيدك الان: {balance:,.2f} ليرة</b>\n\n"
                    f"<b>◽ الايدي المدخل: {player_id}</b>")

            keyboard = {"inline_keyboard": [
                [{"text": "🟢 تأكيد الشراء", "callback_data": safe_callback_data(f"confirm_buy_{user_id}"), "color": "success"}],
                [{"text": "🔵 تغيير الايدي", "callback_data": "change_player_id", "color": "primary"},
                 {"text": "🔴 إلغاء الشراء", "callback_data": "cancel_buy", "color": "danger"}],
                [{"text": "🔵 عودة للفئات", "callback_data": "back_to_categories"}]
            ]}
            send_message(chat_id, msg, reply_markup=keyboard)
            del user_states[user_id]
            return

        elif state.get("action") == "waiting_new_player_id":
            if user_id in pending_orders:
                pending_orders[user_id]["player_id"] = text
                order = pending_orders[user_id]
                price_syp = order["price_syp"]
                price_usd = order["price_usd"]
                price_before_usd = order.get("price_usd_before", price_usd)
                price_before_syp = order.get("price_syp_before", price_syp)
                balance = get_user_balance(user_id)
                discount_percent = order.get("discount_percent", 0)
                discount_name = order.get("discount_name", "")
                msg = (f"<b>❄️ تاكيد عملية الشراء ❄️</b>\n\n"
                       f"<b>🔷 المنتج: {order['product_name']}</b>\n\n"
                       f"<b>🔷 الفئة: {order['cat_name']}</b>\n\n"
                       f"<b>🔷 السعر الاصلي بالدولار: {price_before_usd:.2f}$</b>\n")
                if discount_percent > 0:
                    msg += f"<b>🔷 السعر بعد الخصم بالدولار: {price_usd:.2f}$</b>\n"
                msg += f"<b>🔷 السعر الاصلي بليرة: {price_before_syp:,.2f} ليرة</b>\n"
                if discount_percent > 0:
                    msg += f"<b>🔷 السعر بعد الخصم بليرة: {price_syp:,.2f} ليرة</b>\n\n"
                    msg += f"<b>🎁 الخصم: {discount_name} {discount_percent}%</b>\n\n"
                else:
                    msg += f"<b>🔷 السعر بليرة: {price_syp:,.2f} ليرة</b>\n\n"
                msg += (f"<b>🔷 رصيدك الان: {balance:,.2f} ليرة</b>\n\n"
                        f"<b>◽ الايدي الجديد: {text}</b>")
                keyboard = {"inline_keyboard": [
                    [{"text": "🟢 تأكيد الشراء", "callback_data": safe_callback_data(f"confirm_buy_{user_id}"), "color": "success"}],
                    [{"text": "🔵 تغيير الايدي", "callback_data": "change_player_id", "color": "primary"},
                     {"text": "🔴 إلغاء الشراء", "callback_data": "cancel_buy", "color": "danger"}],
                    [{"text": "🔵 عودة للفئات", "callback_data": "back_to_categories"}]
                ]}
                send_message(chat_id, msg, reply_markup=keyboard)
            else:
                send_message(chat_id, "❌ انتهت صلاحية الطلب، ابدأ من جديد")
            del user_states[user_id]
            return

        elif state.get("action") == "waiting_qty":
            try:
                qty = int(text)
                category_id = state.get("category_id")
                min_qty = state.get("min_qty")
                max_qty = state.get("max_qty")

                if qty < min_qty or qty > max_qty:
                    send_message(chat_id, f"❌ الكمية غير مقبولة، بين {min_qty} و {max_qty}")
                    return

                category = get_category_by_id(category_id)
                if not category:
                    send_message(chat_id, "❌ خطأ في الفئة")
                    del user_states[user_id]
                    return

                cat_id, product_id, cat_name, price_usd, cat_type, min_qty, max_qty = category
                exchange_rate = get_exchange_rate()

                discount_name, discount_percent = get_user_discount(user_id)
                price_usd_before = price_usd
                if discount_percent > 0:
                    price_usd = price_usd * (1 - discount_percent / 100)

                unit_qty = get_category_unit_qty(category_id)
                price_syp = compute_total_price(price_usd, qty, unit_qty) * exchange_rate
                price_syp_before = compute_total_price(price_usd_before, qty, unit_qty) * exchange_rate
                balance = get_user_balance(user_id)
                product = get_product_by_id(product_id)
                linked = get_linked_by_category(category_id)
                player_id = state.get("player_id")

                pending_orders[user_id] = {
                    "category_id": category_id,
                    "product_id": product_id,
                    "product_name": product[1] if product else "غير معروف",
                    "cat_name": cat_name,
                    "price_usd": price_usd,
                    "price_usd_before": price_usd_before,
                    "price_syp": price_syp,
                    "price_syp_before": price_syp_before,
                    "player_id": player_id,
                    "qty": qty,
                    "start_time": time.time(),
                    "linked": linked is not None,
                    "api_product_id": linked[3] if linked else None,
                    "provider_id": linked[8] if linked and len(linked) > 8 else 0,
                    "provider_token": linked[10] if linked and len(linked) > 10 else None,
                    "provider_url": linked[11] if linked and len(linked) > 11 else None,
                    "min_qty": min_qty,
                    "max_qty": max_qty,
                    "discount_percent": discount_percent,
                    "discount_name": discount_name
                }

                msg = (f"<b>❄️ تاكيد عملية الشراء ❄️</b>\n\n"
                       f"<b>🔷 المنتج: {product[1] if product else 'غير معروف'}</b>\n\n"
                       f"<b>🔷 الفئة: {cat_name}</b>\n\n"
                       f"<b>🔷 سعر الواحدة الاصلي: {price_usd_before:.2f}$</b>\n")
                if discount_percent > 0:
                    msg += f"<b>🔷 سعر الواحدة بعد الخصم: {price_usd:.2f}$</b>\n"
                msg += (f"<b>🔷 الكمية: {qty}</b>\n\n"
                        f"<b>🔷 السعر الكلي الاصلي: {price_syp_before:,.2f} ليرة</b>\n")
                if discount_percent > 0:
                    msg += f"<b>🔷 السعر الكلي بعد الخصم: {price_syp:,.2f} ليرة</b>\n\n"
                    msg += f"<b>🎁 الخصم: {discount_name} {discount_percent}%</b>\n\n"
                else:
                    msg += f"<b>🔷 السعر الكلي: {price_syp:,.2f} ليرة</b>\n\n"
                msg += (f"<b>🔷 رصيدك الان: {balance:,.2f} ليرة</b>\n\n"
                        f"<b>🔷 رصيدك بعد الطلب: {max(0, balance - price_syp):,.2f} ليرة</b>")

                keyboard = {"inline_keyboard": [
                    [{"text": "🟢 تأكيد الشراء", "callback_data": safe_callback_data(f"confirm_buy_{user_id}"), "color": "success"}],
                    [{"text": "🔵 تغيير الايدي", "callback_data": "change_player_id", "color": "primary"},
                     {"text": "🔴 إلغاء الشراء", "callback_data": "cancel_buy", "color": "danger"}],
                    [{"text": "🔵 عودة للفئات", "callback_data": "back_to_categories"}]
                ]}
                send_message(chat_id, msg, reply_markup=keyboard)
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ الكمية غير صحيحة، أرسل رقماً صحيحاً")
            return

        elif state.get("action") == "waiting_deposit_title":
            user_states[user_id]["title"] = text
            user_states[user_id]["action"] = "waiting_deposit_description"
            send_message(chat_id, "✏️ اكتب وصف الطريقة:")
            return

        elif state.get("action") == "waiting_deposit_description":
            user_states[user_id]["description"] = text
            user_states[user_id]["action"] = "waiting_deposit_code"
            send_message(chat_id, "🔢 اكتب كود التحويل:")
            return

        elif state.get("action") == "waiting_deposit_code":
            user_states[user_id]["code"] = text
            user_states[user_id]["action"] = "waiting_deposit_rate"
            send_message(chat_id, "💰 اكتب سعر الصرف بليرة سورية:")
            return

        elif state.get("action") == "waiting_deposit_rate":
            try:
                rate = float(text.strip().replace(',', '').replace(' ', '').replace('،', ''))
                title = user_states[user_id]["title"]
                description = user_states[user_id]["description"]
                code = user_states[user_id]["code"]
                add_deposit_method(title, description, code, rate)
                send_message(chat_id, f"✅ تم اضافة طريقة الإيداع '{title}' بنجاح\n💰 سعر الصرف: {rate:,.2f} ليرة")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ السعر غير صحيح، أرسل رقم فقط مثل 15000")
            return

        elif state.get("action") == "waiting_edit_title":
            user_states[user_id]["new_title"] = text
            user_states[user_id]["action"] = "waiting_edit_description"
            send_message(chat_id, "✏️ اكتب الوصف الجديد:")
            return

        elif state.get("action") == "waiting_edit_description":
            user_states[user_id]["new_description"] = text
            user_states[user_id]["action"] = "waiting_edit_code"
            send_message(chat_id, "🔢 اكتب كود التحويل الجديد:")
            return

        elif state.get("action") == "waiting_edit_code":
            user_states[user_id]["new_code"] = text
            user_states[user_id]["action"] = "waiting_edit_rate"
            send_message(chat_id, "💰 اكتب سعر الصرف الجديد:")
            return

        elif state.get("action") == "waiting_edit_rate":
            try:
                rate = float(text.strip().replace(',', '').replace(' ', ''))
                method_id = user_states[user_id]["method_id"]
                update_deposit_method(method_id, user_states[user_id]["new_title"],
                                      user_states[user_id]["new_description"],
                                      user_states[user_id]["new_code"], rate)
                send_message(chat_id, "✅ تم تعديل طريقة الإيداع بنجاح")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ السعر غير صحيح")
            return

        elif state.get("action") == "waiting_deposit_amount":
            try:
                amount_syp = float(text.replace(',', '.').replace(' ', ''))
                method_id = state.get("method_id")
                is_auto = state.get("is_auto", False)
                if is_auto:
                    method = get_auto_deposit_method_by_id(method_id)
                    if method:
                        exchange_rate = method[4]
                        amount_usd = amount_syp / exchange_rate
                        user_states[user_id]["amount_usd"] = amount_usd
                        user_states[user_id]["amount_syp"] = amount_syp
                        user_states[user_id]["method_title"] = method[1]
                        user_states[user_id]["api_token"] = method[5]
                        user_states[user_id]["api_url"] = method[6]
                        user_states[user_id]["action"] = "waiting_auto_transaction_code"
                        send_message(chat_id, f"💰 المبلغ: {amount_syp:,.2f} ليرة\n🔢 ارسل رقم عملية التحويل:")
                    else:
                        send_message(chat_id, "❌ خطأ في طريقة الإيداع")
                else:
                    method = get_deposit_method_by_id(method_id)
                    if method:
                        exchange_rate = method[4]
                        amount_usd = amount_syp / exchange_rate
                        user_states[user_id]["amount_usd"] = amount_usd
                        user_states[user_id]["amount_syp"] = amount_syp
                        user_states[user_id]["method_title"] = method[1]
                        user_states[user_id]["action"] = "waiting_transaction_code"
                        send_message(chat_id, f"💰 المبلغ: {amount_syp:,.2f} ليرة\n🔢 ارسل رقم عملية التحويل:")
                    else:
                        send_message(chat_id, "❌ خطأ في طريقة الإيداع")
            except:
                send_message(chat_id, "❌ المبلغ غير صحيح، أرسل رقم فقط")
            return

        elif state.get("action") == "waiting_transaction_code":
            transaction_code = text
            amount_usd = user_states[user_id]["amount_usd"]
            amount_syp = user_states[user_id]["amount_syp"]
            method_title = user_states[user_id]["method_title"]
            user_info = get_telegram_user_info(user_id)
            request_id = add_deposit_request(user_id, user_info["username"], user_info["name"],
                                              method_title, amount_usd, amount_syp, transaction_code)
            msg = (f"⚡ تم ارسال طلب ايداعك الى المراجعة⚡:\n"
                   f"🟡 طريقة ايداعك: {method_title}\n"
                   f"🟡 المبلغ: {amount_syp:,.2f} ليرة\n"
                   f"🟡 رقم عملية تحويل: {transaction_code}\n"
                   f"💬 سيتم اخبارك بنتيجة ايداعك ✅")
            send_message(chat_id, msg)
            admin_msg = (f"📢 طلب ايداع جديد:\n"
                         f"👤 الاسم: {user_info['name']}\n"
                         f"🆔 الايدي: {user_id}\n"
                         f"🔖 المعرف: {user_info['username']}\n"
                         f"----------------------\n"
                         f"💳 طريقة الايداع: {method_title}\n"
                         f"💰 المبلغ: {amount_syp:,.2f} ليرة\n"
                         f"🔢 رقم العملية: {transaction_code}\n"
                         f"💵 رصيد المستخدم: {get_user_balance(user_id):,.2f} ليرة")
            keyboard = {"inline_keyboard": [[
                {"text": "🟢 قبول الايداع", "callback_data": safe_callback_data(f"accept_deposit_{request_id}"), "color": "success"},
                {"text": "🔴 رفض الايداع", "callback_data": safe_callback_data(f"reject_deposit_{request_id}"), "color": "danger"}
            ]]}
            send_message(ADMIN_CHAT_ID, admin_msg, reply_markup=keyboard)
            del user_states[user_id]
            return

        elif state.get("action") == "waiting_auto_transaction_code":
            transaction_code = text
            amount_syp = user_states[user_id]["amount_syp"]
            amount_usd = user_states[user_id]["amount_usd"]
            method_title = user_states[user_id]["method_title"]
            api_token_dep = user_states[user_id].get("api_token", "")
            api_url_dep = user_states[user_id].get("api_url", "")
            user_info_data = get_telegram_user_info(user_id)
            send_message(chat_id, "⏳ جار التحقق من عملية الإيداع تلقائياً...")
            verified = verify_auto_deposit(api_token_dep, api_url_dep, transaction_code, amount_syp)
            if verified:
                update_user_balance(user_id, amount_syp)
                new_balance = get_user_balance(user_id)
                send_message(chat_id, f"✅ تم التحقق وإضافة الرصيد تلقائياً!\n💳 {method_title}\n💰 {amount_syp:,.2f} ليرة\n💵 رصيدك: {new_balance:,.2f} ليرة")
                send_message(ADMIN_CHAT_ID, f"✅ إيداع تلقائي تم:\n👤 {user_info_data['name']} | {user_id}\n💳 {method_title} | 💰 {amount_syp:,.2f} ليرة")
            else:
                request_id = add_deposit_request(user_id, user_info_data["username"], user_info_data["name"],
                                                  method_title, amount_usd, amount_syp, transaction_code)
                send_message(chat_id, f"⚡ لم يتم التحقق تلقائياً، تم إرسال طلبك للمراجعة اليدوية.\n🟡 المبلغ: {amount_syp:,.2f} ليرة")
                keyboard = {"inline_keyboard": [[
                    {"text": "🟢 قبول الايداع", "callback_data": safe_callback_data(f"accept_deposit_{request_id}"), "color": "success"},
                    {"text": "🔴 رفض الايداع", "callback_data": safe_callback_data(f"reject_deposit_{request_id}"), "color": "danger"}
                ]]}
                send_message(ADMIN_CHAT_ID,
                             f"📢 إيداع يحتاج مراجعة:\n👤 {user_info_data['name']} | {user_id}\n💳 {method_title} | 💰 {amount_syp:,.2f}",
                             reply_markup=keyboard)
            del user_states[user_id]
            return

        elif state.get("action") == "waiting_auto_deposit_token":
            user_states[user_id]["api_token"] = text
            user_states[user_id]["action"] = "waiting_auto_deposit_title"
            send_message(chat_id, "✏️ ارسل اسم طريقة الإيداع التلقائي:")
            return

        elif state.get("action") == "waiting_auto_deposit_title":
            user_states[user_id]["title"] = text
            user_states[user_id]["action"] = "waiting_auto_deposit_description"
            send_message(chat_id, "📝 ارسل وصف طريقة الإيداع:")
            return

        elif state.get("action") == "waiting_auto_deposit_description":
            user_states[user_id]["description"] = text
            user_states[user_id]["action"] = "waiting_auto_deposit_code"
            send_message(chat_id, "🔢 ارسل كود التحويل:")
            return

        elif state.get("action") == "waiting_auto_deposit_code":
            user_states[user_id]["code"] = text
            user_states[user_id]["action"] = "waiting_auto_deposit_rate"
            send_message(chat_id, "💰 ارسل سعر الصرف:")
            return

        elif state.get("action") == "waiting_auto_deposit_rate":
            try:
                rate = float(text.strip().replace(',', '').replace(' ', '').replace('،', ''))
                user_states[user_id]["exchange_rate"] = rate
                user_states[user_id]["action"] = "waiting_auto_deposit_api_url"
                send_message(chat_id,
                    "🔗 ارسل رابط API الكامل للتحقق التلقائي:\n\n"
                    "📌 <b>SAM API - شام كاش:</b>\n"
                    "<code>https://www.sam-api.pro/api/v1/wallets/shamcash/{رقم_المحفظة}</code>\n\n"
                    "📌 <b>SAM API - سيرتيل كاش:</b>\n"
                    "<code>https://www.sam-api.pro/api/v1/wallets/syriatel/{رقم_الهاتف}</code>\n\n"
                    "أو أرسل <b>-</b> إذا لم يكن لديك رابط (سيصبح يدوياً)")
            except:
                send_message(chat_id, "❌ الرقم غير صحيح")
            return

        elif state.get("action") == "waiting_auto_deposit_api_url":
            api_url = text.strip() if text.strip() != "-" else ""
            # تأكد من صحة رابط SAM API إذا أُدخل
            if api_url and '/wallets/' not in api_url and 'sam-api' in api_url.lower():
                send_message(chat_id,
                    "⚠️ تحقق من الرابط!\n"
                    "للشام كاش يجب أن يكون:\n"
                    "<code>https://www.sam-api.pro/api/v1/wallets/shamcash/{رقم_المحفظة}</code>\n\n"
                    "للسيرتيل كاش:\n"
                    "<code>https://www.sam-api.pro/api/v1/wallets/syriatel/{رقم_الهاتف}</code>\n\n"
                    "أرسل الرابط الصحيح أو أرسل - للتخطي:")
                return
            add_auto_deposit_method(
                user_states[user_id]["title"], user_states[user_id]["description"],
                user_states[user_id]["code"], user_states[user_id]["exchange_rate"],
                user_states[user_id]["api_token"], api_url)
            send_message(chat_id, f"✅ تم إضافة طريقة الإيداع التلقائي!\n💳 {user_states[user_id]['title']}")
            del user_states[user_id]
            return

        # ===== تعديل طريقة ايداع تلقائي =====
        elif state.get("action") == "waiting_edit_auto_title":
            user_states[user_id]["new_title"] = text
            user_states[user_id]["action"] = "waiting_edit_auto_description"
            send_message(chat_id, "✏️ اكتب الوصف الجديد (أو أرسل - للإبقاء):")
            return

        elif state.get("action") == "waiting_edit_auto_description":
            user_states[user_id]["new_description"] = text
            user_states[user_id]["action"] = "waiting_edit_auto_code"
            send_message(chat_id, "🔢 اكتب كود التحويل الجديد (رقم المحفظة/الهاتف):")
            return

        elif state.get("action") == "waiting_edit_auto_code":
            user_states[user_id]["new_code"] = text
            user_states[user_id]["action"] = "waiting_edit_auto_rate"
            send_message(chat_id, "💰 اكتب سعر الصرف الجديد:")
            return

        elif state.get("action") == "waiting_edit_auto_rate":
            try:
                rate = float(text.strip().replace(',', '').replace(' ', ''))
                user_states[user_id]["new_rate"] = rate
                user_states[user_id]["action"] = "waiting_edit_auto_token"
                send_message(chat_id, "🔑 ارسل التوكن الجديد (أو أرسل - للإبقاء):")
            except:
                send_message(chat_id, "❌ السعر غير صحيح، أرسل رقم فقط مثل 15000")
            return

        elif state.get("action") == "waiting_edit_auto_token":
            user_states[user_id]["new_token"] = text
            user_states[user_id]["action"] = "waiting_edit_auto_url"
            send_message(chat_id,
                         "🌐 ارسل رابط API الجديد للتحقق التلقائي:\n"
                         "ShamCash مثال: https://api.example.com/v1/wallets/shamcash/WALLET_ADDRESS\n"
                         "SyriaTel مثال: https://api.example.com/v1/wallets/syriatel/PHONE\n"
                         "(أو أرسل - للإبقاء)")
            return

        elif state.get("action") == "waiting_edit_auto_url":
            mid = user_states[user_id]["method_id"]
            method = get_auto_deposit_method_by_id(mid)
            if method:
                new_title = user_states[user_id].get("new_title", method[1])
                new_desc = user_states[user_id].get("new_description", method[2])
                new_code = user_states[user_id].get("new_code", method[3])
                new_rate = user_states[user_id].get("new_rate", method[4])
                raw_token = user_states[user_id].get("new_token", "-")
                new_token = method[5] if raw_token.strip() == "-" else raw_token
                new_url = method[6] if text.strip() == "-" else text.strip()
                update_auto_deposit_method(mid, new_title, new_desc, new_code, new_rate, new_token, new_url)
                send_message(chat_id, f"✅ تم تعديل طريقة الإيداع التلقائي: {new_title}")
            else:
                send_message(chat_id, "❌ لم يتم العثور على الطريقة")
            del user_states[user_id]
            return

        elif state.get("action") == "waiting_exchange_rate":
            try:
                rate = float(text.strip().replace(',', '').replace(' ', '').replace('،', ''))
                set_exchange_rate(rate)
                send_message(chat_id, f"✅ تم وضع سعر صرف بنجاح\n💰 سعر الصرف الجديد: {rate:,.2f} ليرة = 1$")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ السعر غير صحيح")
            return

        elif state.get("action") == "waiting_product_name":
            product_name = text
            sections = get_all_sections()
            if sections:
                keyboard = {"inline_keyboard": []}
                for section in sections:
                    sec_id, sec_name, color, emoji, is_active = section
                    keyboard["inline_keyboard"].append([{"text": sec_name, "callback_data": safe_callback_data(f"save_product_{sec_name}")}])
                user_states[user_id]["product_name"] = product_name
                send_message(chat_id, "📂 اختر القسم:", reply_markup=keyboard)
            else:
                send_message(chat_id, "❌ لا توجد أقسام. أضف قسماً أولاً.")
                del user_states[user_id]
            return

        elif state.get("action") == "waiting_product_image":
            return

        elif state.get("action") == "waiting_product_description":
            product_id = state.get("product_id")
            update_product_description(product_id, text)
            send_message(chat_id, "✅ تم حفظ الوصف بنجاح")
            del user_states[user_id]
            return

        elif state.get("action") == "waiting_new_section_name":
            section_id = state.get("section_id")
            update_section_name(section_id, text)
            send_message(chat_id, "✅ تم تحديث الاسم بنجاح")
            del user_states[user_id]
            return

        elif state.get("action") == "waiting_new_section":
            if add_section(text):
                send_message(chat_id, f"✅ تم اضافة القسم {text} بنجاح")
            else:
                send_message(chat_id, "❌ هذا القسم موجود مسبقاً")
            del user_states[user_id]
            return

        elif state.get("action") == "waiting_channel_username":
            channel_username = text if text.startswith('@') else '@' + text
            if add_required_channel(channel_username):
                send_message(chat_id, "✅ تم حفظ قناة الاشتراك بنجاح")
            else:
                send_message(chat_id, "❌ هذه القناة موجودة مسبقاً")
            del user_states[user_id]
            return

        elif state.get("action") == "waiting_description_category":
            user_states[user_id]["desc_category"] = text
            user_states[user_id]["action"] = "waiting_description_text"
            send_message(chat_id, "📝 ارسل وصف القسم الجديد:")
            return

        elif state.get("action") == "waiting_description_text":
            set_category_description(user_states[user_id]["desc_category"], text)
            send_message(chat_id, "✅ تم وضع الوصف للقسم بنجاح")
            del user_states[user_id]
            return

        elif state.get("action") == "waiting_broadcast_message":
            send_message(chat_id, "📢 جار الاذاعة...")
            success, failed, total = broadcast_to_all(text, user_id)
            send_message(chat_id, f"✅ تم الارسال: {success}\n❌ فشل: {failed}\n🔶 الاجمالي: {total}")
            del user_states[user_id]
            return

        elif state.get("action") == "waiting_broadcast_user_id":
            try:
                target_user_id = int(text)
                user_states[user_id]["target_user_id"] = target_user_id
                user_states[user_id]["action"] = "waiting_broadcast_user_message"
                send_message(chat_id, "📝 ارسل الاذاعة:")
            except:
                send_message(chat_id, "❌ الايدي غير صحيح")
            return

        elif state.get("action") == "waiting_broadcast_user_message":
            target_user_id = user_states[user_id]["target_user_id"]
            if broadcast_to_user(target_user_id, text):
                send_message(chat_id, "✅ تم الارسال بنجاح")
            else:
                send_message(chat_id, "❌ فشل الارسال")
            del user_states[user_id]
            return

        elif state.get("action") == "waiting_user_id_for_add_balance":
            try:
                target_user_id = int(text)
                user_states[user_id]["target_user_id"] = target_user_id
                user_states[user_id]["action"] = "waiting_add_balance_amount"
                send_message(chat_id, "💰 اكتب المبلغ الذي تريد اضافته بليرة:")
            except:
                send_message(chat_id, "❌ الايدي غير صحيح")
            return

        elif state.get("action") == "waiting_add_balance_amount":
            try:
                amount = float(text.replace(',', '.').replace(' ', ''))
                target_user_id = user_states[user_id]["target_user_id"]
                add_user_balance(target_user_id, amount)
                send_message(chat_id, "✅ تم اضافة الرصيد بنجاح")
                send_message(target_user_id, f"💸 تم اضافة مبلغ: {amount:,.2f} ليرة بواسطة الادارة❄")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ المبلغ غير صحيح")
            return

        elif state.get("action") == "waiting_user_id_for_deduct_balance":
            try:
                target_user_id = int(text)
                user_states[user_id]["target_user_id"] = target_user_id
                user_states[user_id]["action"] = "waiting_deduct_balance_amount"
                send_message(chat_id, "💰 اكتب المبلغ الذي تريد خصمه بليرة:")
            except:
                send_message(chat_id, "❌ الايدي غير صحيح")
            return

        elif state.get("action") == "waiting_deduct_balance_amount":
            try:
                amount = float(text.replace(',', '.').replace(' ', ''))
                target_user_id = user_states[user_id]["target_user_id"]
                deduct_user_balance(target_user_id, amount)
                send_message(chat_id, "✅ تم خصم الرصيد بنجاح")
                send_message(target_user_id, f"⚠ تم خصم مبلغ: {amount:,.2f} ليرة من قبل الادمن🧩")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ المبلغ غير صحيح")
            return

        elif state.get("action") == "waiting_user_id_for_add_admin":
            try:
                target_user_id = int(text)
                if target_user_id == MAIN_ADMIN_ID:
                    send_message(chat_id, "❌ هذا المستخدم هو المدير الرئيسي بالفعل")
                else:
                    add_admin(target_user_id)
                    send_message(chat_id, f"✅ تم اضافة المستخدم {target_user_id} لادمن بنجاح")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ الايدي غير صحيح")
            return

        elif state.get("action") == "waiting_user_id_for_remove_admin":
            try:
                target_user_id = int(text)
                if target_user_id == MAIN_ADMIN_ID:
                    send_message(chat_id, "عذرا لايمكن حذف المدير الرئيسي 😉")
                else:
                    remove_admin(target_user_id)
                    send_message(chat_id, "✅ تم حذف المستخدم من الادمن ⚡✅")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ الايدي غير صحيح")
            return

        elif state.get("action") == "waiting_user_id_for_info":
            try:
                target_user_id = int(text)
                stats = get_user_stats(target_user_id)
                user_info2 = get_telegram_user_info(target_user_id)
                msg = (f"♕⚡ اسم: {user_info2['name']}\n"
                       f"♕⚡ ايدي: {target_user_id}\n"
                       f"♕⚡ معرف: {user_info2['username']}\n"
                       f"------------------\n"
                       f"♕⚡ اجمالي المصروفات: {stats['total_shop']:,.2f} ليرة\n"
                       f"♕⚡ رصيد: {stats['balance']:,.2f} ليرة\n")
                if stats['discount_name']:
                    msg += f"♕⚡ الخصم: {stats['discount_name']} {stats['discount_percent']}%\n"
                keyboard = {"inline_keyboard": [[
                    {"text": "📋 طلباته", "callback_data": safe_callback_data(f"my_orders_{target_user_id}")},
                    {"text": "💰 ايداعاته", "callback_data": safe_callback_data(f"my_deposits_{target_user_id}")}
                ]]}
                send_message(chat_id, msg, reply_markup=keyboard)
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ الايدي غير صحيح")
            return

        elif state.get("action") == "waiting_user_id_for_block":
            try:
                target_user_id = int(text)
                if target_user_id == MAIN_ADMIN_ID:
                    send_message(chat_id, "❌ لا يمكن حظر المدير الرئيسي")
                else:
                    block_user(target_user_id)
                    send_message(chat_id, f"✅ تم حظر المستخدم {target_user_id}")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ الايدي غير صحيح")
            return

        elif state.get("action") == "waiting_user_id_for_unblock":
            try:
                target_user_id = int(text)
                unblock_user(target_user_id)
                send_message(chat_id, f"✅ تم فك حظر المستخدم {target_user_id}")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ الايدي غير صحيح")
            return

        elif state.get("action") == "waiting_discount_user_id":
            try:
                target_user_id = int(text)
                user_states[user_id]["target_user_id"] = target_user_id
                user_states[user_id]["action"] = "waiting_discount_name"
                send_message(chat_id, "🎁 ضع اسم الخصم:")
            except:
                send_message(chat_id, "❌ الايدي غير صحيح")
            return

        elif state.get("action") == "waiting_discount_name":
            user_states[user_id]["discount_name"] = text
            user_states[user_id]["action"] = "waiting_discount_percent"
            send_message(chat_id, "📊 اكتب نسبة الخصم (رقم فقط):")
            return

        elif state.get("action") == "waiting_discount_percent":
            try:
                percent = float(text.replace(',', '.').replace(' ', ''))
                if percent <= 0 or percent > 100:
                    send_message(chat_id, "❌ النسبة يجب أن تكون بين 1 و 100")
                    return
                target_user_id = user_states[user_id]["target_user_id"]
                discount_name = user_states[user_id]["discount_name"]
                set_user_discount(target_user_id, discount_name, percent)
                send_message(chat_id, f"✅ تم تطبيق الخصم بنجاح\n🎁 {discount_name}: {percent}%")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ النسبة غير صحيحة")
            return

        elif state.get("action") == "waiting_remove_discount_user_id":
            try:
                target_user_id = int(text)
                remove_user_discount(target_user_id)
                send_message(chat_id, "✅ تم حذف الخصم بنجاح")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ الايدي غير صحيح")
            return

        elif state.get("action") == "waiting_support_username":
            set_support_username(text)
            uname = get_support_username()
            send_message(chat_id, f"✅ تم تغيير يوزر الدعم إلى: @{uname}")
            del user_states[user_id]
            return

        elif state.get("action") == "waiting_referral_amount":
            try:
                amount = float(text.strip().replace(',', '').replace(' ', '').replace('،', ''))
                if amount <= 0:
                    send_message(chat_id, "❌ المبلغ يجب أن يكون أكبر من صفر")
                    return
                set_referral_amount(amount)
                send_message(chat_id, f"✅ تم تعديل مبلغ مكافأة الإحالة إلى: {amount:,.0f} ل.س")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ المبلغ غير صحيح، أرسل رقماً فقط مثل 1000")
            return

        elif state.get("action") == "waiting_welcome_message":
            set_welcome_message(text)
            send_message(chat_id, "✅ تم تغيير رسالة الترحيب بنجاح")
            del user_states[user_id]
            return

        elif state.get("action") == "waiting_edit_category_price":
            try:
                new_price = float(text.strip().replace(",", ".").replace(" ", ""))
                cat_id = state.get("category_id")
                cat_name = state.get("category_name")
                product_name = state.get("product_name")
                with get_db() as conn:
                    conn.cursor().execute("UPDATE categories SET price = ? WHERE id = ?", (new_price, cat_id))
                exchange_rate = get_exchange_rate()
                price_syp = new_price * exchange_rate
                keyboard_back = {"inline_keyboard": [
                    [{"text": "💲 العودة لتعديل الأسعار", "callback_data": "edit_prices_menu"}],
                    [{"text": "🔙 لوحة التحكم", "callback_data": "back_admin"}]
                ]}
                send_message(chat_id,
                    f"✅ تم تعديل سعر الفئة بنجاح\n\n"
                    f"📦 المنتج: {product_name}\n"
                    f"🏷️ الفئة: {cat_name}\n"
                    f"💲 السعر الجديد: <b>{new_price:.2f}$</b>\n"
                    f"💵 بالليرة: <b>{price_syp:,.0f} ل.س</b>",
                    reply_markup=keyboard_back)
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ السعر غير صحيح، أرسل رقماً بالدولار مثل: 1.5")
            return

    is_admin_user = is_admin(user_id)

    if text == "🛡️ لوحة التحكم" and is_admin_user:
        keyboard = get_admin_main_keyboard()
        send_message(chat_id, "🛡️ لوحة التحكم:", reply_markup=keyboard)
        return

    sections = get_all_sections()
    handled = False
    for section in sections:
        sec_id, sec_name, color, emoji, is_active = section
        if text == sec_name:
            keyboard, msg = get_products_buttons(sec_name)
            section_image = get_section_image_by_name(sec_name)
            if keyboard:
                if section_image:
                    send_message(chat_id, msg, reply_markup=keyboard, photo=section_image)
                else:
                    send_message(chat_id, msg, reply_markup=keyboard)
            else:
                send_message(chat_id, msg)
            handled = True
            break

    if not handled:
        if text == "تعبئة رصيد 🏦":
            keyboard, msg = get_deposit_methods_buttons()
            if keyboard:
                send_message(chat_id, msg, reply_markup=keyboard)
            else:
                send_message(chat_id, msg)
        elif text == "الحساب والمعلومات 🗂️":
            user_info = get_telegram_user_info(user_id)
            stats = get_user_stats(user_id)
            exchange_rate = get_exchange_rate()
            balance_usd = stats['balance'] / exchange_rate if exchange_rate > 0 else 0
            ref_enabled, ref_amount = get_referral_settings()
            ref_count = get_referral_count(user_id)
            msg = (f"<b>🟢 اسمك:</b> {user_info['name']}\n"
                   f"<b>🟢 رصيدك:</b> <code>{stats['balance']:,.2f}</code> ل.س\n"
                   f"<b>🟢 ايديك:</b> <code>{user_info['user_id']}</code>\n\n"
                   f"<b>🟢 اجمالي مصروفاتك:</b> <code>{stats['total_shop']:,.2f}</code> ل.س\n"
                   f"<b>🟢 اجمالي طلباتك:</b> <code>{stats.get('total_orders', 0)}</code>\n\n"
                   f"<b>🟢 الخصم:</b> {stats['discount_percent']}%\n")
            if ref_enabled:
                bot_info = tg_api("getMe")
                bot_username = bot_info.get("result", {}).get("username", "bot") if bot_info else "bot"
                ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
                msg += (f"\n<b>🔗 رابط إحالتك:</b>\n"
                        f"<code>{ref_link}</code>\n"
                        f"<b>👥 عدد إحالاتك: {ref_count}</b>\n"
                        f"<b>💰 مكافأة كل إحالة: {ref_amount:,.0f} ل.س</b>\n")
            keyboard = {"inline_keyboard": [[
                {"text": "📋 طـلـباتـي", "callback_data": safe_callback_data(f"my_orders_{user_id}"), "color": "danger"},
                {"text": "💰 أيـداعـاتـي", "callback_data": safe_callback_data(f"my_deposits_{user_id}"), "color": "success"}
            ]]}
            send_message(chat_id, msg, reply_markup=keyboard)
        elif text == "حساب الإدارة 💬":
            uname = get_support_username()
            send_message(chat_id, f"أهلاً وسهلاً، للاستفسار والتواصل:\n\n@{uname}")
        else:
            # أي رسالة غير معروفة -> خيار غير معروف فقط + زر /start
            kb_start = {"inline_keyboard": [[{"text": "🏠 القائمة الرئيسية", "callback_data": "back_main"}]]}
            send_message(chat_id, "⚠️ خيار غير معروف\n\nاضغط الزر أدناه أو ارسل /start للقائمة الرئيسية.", reply_markup=kb_start)


# ===== معالجة الـ Callbacks =====

def handle_callback(chat_id, message_id, callback_id, data, user_id):
    try:
        answer_callback(callback_id)
        is_admin_user = is_admin(user_id)

        if not check_user_subscribed(user_id) and user_id != MAIN_ADMIN_ID and not is_admin(user_id):
            send_message(chat_id, "⚠️ عذرا عليك الاشتراك بالقنوات التالية:", reply_markup=get_check_subscription_keyboard())
            return

        # ===== القائمة الرئيسية =====
        if data == "back_main":
            send_main_menu(chat_id, user_id)

        elif data == "back_admin" and is_admin_user:
            edit_message(chat_id, message_id, "🛡️ لوحة التحكم:", reply_markup=get_admin_main_keyboard())

        elif data == "check_sub":
            if check_user_subscribed(user_id):
                delete_message(chat_id, message_id)
                send_main_menu(chat_id, user_id)
            else:
                send_message(chat_id, "⚠️ عذرا عليك الاشتراك:", reply_markup=get_check_subscription_keyboard())

        # ===== عرض المنتجات =====
        elif data.startswith("show_product_"):
            parts = data.split("_")
            if len(parts) >= 3 and parts[2].isdigit():
                product_id = int(parts[2])
                product = get_product_by_id(product_id)
                if product:
                    keyboard, msg = get_categories_buttons(product_id, product[1])
                    product_image = get_product_image(product_id)
                    delete_message(chat_id, message_id)
                    if product_image:
                        send_message(chat_id, msg, reply_markup=keyboard, photo=product_image)
                    else:
                        send_message(chat_id, msg, reply_markup=keyboard)

        elif data.startswith("category_"):
            parts = data.split("_")
            if len(parts) >= 2 and parts[1].isdigit():
                category_id = int(parts[1])
                category = get_category_by_id(category_id)
                if category:
                    cat_id, product_id, cat_name, price_usd, cat_type, min_qty, max_qty = category
                    exchange_rate = get_exchange_rate()
                    balance = get_user_balance(user_id)
                    product = get_product_by_id(product_id)

                    delete_message(chat_id, message_id)

                    discount_name, discount_percent = get_user_discount(user_id)
                    price_before_discount_usd = price_usd
                    if discount_percent > 0:
                        price_usd = price_usd * (1 - discount_percent / 100)

                    price_before_syp = price_before_discount_usd * exchange_rate
                    price_after_syp = price_usd * exchange_rate

                    # المنتجات المرتبطة للعرض
                    related = get_related_products_by_category(category_id)

                    if cat_type in ('counter', 'limited'):
                        msg = (f"<b>⚡ المنتج: {product[1] if product else 'غير معروف'}</b>\n"
                               f"<b>⚡ الفئة: {cat_name}</b>\n"
                               f"<b>🔷 السعر لكل {get_category_unit_qty(category_id)}: {price_before_discount_usd:.2f}$</b>\n")
                        if discount_percent > 0:
                            msg += f"<b>🔷 السعر بعد الخصم: {price_usd:.2f}$</b>\n"
                        msg += (f"<b>🔷 السعر بليرة: {price_before_syp:,.2f} ليرة</b>\n"
                                f"<b>⚡ الحد الادنى: {min_qty}</b>\n"
                                f"<b>⚡ الحد الاعلى: {max_qty}</b>\n")
                        if discount_percent > 0:
                            msg += f"<b>🎁 خصم {discount_name}: {discount_percent}%</b>\n"
                        # عرض المنتجات المرتبطة إن وجدت
                        if related:
                            msg += f"\n<b>━━━━━━━━━━━━━━━━━━━━</b>\n<b>🔗 منتجات مرتبطة من مزودين:</b>\n"
                            for rel in related:
                                rel_id, rel_prov_id, rel_api_id, rel_api_name, rel_api_price, rel_prov_name = rel
                                msg += f"• <b>{rel_api_name}</b> - {float(rel_api_price):.2f}$ [{rel_prov_name or 'مزود'}]\n"
                            msg += "<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
                        if category_requires_id(category_id):
                            msg += f"<b>🔶 ارسل متطلبات شراء الخدمة (ايدي الاعب) 🔶:</b>"
                        else:
                            msg += f"<b>🔶 هذا المنتج لا يحتاج ايدي — ارسل نقطة ( . ) للمتابعة 🔶:</b>"
                        user_states[user_id] = {
                            "action": "waiting_player_id",
                            "category_id": category_id,
                            "cat_type": cat_type,
                            "min_qty": min_qty,
                            "max_qty": max_qty,
                            "price_usd": price_usd
                        }
                        # عرض صورة الفئة إن وجدت
                        cat_image = get_category_image_by_id(category_id)
                        if cat_image:
                            send_message(chat_id, msg, photo=cat_image)
                        else:
                            send_message(chat_id, msg)
                    else:
                        msg = (f"<b>🔶 المنتج: {product[1] if product else 'غير معروف'}</b>\n\n"
                               f"<b>🔶 الفئة: {cat_name}</b>\n\n"
                               f"<b>🔶 السعر الاصلي بالدولار: {price_before_discount_usd:.2f}$</b>\n")
                        if discount_percent > 0:
                            msg += f"<b>🔶 السعر بعد الخصم بالدولار: {price_usd:.2f}$</b>\n"
                        msg += f"<b>🔶 السعر الاصلي بليرة: {price_before_syp:,.2f} ليرة</b>\n"
                        if discount_percent > 0:
                            msg += f"<b>🔶 السعر بعد الخصم بليرة: {price_after_syp:,.2f} ليرة</b>\n\n"
                            msg += f"<b>🎁 خصم {discount_name}: {discount_percent}%</b>\n\n"
                        else:
                            msg += f"<b>🔶 السعر بليرة: {price_after_syp:,.2f} ليرة</b>\n\n"
                        msg += f"<b>🔶 رصيدك الان: {balance:,.2f} ليرة</b>\n\n"
                        # عرض المنتجات المرتبطة إن وجدت
                        if related:
                            msg += f"<b>━━━━━━━━━━━━━━━━━━━━</b>\n<b>🔗 منتجات مرتبطة من مزودين:</b>\n"
                            for rel in related:
                                rel_id, rel_prov_id, rel_api_id, rel_api_name, rel_api_price, rel_prov_name = rel
                                msg += f"• <b>{rel_api_name}</b> - {float(rel_api_price):.2f}$ [{rel_prov_name or 'مزود'}]\n"
                            msg += "<b>━━━━━━━━━━━━━━━━━━━━</b>\n\n"
                        if category_requires_id(category_id):
                            msg += f"<b>◽ ادخل ايدي الاعب لشحن المنتج او متطلبات الخدمة:</b>"
                        else:
                            msg += f"<b>◽ هذا المنتج لا يحتاج ايدي — ارسل نقطة ( . ) للمتابعة:</b>"

                        user_states[user_id] = {"action": "waiting_player_id", "category_id": category_id}
                        # عرض صورة الفئة إن وجدت
                        cat_image = get_category_image_by_id(category_id)
                        if cat_image:
                            send_message(chat_id, msg, photo=cat_image)
                        else:
                            send_message(chat_id, msg)

        elif data.startswith("auto_deposit_") and not data.startswith("auto_deposit_menu"):
            parts = data.split("_")
            if len(parts) >= 3 and parts[2].isdigit():
                method_id = int(parts[2])
                msg, image, api_token, api_url = get_auto_deposit_method_details(method_id)
                if msg:
                    user_states[user_id] = {
                        "action": "waiting_deposit_amount",
                        "method_id": method_id,
                        "is_auto": True,
                        "api_token": api_token,
                        "api_url": api_url
                    }
                    if image:
                        delete_message(chat_id, message_id)
                        send_message(chat_id, msg, photo=image)
                    else:
                        edit_message(chat_id, message_id, msg)

        elif data.startswith("deposit_") and data != "deposit_management":
            parts = data.split("_")
            if len(parts) >= 2 and parts[1].isdigit():
                method_id = int(parts[1])
                msg, image = get_deposit_method_details(method_id)
                if msg:
                    user_states[user_id] = {"action": "waiting_deposit_amount", "method_id": method_id, "is_auto": False}
                    if image:
                        delete_message(chat_id, message_id)
                        send_message(chat_id, msg, photo=image)
                    else:
                        edit_message(chat_id, message_id, msg)

        elif data.startswith("confirm_buy_"):
            buyer_id = int(data.split("_")[2])
            if user_id == buyer_id:
                if user_id in pending_orders:
                    order = pending_orders[user_id]
                    balance = get_user_balance(user_id)

                    if balance >= order["price_syp"]:
                        new_balance = update_user_balance(user_id, -order["price_syp"])

                        if order.get("linked"):
                            api_product_id = order["api_product_id"]
                            player_id = order["player_id"]
                            qty = order.get("qty", 1)
                            p_token = order.get("provider_token")
                            p_url = order.get("provider_url")
                            provider_id = order.get("provider_id", 0)

                            start_time = time.time()
                            api_result = buy_from_api(api_product_id, player_id, qty,
                                                      api_token=p_token, api_base_url=p_url)

                            if isinstance(api_result, dict) and api_result.get("status") == "OK":
                                data_res = api_result.get("data", {})
                                order_id = data_res.get("order_id")
                                # يستخرج الملاحظات من أي حقل (replay_api, notes, message...)
                                replay_text = extract_replay_text(data_res) or "جاري المعالجة"
                                data_status = str(data_res.get("status", "")).lower()

                                # ===== فحص الرفض الفوري من الرد الأول =====
                                REJECT_KEYWORDS = [
                                    "invalid", "error", "fail", "wrong", "not found",
                                    "invalid player", "invalid id", "try again",
                                    "غير صحيح", "خطأ", "لا يوجد", "reject", "failed"
                                ]
                                # نجمع كل النصوص الممكنة للفحص
                                all_texts = " ".join([
                                    str(data_res.get("replay_api", "") or ""),
                                    str(data_res.get("notes", "") or ""),
                                    str(data_res.get("note", "") or ""),
                                    str(data_res.get("message", "") or ""),
                                ]).lower()
                                is_instant_reject = (
                                    any(kw in all_texts for kw in REJECT_KEYWORDS)
                                    or data_status in ["reject", "rejected", "failed", "fail", "error", "canceled"]
                                )

                                if is_instant_reject:
                                    # الموقع رفض فوراً ← نسترد الرصيد مباشرة بدون انتظار
                                    update_user_balance(user_id, order["price_syp"])
                                    new_bal = get_user_balance(user_id)
                                    elapsed_time = time.time() - start_time
                                    instant_reject_msg = (
                                        f"❌ عذراً، تعذر إكمال طلبك\n\n"
                                        f"⚡المنتج: {order['product_name']}\n"
                                        f"⚡️ الحزمة: {order['cat_name']}\n"
                                        f"⚡️ الكمية: {qty}\n"
                                        f"⚡️ السعر: {order['price_syp']:,.0f} ل.س\n"
                                        f"⚡️ اللاعب: {player_id} ⚡\n"
                                        f"⚡️ رقم الطلب: \n"
                                        f"⚡️ حالة الطلب: رفض ❌\n"
                                        f"⚡️ السبب: {replay_text}\n\n"
                                        f"تم استعادة رصيدك تلقائياً.\n"
                                        f"الرصيد الحالي: {new_bal:,.0f} ل.س"
                                    )
                                    send_message(user_id, instant_reject_msg)
                                    send_message(ADMIN_CHAT_ID,
                                        f"<b>تم رفض الطلب من API❌ (فوري):</b>\n"
                                        f"<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
                                        f"<b>🔴⚡ المنتج: {order['product_name']}</b>\n"
                                        f"<b>🔴⚡ الفئة: {order['cat_name']}</b>\n"
                                        f"<b>🔴⚡ السعر: {order['price_syp']:,.2f} ليرة</b>\n"
                                        f"<b>🔴⚡ الايدي: {player_id}</b>\n"
                                        f"<b>🔴⚡ رد النظام: <code>{replay_text}</code></b>\n"
                                        f"<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
                                        f"<b>◽ المستخدم: {get_telegram_user_info(user_id)['name']}</b>\n"
                                        f"<b>◽ ايديه: {user_id}</b>\n"
                                        f"<b>◽ رصيده: {new_bal:,.2f} ليرة</b>"
                                    )
                                else:
                                    # الطلب مقبول ← ابدأ المراقبة
                                    order_db_id = save_api_order(user_id, 0, order_id,
                                                                  order["product_name"], order["cat_name"],
                                                                  order["price_syp"], player_id, qty,
                                                                  replay_text, provider_id)

                                    success_msg = (
                                        f"✅ تم إنشاء طلبك بنجاح!\n\n"
                                        f"▪️ اللعبة: {order['product_name']}\n"
                                        f"▪️ الحزمة: {order['cat_name']}\n"
                                        f"▪️ الكمية: {qty}\n"
                                        f"▪️ ID اللاعب: {player_id}\n"
                                        f"▪️ رقم الطلب: {order_db_id}\n"
                                        f"▪️ السعر: {order['price_syp']:,.0f} ل.س ({order['price_syp'] / get_exchange_rate():.2f}$)\n"
                                        
                                    )
                                    _sent = send_message(user_id, success_msg)
                                    _pending_msg_id = _sent.get("result", {}).get("message_id") if isinstance(_sent, dict) else None

                                    threading.Thread(
                                        target=monitor_api_order,
                                        args=(order_db_id, user_id, chat_id, start_time, order["price_syp"]),
                                        kwargs={"api_token": p_token, "api_base_url": p_url, "pending_msg_id": _pending_msg_id},
                                        daemon=True
                                    ).start()
                            else:
                                update_user_balance(user_id, order["price_syp"])
                                new_bal = get_user_balance(user_id)
                                error_msg = str(api_result)
                                fail_msg = (
                                    f"تم رفض طلبك من المزود❌:\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"🔴⚡ المنتج: {order['product_name']}\n"
                                    f"🔴⚡ الفئة: {order['cat_name']}\n"
                                    f"🔴⚡ السعر: {order['price_syp']:,.2f} ليرة\n"
                                    f"🔴⚡ الايدي: {order['player_id']}\n"
                                    f"🔴⚡ الكمية: {order.get('qty', 1)}\n"
                                    f"🔴⚡ رد النظام: {error_msg}\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"💰 تم استرداد رصيدك: {order['price_syp']:,.2f} ليرة\n"
                                    f"💰 رصيدك الحالي: {new_bal:,.2f} ليرة"
                                )
                                send_message(user_id, fail_msg)
                        else:
                            with get_db() as conn:
                                c = conn.cursor()
                                c.execute('''INSERT INTO shop_orders (user_id, product_name, category_name, price, player_id, qty, status)
                                    VALUES (?, ?, ?, ?, ?, ?, 'pending')''',
                                          (user_id, order["product_name"], order["cat_name"],
                                           order["price_syp"], order["player_id"], order.get("qty", 1)))
                                order_id_db = c.lastrowid

                            success_msg = (
                                f"✅ تم إنشاء طلبك بنجاح!\n\n"
                                f"▪️ اللعبة: {order['product_name']}\n"
                                f"▪️ الحزمة: {order['cat_name']}\n"
                                f"▪️ الكمية: {order.get('qty', 1)}\n"
                                f"▪️ ID اللاعب: {order['player_id']}\n"
                                f"▪️ رقم الطلب: {order_id_db}\n"
                                f"▪️ السعر: {order['price_syp']:,.0f} ل.س ({order['price_syp'] / get_exchange_rate():.2f}$)\n"
                                
                            )
                            _sent_manual = send_message(user_id, success_msg)
                            _manual_msg_id = _sent_manual.get("result", {}).get("message_id") if isinstance(_sent_manual, dict) else None
                            if _manual_msg_id:
                                manual_order_msg_ids[order_id_db] = (user_id, _manual_msg_id)

                            user_info = get_telegram_user_info(user_id)
                            admin_msg = (f"🔶 طلب شحن منتج جديد 🔶\n"
                                         f"🔶 المستخدم: {user_info['name']}\n"
                                         f"🔶 الايدي: {user_id}\n"
                                         f"🔶 المعرف: {user_info['username']}\n"
                                         f"----------------------------\n"
                                         f"🔶 المنتج: {order['product_name']}\n"
                                         f"🔶 الفئة: {order['cat_name']}\n"
                                         f"🔶 سعر المنتج: {order['price_syp']:,.2f} ليرة\n"
                                         f"🔶 الكمية: {order.get('qty', 1)}\n"
                                         f"🔶 رصيده الان: {new_balance:,.2f} ليرة\n"
                                         f"🔶 ايدي الاعب: {order['player_id']}")
                            if order.get('discount_percent', 0) > 0:
                                admin_msg += f"\n🎁 الخصم: {order.get('discount_name', '')} {order.get('discount_percent', 0)}%"

                            keyboard = {"inline_keyboard": [[
                                {"text": "🟢 قبول الشحن", "callback_data": safe_callback_data(f"accept_order_{order_id_db}"), "color": "success"},
                                {"text": "🔴 رفض الشحن", "callback_data": safe_callback_data(f"reject_order_{order_id_db}"), "color": "danger"}
                            ]]}
                            send_message(ADMIN_CHAT_ID, admin_msg, reply_markup=keyboard)

                        del pending_orders[user_id]
                        edit_message(chat_id, message_id, "✅ تم تأكيد الطلب بنجاح")
                    else:
                        send_message(user_id, "❌ رصيدك غير كافي لإتمام العملية")
                        edit_message(chat_id, message_id, "❌ رصيد غير كافي")
                else:
                    edit_message(chat_id, message_id, "❌ لا يوجد طلب معلق")

        elif data == "change_player_id":
            user_states[user_id] = {"action": "waiting_new_player_id"}
            edit_message(chat_id, message_id, "🎮 ارسل ايدي اللاعب الجديد:")

        elif data == "cancel_buy":
            if user_id in pending_orders:
                del pending_orders[user_id]
            edit_message(chat_id, message_id, "❌ تم الغاء عملية الشراء")

        elif data == "back_to_categories":
            if user_id in pending_orders:
                order = pending_orders[user_id]
                product = get_product_by_id(order["product_id"])
                if product:
                    keyboard, msg = get_categories_buttons(order["product_id"], product[1])
                    product_image = get_product_image(order["product_id"])
                    delete_message(chat_id, message_id)
                    if product_image:
                        send_message(chat_id, msg, reply_markup=keyboard, photo=product_image)
                    else:
                        send_message(chat_id, msg, reply_markup=keyboard)
                del pending_orders[user_id]

        elif data == "back_to_products":
            sections = get_all_sections()
            keyboard = {"inline_keyboard": []}
            for section in sections:
                sec_id, sec_name, color, emoji, is_active = section
                keyboard["inline_keyboard"].append([{"text": sec_name, "callback_data": safe_callback_data(f"back_to_{sec_name}")}])
            edit_message(chat_id, message_id, "اختر القسم:", reply_markup=keyboard)

        elif data.startswith("back_to_"):
            section_name = data[len("back_to_"):]
            keyboard, msg = get_products_buttons(section_name)
            if keyboard:
                edit_message(chat_id, message_id, msg, reply_markup=keyboard)

        # ===== قبول/رفض الطلبات =====
        elif data.startswith("accept_order_"):
            if is_admin_user:
                order_id = int(data.split("_")[2])
                with get_db() as conn:
                    c = conn.cursor()
                    c.execute("SELECT user_id, product_name, category_name, price, player_id, qty, created_at FROM shop_orders WHERE id = ?", (order_id,))
                    order = c.fetchone()
                    if order:
                        target_user_id, product_name, category_name, price, player_id, qty, created_at = order
                        c.execute("UPDATE shop_orders SET status = 'accepted', completed_at = ? WHERE id = ?", (datetime.utcnow(), order_id))

                if order:
                    add_notification(target_user_id, "✅ تم شحن طلبك", f"تم تنفيذ طلب «{product_name}» بنجاح", "success")
                    try:
                        created_time = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                        elapsed_time = time.time() - created_time.timestamp()
                    except:
                        elapsed_time = 0
                    _m_h = int(elapsed_time // 3600)
                    _m_m = int((elapsed_time % 3600) // 60)
                    _m_s = int(elapsed_time % 60)
                    _price_usd_m = price / get_exchange_rate() if get_exchange_rate() > 0 else 0
                    success_msg = (f"✅ تم اكتمال طلبك بنجاح!\n\n"
                                   f"▪️ اللعبة: {product_name}\n"
                                   f"▪️ الحزمة: {category_name}\n"
                                   f"▪️ الكمية: {qty if qty else 1}\n"
                                   f"▪️ ID اللاعب: {player_id}\n"
                                   f"▪️ رقم الطلب: {order_id}\n"
                                   f"▪️ السعر: {price:,.0f} ل.س ({_price_usd_m:.2f}$)\n"
                                   f"▪️ الوقت المستغرق:  {_m_m} دقائق و {_m_s} ثانية\n\n"
                                   f"شكراً لاستخدامك خدماتنا ❤️")
                    _m = manual_order_msg_ids.pop(order_id, None)
                    if _m:
                        edit_or_send(_m[0], _m[1], success_msg)
                    else:
                        send_message(target_user_id, success_msg)
                    edit_message(chat_id, message_id, "✅ تم قبول طلب الشحن")

        elif data.startswith("reject_order_"):
            if is_admin_user:
                order_id = int(data.split("_")[2])
                with get_db() as conn:
                    c = conn.cursor()
                    c.execute("""SELECT user_id, price, product_name, category_name, player_id, qty
                                 FROM shop_orders WHERE id = ?""", (order_id,))
                    order = c.fetchone()
                    new_bal_rej = None
                    if order:
                        target_user_id, price, _pname, _cname, _plid, _qty = order
                        c.execute("UPDATE shop_orders SET status = 'rejected', completed_at = ? WHERE id = ?", (datetime.utcnow(), order_id))
                        # استرداد الرصيد وقراءة الرصيد الجديد بنفس الاتصال (بدون فتح اتصال متداخل جديد)
                        c.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (target_user_id,))
                        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, target_user_id))
                        c.execute("SELECT balance FROM users WHERE user_id = ?", (target_user_id,))
                        new_bal_rej = c.fetchone()[0]

                # الإشعار وإرسال الرسالة بعد إغلاق الاتصال (commit) — يمنع تزاحم اتصالات SQLite
                # متداخلة بنفس اللحظة (كانت add_notification/get_user_balance تفتح اتصالات جديدة
                # وسط معاملة لسا مفتوحة، وهاد بيسبب "database is locked" تحت الضغط الحقيقي)
                if order:
                    add_notification(target_user_id, "❌ تم رفض طلبك", "تم رفض طلبك وإعادة المبلغ لرصيدك", "danger")
                    _m = manual_order_msg_ids.pop(order_id, None)
                    _price_usd_rej = price / get_exchange_rate() if get_exchange_rate() > 0 else 0
                    reject_txt = (
                        f"❌ عذراً، تعذر إكمال طلبك\n\n"
                        f"⚡المنتج: {_pname}\n"
                        f"⚡️ الحزمة: {_cname}\n"
                        f"⚡️ الكمية: {_qty if _qty else 1}\n"
                        f"⚡️ السعر: {price:,.0f} ل.س\n"
                        f"⚡️ اللاعب: {_plid} ⚡\n"
                        f"⚡️ رقم الطلب: {order_id}\n"
                        f"⚡️ حالة الطلب: رفض ❌\n"
                        f"⚡️ السبب: \n\n"
                        f"تم استعادة رصيدك تلقائياً.\n"
                        f"الرصيد الحالي: {new_bal_rej:,.0f} ل.س"
                    )
                    if _m:
                        edit_or_send(_m[0], _m[1], reject_txt)
                    else:
                        send_message(target_user_id, reject_txt)
                edit_message(chat_id, message_id, "❌ تم رفض طلب الشحن")

        elif data.startswith("accept_deposit_"):
            if is_admin_user:
                request_id = int(data.split("_")[2])
                success, req_user_id, amount = accept_deposit_request(request_id)
                if success:
                    send_message(req_user_id, f"🎉 تم معالجة ايداعك بنجاح✅:\n⚡ المبلغ: {amount:,.2f} ليرة\n❤ تم قبول الايداع بنجاح")
                    edit_message(chat_id, message_id, f"✅ تم قبول الإيداع\n💰 المبلغ: {amount:,.2f} ليرة")
                else:
                    edit_message(chat_id, message_id, "❌ فشل في قبول الطلب")

        elif data.startswith("reject_deposit_"):
            if is_admin_user:
                request_id = int(data.split("_")[2])
                reject_deposit_request(request_id)
                with get_db() as conn:
                    c = conn.cursor()
                    c.execute("SELECT user_id FROM deposit_requests WHERE id = ?", (request_id,))
                    result = c.fetchone()
                    if result:
                        send_message(result[0], "❌ تم رفض ايداعك من قبل الادارة❌\n\n⚠ يرجى تأكد من المعلومات وتواصل مع الدعم")
                edit_message(chat_id, message_id, "❌ تم رفض طلب الإيداع")

        # ===== المنتجات والفئات =====
        elif data.startswith("my_orders_"):
            target_user_id = int(data.split("_")[2])
            if target_user_id == user_id or is_admin_user:
                orders = get_user_orders(target_user_id)
                if not orders:
                    send_message(chat_id, "📋 لا توجد طلبات سابقة")
                else:
                    msg = "📋 <b>قائمة طلباتك:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                    for order in orders[:20]:
                        product_name, category_name, price, player_id, qty, status, created_at = order
                        s_emoji = "✅" if status == "accepted" else ("⏳" if status == "pending" else "❌")
                        s_text = "مقبول" if status == "accepted" else ("قيد المعالجة" if status == "pending" else "مرفوض")
                        msg += f"{s_emoji} <b>{product_name}</b> - {category_name}\n"
                        msg += f"   💰 {price:,.2f} ليرة | 🆔 {player_id}\n"
                        msg += f"   📦 الكمية: {qty} | 📅 {created_at[:16]}\n"
                        msg += f"   📌 الحالة: {s_text}\n━━━━━━━━━━━━━━━━━━━━\n"
                    send_message(chat_id, msg)
            else:
                send_message(chat_id, "❌ لا يمكنك عرض طلبات مستخدم آخر")

        elif data.startswith("my_deposits_"):
            target_user_id = int(data.split("_")[2])
            if target_user_id == user_id or is_admin_user:
                deposits = get_user_deposits(target_user_id)
                if not deposits:
                    send_message(chat_id, "💰 لا توجد ايداعات سابقة")
                else:
                    msg = "💰 <b>قائمة ايداعاتك:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                    for dep in deposits[:20]:
                        method_title, amount_syp, transaction_code, status, created_at = dep
                        s_emoji = "✅" if status == "accepted" else ("⏳" if status == "pending" else "❌")
                        s_text = "مقبول" if status == "accepted" else ("قيد المراجعة" if status == "pending" else "مرفوض")
                        msg += f"{s_emoji} <b>{method_title}</b>\n   💰 {amount_syp:,.2f} ليرة\n   🔢 {transaction_code}\n   📅 {created_at[:16]}\n   📌 {s_text}\n━━━━━━━━━━━━━━━━━━━━\n"
                    send_message(chat_id, msg)
            else:
                send_message(chat_id, "❌ لا يمكنك عرض ايداعات مستخدم آخر")

        # ===== لوحة التحكم - المنتجات =====
        elif data == "admin_products" and is_admin_user:
            edit_message(chat_id, message_id, "📦 إدارة المنتجات:", reply_markup=get_admin_products_keyboard())

        elif data == "manage_description" and is_admin_user:
            keyboard = get_description_management_keyboard()
            edit_message(chat_id, message_id, "📝 إدارة وصف الأقسام:", reply_markup=keyboard)

        elif data.startswith("desc_section_"):
            section_id_str = data[len("desc_section_"):]
            section_name = section_id_str
            if section_id_str.isdigit():
                sec_row = get_section_by_id(int(section_id_str))
                if sec_row:
                    section_name = sec_row[1]
            edit_message(chat_id, message_id, f"📝 قسم {section_name}\nارسل وصف القسم الجديد:")

        elif data == "manage_images" and is_admin_user:
            keyboard, msg = get_products_for_image_menu()
            if keyboard:
                edit_message(chat_id, message_id, msg, reply_markup=keyboard)
            else:
                edit_message(chat_id, message_id, msg)

        # صور الفئات من لوحة المنتجات
        elif data == "manage_category_images_prod" and is_admin_user:
            keyboard, msg = get_categories_for_image_menu("admin_products")
            if keyboard:
                edit_message(chat_id, message_id, msg, reply_markup=keyboard)
            else:
                edit_message(chat_id, message_id, msg)

        elif data == "product_description_menu" and is_admin_user:
            keyboard, msg = get_products_for_product_desc_menu()
            if keyboard:
                edit_message(chat_id, message_id, msg, reply_markup=keyboard)
            else:
                edit_message(chat_id, message_id, msg)

        elif data == "delete_category_menu" and is_admin_user:
            keyboard, msg = get_delete_category_menu()
            if keyboard:
                edit_message(chat_id, message_id, msg, reply_markup=keyboard)
            else:
                edit_message(chat_id, message_id, msg)

        elif data.startswith("delete_category_"):
            if is_admin_user:
                category_id = int(data.split("_")[2])
                delete_category(category_id)
                edit_message(chat_id, message_id, "✅ تم حذف الفئة بنجاح")

        elif data == "add_counter_category" and is_admin_user:
            products = get_all_products()
            if not products:
                edit_message(chat_id, message_id, "🚫 لا توجد منتجات")
            else:
                keyboard = {"inline_keyboard": []}
                for product in products:
                    product_id, name, category, emoji, desc, img = product
                    display_name = f"{emoji} {name}" if emoji else name
                    keyboard["inline_keyboard"].append([{"text": f"{display_name} ({category})", "callback_data": safe_callback_data(f"counter_category_{product_id}")}])
                keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "admin_products"}])
                edit_message(chat_id, message_id, "اختر المنتج لإضافة فئة عداد:", reply_markup=keyboard)

        elif data == "add_limited_category" and is_admin_user:
            products = get_all_products()
            if not products:
                edit_message(chat_id, message_id, "🚫 لا توجد منتجات")
            else:
                keyboard = {"inline_keyboard": []}
                for product in products:
                    product_id, name, category, emoji, desc, img = product
                    display_name = f"{emoji} {name}" if emoji else name
                    keyboard["inline_keyboard"].append([{"text": f"{display_name} ({category})", "callback_data": safe_callback_data(f"limited_category_{product_id}")}])
                keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "admin_products"}])
                edit_message(chat_id, message_id, "اختر المنتج لإضافة فئة (كمية محددة):", reply_markup=keyboard)

        elif data.startswith("counter_category_"):
            if is_admin_user:
                product_id = int(data.split("_")[2])
                product = get_product_by_id(product_id)
                if product:
                    user_states[user_id] = {"action": "waiting_category_name", "product_id": product_id, "product_name": product[1], "cat_type": "counter"}
                    edit_message(chat_id, message_id, f"📝 {product[1]}\nاكتب اسم الفئة:")

        elif data.startswith("limited_category_"):
            if is_admin_user:
                product_id = int(data.split("_")[2])
                product = get_product_by_id(product_id)
                if product:
                    user_states[user_id] = {"action": "waiting_category_name", "product_id": product_id, "product_name": product[1], "cat_type": "limited"}
                    edit_message(chat_id, message_id, f"📝 {product[1]}\nاكتب اسم الفئة:")

        elif data.startswith("image_product_"):
            if is_admin_user:
                product_id = int(data.split("_")[2])
                product = get_product_by_id(product_id)
                if product:
                    user_states[user_id] = {"action": "waiting_product_image", "product_id": product_id}
                    edit_message(chat_id, message_id, f"🖼️ المنتج: {product[1]}\nارسل الصورة (كصورة وليس رابط):")

        elif data.startswith("desc_product_"):
            if is_admin_user:
                product_id = int(data.split("_")[2])
                product = get_product_by_id(product_id)
                if product:
                    user_states[user_id] = {"action": "waiting_product_description", "product_id": product_id}
                    edit_message(chat_id, message_id, f"📝 المنتج: {product[1]}\nارسل وصف المنتج الجديد:")

        elif data.startswith("cat_img_") and is_admin_user:
            cat_id = int(data.split("_")[2])
            cat = get_category_by_id(cat_id)
            if cat:
                user_states[user_id] = {"action": "waiting_category_image", "category_id": cat_id}
                edit_message(chat_id, message_id, f"🖼️ الفئة: {cat[2]}\nارسل الصورة (كصورة وليس رابط):")

        # ===== لوحة التحكم - الايداعات =====
        elif data == "deposit_management" and is_admin_user:
            edit_message(chat_id, message_id, "💳 إدارة الايداعات:", reply_markup=get_deposit_management_keyboard())

        elif data == "add_deposit" and is_admin_user:
            user_states[user_id] = {"action": "waiting_deposit_title"}
            edit_message(chat_id, message_id, "✏️ اكتب اسم طريقة الإيداع:")

        elif data == "edit_deposit" and is_admin_user:
            keyboard, msg = get_deposit_methods_for_edit()
            if keyboard:
                edit_message(chat_id, message_id, msg, reply_markup=keyboard)
            else:
                kb_back = {"inline_keyboard": [[{"text": "🔙 رجوع", "callback_data": "deposit_management"}]]}
                edit_message(chat_id, message_id, msg, reply_markup=kb_back)

        elif data == "edit_auto_deposit_menu" and is_admin_user:
            keyboard, msg = get_auto_deposit_methods_for_edit()
            if keyboard:
                edit_message(chat_id, message_id, msg, reply_markup=keyboard)
            else:
                kb_back = {"inline_keyboard": [[{"text": "🔙 رجوع", "callback_data": "deposit_management"}]]}
                edit_message(chat_id, message_id, msg, reply_markup=kb_back)

        elif data.startswith("edit_auto_method_") and is_admin_user:
            mid = int(data.replace("edit_auto_method_", ""))
            method = get_auto_deposit_method_by_id(mid)
            if method:
                user_states[user_id] = {"action": "waiting_edit_auto_title", "method_id": mid}
                edit_message(chat_id, message_id,
                             f"✏️ تعديل: {method[1]}\n\n"
                             f"📋 الحالي:\n"
                             f"  الاسم: {method[1]}\n"
                             f"  الكود: {method[3]}\n"
                             f"  سعر الصرف: {method[4]:,.0f}\n"
                             f"  الرابط: {method[6] or 'غير محدد'}\n\n"
                             f"اكتب الاسم الجديد:")
            else:
                edit_message(chat_id, message_id, "❌ لم يتم العثور على الطريقة")

        elif data.startswith("edit_method_") and is_admin_user:
            method_id = int(data.replace("edit_method_", ""))
            method = get_deposit_method_by_id(method_id)
            if method:
                user_states[user_id] = {"action": "waiting_edit_title", "method_id": method_id}
                edit_message(chat_id, message_id,
                             f"✏️ تعديل: {method[1]}\n\n"
                             f"📋 الحالي:\n"
                             f"  الاسم: {method[1]}\n"
                             f"  الكود: {method[3]}\n"
                             f"  سعر الصرف: {method[4]:,.0f}\n\n"
                             f"اكتب الاسم الجديد:")

        elif data == "delete_deposit" and is_admin_user:
            keyboard, msg = get_deposit_methods_for_delete()
            if keyboard:
                edit_message(chat_id, message_id, msg, reply_markup=keyboard)

        elif data.startswith("delete_method_"):
            if is_admin_user:
                method_id = int(data.split("_")[2])
                delete_deposit_method(method_id)
                edit_message(chat_id, message_id, "✅ تم حذف طريقة الإيداع")

        elif data == "add_auto_deposit" and is_admin_user:
            user_states[user_id] = {"action": "waiting_auto_deposit_token"}
            edit_message(chat_id, message_id, "🔑 ارسل توكن API للتحقق التلقائي:")

        elif data == "delete_auto_deposit_menu" and is_admin_user:
            keyboard, msg = get_auto_deposit_methods_for_delete()
            if keyboard:
                edit_message(chat_id, message_id, msg, reply_markup=keyboard)
            else:
                edit_message(chat_id, message_id, msg)

        elif data.startswith("delete_auto_method_") and is_admin_user:
            mid = int(data.split("_")[3])
            delete_auto_deposit_method(mid)
            edit_message(chat_id, message_id, "✅ تم حذف طريقة الإيداع التلقائي")

        elif data == "manage_deposit_images" and is_admin_user:
            keyboard, msg = get_deposit_methods_for_image_menu()
            if keyboard:
                edit_message(chat_id, message_id, msg, reply_markup=keyboard)
            else:
                edit_message(chat_id, message_id, msg)

        elif data.startswith("dep_img_") and is_admin_user:
            mid = int(data.split("_")[2])
            method = get_deposit_method_by_id(mid)
            if method:
                user_states[user_id] = {"action": "waiting_deposit_method_image", "method_id": mid, "is_auto": False}
                edit_message(chat_id, message_id, f"🖼️ طريقة الإيداع: {method[1]}\nارسل الصورة:")

        elif data.startswith("auto_dep_img_") and is_admin_user:
            mid = int(data.split("_")[3])
            method = get_auto_deposit_method_by_id(mid)
            if method:
                user_states[user_id] = {"action": "waiting_deposit_method_image", "method_id": mid, "is_auto": True}
                edit_message(chat_id, message_id, f"🖼️ طريقة الإيداع: {method[1]}\nارسل الصورة:")

        # ===== لوحة التحكم - API =====
        elif data == "admin_api" and is_admin_user:
            providers_count = len(get_all_api_providers())
            linked_count = len(get_linked_products())
            api_msg = (
                f"🔐 <b>مركز إدارة API</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔌 المزودون المتصلون: <b>{providers_count}/10000</b>\n"
                f"🔗 المنتجات المربوطة: <b>{linked_count}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"اختر العملية المطلوبة:"
            )
            keyboard = {"inline_keyboard": [
                [{"text": f"🔌 إدارة المزودين  ({providers_count}/10000)", "callback_data": "providers_management"}],
                [{"text": "🔗 ربط منتج بـ API", "callback_data": "link_products"},
                 {"text": "🔓 فك الربط", "callback_data": "unlink_products"}],
                [{"text": "📋 المنتجات المرتبطة للعرض", "callback_data": "related_products_menu"}],
                [{"text": "🔍 بحث في منتجات API", "callback_data": "search_products"}],
                [{"text": "🔙 رجوع للوحة التحكم", "callback_data": "back_admin"}]
            ]}
            edit_message(chat_id, message_id, api_msg, reply_markup=keyboard)

        # ===== إدارة المزودين =====
        elif data == "providers_management" and is_admin_user:
            keyboard, msg = get_providers_management_keyboard()
            edit_message(chat_id, message_id, msg, reply_markup=keyboard)

        elif data == "add_provider" and is_admin_user:
            providers = get_all_api_providers()
            if len(providers) >= 10000:
                edit_message(chat_id, message_id, "❌ وصلت الحد الأقصى (10000 مزود). احذف مزوداً لإضافة جديد.")
            else:
                user_states[user_id] = {"action": "waiting_provider_name"}
                edit_message(chat_id, message_id, "✏️ ارسل اسم المزود الجديد:")

        elif data.startswith("edit_provider_") and is_admin_user:
            pid = int(data.split("_")[2])
            provider = get_api_provider_by_id(pid)
            if provider:
                user_states[user_id] = {"action": "waiting_edit_provider_name", "provider_id": pid}
                edit_message(chat_id, message_id, f"✏️ تعديل المزود: {provider[1]}\nارسل الاسم الجديد:")

        elif data.startswith("delete_provider_") and is_admin_user:
            pid = int(data.split("_")[2])
            provider = get_api_provider_by_id(pid)
            if provider:
                delete_api_provider(pid)
                edit_message(chat_id, message_id, f"✅ تم حذف المزود '{provider[1]}' بنجاح")

        elif data.startswith("test_provider_") and is_admin_user:
            pid = int(data.split("_")[2])
            provider = get_api_provider_by_id(pid)
            if provider:
                pid2, pname, ptoken, purl = provider
                edit_message(chat_id, message_id,
                             f"⏳ جاري اختبار الاتصال بـ {pname}...\nقد يستغرق بضع ثوانٍ.")
                profile = get_profile(api_token=ptoken, api_base_url=purl)
                if profile:
                    balance = profile.get("balance", profile.get("credit", profile.get("wallet", "غير محدد")))
                    email   = profile.get("email", profile.get("username", profile.get("name", "غير محدد")))
                    edit_message(chat_id, message_id,
                                 f"✅ الربط يعمل!\n"
                                 f"🔌 المزود: {pname}\n"
                                 f"💰 الرصيد: {balance}\n"
                                 f"📧 الحساب: {email}\n\n"
                                 f"🌐 الرابط: {purl}")
                else:
                    # جرب جلب المنتجات كبديل للتحقق
                    products = get_all_api_products(api_token=ptoken, api_base_url=purl)
                    if products:
                        edit_message(chat_id, message_id,
                                     f"✅ الربط يعمل! (تم جلب {len(products)} منتج)\n"
                                     f"🔌 المزود: {pname}\n"
                                     f"⚠️ ملاحظة: endpoint البروفايل غير متوفر لكن المنتجات تعمل")
                    else:
                        edit_message(chat_id, message_id,
                                     f"❌ فشل الربط مع المزود: {pname}\n\n"
                                     f"🔍 تحقق من:\n"
                                     f"• صحة التوكن\n"
                                     f"• صحة الرابط: {purl}\n"
                                     f"• أن الرابط ينتهي بـ / مثلاً: https://api.example.com/")

        # ===== ربط المنتجات =====
        elif data == "link_products" and is_admin_user:
            keyboard, msg = get_link_products_menu()
            edit_message(chat_id, message_id, msg, reply_markup=keyboard)

        elif data.startswith("link_section_"):
            if is_admin_user:
                section_id_str = data[len("link_section_"):]
                section_name = section_id_str
                if section_id_str.isdigit():
                    sec_row = get_section_by_id(int(section_id_str))
                    if sec_row:
                        section_name = sec_row[1]
                products = get_products_by_category(section_name)
                if not products:
                    edit_message(chat_id, message_id, f"🚫 لا توجد منتجات في قسم {section_name}")
                else:
                    keyboard = {"inline_keyboard": []}
                    for product in products:
                        product_id, product_name, emoji = product
                        display_name = f"{emoji} {product_name}" if emoji else product_name
                        categories = get_categories_by_product(product_id)
                        for cat in categories:
                            cat_id, cat_name, price_usd, cat_type, min_qty, max_qty = cat
                            if cat_type == 'default':
                                keyboard["inline_keyboard"].append([
                                    {"text": f"{display_name} - {cat_name}", "callback_data": safe_callback_data(f"link_category_{cat_id}")}
                                ])
                    keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "link_products"}])
                    edit_message(chat_id, message_id, "اختر الفئة لربطها:", reply_markup=keyboard)

        elif data.startswith("link_category_"):
            if is_admin_user:
                category_id = int(data.split("_")[2])
                category = get_category_by_id(category_id)
                if category:
                    cat_id, product_id, cat_name, price_usd, cat_type, min_qty, max_qty = category
                    product = get_product_by_id(product_id)
                    # أولاً نختار المزود
                    providers = get_all_api_providers()
                    if not providers:
                        edit_message(chat_id, message_id, "❌ لا يوجد مزودين. أضف مزوداً من إدارة API أولاً.")
                    else:
                        keyboard = {"inline_keyboard": []}
                        for p in providers:
                            pid, pname, ptoken, purl = p
                            keyboard["inline_keyboard"].append([
                                {"text": f"🔌 {pname}", "callback_data": safe_callback_data(f"link_cat_provider_{pid}_{category_id}")}
                            ])
                        keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "link_products"}])
                        edit_message(chat_id, message_id,
                                     f"🔌 اختر المزود لربط الفئة:\n📦 {product[1] if product else ''} - {cat_name}",
                                     reply_markup=keyboard)

        elif data.startswith("link_cat_provider_"):
            if is_admin_user:
                parts = data.split("_")
                # link_cat_provider_{provider_id}_{category_id}
                provider_id = int(parts[3])
                category_id = int(parts[4])
                category = get_category_by_id(category_id)
                if category:
                    cat_id, product_id, cat_name, price_usd, cat_type, min_qty, max_qty = category
                    product = get_product_by_id(product_id)
                    user_states[user_id] = {
                        "action": "waiting_api_product_id",
                        "product_id": product_id,
                        "category_id": category_id,
                        "product_name": product[1] if product else "غير معروف",
                        "category_name": cat_name,
                        "provider_id": provider_id
                    }
                    provider = get_api_provider_by_id(provider_id)
                    pname = provider[1] if provider else "غير محدد"
                    edit_message(chat_id, message_id,
                                 f"🔌 المزود: {pname}\n📦 {product[1] if product else ''} - {cat_name}\n\n🔷 ارسل ايدي المنتج من API لربطه:")

        elif data == "unlink_products" and is_admin_user:
            keyboard, msg = get_unlink_products_menu()
            if keyboard:
                edit_message(chat_id, message_id, msg, reply_markup=keyboard)
            else:
                keyboard_back = {"inline_keyboard": [[{"text": "🔙 رجوع", "callback_data": "admin_api"}]]}
                edit_message(chat_id, message_id, msg, reply_markup=keyboard_back)

        elif data.startswith("do_unlink_") and is_admin_user:
            try:
                raw_id = data[len("do_unlink_"):]
                link_id = int(raw_id)
                unlink_product(link_id)
                keyboard_back = {"inline_keyboard": [
                    [{"text": "🔓 فك ربط منتج آخر", "callback_data": "unlink_products"}],
                    [{"text": "🔙 رجوع لإدارة API", "callback_data": "admin_api"}]
                ]}
                edit_message(chat_id, message_id, "✅ تم فك ربط المنتج بنجاح", reply_markup=keyboard_back)
            except Exception as unlink_err:
                edit_message(chat_id, message_id, f"❌ خطأ أثناء فك الربط: {str(unlink_err)}")

        # ===== عرض المنتجات المرتبطة =====
        elif data == "related_products_menu" and is_admin_user:
            keyboard, msg = get_related_products_admin_keyboard()
            edit_message(chat_id, message_id, msg, reply_markup=keyboard)

        elif data == "add_related_product" and is_admin_user:
            products = get_all_products()
            if not products:
                edit_message(chat_id, message_id, "🚫 لا توجد منتجات")
            else:
                keyboard = {"inline_keyboard": []}
                for product in products:
                    product_id, name, category, emoji, desc, img = product
                    display_name = f"{emoji} {name}" if emoji else name
                    keyboard["inline_keyboard"].append([
                        {"text": f"{display_name} ({category})", "callback_data": safe_callback_data(f"related_prod_select_{product_id}")}
                    ])
                keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "related_products_menu"}])
                edit_message(chat_id, message_id, "📦 اختر المنتج:", reply_markup=keyboard)

        elif data.startswith("related_prod_select_") and is_admin_user:
            product_id = int(data.split("_")[3])
            categories = get_categories_by_product(product_id)
            if not categories:
                edit_message(chat_id, message_id, "🚫 لا توجد فئات لهذا المنتج")
            else:
                product = get_product_by_id(product_id)
                keyboard = {"inline_keyboard": []}
                for cat in categories:
                    cat_id, cat_name, price_usd, cat_type, min_qty, max_qty = cat
                    keyboard["inline_keyboard"].append([
                        {"text": cat_name, "callback_data": safe_callback_data(f"related_cat_select_{product_id}_{cat_id}")}
                    ])
                keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "add_related_product"}])
                edit_message(chat_id, message_id, f"📦 {product[1] if product else ''}\n🏷️ اختر الفئة:", reply_markup=keyboard)

        elif data.startswith("related_cat_select_") and is_admin_user:
            parts = data.split("_")
            product_id = int(parts[3])
            category_id = int(parts[4])
            category = get_category_by_id(category_id)
            product = get_product_by_id(product_id)
            providers = get_all_api_providers()
            if not providers:
                edit_message(chat_id, message_id, "❌ لا يوجد مزودين. أضف مزوداً أولاً.")
            else:
                keyboard = {"inline_keyboard": []}
                for p in providers:
                    pid, pname, ptoken, purl = p
                    keyboard["inline_keyboard"].append([
                        {"text": f"🔌 {pname}", "callback_data": safe_callback_data(f"related_prov_select_{product_id}_{category_id}_{pid}")}
                    ])
                keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "add_related_product"}])
                edit_message(chat_id, message_id,
                             f"📦 {product[1] if product else ''} - {category[2] if category else ''}\n🔌 اختر المزود:",
                             reply_markup=keyboard)

        elif data.startswith("related_prov_select_") and is_admin_user:
            parts = data.split("_")
            product_id = int(parts[3])
            category_id = int(parts[4])
            provider_id = int(parts[5])
            provider = get_api_provider_by_id(provider_id)
            pname = provider[1] if provider else "غير محدد"
            user_states[user_id] = {
                "action": "waiting_related_api_product_id",
                "product_id": product_id,
                "category_id": category_id,
                "provider_id": provider_id
            }
            edit_message(chat_id, message_id,
                         f"🔌 المزود: {pname}\n🔷 ارسل ايدي المنتج من API لإضافته كمنتج مرتبط للعرض:")

        elif data == "delete_related_product_menu" and is_admin_user:
            all_related = get_all_related_products()
            if not all_related:
                edit_message(chat_id, message_id, "🚫 لا توجد منتجات مرتبطة للعرض")
            else:
                keyboard = {"inline_keyboard": []}
                for rel in all_related:
                    rel_id, product_name, category_name, api_name, api_price, provider_name = rel
                    keyboard["inline_keyboard"].append([
                        {"text": f"🗑 {product_name}-{category_name}: {api_name}", "callback_data": safe_callback_data(f"delete_related_{rel_id}")}
                    ])
                keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "related_products_menu"}])
                edit_message(chat_id, message_id, "اختر المنتج المرتبط لحذفه:", reply_markup=keyboard)

        elif data.startswith("delete_related_") and is_admin_user:
            rel_id = int(data.split("_")[2])
            delete_related_product(rel_id)
            edit_message(chat_id, message_id, "✅ تم حذف المنتج المرتبط بنجاح")

        elif data == "list_related_products" and is_admin_user:
            all_related = get_all_related_products()
            if not all_related:
                edit_message(chat_id, message_id, "🚫 لا توجد منتجات مرتبطة للعرض")
            else:
                msg = "📋 <b>المنتجات المرتبطة للعرض:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                for rel in all_related:
                    rel_id, product_name, category_name, api_name, api_price, provider_name = rel
                    msg += (f"<b>📦 {product_name} - {category_name}</b>\n"
                            f"   🔗 API: {api_name} | 💰 {float(api_price):.2f}$\n"
                            f"   🔌 المزود: {provider_name or 'غير محدد'}\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n")
                keyboard = {"inline_keyboard": [[{"text": "🔙 رجوع", "callback_data": "related_products_menu"}]]}
                edit_message(chat_id, message_id, msg[:4000], reply_markup=keyboard)

        # ===== بحث المنتجات =====
        elif data == "search_products" and is_admin_user:
            providers = get_all_api_providers()
            if not providers:
                user_states[user_id] = {"action": "waiting_search_term", "provider_id": 0}
                edit_message(chat_id, message_id, "✏️ اكتب اسم المنتج للبحث عنه:")
            else:
                keyboard = {"inline_keyboard": []}
                for p in providers:
                    pid, pname, ptoken, purl = p
                    keyboard["inline_keyboard"].append([{"text": f"🔌 بحث في {pname}", "callback_data": safe_callback_data(f"search_in_provider_{pid}")}])
                keyboard["inline_keyboard"].append([{"text": "🔙 رجوع", "callback_data": "admin_api"}])
                edit_message(chat_id, message_id, "🔍 اختر المزود للبحث فيه:", reply_markup=keyboard)

        elif data.startswith("search_in_provider_") and is_admin_user:
            pid = int(data.split("_")[3])
            user_states[user_id] = {"action": "waiting_search_term", "provider_id": pid}
            edit_message(chat_id, message_id, "✏️ اكتب اسم المنتج للبحث عنه:")

        # ===== لوحة التحكم - المنتجات الإضافية =====
        elif data == "add_product" and is_admin_user:
            user_states[user_id] = {"action": "waiting_product_name"}
            edit_message(chat_id, message_id, "✏️ أرسل اسم المنتج:")

        elif data.startswith("save_product_"):
            if is_admin_user:
                section_name = data[len("save_product_"):]
                if user_id in user_states:
                    add_product(user_states[user_id]["product_name"], section_name, "", "", "")
                    del user_states[user_id]
                    edit_message(chat_id, message_id, f"✅ تم اضافة المنتج لقسم {section_name}")

        elif data == "add_category_menu" and is_admin_user:
            keyboard, msg = get_products_for_category_menu()
            if keyboard:
                edit_message(chat_id, message_id, msg, reply_markup=keyboard)

        elif data.startswith("select_product_"):
            if is_admin_user:
                product_id = int(data.split("_")[2])
                product = get_product_by_id(product_id)
                if product:
                    user_states[user_id] = {"action": "waiting_category_name", "product_id": product_id, "product_name": product[1]}
                    edit_message(chat_id, message_id, f"📝 {product[1]}\nاكتب اسم الفئة:")

        elif data == "delete_product_menu" and is_admin_user:
            keyboard, msg = get_delete_products_menu()
            if keyboard:
                edit_message(chat_id, message_id, msg, reply_markup=keyboard)

        elif data.startswith("delete_product_"):
            if is_admin_user:
                product_id = int(data.split("_")[2])
                delete_product(product_id)
                edit_message(chat_id, message_id, "✅ تم حذف المنتج")

        # ===== لوحة التحكم - الأقسام =====
        elif data == "sections_management" and is_admin_user:
            keyboard, msg = get_sections_management_keyboard()
            edit_message(chat_id, message_id, msg, reply_markup=keyboard)

        elif data.startswith("section_img_") and is_admin_user:
            sec_id = int(data.split("_")[2])
            section = get_section_by_id(sec_id)
            if section:
                user_states[user_id] = {"action": "waiting_section_image", "section_id": sec_id}
                current_img = get_section_image_by_id(sec_id)
                status = "✅ تم رفع صورة مسبقاً" if current_img else "❌ لا توجد صورة حالياً"
                edit_message(chat_id, message_id,
                             f"🖼️ صورة القسم: <b>{section[1]}</b>\n"
                             f"الحالة: {status}\n\n"
                             f"ارسل الصورة الجديدة للقسم (كصورة وليس رابط):")

        elif data == "add_section" and is_admin_user:
            user_states[user_id] = {"action": "waiting_new_section"}
            edit_message(chat_id, message_id, "📝 اكتب اسم القسم الجديد:")

        elif data.startswith("delete_section_"):
            if is_admin_user:
                section_id = int(data.split("_")[2])
                delete_section(section_id)
                edit_message(chat_id, message_id, "✅ تم حذف القسم بنجاح")

        elif data.startswith("color_section_"):
            if is_admin_user:
                section_id = int(data.split("_")[2])
                edit_message(chat_id, message_id, "🎨 اختر لون القسم:",
                             reply_markup=get_color_selection_keyboard(section_id))

        elif data.startswith("set_color_"):
            if is_admin_user:
                parts = data.split("_")
                section_id = int(parts[2])
                color = parts[3]
                update_section_color(section_id, color)
                section = get_section_by_id(section_id)
                color_label = {"success": "🟢 أخضر", "danger": "🔴 أحمر", "primary": "🔵 أزرق"}.get(color, color)
                keyboard, msg = get_sections_management_keyboard()
                edit_message(chat_id, message_id,
                    f"✅ تم تغيير لون القسم <b>{section[1] if section else ''}</b> إلى {color_label}\n\n{msg}",
                    reply_markup=keyboard)

        # ===== لوحة التحكم - المستخدمون =====
        elif data == "user_management" and is_admin_user:
            edit_message(chat_id, message_id, "👥 إدارة المستخدمين:", reply_markup=get_user_management_keyboard())

        elif data == "add_balance" and is_admin_user:
            user_states[user_id] = {"action": "waiting_user_id_for_add_balance"}
            edit_message(chat_id, message_id, "📝 ارسل ايدي المستخدم لاضافة رصيد:")

        elif data == "deduct_balance" and is_admin_user:
            user_states[user_id] = {"action": "waiting_user_id_for_deduct_balance"}
            edit_message(chat_id, message_id, "📝 ارسل ايدي المستخدم لخصم رصيد:")

        elif data == "add_admin" and is_admin_user:
            user_states[user_id] = {"action": "waiting_user_id_for_add_admin"}
            edit_message(chat_id, message_id, "👑 ارسل ايدي المستخدم لاضافته للادمن:")

        elif data == "remove_admin" and is_admin_user:
            user_states[user_id] = {"action": "waiting_user_id_for_remove_admin"}
            edit_message(chat_id, message_id, "🗑 ارسل ايدي المستخدم لحذفه من الادمن:")

        elif data == "user_info" and is_admin_user:
            user_states[user_id] = {"action": "waiting_user_id_for_info"}
            edit_message(chat_id, message_id, "🔍 ارسل ايدي المستخدم للكشف:")

        elif data == "block_user" and is_admin_user:
            user_states[user_id] = {"action": "waiting_user_id_for_block"}
            edit_message(chat_id, message_id, "🚫 ارسل ايدي المستخدم لحظره:")

        elif data == "unblock_user" and is_admin_user:
            user_states[user_id] = {"action": "waiting_user_id_for_unblock"}
            edit_message(chat_id, message_id, "🔓 ارسل ايدي المستخدم لفك حظره:")

        elif data == "general_stats" and is_admin_user:
            users_count = get_total_users_count()
            total_balance = get_total_balance()
            total_orders = get_total_orders()
            providers_count = len(get_all_api_providers())
            msg = (f"📊 <b>الاحصائية العامة:</b>\n\n"
                   f"👥 <b>اجمالي المستخدمين: {users_count}</b>\n"
                   f"💰 <b>اجمالي الارصدة: {total_balance:,.2f} ليرة</b>\n"
                   f"📦 <b>اجمالي الطلبات المنفذة: {total_orders}</b>\n"
                   f"🔌 <b>مزودو API المتصلين: {providers_count}/10000</b>")
            edit_message(chat_id, message_id, msg)

        # ===== الخصومات =====
        elif data == "discount_management" and is_admin_user:
            edit_message(chat_id, message_id, "🎁 إدارة الخصومات:", reply_markup=get_discount_management_keyboard())

        elif data == "add_discount" and is_admin_user:
            user_states[user_id] = {"action": "waiting_discount_user_id"}
            edit_message(chat_id, message_id, "🎁 ارسل ايدي المستخدم لوضع خصم له:")

        elif data == "remove_discount" and is_admin_user:
            user_states[user_id] = {"action": "waiting_remove_discount_user_id"}
            edit_message(chat_id, message_id, "🗑 ارسل ايدي المستخدم لحذف الخصم:")

        elif data == "list_discount_users" and is_admin_user:
            users_with_discount = get_all_users_with_discount()
            if not users_with_discount:
                edit_message(chat_id, message_id, "📋 لا يوجد مستخدمين لديهم خصومات")
            else:
                msg = "🎁 <b>المستخدمين المميزين:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                for usr in users_with_discount:
                    uid, dname, dpercent = usr
                    uinfo = get_telegram_user_info(uid)
                    msg += (f"👤 {uinfo['name']} | 🆔 {uid}\n"
                            f"🎁 {dname}: {dpercent}%\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n")
                edit_message(chat_id, message_id, msg)

        # ===== الاشتراك الاجباري =====
        elif data == "subscription_management" and is_admin_user:
            keyboard, msg = get_subscription_management_keyboard()
            edit_message(chat_id, message_id, msg, reply_markup=keyboard)

        elif data == "add_channel" and is_admin_user:
            user_states[user_id] = {"action": "waiting_channel_username"}
            edit_message(chat_id, message_id, "📢 ارسل معرف قناة الاشتراك الاجباري:")

        elif data.startswith("delete_channel_"):
            if is_admin_user:
                channel_id = int(data.split("_")[2])
                delete_required_channel(channel_id)
                edit_message(chat_id, message_id, "✅ تم حذف القناة بنجاح")

        # ===== الاذاعة =====
        elif data == "broadcast_menu" and is_admin_user:
            edit_message(chat_id, message_id, "📣 الاذاعة:", reply_markup=get_broadcast_keyboard())

        elif data == "broadcast_all" and is_admin_user:
            user_states[user_id] = {"action": "waiting_broadcast_message"}
            edit_message(chat_id, message_id, "📝 اكتب الاذاعة لجميع المستخدمين:")

        elif data == "broadcast_user" and is_admin_user:
            user_states[user_id] = {"action": "waiting_broadcast_user_id"}
            edit_message(chat_id, message_id, "🆔 ارسل ايدي المستخدم:")

        # ===== الاعدادات =====
        elif data == "basic_settings" and is_admin_user:
            edit_message(chat_id, message_id, "⚙️ الاعدادات الاساسية:", reply_markup=get_basic_settings_keyboard())

        elif data == "referral_settings" and is_admin_user:
            ref_enabled, ref_amount = get_referral_settings()
            ref_status = "🟢 مفعّل" if ref_enabled else "🔴 معطّل"
            keyboard = {"inline_keyboard": [
                [{"text": f"{'🔴 إيقاف نظام الإحالة' if ref_enabled else '🟢 تفعيل نظام الإحالة'}", "callback_data": "toggle_referral"}],
                [{"text": f"💰 تعديل مبلغ المكافأة ({ref_amount:,.0f} ل.س)", "callback_data": "edit_referral_amount"}],
                [{"text": "🔙 رجوع", "callback_data": "basic_settings"}]
            ]}
            msg = (f"🔗 <b>نظام الإحالة</b>\n\n"
                   f"الحالة: <b>{ref_status}</b>\n"
                   f"💰 مبلغ المكافأة: <b>{ref_amount:,.0f} ل.س</b>\n\n"
                   f"عند تفعيل النظام، يحصل المستخدم على مكافأة مالية عند كل شخص يدخل البوت عبر رابط إحالته.\n\n"
                   f"رابط الإحالة: <code>https://t.me/البوت?start=ref_USERID</code>")
            edit_message(chat_id, message_id, msg, reply_markup=keyboard)

        elif data == "toggle_referral" and is_admin_user:
            ref_enabled, ref_amount = get_referral_settings()
            new_status = not ref_enabled
            set_referral_enabled(new_status)
            status_text = "🟢 تم تفعيل نظام الإحالة" if new_status else "🔴 تم إيقاف نظام الإحالة"
            edit_message(chat_id, message_id, f"✅ {status_text}",
                         reply_markup={"inline_keyboard": [[{"text": "🔙 رجوع لإعدادات الإحالة", "callback_data": "referral_settings"}]]})

        elif data == "edit_referral_amount" and is_admin_user:
            ref_enabled, ref_amount = get_referral_settings()
            user_states[user_id] = {"action": "waiting_referral_amount"}
            edit_message(chat_id, message_id, f"💰 مبلغ المكافأة الحالي: {ref_amount:,.0f} ل.س\n\nارسل المبلغ الجديد بالليرة السورية:")

        elif data == "rename_sections" and is_admin_user:
            keyboard, msg = get_rename_sections_menu()
            if keyboard:
                edit_message(chat_id, message_id, msg, reply_markup=keyboard)
            else:
                edit_message(chat_id, message_id, msg)

        elif data.startswith("rename_section_"):
            if is_admin_user:
                section_id = int(data.split("_")[2])
                section = get_section_by_id(section_id)
                if section:
                    user_states[user_id] = {"action": "waiting_new_section_name", "section_id": section_id}
                    edit_message(chat_id, message_id, f"✏️ تعديل اسم القسم: {section[1]}\n\nاكتب اسم القسم الجديد:")
 
        elif data == "general_settings" and is_admin_user:
            edit_message(chat_id, message_id, "🔄 الاعدادات العامة:", reply_markup=get_general_settings_keyboard())

        elif data == "toggle_bot" and is_admin_user:
            new_status = not bot_enabled
            set_bot_status(new_status)
            status_text = "🟢 تم تشغيل البوت" if new_status else "🔴 تم ايقاف البوت"
            edit_message(chat_id, message_id, f"✅ {status_text}")

        elif data == "change_welcome" and is_admin_user:
            user_states[user_id] = {"action": "waiting_welcome_message"}
            edit_message(chat_id, message_id, "📝 ارسل رسالة ترحيب الجديدة:")

        elif data == "toggle_button_type" and is_admin_user:
            new_mode = 'inline' if button_mode == 'reply' else 'reply'
            set_button_mode(new_mode)
            if new_mode == 'inline':
                mode_label = "أزرار شفافة (Inline) 🔲"
            else:
                mode_label = "كيبورد عادي (Reply) ⌨️"
            edit_message(chat_id, message_id, f"✅ تم التبديل إلى: {mode_label}\n\nيجب على المستخدمين الضغط /start لتطبيق التغيير.")

        elif data == "change_support_username" and is_admin_user:
            uname = get_support_username()
            user_states[user_id] = {"action": "waiting_support_username"}
            edit_message(chat_id, message_id, f"💬 يوزر الدعم الحالي: @{uname}\n\nارسل اليوزر الجديد (بدون @):")

        elif data == "edit_exchange_rate" and is_admin_user:
            current_rate = get_exchange_rate()
            user_states[user_id] = {"action": "waiting_exchange_rate"}
            edit_message(chat_id, message_id, f"💰 سعر الصرف الحالي: {current_rate:,.2f} ليرة = 1$\n\nارسل سعر الصرف الجديد:")

        # ===== إحصائيات المبيعات =====
        elif data == "sales_analytics" and is_admin_user:
            try:
                msg = format_sales_analytics_msg()
                kb = {"inline_keyboard": [
                    [{"text": "🔄 تحديث", "callback_data": "sales_analytics"}],
                    [{"text": "🔙 رجوع للوحة التحكم", "callback_data": "back_admin"}]
                ]}
                edit_message(chat_id, message_id, msg, reply_markup=kb)
            except Exception as e:
                edit_message(chat_id, message_id, f"❌ خطأ في تحميل الإحصائيات: {e}")

        # ===== تعديل الأسعار =====
        elif data == "edit_prices_menu" and is_admin_user:
            keyboard, msg = get_edit_prices_menu()
            if keyboard:
                edit_message(chat_id, message_id, msg, reply_markup=keyboard)
            else:
                kb_back = {"inline_keyboard": [[{"text": "🔙 رجوع", "callback_data": "back_admin"}]]}
                edit_message(chat_id, message_id, msg, reply_markup=kb_back)

        elif data.startswith("editprice_") and is_admin_user:
            cat_id = int(data.split("_")[1])
            category = get_category_by_id(cat_id)
            if category:
                cat_id2, product_id, cat_name, price_usd, cat_type, min_qty, max_qty = category
                product = get_product_by_id(product_id)
                product_name = product[1] if product else "غير معروف"
                exchange_rate = get_exchange_rate()
                price_syp = price_usd * exchange_rate
                user_states[user_id] = {
                    "action": "waiting_edit_category_price",
                    "category_id": cat_id,
                    "category_name": cat_name,
                    "product_name": product_name
                }
                edit_message(chat_id, message_id,
                    f"✏️ تعديل سعر الفئة\n\n"
                    f"📦 المنتج: <b>{product_name}</b>\n"
                    f"🏷️ الفئة: <b>{cat_name}</b>\n"
                    f"💲 السعر الحالي: <b>{price_usd:.2f}$</b>\n"
                    f"💵 بالليرة: <b>{price_syp:,.0f} ل.س</b>\n\n"
                    f"ارسل السعر الجديد بالدولار (مثال: 1.5):")
            else:
                edit_message(chat_id, message_id, "❌ لم يتم العثور على الفئة")

        # ===== القائمة الرئيسية Inline =====
        elif data.startswith("inline_section_"):
            section_id_str = data[len("inline_section_"):]
            # دعم الـ ID الرقمي (الجديد) أو الاسم النصي (القديم للتوافق)
            section_name = None
            if section_id_str.isdigit():
                sec_row = get_section_by_id(int(section_id_str))
                if sec_row:
                    section_name = sec_row[1]
            if not section_name:
                section_name = section_id_str
            keyboard, msg = get_products_buttons(section_name)
            section_image = get_section_image_by_name(section_name)
            if keyboard:
                if section_image:
                    delete_message(chat_id, message_id)
                    send_message(chat_id, msg, reply_markup=keyboard, photo=section_image)
                else:
                    edit_message(chat_id, message_id, msg, reply_markup=keyboard)
            else:
                edit_message(chat_id, message_id, msg if msg else f"🚫 لا توجد منتجات في قسم {section_name}")

        elif data == "inline_deposit":
            keyboard, msg = get_deposit_methods_buttons()
            if keyboard:
                send_message(chat_id, msg, reply_markup=keyboard)
            else:
                send_message(chat_id, msg)

        elif data == "inline_account":
            user_info_data = get_telegram_user_info(user_id)
            stats = get_user_stats(user_id)
            exchange_rate = get_exchange_rate()
            balance_usd = stats['balance'] / exchange_rate if exchange_rate > 0 else 0
            ref_enabled, ref_amount = get_referral_settings()
            ref_count = get_referral_count(user_id)
            msg = (f"<b>🟢 اسمك:</b> {user_info_data['name']}\n"
                   f"<b>🟢 رصيدك:</b> <code>{stats['balance']:,.2f}</code> ل.س\n"
                   f"<b>🟢 ايديك:</b> <code>{user_info_data['user_id']}</code>\n\n"
                   f"<b>🟢 اجمالي مصروفاتك:</b> <code>{stats['total_shop']:,.2f}</code> ل.س\n"
                   f"<b>🟢 اجمالي طلباتك:</b> <code>{stats.get('total_orders', 0)}</code>\n\n"
                   f"<b>🟢 الخصم:</b> {stats['discount_percent']}%\n")
            if ref_enabled:
                bot_info = tg_api("getMe")
                bot_username = bot_info.get("result", {}).get("username", "bot") if bot_info else "bot"
                ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
                msg += (f"\n<b>🔗 رابط إحالتك:</b>\n"
                        f"<code>{ref_link}</code>\n"
                        f"<b>👥 عدد إحالاتك: {ref_count}</b>\n"
                        f"<b>💰 مكافأة كل إحالة: {ref_amount:,.0f} ل.س</b>\n")
            kb = {"inline_keyboard": [[
                {"text": "📋 طـلـباتـي", "callback_data": safe_callback_data(f"my_orders_{user_id}")},
                {"text": "💰 أيـداعـاتـي", "callback_data": safe_callback_data(f"my_deposits_{user_id}")}
            ]]}
            send_message(chat_id, msg, reply_markup=kb)

        elif data == "inline_support":
            uname = get_support_username()
            send_message(chat_id, f"أهلاً وسهلاً، للاستفسار والتواصل:\n\n@{uname}")

        elif data == "inline_admin_panel" and is_admin_user:
            send_message(chat_id, "🛡️ لوحة التحكم:", reply_markup=get_admin_main_keyboard())

    except Exception as e:
        print(f"Error in handle_callback: {e}")
        traceback.print_exc()
        try:
            send_message(chat_id, f"❌ خطأ: {str(e)}")
        except:
            pass


def main():
    global last_update_id
    init_db()
    print("✅ البوت يعمل...")
    print("✅ قاعدة البيانات جاهزة")
    print(f"✅ المزودون: {len(get_all_api_providers())}")

    consecutive_errors = 0

    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            params = {"timeout": 30, "offset": last_update_id + 1}
            r = requests.get(url, params=params, timeout=40)

            try:
                updates = r.json()
            except Exception:
                print(f"getUpdates: non-JSON response: {r.text[:200]}")
                time.sleep(3)
                continue

            if not updates.get("ok"):
                err_code = updates.get("error_code")
                description = updates.get("description", "")
                print(f"getUpdates not ok: {err_code} - {description}")
                # 409 Conflict: webhook قديم موجود أو نسخة ثانية شغّالة
                if err_code == 409:
                    print("⚠️ Conflict 409 - هناك نسخة أخرى أو webhook نشط. انتظار 10 ثوانٍ...")
                    time.sleep(10)
                elif err_code == 401:
                    print("❌ توكن البوت غير صحيح! أوقف البرنامج وتحقق من BOT_TOKEN")
                    time.sleep(30)
                else:
                    time.sleep(5)
                consecutive_errors += 1
                continue

            consecutive_errors = 0
            result_list = updates.get("result", [])

            if not result_list:
                # لا توجد رسائل جديدة - انتظر قليلاً لتجنب الـ flood
                time.sleep(0.1)
                continue

            for update in result_list:
                # نُحدّث last_update_id فوراً قبل المعالجة لتجنب إعادة المعالجة عند الخطأ
                update_id = update.get("update_id")
                if update_id and update_id > last_update_id:
                    last_update_id = update_id

                try:
                    if "message" in update:
                        msg = update["message"]
                        chat_id = msg["chat"]["id"]
                        user_id = msg["from"]["id"]

                        if "text" in msg:
                            if msg["text"] == "/start" or msg["text"].startswith("/start "):
                                if not bot_enabled and user_id != MAIN_ADMIN_ID and not is_admin(user_id):
                                    send_message(chat_id, "⚠️ الــبــوت مــتــوقــف حــالــيًــا عــن الــعــمــل .⚠️")
                                else:
                                    # أخذ بيانات المستخدم مباشرة من الأبديت
                                    _from = msg.get("from", {})
                                    _first = _from.get("first_name", "")
                                    _last = _from.get("last_name", "")
                                    _uname = _from.get("username", "")
                                    _full_name = f"{_first} {_last}".strip() or _first or "مستخدم"
                                    _username = f"@{_uname}" if _uname else "لا يوجد"
                                    # تسجيل المستخدم الجديد
                                    _is_new_user = register_new_user(user_id, _username, _full_name)
                                    # معالجة رابط الإحالة
                                    start_param = msg["text"][7:].strip() if msg["text"].startswith("/start ") else ""
                                    if start_param.startswith("link_"):
                                        # ===== ربط تلقائي بضغطة واحدة عبر رابط الموقع =====
                                        try:
                                            link_code = start_param[5:].strip()
                                            ok, info = web_link_telegram_account(link_code, user_id, _username, _full_name)
                                            if ok:
                                                send_message(chat_id, "✅ تم ربط حسابك بالموقع بنجاح! رصيدك وطلباتك صارت موحّدة بين البوت والموقع.")
                                            else:
                                                send_message(chat_id, f"❌ {info}")
                                        except Exception as link_err:
                                            print(f"[link] error: {link_err}")
                                            send_message(chat_id, "❌ تعذّر إتمام الربط، الكود منتهي أو غير صحيح. جرّب تولّد كود جديد من صفحة الحساب بالموقع.")
                                    elif start_param.startswith("ref_"):
                                        try:
                                            referrer_id = int(start_param[4:])
                                            if referrer_id != user_id:
                                                if _is_new_user:
                                                    rewarded = process_referral(referrer_id, user_id)
                                                    if rewarded:
                                                        ref_enabled, ref_amount = get_referral_settings()
                                                        send_message(referrer_id, f"🎉 تهانينا! أحد أصدقائك انضم عبر رابط إحالتك\n💰 تم إضافة {ref_amount:,.0f} ل.س لرصيدك!")
                                                else:
                                                    # المستخدم قديم لكن لم تُسجَّل إحالته بعد
                                                    rewarded = process_referral(referrer_id, user_id)
                                                    if rewarded:
                                                        ref_enabled, ref_amount = get_referral_settings()
                                                        send_message(referrer_id, f"🎉 تهانينا! أحد أصدقائك انضم عبر رابط إحالتك\n💰 تم إضافة {ref_amount:,.0f} ل.س لرصيدك!")
                                        except Exception as ref_err:
                                            print(f"[referral] error: {ref_err}")
                                    send_main_menu(chat_id, user_id)
                            elif msg["text"] == "/admin":
                                if is_admin(user_id):
                                    send_message(chat_id, "🛡️ لوحة التحكم:", reply_markup=get_admin_main_keyboard())
                                else:
                                    send_message(chat_id, "❌ ليس لديك صلاحية")
                            else:
                                handle_message(chat_id, user_id, msg["text"])

                        elif "photo" in msg and user_id in user_states:
                            action = user_states[user_id].get("action")
                            file_id = msg["photo"][-1]["file_id"]

                            if action == "waiting_product_image":
                                product_id = user_states[user_id]["product_id"]
                                update_product_image(product_id, file_id)
                                send_message(chat_id, "✅ تم وضع صورة المنتج بنجاح")
                                del user_states[user_id]

                            elif action == "waiting_deposit_method_image":
                                method_id = user_states[user_id]["method_id"]
                                is_auto = user_states[user_id].get("is_auto", False)
                                if is_auto:
                                    update_auto_deposit_method_image(method_id, file_id)
                                else:
                                    update_deposit_method_image(method_id, file_id)
                                send_message(chat_id, "✅ تم وضع صورة طريقة الإيداع بنجاح")
                                del user_states[user_id]

                            elif action == "waiting_category_image":
                                cat_id = user_states[user_id]["category_id"]
                                update_category_image(cat_id, file_id)
                                send_message(chat_id, "✅ تم وضع صورة الفئة بنجاح")
                                del user_states[user_id]

                            elif action == "waiting_section_image":
                                sec_id = user_states[user_id]["section_id"]
                                update_section_image(sec_id, file_id)
                                send_message(chat_id, "✅ تم وضع صورة القسم بنجاح")
                                del user_states[user_id]

                        elif "sticker" in msg:
                            # معالجة الستيكرات - إرسال رد بدلاً من التجاهل
                            send_message(chat_id, "😊 الستيكرات غير مدعومة. اضغط /start للقائمة الرئيسية.")

                    elif "callback_query" in update:
                        cb = update["callback_query"]
                        chat_id = cb["message"]["chat"]["id"]
                        message_id = cb["message"]["message_id"]
                        callback_id = cb["id"]
                        cb_data = cb["data"]
                        user_id = cb["from"]["id"]
                        handle_callback(chat_id, message_id, callback_id, cb_data, user_id)

                except Exception as e:
                    print(f"Error processing update {update_id}: {e}")
                    traceback.print_exc()
                    # نكمل للـ update التالي بدون توقف البوت

        except requests.exceptions.ConnectionError as e:
            consecutive_errors += 1
            print(f"Connection error (#{consecutive_errors}): {e}")
            sleep_time = min(5 * consecutive_errors, 60)
            time.sleep(sleep_time)
        except requests.exceptions.Timeout:
            # timeout طبيعي جداً مع long polling - لا داعي للطباعة
            consecutive_errors = 0
            continue
        except Exception as e:
            consecutive_errors += 1
            print(f"Main error (#{consecutive_errors}): {e}")
            traceback.print_exc()
            sleep_time = min(2 * consecutive_errors, 30)
            time.sleep(sleep_time)


if __name__ == "__main__":
    main()
