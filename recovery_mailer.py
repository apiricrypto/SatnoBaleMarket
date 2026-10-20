"""TLS SMTP transport; all secrets and public origin come from server configuration."""
import ipaddress
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlsplit

from staff_email import normalize_email


class RecoveryUnavailable(ValueError):
    pass


def recovery_settings():
    try:
        base = os.getenv('SATNO_PUBLIC_BASE_URL', '').strip().rstrip('/')
        url = urlsplit(base)
        loopback = url.hostname == 'localhost'
        try:
            loopback = loopback or ipaddress.ip_address(url.hostname or '').is_loopback
        except ValueError:
            pass
        if (url.scheme not in {'https', 'http'} or not url.hostname or url.port == 0 or any(c.isspace() or c == '\\' for c in base) or url.username or url.password
                or url.path or url.query or url.fragment
                or (url.scheme == 'http' and not loopback and os.getenv('SATNO_RECOVERY_ALLOW_HTTP') != '1')):
            raise ValueError()
        host = os.getenv('SATNO_SMTP_HOST', '').strip()
        port = int(os.getenv('SATNO_SMTP_PORT', '587'))
        security = os.getenv('SATNO_SMTP_SECURITY', 'starttls')
        username = os.getenv('SATNO_SMTP_USERNAME', '')
        password = os.getenv('SATNO_SMTP_PASSWORD', '')
        sender = normalize_email(os.getenv('SATNO_SMTP_FROM', ''))
        if not host or not 1 <= port <= 65535 or security not in {'starttls', 'ssl'} or not username or not password or not sender:
            raise ValueError()
        return dict(base=base, host=host, port=port, security=security, username=username, password=password, sender=sender)
    except (ValueError, TypeError):
        raise RecoveryUnavailable('Email recovery is not configured') from None


def send_reset_email(recipient, link):
    config = recovery_settings()
    message = EmailMessage()
    message['Subject'] = 'بازیابی رمز عبور بله مارکت ساتنو'
    message['From'] = config['sender']
    message['To'] = normalize_email(recipient)
    message.set_content('درخواست بازیابی رمز عبور حساب بله مارکت شما ثبت شده است.\n'
                        'این پیوند یک‌بارمصرف است و تا ۳۰ دقیقه اعتبار دارد:\n\n' + link + '\n\n'
                        'اگر شما درخواست نداده‌اید، این ایمیل را نادیده بگیرید. رمز شما تغییر نکرده است.\n'
                        'گروه ساتنو')
    context = ssl.create_default_context()
    cls = smtplib.SMTP_SSL if config['security'] == 'ssl' else smtplib.SMTP
    kwargs = {'timeout': 10}
    if config['security'] == 'ssl':
        kwargs['context'] = context
    with cls(config['host'], config['port'], **kwargs) as smtp:
        if config['security'] == 'starttls':
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
        smtp.login(config['username'], config['password'])
        smtp.send_message(message)
