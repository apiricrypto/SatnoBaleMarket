"""Real browser + STARTTLS SMTP acceptance with disposable data; no external mail."""
import argparse
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit, parse_qs
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright, expect
from tests.smtp_fixture import TLSInbox


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifacts', required=True)
    parser.add_argument('--port', type=int, default=8007)
    parser.add_argument('--chromium', default='/usr/bin/chromium')
    args = parser.parse_args()
    out = Path(args.artifacts).resolve()
    out.mkdir(parents=True, exist_ok=True)
    base = 'http://127.0.0.1:' + str(args.port)
    original = secrets.token_urlsafe(24)
    replacement = secrets.token_urlsafe(24)
    tokens = []
    with tempfile.TemporaryDirectory() as temp, TLSInbox() as inbox:
        import db
        from auth import create_user
        previous = db.DB_PATH
        db.DB_PATH = str(Path(temp) / 'recovery-browser.db')
        for role in ('admin', 'sales', 'viewer'):
            create_user('recover-'+role, original, role, email=role+'@example.com')
        env = {**os.environ, **inbox.settings, 'DATABASE_PATH': db.DB_PATH,
               'SATNO_PUBLIC_BASE_URL': base, 'SESSION_COOKIE_SECURE': '0',
               'SATNO_CRM_LEAD_URL': '', 'SATNO_BALE_MARKET_INGEST_TOKEN': ''}
        db.DB_PATH = previous
        with (out / 'server.log').open('w') as log:
            process = subprocess.Popen([sys.executable,'-m','uvicorn','main:app','--host','127.0.0.1','--port',str(args.port)],
                                       cwd=ROOT, env=env, stdout=log, stderr=log)
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError('Test app exited; see server.log')
                    try:
                        with urlopen(base+'/health', timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise RuntimeError('Readiness timed out')
                with sync_playwright() as p:
                    browser = p.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox'])
                    page = browser.new_page()
                    errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
                    page.goto(base+'/login')
                    page.get_by_role('link', name='رمز عبور را فراموش کرده‌اید؟', exact=True).click()
                    for width in (375,768,1440):
                        page.set_viewport_size({'width':width,'height':900})
                        expect(page.get_by_role('button', name='درخواست پیوند بازیابی', exact=True)).to_be_enabled()
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                        page.screenshot(path=str(out / f'forgot-{width}.png'), full_page=True)
                    for role in ('admin','sales','viewer'):
                        stale = browser.new_context()
                        assert stale.request.post(base+'/api/auth/login', data={'username':'recover-'+role,'password':original}).ok
                        page.goto(base+'/forgot-password')
                        page.get_by_label('ایمیل ثبت‌شدهٔ حساب', exact=True).fill(role+'@example.com')
                        page.get_by_role('button', name='درخواست پیوند بازیابی', exact=True).click()
                        expect(page.locator('#result')).to_contain_text('اگر حساب فعالی')
                        mail = inbox.messages.get(timeout=10)
                        assert str(mail['To']) == role+'@example.com'
                        link = re.search(r'http://\S+', mail.get_content()).group()
                        token = parse_qs(urlsplit(link).fragment)['token'][0]
                        tokens.append(token)
                        page.goto(link)
                        expect(page.get_by_role('button', name='ثبت رمز جدید', exact=True)).to_be_enabled()
                        assert '#' not in page.url
                        if role == 'admin':
                            for width in (375,768,1440):
                                page.set_viewport_size({'width':width,'height':900})
                                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                                page.screenshot(path=str(out / f'reset-{width}.png'), full_page=True)
                            page.get_by_label('رمز جدید (حداقل ۱۲ کاراکتر)', exact=True).fill(replacement)
                            page.get_by_label('تکرار رمز جدید', exact=True).fill('DifferentSyntheticPassword123!')
                            page.get_by_role('button', name='ثبت رمز جدید', exact=True).click()
                            expect(page.locator('#result')).to_contain_text('یکسان نیستند')
                        page.get_by_label('رمز جدید (حداقل ۱۲ کاراکتر)', exact=True).fill(replacement)
                        page.get_by_label('تکرار رمز جدید', exact=True).fill(replacement)
                        page.get_by_role('button', name='ثبت رمز جدید', exact=True).click()
                        expect(page.locator('#result')).to_contain_text('رمز تغییر کرد')
                        assert stale.request.get(base+'/api/auth/me').status == 401
                        assert page.request.post(base+'/api/auth/login', data={'username':'recover-'+role,'password':original}).status == 401
                        assert page.request.post(base+'/api/auth/login', data={'username':'recover-'+role,'password':replacement}).ok
                        assert page.request.post(base+'/api/auth/reset-password', data={'token':token,'new_password':original,'confirm_password':original}).status == 400
                        page.request.post(base+'/api/auth/logout')
                        stale.close()
                    page.request.post(base+'/api/auth/login', data={'username':'recover-admin','password':replacement})
                    page.goto(base+'/admin/users')
                    email = page.get_by_label('ایمیل بازیابی recover-sales', exact=True)
                    expect(email).to_have_value('sales@example.com')
                    row = page.locator('tr').filter(has=email)
                    email.fill('changed-sales@example.com')
                    row.get_by_role('button', name='ذخیره', exact=True).click()
                    expect(email).to_have_value('changed-sales@example.com')
                    page.reload()
                    expect(email).to_have_value('changed-sales@example.com')
                    page.screenshot(path=str(out/'admin-email-1440.png'),full_page=True)
                    assert not errors, errors
                    browser.close()
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        assert all(token not in (out/'server.log').read_text() for token in tokens)
    print('PASS: real STARTTLS email, admin/sales/viewer reset, mismatch, old-password rejection, session revocation, single use, email administration; no browser errors/token access-log leaks; 375/768/1440')


if __name__ == '__main__':
    main()
