from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field

from password_reset import GENERIC_MESSAGE, reserve_reset_request, deliver_reset_email, reset_password
from recovery_mailer import recovery_settings, RecoveryUnavailable

router = APIRouter()
PRIVATE = {'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'}


class ForgotIn(BaseModel):
    email: str = Field(max_length=254)


class ResetIn(BaseModel):
    token: str = Field(max_length=128)
    new_password: str = Field(max_length=512)
    confirm_password: str = Field(max_length=512)


@router.get('/api/auth/recovery-status')
def recovery_status():
    try:
        recovery_settings()
        enabled = True
    except RecoveryUnavailable:
        enabled = False
    from fastapi.responses import JSONResponse
    return JSONResponse({'enabled': enabled}, headers=PRIVATE)


@router.post('/api/auth/forgot-password')
def forgot_password(payload: ForgotIn, request: Request, background: BackgroundTasks, response: Response):
    try:
        recovery_settings()
    except RecoveryUnavailable:
        raise HTTPException(503, 'سرویس ارسال ایمیل بازیابی هنوز تنظیم نشده است؛ با مدیر سامانه تماس بگیرید.', headers=PRIVATE) from None
    try:
        email = reserve_reset_request(payload.email, request.client.host if request.client else 'unknown')
    except ValueError:
        raise HTTPException(400, 'آدرس ایمیل معتبر وارد کنید.', headers=PRIVATE) from None
    if email:
        background.add_task(deliver_reset_email, email)
    response.headers.update(PRIVATE)
    return {'message': GENERIC_MESSAGE}


@router.post('/api/auth/reset-password')
def complete_reset(payload: ResetIn, response: Response):
    if payload.new_password != payload.confirm_password:
        raise HTTPException(400, 'رمز جدید و تکرار آن یکسان نیستند.', headers=PRIVATE)
    try:
        reset_password(payload.token, payload.new_password)
    except ValueError as exc:
        raise HTTPException(400, str(exc), headers=PRIVATE) from None
    response.delete_cookie('satno_staff_session', path='/')
    response.headers.update(PRIVATE)
    return {'message': 'رمز تغییر کرد و نشست‌های قبلی بسته شدند. با رمز جدید وارد شوید.'}


@router.get('/assets/password-recovery.js')
def recovery_script():
    return FileResponse(Path(__file__).with_name('assets') / 'password-recovery.js', media_type='text/javascript', headers={'Cache-Control': 'no-cache'})


def recovery_page(mode):
    reset = mode == 'reset'
    title = 'تعیین رمز جدید' if reset else 'بازیابی رمز عبور'
    fields = ('''<label for="new">رمز جدید (حداقل ۱۲ کاراکتر)</label><input id="new" type="password" autocomplete="new-password" minlength="12" maxlength="512" required>
<label for="confirm">تکرار رمز جدید</label><input id="confirm" type="password" autocomplete="new-password" minlength="12" maxlength="512" required>
<button type="button" id="toggle" aria-pressed="false">نمایش رمز</button>''' if reset else
        '''<label for="email">ایمیل ثبت‌شدهٔ حساب</label><input id="email" type="email" autocomplete="email" maxlength="254" dir="ltr" required>
<p class="muted">ایمیلی را وارد کنید که مدیر برای حساب شما ثبت کرده است. پیوند بازیابی ۳۰ دقیقه اعتبار دارد.</p>''')
    html = '''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>''' + title + ''' | ساتنو</title><link rel="icon" href="data:,"><link rel="stylesheet" href="/assets/satno-ui.css">
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;padding:20px}.recovery-card{width:min(100%,480px);padding:28px}.recovery-card img{display:block;width:76px;height:auto;margin:0 auto 20px}.recovery-card h1{font-size:24px!important}.recovery-card label{display:block;margin:16px 0 7px}.recovery-card input{width:100%;padding:12px;font:inherit;direction:ltr;min-height:48px}.recovery-card button{padding:12px;min-height:46px;font:inherit}.recovery-card .primary{display:block;width:100%;margin-top:18px}.recovery-card p{line-height:1.9}.recovery-card #toggle{margin-top:9px}#result{overflow-wrap:anywhere}a{display:inline-flex;min-height:44px;align-items:center}</style>
<script src="/assets/password-recovery.js" defer></script></head><body data-recovery="''' + mode + '''"><main class="card recovery-card"><img src="/assets/satno-logo.jpg" alt="لوگوی رسمی گروه ساتنو" width="1280" height="1218"><h1>''' + title + '''</h1><form id="recoveryForm">''' + fields + '''<button class="primary" id="submit" type="submit">''' + ('ثبت رمز جدید' if reset else 'درخواست پیوند بازیابی') + '''</button></form><p id="result" role="status" aria-live="polite"></p><a href="/login">بازگشت به ورود</a></main></body></html>'''
    return HTMLResponse(html, headers={**PRIVATE, 'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"})


@router.get('/forgot-password', response_class=HTMLResponse)
def forgot_page():
    return recovery_page('forgot')


@router.get('/reset-password', response_class=HTMLResponse)
def reset_page():
    return recovery_page('reset')
