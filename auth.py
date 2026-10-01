import hashlib
import hmac
import secrets
from db import connect, init_db

ITERATIONS=310000

def hash_password(password, salt=None):
    salt=salt or secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac("sha256",password.encode("utf-8"),bytes.fromhex(salt),ITERATIONS)
    return "pbkdf2_sha256$%s$%s$%s" % (ITERATIONS,salt,digest.hex())

def verify_password(password, encoded):
    try:
        scheme,iters,salt,digest=encoded.split("$",3)
        if scheme!="pbkdf2_sha256": return False
        candidate=hashlib.pbkdf2_hmac("sha256",password.encode("utf-8"),bytes.fromhex(salt),int(iters)).hex()
        return hmac.compare_digest(candidate,digest)
    except Exception:
        return False

def create_user(username,password,role="viewer",display_name=None):
    if role not in {"admin","sales","viewer"}: raise ValueError("invalid role")
    if len(password)<10: raise ValueError("password must be at least 10 characters")
    init_db()
    with connect() as con:
        con.execute("INSERT INTO staff_users(username,password_hash,role,display_name) VALUES(?,?,?,?)",
                    (username.strip().lower(),hash_password(password),role,display_name))
