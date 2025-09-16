import os
import bcrypt
from enum import Enum
from typing import Optional, ContextManager
from contextlib import contextmanager
from sqlalchemy import create_engine, Column, Integer, String, DateTime, func
from sqlalchemy.types import Enum as DBEnum
from sqlalchemy.orm import sessionmaker, declarative_base, Session

DB_URL = os.getenv("AUTH_DB_URL", "sqlite:///./auth.db")
ENGINE = create_engine(
    DB_URL, 
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {} # remove thread restriction for sqlite
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)
Base = declarative_base()

class Role(Enum):
    USER = "user"
    ADMIN = "admin"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(DBEnum(Role, name="role"), default=Role.USER, nullable=False)
    created_at = Column(DateTime, default=func.now())

def init_db():
    Base.metadata.create_all(bind=ENGINE)

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed_password.encode())
    except ValueError:
        return False

@contextmanager
def get_db() -> ContextManager[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_user(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()

def authenticate_user(db: Session, username: str, password: str) -> bool:
    user = get_user(db, username)
    if not user:
        return False
    return verify_password(password, user.password_hash)

def get_role(username: str) -> Role:
    with get_db() as db:
        user = get_user(db, username)
        if not user:
            return Role.USER
        return user.role

def register_user(username: str, password: str, role: Role = Role.USER) -> bool: # admin functionality
    uname = (username or "").strip()
    if not uname:
        return False
    if not password or not password.strip():
        return False
    with get_db() as db:
        if get_user(db, uname):
            return False
        hashed_password = hash_password(password)
        new_user = User(username=uname, password_hash=hashed_password, role=role)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return True

def verify_user_db(username: str, password: str) -> bool: # gradio auth wrapper
    with get_db() as db:
        return authenticate_user(db, username, password)

def list_users() -> list[tuple[str, str]]:
    with get_db() as db:
        users = db.query(User).all()
        return [(u.username, u.role.value) for u in users]

def update_user_password(username: str, new_password: str) -> bool:
    if not new_password or not new_password.strip():
        return False
    with get_db() as db:
        user = get_user(db, username)
        if not user:
            return False
        user.password_hash = hash_password(new_password)
        db.commit()
        return True

def update_user_role(username: str, role: Role) -> bool:
    with get_db() as db:
        user = get_user(db, username)
        if not user:
            return False
        user.role = role
        db.commit()
        return True

def delete_user(username: str) -> bool:
    with get_db() as db:
        user = get_user(db, username)
        if not user:
            return False
        db.delete(user)
        db.commit()
        return True