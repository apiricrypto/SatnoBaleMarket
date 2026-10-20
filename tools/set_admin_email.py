"""Review/apply an administrator recovery address against an explicit existing database."""
import argparse
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--email', required=True)
    parser.add_argument('--username', help='Required if more than one active administrator exists')
    parser.add_argument('--apply', action='store_true', help='Write only after backup and reviewed account selection')
    args = parser.parse_args()
    from staff_email import normalize_email
    email = normalize_email(args.email)
    if not email:
        raise SystemExit('A valid recovery email is required')
    database = Path(args.database).resolve()
    if not database.is_file():
        raise SystemExit('Existing database not found; nothing created')
    con = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
    try:
        rows = con.execute("SELECT id,username FROM staff_users WHERE role='admin' AND is_active=1").fetchall()
    finally:
        con.close()
    if args.username:
        rows = [r for r in rows if r[1] == args.username.strip().lower()]
    if len(rows) != 1:
        raise SystemExit('Select exactly one active administrator with --username; no changes made')
    user_id, username = rows[0]
    print('DATABASE:', database)
    print('ADMIN:', username, 'ID:', user_id)
    if not args.apply:
        print('MODE: READ_ONLY; use --apply after backup to register the address')
        return
    import db
    db.DB_PATH = str(database)  # Never inherit a temporary DATABASE_PATH.
    from auth import update_user
    update_user(user_id, email=email)
    print('ADMIN_RECOVERY_EMAIL_UPDATED; password and role preserved')


if __name__ == '__main__':
    main()
