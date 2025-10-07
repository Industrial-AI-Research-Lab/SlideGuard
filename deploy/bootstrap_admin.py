"""Bootstrap first admin user"""
import os
from slideguard.ui.auth import init_db, register_user, Role

def main():
    u = (os.getenv("ADMIN_USERNAME") or "").strip()
    p = (os.getenv("ADMIN_PASSWORD") or "").strip()
    r = (os.getenv("ADMIN_ROLE") or "admin").strip().lower()
    if not u or not p:
        return
    init_db()
    role = Role.ADMIN if r == "admin" else Role.USER
    try:
        register_user(u, p, role)
    except Exception:
        pass

if __name__ == "__main__":
    main()