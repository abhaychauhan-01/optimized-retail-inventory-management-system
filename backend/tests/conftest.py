from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.database import Base, get_db
from backend.app.main import app
from backend.app.models import Product, Supplier, User
from backend.app.services.auth import hash_password


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestingSession() as db:
        db.add(Supplier(supplier_id="SUP-T", lead_days=4))
        db.add(Product(product_id="SKU-T", category="Test", stock_qty=8, reorder_level=8, daily_sales=2, supplier_id="SUP-T", lead_days=3))
        db.add(User(email="tester@example.test", password_hash=hash_password("correct-test-password"), is_admin=True))
        db.commit()
    with TestClient(app) as test_client:
        response = test_client.post("/api/v1/auth/login", json={"email": "tester@example.test", "password": "correct-test-password"})
        assert response.status_code == 200
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()