"""Recover an existing active administrator using trusted server access."""
import argparse
import getpass
import sqlite3
import warnings
from contextlib import closing
from pathlib import Path

import db
from auth import recover_admin_password


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('username')
    parser.add_argument('--database', required=True, help='Path to the existing application database')
    args = parser.parse_args(argv)
    database = Path(args.database).resolve()
    if not database.is_file():
        raise SystemExit('Database does not exist; use the running application database path.')
    previous = db.DB_PATH
    try:
        # Inspect before migrations or password prompts; a wrong database must not be created.
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as con:
            row = con.execute(
                "SELECT id FROM staff_users WHERE username=? AND role='admin' AND is_active=1",
                (args.username.strip().lower(),),
            ).fetchone()
        if not row:
            raise SystemExit('Active administrator not found. No account was changed.')
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            password = getpass.getpass('New password (at least 12 characters): ')
            confirm = getpass.getpass('Confirm new password: ')
        if password != confirm:
            raise SystemExit('Passwords do not match. No account was changed.')
        db.DB_PATH = str(database)
        recover_admin_password(args.username, password)
    except getpass.GetPassWarning as exc:
        raise SystemExit('Hidden password entry unavailable. Use an interactive server terminal.') from exc
    except (ValueError, sqlite3.Error) as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        db.DB_PATH = previous
    print('Administrator password reset. Previous sessions revoked.')


if __name__ == '__main__':
    main()
