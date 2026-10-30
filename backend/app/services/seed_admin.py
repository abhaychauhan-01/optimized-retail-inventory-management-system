from __future__ import annotations

import os

from sqlalchemy import select

from ..db.database import Base, SessionLocal, engine
from ..models import User
from .auth import hash_password


def seed_demo_admin() -> None:
    if os.getenv("APP_ENV", "development").strip().lower() != "development":
        raise RuntimeError("The demo administrator seed is available only when APP_ENV=development.")

    email = os.getenv("DEMO_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("DEMO_ADMIN_PASSWORD", "")
    if not email or not password:
        print("Demo admin not created. Set DEMO_ADMIN_EMAIL and DEMO_ADMIN_PASSWORD in the development environment.")
        return
    if len(password) < 12:
        raise ValueError("DEMO_ADMIN_PASSWORD must contain at least 12 characters.")
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise ValueError("DEMO_ADMIN_EMAIL must be a valid email address.")

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            print(f"Demo admin {email} already exists; no account changes were made.")
            return
        db.add(User(email=email, password_hash=hash_password(password), is_admin=True, is_active=True))
        db.commit()
    print(f"Development demo admin created for {email}.")


if __name__ == "__main__":
    seed_demo_admin()