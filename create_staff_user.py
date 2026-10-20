import argparse
import getpass
from auth import create_user

def main():
    p=argparse.ArgumentParser()
    p.add_argument("username")
    p.add_argument("--role",choices=["admin","sales","viewer"],default="viewer")
    p.add_argument("--name",default=None)
    p.add_argument("--email", default=None, help="Recovery email assigned by administrator")
    args=p.parse_args()
    password=getpass.getpass("Password: ")
    confirm=getpass.getpass("Confirm password: ")
    if password!=confirm: raise SystemExit("Passwords do not match")
    create_user(args.username,password,args.role,args.name,email=args.email)
    print("USER CREATED:",args.username,args.role)

if __name__=="__main__":
    main()
