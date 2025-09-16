import argparse, getpass
from slideguard.ui.auth import get_db, register_user, hash_password, User, Role

def cmd_create(args):
    pw1 = getpass.getpass("Password: ")
    pw2 = getpass.getpass("Confirm: ")
    if pw1 != pw2:
        print("Passwords do not match")
        return
    ok = register_user(args.username, pw1, Role(args.role))
    print("Created" if ok else "Username already exists")

def cmd_passwd(args):
    pw1 = getpass.getpass("New password: ")
    pw2 = getpass.getpass("Confirm: ")
    if pw1 != pw2:
        print("Passwords do not match")
        return
    with get_db() as db:
        u = db.query(User).filter(User.username == args.username).first()
        if not u:
            print("User not found"); return
        u.password_hash = hash_password(pw1)
        db.commit()
        print("Password updated")

def cmd_role(args):
    with get_db() as db:
        u = db.query(User).filter(User.username == args.username).first()
        if not u:
            print("User not found"); return
        u.role = Role(args.role)
        db.commit()
        print("Role updated")

def cmd_delete(args):
    with get_db() as db:
        u = db.query(User).filter(User.username == args.username).first()
        if not u:
            print("User not found"); return
        db.delete(u)
        db.commit()
        print("Deleted")

def cmd_list(args):
    with get_db() as db:
        users = db.query(User).all()
        for u in users:
            print(f"{u.username}\t{u.role.value}")

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create"); c.add_argument("--username", required=True); c.add_argument("--role", choices=[r.value for r in Role], default="user"); c.set_defaults(func=cmd_create)
    s = sub.add_parser("passwd"); s.add_argument("--username", required=True); s.set_defaults(func=cmd_passwd)
    r = sub.add_parser("role"); r.add_argument("--username", required=True); r.add_argument("--role", choices=[r.value for r in Role], required=True); r.set_defaults(func=cmd_role)
    x = sub.add_parser("delete"); x.add_argument("--username", required=True); x.set_defaults(func=cmd_delete)
    l = sub.add_parser("list"); l.set_defaults(func=cmd_list)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()