# Telegram Bot for Vercel

بوت تيليجرام لفلترة الشتائم والألفاظ غير اللائقة باستخدام الذكاء الاصطناعي.

## المتطلبات

- حساب Vercel
- توكن بوت تيليجرام
- مفتاح API لـ Google Gemini

## خطوات النشر على Vercel

### 1. تثبيت Vercel CLI

```bash
npm install -g vercel
```

### 2. تسجيل الدخول إلى Vercel

```bash
vercel login
```

### 3. إعداد متغيرات البيئة

قم بإعداد المتغيرات التالية في لوحة تحكم Vercel أو باستخدام CLI:

```bash
vercel env add TELEGRAM_BOT_TOKEN
vercel env add GEMINI_API_KEY  
vercel env add MAIN_GROUP_CHAT_ID
vercel env add WEBHOOK_URL
```

### 4. نشر التطبيق

```bash
vercel --prod
```

### 5. إعداد Webhook

بعد النشر، قم بزيارة:
```
https://your-app-name.vercel.app/set_webhook
```

## الملفات المهمة

- `app.py`: التطبيق الرئيسي
- `vercel.json`: تكوين Vercel
- `requirements.txt`: المكتبات المطلوبة
- `.env`: متغيرات البيئة (للتطوير المحلي فقط)

## ملاحظات مهمة

1. **قاعدة البيانات**: يستخدم البوت SQLite، والذي قد لا يكون مناسباً للإنتاج على Vercel بسبب طبيعة البيئة الخالية من الحالة. يُنصح بالانتقال إلى قاعدة بيانات خارجية مثل PostgreSQL أو MongoDB.

2. **الملفات الثابتة**: ملف `extracted_swear_words.txt` وقاعدة البيانات يجب أن يكونا متاحين في بيئة الإنتاج.

3. **المتغيرات البيئية**: تأكد من إعداد جميع المتغيرات المطلوبة في Vercel.

## الاستخدام

- `/start` - بدء البوت
- `/stat` - عرض إحصائيات المستخدم

البوت يراقب الرسائل تلقائياً ويحذف المحتوى غير اللائق باستخدام الذكاء الاصطناعي.

