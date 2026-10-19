# SATNO Bale Market Intelligence

سامانه هوش بازار بله برای گروه ساتنو.

## v0.5 Staff Edition

Branch عملیاتی/توسعه نگهداری: `feature/staff-v05`

قابلیت‌های اصلی:
- Login پرسنل با password hash امن
- Session سمت‌سرور با token hash و Logout/Revoke
- RBAC نقش‌های `admin`، `sales` و `viewer`
- حفاظت Dashboard و API
- مدیریت کاربران پرسنل و جلوگیری از حذف آخرین Admin فعال
- تفکیک پیام‌ها به تأمین‌کننده/فروشنده، موجودی/فروش، تقاضای خرید، استعلام/پروژه و سایر
- استخراج قابل بازبینی برند، محصول، مدل، توان، ظرفیت، قیمت، واحد پول، محل و تماس
- Search Ranking وزن‌دار و فیلتر پیام‌ها
- حفظ منشأ پیام و Sender Resolution
- صفحه وضعیت منابع و Sync
- مدیریت دستی منابع بله: افزودن، ویرایش، فعال/غیرفعال و حذف
- بررسی انسانی سرنخ، انتخاب/رد و ثبت reviewer
- Outbox پایدار و idempotent برای اتصال آینده SATNO CRM Alpha 2.2
- Adapter منطبق با قرارداد `ingest_leads` و هدر `x-satno-connector: bale_market`
- رسید معتبر CRM، retry محدود و ثبت وضعیت/خطا
- گیرنده آزمایشی loopback برای تست بدون CRM واقعی

## بازبینی طرف تجاری بازار

در صفحهٔ بررسی، نام اعلام‌شدهٔ شرکت/شخص، نقش تأمین‌کننده/خریدار/هر دو، نمایندهٔ احتمالی و وضعیت تعلق تماس اصلی قابل بازبینی است. ورود به صف به معنی ایجاد شرکت یا سرنخ در CRM نیست. بسته‌های قرارداد جدید تا هماهنگی گیرنده ارسال نمی‌شوند؛ از صف می‌توان بستهٔ JSON بازبینی‌شده را دریافت کرد.

- [قرارداد طرف تجاری و راهنمای نصب](docs/CRM_MARKET_PARTY_HANDOFF_V1.md)
- [متن تحویل به کدکس CRM](docs/crm-handoff/CRM_CODEX_BRIEF_FA.md)
- [نمونهٔ JSON نمایشی](docs/crm-handoff/supplier-example.json)

## صفحات

- `/login`
- `/` داشبورد و جست‌وجو
- `/status` وضعیت منابع و Sync
- `/review` بررسی انسانی و انتخاب سرنخ
- `/sources/manage` مدیریت منابع بله
- `/crm/outbox` وضعیت صف اتصال CRM
- `/admin/users` مدیریت کاربران

## اجرای محلی

```bash
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8005
```

Health check:

```
GET /health
```

## ساخت اولین Admin

```bash
python create_staff_user.py admin --role admin --name "SATNO Admin"
```

رمز به‌صورت interactive دریافت می‌شود و password خام در Git یا کد ذخیره نمی‌شود.

## فراموشی رمز عبور

در صفحهٔ ورود، «رمز عبور را فراموش کرده‌اید؟» را انتخاب و نام کاربری را ثبت کنید.
درخواست حساب فعال در بخش «درخواست‌های بازیابی رمز» در `/admin/users` نمایش داده می‌شود.
مدیر پس از تأیید هویت از راه ارتباطی مورد اعتماد، «تعیین رمز جدید» را انتخاب و رمز را از همان راه تحویل می‌دهد.
ثبت درخواست، رمز را تغییر نمی‌دهد؛ درخواست تکراری در صف تکثیر نمی‌شود و وجود حساب به مراجعه‌کننده اعلام نمی‌شود.
پس از تغییر رمز، درخواست بسته و همهٔ نشست‌های قبلی آن کاربر باطل می‌شوند.

اگر خود مدیر امکان ورود ندارد، مسئول دارای دسترسی به سرور باید در پوشهٔ پروژه و با محیط پایتون همان برنامه اجرا کند:

```powershell
python reset_admin_password.py admin --database "D:\path\to\satno_market.db"
```

`admin` را با نام کاربری واقعی مدیر و مسیر را با مسیر **دیتابیس موجود برنامهٔ در حال اجرا** (تنظیم `DATABASE_PATH`) جایگزین کنید.
پیش از اجرا از دیتابیس پشتیبان بگیرید. ابزار برای جلوگیری از انتخاب دیتابیس اشتباه، مسیر دیتابیس را اجباری می‌گیرد و فایل جدید نمی‌سازد.
رمز جدید حداقل ۱۲ کاراکتر است و دو بار به‌صورت مخفی دریافت می‌شود؛ رمز را در فرمان یا پیام وارد نکنید.
فقط رمز مدیر فعال موجود عوض می‌شود؛ نقش‌ها تغییری نمی‌کنند و نشست‌های قبلی باطل می‌شوند.
این روش به دسترسی مورد اعتماد به سرور نیاز دارد و از طریق وب قابل اجرا نیست.
برای نصب این اصلاح، کد را روی سرور به‌روز و برنامه را دوباره راه‌اندازی کنید؛ جدول درخواست‌ها در راه‌اندازی ساخته می‌شود.

## تست

Regression روی Windows:

```powershell
.\scripts\test-v05-windows.ps1
```

Acceptance آداپتر CRM با گیرنده آزمایشی:

```powershell
.\scripts\test-crm-adapter-windows.ps1
```

یا unit/regression:

```bash
python -m unittest discover -s tests -v
```

## امنیت

موارد زیر نباید commit یا در UI/Log افشا شوند:
- `.env.local`
- `BALE_TOKEN`
- `SATNO_BALE_MARKET_INGEST_TOKEN`
- password خام
- session runtime
- `satno_market.db` و سایر SQLiteهای عملیاتی

## CRM Alpha 2.2

اتصال زنده در Alpha 2.1 عمداً غیرفعال می‌ماند.

تا زمان تأیید Alpha 2.2:
- `SATNO_CRM_LEAD_URL` خالی بماند.
- سرنخ انتخاب‌شده فقط وارد `crm_lead_outbox` می‌شود.
- ورود به Lead Inbox به معنی ساخت خودکار Company، Contact، Deal یا Project نیست.

سند اصلی آمادگی:
- [docs/CRM_ALPHA22_READINESS.md](docs/CRM_ALPHA22_READINESS.md)
- [docs/sample-bale-lead-alpha22.json](docs/sample-bale-lead-alpha22.json)

## Production

Production فعلی Windows Server:
- مسیر: `C:\Satno\SatnoBaleMarket-v05`
- پورت: `8000`

نصب بسته آمادگی Alpha 2.2:

```powershell
.\scripts\install-alpha22-readiness-windows.ps1
```

Rollback با backup path تولیدشده توسط installer:

```powershell
.\scripts\rollback-alpha22-readiness-windows.ps1 -BackupPath "C:\Satno\backup\bale-market-alpha22-YYYYMMDD-HHMMSS"
```

اسکریپت‌های این بسته فقط SATNO Bale Market را مدیریت می‌کنند و نباید فارسیکام، VoIP یا سرویس‌های دیگر سرور را تغییر دهند.
