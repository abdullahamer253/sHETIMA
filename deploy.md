# دليل نشر بوت تيليجرام على Vercel

## الملفات الجاهزة للنشر

تم إعداد جميع الملفات المطلوبة لنشر البوت على Vercel:

### 1. الملفات الأساسية
- `app.py` - التطبيق الرئيسي (Flask + Telegram Bot)
- `requirements.txt` - المكتبات المطلوبة
- `vercel.json` - تكوين Vercel
- `.vercelignore` - الملفات المستبعدة من النشر
- `offense_log.db` - قاعدة البيانات (SQLite)
- `extracted_swear_words.txt` - قائمة الكلمات المحظورة

### 2. متغيرات البيئة المطلوبة

يجب إعداد هذه المتغيرات في Vercel:

```
TELEGRAM_BOT_TOKEN=8112033822:AAH2X-sSkf_djHKIzpyqU__Jlh-84gYnAJA
GEMINI_API_KEY=AIzaSyBuOCJvstyRUjFm3R7qP7i1N6FhpM6rhck
MAIN_GROUP_CHAT_ID=-1001734737806
WEBHOOK_URL=https://your-app-name.vercel.app
```

### 3. خطوات النشر

#### الطريقة الأولى: استخدام Vercel CLI

```bash
# 1. تسجيل الدخول إلى Vercel
vercel login

# 2. النشر
vercel --prod

# 3. إعداد متغيرات البيئة
vercel env add TELEGRAM_BOT_TOKEN
vercel env add GEMINI_API_KEY
vercel env add MAIN_GROUP_CHAT_ID
vercel env add WEBHOOK_URL
```

#### الطريقة الثانية: استخدام GitHub + Vercel

1. رفع الملفات إلى مستودع GitHub
2. ربط المستودع بـ Vercel
3. إعداد متغيرات البيئة في لوحة تحكم Vercel
4. النشر التلقائي

### 4. إعداد Webhook

بعد النشر، قم بزيارة:
```
https://your-app-name.vercel.app/set_webhook
```

### 5. اختبار البوت

- تأكد من أن البوت يرد على `/start`
- اختبر فلترة الشتائم
- تحقق من `/stat` للإحصائيات

## ملاحظات مهمة

### قيود قاعدة البيانات
- Vercel لا يدعم الكتابة في نظام الملفات
- قاعدة البيانات SQLite ستكون للقراءة فقط
- للإنتاج، يُنصح بالانتقال إلى قاعدة بيانات خارجية مثل:
  - PostgreSQL (Supabase, Neon)
  - MongoDB (Atlas)
  - Redis (Upstash)

### بدائل قاعدة البيانات

#### استخدام Supabase (PostgreSQL)
```python
import psycopg2
from urllib.parse import urlparse

DATABASE_URL = os.getenv("DATABASE_URL")
url = urlparse(DATABASE_URL)

conn = psycopg2.connect(
    database=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)
```

#### استخدام MongoDB Atlas
```python
from pymongo import MongoClient

MONGODB_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGODB_URI)
db = client.telegram_bot
```

### الأمان
- لا تضع المفاتيح السرية في الكود
- استخدم متغيرات البيئة دائماً
- فعّل HTTPS للـ webhook

## الدعم والصيانة

- راقب السجلات في لوحة تحكم Vercel
- تحديث المكتبات بانتظام
- نسخ احتياطي لقاعدة البيانات

## الملفات الجاهزة

جميع الملفات موجودة في مجلد `/home/ubuntu/telegram_bot_vercel/` وجاهزة للنشر.

