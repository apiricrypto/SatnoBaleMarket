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
