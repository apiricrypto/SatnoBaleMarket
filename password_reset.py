"""Single-use recovery tokens, durable request limits and account/session revocation."""
import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

from auth import hash_password, verify_password, _revoke_user_sessions, _revoke_reset_tokens
from db import connect, init_db
from staff_email import normalize_email
from recovery_mailer import recovery_settings, send_reset_email

GENERIC_MESSAGE = 'اگر حساب فعالی با این ایمیل ثبت شده باشد، پیوند بازیابی ارسال می‌شود. پوشهٔ هرزنامه را نیز بررسی کنید.'
TOKEN_MINUTES = 30


def _digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def reserve_reset_request(email, request_ip):
    email = normalize_email(email)
    if not email:
        raise ValueError('email is required')
    init_db()
    now = datetime.now(timezone.utc)
    keys = (_digest('email:' + email), _digest('ip:' + str(request_ip)))
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        con.execute('DELETE FROM staff_reset_requests WHERE created_at<?', ((now-timedelta(days=1)).isoformat(),))
        con.execute('DELETE FROM staff_password_resets WHERE expires_at<?', ((now-timedelta(days=1)).isoformat(),))
        for key, minutes, limit in ((keys[0], 15, 3), (keys[0], 1, 1), (keys[1], 60, 30)):
            count = con.execute('SELECT COUNT(*) FROM staff_reset_requests WHERE request_key=? AND created_at>?',
                                (key, (now-timedelta(minutes=minutes)).isoformat())).fetchone()[0]
            if count >= limit:
                return None
        con.executemany('INSERT INTO staff_reset_requests(request_key,created_at) VALUES(?,?)',
                        [(key, now.isoformat()) for key in keys])
    return email


def deliver_reset_email(email):
    """Background delivery. Never return/log token, address, SMTP exception or account state."""
    config = recovery_settings()
    email = normalize_email(email)
    token = secrets.token_urlsafe(32)
    digest = _digest(token)
    now = datetime.now(timezone.utc)
    init_db()
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        user = con.execute('SELECT id FROM staff_users WHERE email=? COLLATE NOCASE AND is_active=1', (email,)).fetchone()
        if not user:
            return
        _revoke_reset_tokens(con, user['id'])
        con.execute('INSERT INTO staff_password_resets(token_hash,user_id,email,expires_at,created_at) VALUES(?,?,?,?,?)',
                    (digest, user['id'], email, (now+timedelta(minutes=TOKEN_MINUTES)).isoformat(), now.isoformat()))
    try:
        # Fragment never appears in HTTP access logs or the initial reset page request.
        send_reset_email(email, config['base'] + '/reset-password#token=' + token)
    except Exception:
        logging.getLogger(__name__).warning('Password recovery email delivery failed')
        with connect() as con:
            con.execute('UPDATE staff_password_resets SET used_at=? WHERE token_hash=?', (datetime.now(timezone.utc).isoformat(), digest))


def reset_password(token, new_password):
    if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        raise ValueError('پیوند بازیابی نامعتبر یا منقضی شده است.')
    if not isinstance(new_password, str) or not 12 <= len(new_password) <= 512:
        raise ValueError('رمز جدید باید بین ۱۲ و ۵۱۲ کاراکتر باشد.')
    init_db()
    # Reject random/expired tokens before spending PBKDF2 work; recheck under write lock.
    with connect() as con:
        valid = con.execute('''SELECT 1 FROM staff_password_resets r JOIN staff_users u ON u.id=r.user_id
            WHERE r.token_hash=? AND r.used_at IS NULL AND r.expires_at>? AND u.is_active=1
              AND u.email=r.email COLLATE NOCASE''', (_digest(token), datetime.now(timezone.utc).isoformat())).fetchone()
    if not valid:
        raise ValueError('پیوند بازیابی نامعتبر یا منقضی شده است.')
    encoded = hash_password(new_password)
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        now = datetime.now(timezone.utc).isoformat()
        row = con.execute('''SELECT u.id,u.password_hash FROM staff_password_resets r
            JOIN staff_users u ON u.id=r.user_id
            WHERE r.token_hash=? AND r.used_at IS NULL AND r.expires_at>? AND u.is_active=1
              AND u.email=r.email COLLATE NOCASE''', (_digest(token), now)).fetchone()
        if not row:
            raise ValueError('پیوند بازیابی نامعتبر یا منقضی شده است.')
        if verify_password(new_password, row['password_hash']):
            raise ValueError('رمز جدید باید با رمز قبلی متفاوت باشد.')
        con.execute('UPDATE staff_users SET password_hash=? WHERE id=?', (encoded, row['id']))
        _revoke_user_sessions(con, row['id'])
        _revoke_reset_tokens(con, row['id'])
    return True
