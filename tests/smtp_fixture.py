"""Disposable TLS SMTP receiver bound strictly to loopback, for acceptance tests only."""
from contextlib import AbstractContextManager
from email import policy
from email.parser import BytesParser
from pathlib import Path
import queue
import socketserver
import ssl
import subprocess
import tempfile
import threading


class TLSInbox(AbstractContextManager):
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cert = Path(self.tmp.name) / 'localhost.crt'
        key = Path(self.tmp.name) / 'localhost.key'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost',
                        '-keyout', str(key), '-out', str(self.cert)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.messages = queue.Queue()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(self.cert), str(key))
        inbox = self

        class Handler(socketserver.StreamRequestHandler):
            def reply(self, value):
                self.wfile.write(value.encode('ascii') + b'\r\n')
                self.wfile.flush()

            def handle(self):
                self.connection.settimeout(10)
                secure = authenticated = False
                self.reply('220 localhost test inbox')
                while True:
                    line = self.rfile.readline(8192)
                    if not line:
                        return
                    command = line.decode('ascii', errors='replace').strip().upper()
                    if command.startswith(('EHLO', 'HELO')):
                        self.reply('250-localhost\r\n250-STARTTLS\r\n250 AUTH PLAIN')
                    elif command == 'STARTTLS':
                        self.reply('220 Start TLS')
                        self.rfile.close()
                        self.wfile.close()
                        self.connection = context.wrap_socket(self.connection, server_side=True)
                        self.rfile = self.connection.makefile('rb')
                        self.wfile = self.connection.makefile('wb')
                        secure = True
                    elif command.startswith('AUTH'):
                        authenticated = secure
                        self.reply('235 Authenticated' if secure else '530 TLS required')
                    elif command.startswith(('MAIL FROM:', 'RCPT TO:')):
                        self.reply('250 OK' if authenticated else '530 Authentication required')
                    elif command == 'DATA' and authenticated:
                        self.reply('354 End with dot')
                        data = []
                        while True:
                            part = self.rfile.readline(65536)
                            if part in (b'.\r\n', b'.\n', b''):
                                break
                            data.append(part[1:] if part.startswith(b'..') else part)
                        inbox.messages.put(BytesParser(policy=policy.default).parsebytes(b''.join(data)))
                        self.reply('250 Stored')
                    elif command == 'QUIT':
                        self.reply('221 Bye')
                        return
                    else:
                        self.reply('250 OK')

        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True
        self.server = Server(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    @property
    def settings(self):
        return {'SATNO_SMTP_HOST': 'localhost', 'SATNO_SMTP_PORT': str(self.server.server_address[1]),
                'SATNO_SMTP_SECURITY': 'starttls', 'SATNO_SMTP_USERNAME': 'fixture@example.com',
                'SATNO_SMTP_PASSWORD': 'synthetic-fixture-only', 'SATNO_SMTP_FROM': 'fixture@example.com',
                'SSL_CERT_FILE': str(self.cert)}

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()
