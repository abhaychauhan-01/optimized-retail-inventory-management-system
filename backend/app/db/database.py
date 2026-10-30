from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "inventory.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DATABASE.as_posix()}")
if DATABASE_URL.startswith("sqlite:///") and not DATABASE_URL.startswith("sqlite:////"):
    relative = DATABASE_URL.removeprefix("sqlite:///")
    if relative and relative != ":memory:":
        candidate = Path(relative)
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        candidate.parent.mkdir(parents=True, exist_ok=True)
        DATABASE_URL = f"sqlite:///{candidate.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()