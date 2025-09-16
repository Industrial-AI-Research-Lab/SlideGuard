import argparse, getpass
from slideguard.ui.auth import (init_db, register_user, Role, update_user_password, 
                                update_user_role, delete_user, list_users)

def cmd_create(args):
    if not args.username or not args.username.strip():
        print("Username cannot be empty"); return
    pw1 = getpass.getpass("Password: ")
    pw2 = getpass.getpass("Confirm: ")
    if pw1 != pw2:
        print("Passwords do not match")
        return
    if not pw1 or not pw1.strip():
        print("Password cannot be empty"); return
    ok = register_user(args.username, pw1, Role(args.role))
    print("Created" if ok else "Username already exists")

def cmd_pwd(args):
    if not args.username or not args.username.strip():
        print("Username cannot be empty"); return
    pw1 = getpass.getpass("New password: ")
    pw2 = getpass.getpass("Confirm: ")
    if pw1 != pw2:
        print("Passwords do not match")
        return
    if not pw1 or not pw1.strip():
        print("Password cannot be empty"); return
    ok = update_user_password(args.username, pw1)
    print("Password updated" if ok else "User not found")

def cmd_role(args):
    ok = update_user_role(args.username, Role(args.role))
    print("Role updated" if ok else "User not found")

def cmd_delete(args):
    ok = delete_user(args.username)
    print("Deleted" if ok else "User not found")

def cmd_list(args):
    users = list_users()
    if not users:
        print("No users found in the database")
        return
    for uname, role in users:
        print(f"{uname}\t{role}")

def main():
    init_db()
    
    p = argparse.ArgumentParser(
        prog="slideguard-admin",
        description="SlideGuard Admin CLI - Manage user accounts and roles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Use -h or --help with any command for detailed help."
    )
    sub = p.add_subparsers(
        dest="cmd", 
        required=True,
        title="Available commands",
        description="Choose a command to manage users",
        help="Command help"
    )

    c = sub.add_parser(
        "create", 
        help="Create a new user account",
        description="Create a new user with specified username and role"
    )
    c.add_argument("-u", "--username", required=True, help="Username for the new account")
    c.add_argument("-r", "--role", choices=["admin","user"], default="user", help="User role (default: user)")
    c.set_defaults(func=cmd_create)
    
    s = sub.add_parser(
        "pwd", 
        help="Change user password",
        description="Change password for an existing user (will prompt for new password interactively)"
    )
    s.add_argument("-u", "--username", required=True, help="Username to change password for")
    s.set_defaults(func=cmd_pwd)
    
    r = sub.add_parser(
        "role", 
        help="Change user role",
        description="Change role for an existing user"
    )
    r.add_argument("-u", "--username", required=True, help="Username to change role for")
    r.add_argument("-r", "--role", choices=["admin","user"], required=True, help="New role to assign")
    r.set_defaults(func=cmd_role)
    
    x = sub.add_parser(
        "delete", 
        help="Delete user account",
        description="Permanently delete a user account"
    )
    x.add_argument("-u", "--username", required=True, help="Username to delete")
    x.set_defaults(func=cmd_delete)
    
    l = sub.add_parser(
        "list", 
        help="List all users",
        description="Display all users and their roles"
    )
    l.set_defaults(func=cmd_list)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()