# SATNO Bale Market Intelligence

سامانه هوش بازار بله برای گروه ساتنو.

## v0.5 Staff Edition

Branch توسعه: `feature/staff-v05`

قابلیت‌های اصلی این نسخه:
- Login پرسنل با password hash امن
- Session سمت‌سرور با token hash و Logout/Revoke
- RBAC نقش‌های `admin`، `sales` و `viewer`
- حفاظت Dashboard و API
- مدیریت کاربران پرسنل و جلوگیری از حذف آخرین Admin فعال
- Search Ranking وزن‌دار برای برند، مدل، نوع محصول، محل و متن
- صفحه وضعیت منابع و Sync
- Sender Resolution با cache پایدار در SQLite
- قرارداد `satno.lead.v1` و Outbox idempotent برای SATNO CRM
- دکمه ارسال Lead به CRM
- آمادگی تست ایزوله Windows Server روی پورت جداگانه

## اجرای محلی

```bash
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8005
```

Health check:

```
GET /health
```

صفحات:
- `/login`
- `/` داشبورد
- `/status` وضعیت منابع و Sync
- `/admin/users` مدیریت کاربران Admin

## ساخت اولین Admin

```bash
python create_staff_user.py admin --role admin --name "SATNO Admin"
```

رمز به‌صورت interactive دریافت می‌شود و password خام در Git یا کد ذخیره نمی‌شود.

## تست

Windows:

```powershell
.\scripts\test-v05-windows.ps1
```

یا:

```bash
python -m unittest discover -s tests -v
```

## امنیت

فایل‌ها و داده‌های زیر نباید commit شوند:
- `.env.local`
- `BALE_TOKEN`
- `SATNO_CRM_API_TOKEN`
- password خام
- session runtime
- `satno_market.db` و سایر SQLiteهای عملیاتی

نمونه تنظیمات در `.env.example` است. مقادیر واقعی فقط server-side قرار می‌گیرند.

## CRM

اگر `SATNO_CRM_LEAD_URL` تنظیم نشده باشد، Leadها در `crm_lead_outbox` با idempotency ذخیره می‌شوند و داده از بین نمی‌رود. پس از تنظیم endpoint واقعی CRM، ارسال توسط backend انجام می‌شود و token CRM به مرورگر داده نمی‌شود.

## Production

راهنمای تست و استقرار در [DEPLOYMENT_V05.md](DEPLOYMENT_V05.md) است.

**v0.5 نباید بدون تأیید صریح روی Production جایگزین v0.4 شود.**
