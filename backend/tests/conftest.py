"""Pytest fixtures: isolated SQLite per test, seed-lite data (2 orgs).

Run: cd backend && python -m pytest tests/ -q

Each test gets a fresh file-backed SQLite database (tmp_path) with:
- org A ("acme") and org B ("globex")
- org A users: admin, dispatcher, broker, driver, shipper, finance, ops_manager
- org B user: admin
- customers, carriers, drivers, vehicles, loads, an invoice, a rate, flags

The FastAPI dependency get_db is overridden per test so all HTTP goes to
the isolated database.
"""

import os
import sys
from datetime import date, datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/tms_test_boot.db")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-prod")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import models  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.security import hash_password  # noqa: E402

PASSWORD = "Demo1234!"
# Hash once at import: bcrypt is slow and the stored hash verifies for all users.
PASSWORD_HASH = hash_password(PASSWORD)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Fixed fixture ids (deterministic across tests).
ORG_A = "org-a-fixture"
ORG_B = "org-b-fixture"
CUST_A = "cust-a-fixture"
CUST_B = "cust-b-fixture"
CAR_A = "carrier-a-fixture"   # strong carrier
CAR_B = "carrier-b-fixture"   # weak carrier, expired insurance
DRV_A = "driver-a-fixture"
VEH_A = "vehicle-a-fixture"
LOAD_A1 = "load-a1-fixture"   # LD-10001 available, unassigned
LOAD_A2 = "load-a2-fixture"   # LD-10002 in_transit, late delivery
LOAD_A3 = "load-a3-fixture"   # LD-10003 delivered 2d ago, no POD/BOL
LOAD_B1 = "load-b1-fixture"   # LD-20001 org B


def _user(db, org_id, uid, email, role, **kw):
    db.add(models.User(id=uid, org_id=org_id, email=email,
                       password_hash=PASSWORD_HASH, full_name=email.split("@")[0],
                       role=role, is_active=True, **kw))


def seed_lite(db) -> None:
    now = utcnow()
    db.add(models.Organization(id=ORG_A, name="Acme Test Co",
                               slug="acme-test", plan="professional"))
    db.add(models.Organization(id=ORG_B, name="Globex Test Co",
                               slug="globex-test", plan="starter"))

    _user(db, ORG_A, "user-admin-a", "admin@acme.test", "admin")
    _user(db, ORG_A, "user-disp-a", "dispatcher@acme.test", "dispatcher")
    _user(db, ORG_A, "user-broker-a", "broker@acme.test", "broker")
    _user(db, ORG_A, "user-driver-a", "driver@acme.test", "driver",
          driver_id=DRV_A)
    _user(db, ORG_A, "user-shipper-a", "shipper@acme.test", "shipper",
          customer_id=CUST_A)
    _user(db, ORG_A, "user-finance-a", "finance@acme.test", "finance")
    _user(db, ORG_A, "user-ops-a", "ops@acme.test", "ops_manager")
    _user(db, ORG_B, "user-admin-b", "admin@globex.test", "admin")

    db.add(models.Customer(id=CUST_A, org_id=ORG_A, name="Acme Foods",
                           city="Atlanta", state="GA"))
    db.add(models.Customer(id=CUST_B, org_id=ORG_B, name="Globex Goods",
                           city="Denver", state="CO"))

    db.add(models.Carrier(
        id=CAR_A, org_id=ORG_A, legal_name="Fast Freight LLC",
        mc_number="MC-111", equipment_types=["dry_van"],
        service_areas=["GA", "TX"],
        insurance_expiry=date(2030, 1, 1), compliance_status="compliant",
        on_time_pct=95.0, acceptance_rate=90.0, performance_score=88.0,
        claims_count=0, cancellations_count=0, is_active=True))
    db.add(models.Carrier(
        id=CAR_B, org_id=ORG_A, legal_name="Slow Haul Inc",
        mc_number="MC-222", equipment_types=["dry_van"],
        service_areas=["GA"],
        insurance_expiry=date(2020, 1, 1), compliance_status="warning",
        on_time_pct=70.0, acceptance_rate=60.0, performance_score=60.0,
        claims_count=3, cancellations_count=2, is_active=True))

    db.add(models.Driver(
        id=DRV_A, org_id=ORG_A, full_name="John Driver", status="available",
        current_location={"lat": 33.749, "lng": -84.388,
                          "city": "Atlanta", "state": "GA"},
        hours_available=60.0, is_active=True))
    db.add(models.Vehicle(
        id=VEH_A, org_id=ORG_A, unit_number="T-100", vehicle_type="truck",
        availability_status="available", is_active=True))

    db.add(models.Load(
        id=LOAD_A1, org_id=ORG_A, load_number="LD-10001", customer_id=CUST_A,
        origin={"city": "Atlanta", "state": "GA", "lat": 33.749, "lng": -84.388},
        destination={"city": "Dallas", "state": "TX",
                     "lat": 32.7767, "lng": -96.797},
        pickup_datetime=now + timedelta(days=1),
        delivery_datetime=now + timedelta(days=3),
        equipment_type="dry_van", customer_rate=2000.0, carrier_rate=1700.0,
        distance_miles=800.0, status="available"))
    db.add(models.Load(
        id=LOAD_A2, org_id=ORG_A, load_number="LD-10002", customer_id=CUST_A,
        origin={"city": "Chicago", "state": "IL",
                "lat": 41.878, "lng": -87.629},
        destination={"city": "Atlanta", "state": "GA",
                     "lat": 33.749, "lng": -84.388},
        pickup_datetime=now - timedelta(days=3),
        delivery_datetime=now - timedelta(days=1),
        equipment_type="dry_van", customer_rate=3000.0, carrier_rate=2600.0,
        distance_miles=720.0, status="in_transit", driver_id=DRV_A))
    db.add(models.Load(
        id=LOAD_A3, org_id=ORG_A, load_number="LD-10003", customer_id=CUST_A,
        origin={"city": "Atlanta", "state": "GA"},
        destination={"city": "Charlotte", "state": "NC"},
        pickup_datetime=now - timedelta(days=4),
        delivery_datetime=now - timedelta(days=2),
        equipment_type="dry_van", customer_rate=1000.0, carrier_rate=950.0,
        distance_miles=250.0, status="delivered",
        updated_at=now - timedelta(days=2)))
    db.add(models.Load(
        id=LOAD_B1, org_id=ORG_B, load_number="LD-20001", customer_id=CUST_B,
        origin={"city": "Denver", "state": "CO"},
        destination={"city": "Phoenix", "state": "AZ"},
        equipment_type="dry_van", customer_rate=1500.0, carrier_rate=1200.0,
        status="available"))

    db.add(models.Invoice(
        id="inv-a1-fixture", org_id=ORG_A, invoice_number="INV-90001",
        customer_id=CUST_A, load_id=LOAD_A1,
        issue_date=date.today() - timedelta(days=10),
        due_date=date.today() - timedelta(days=1),
        line_items=[{"description": "Freight", "amount": 2000.0},
                    {"description": "Freight", "amount": 2000.0}],
        subtotal=4000.0, tax=0.0, total=4000.0, amount_paid=0.0,
        status="issued"))

    db.add(models.Rate(
        id="rate-a1-fixture", org_id=ORG_A,
        origin_city="Atlanta", origin_state="GA",
        dest_city="Dallas", dest_state="TX", equipment_type="dry_van",
        customer_rate=2100.0, carrier_rate=1750.0, rate_type="spot",
        is_active=True))

    db.add(models.FeatureFlag(
        id="flag-budget-a", org_id=ORG_A, key="ai_monthly_budget_usd",
        enabled=True, config={"value": 500}))


@pytest.fixture()
def session_factory(tmp_path):
    path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{path}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False,
                           future=True, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture()
def db(session_factory):
    """Direct DB session with seed data (for assertions / direct writes)."""
    session = session_factory()
    seed_lite(session)
    session.commit()
    yield session
    session.close()


@pytest.fixture()
def client(session_factory, db):
    """TestClient wired to the isolated database."""
    def _override():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def login(client: TestClient, email: str, password: str = PASSWORD) -> dict:
    resp = client.post("/api/v1/auth/login",
                       json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
