"""All SQLAlchemy 2.0 typed models. Tables only — no business/AI logic lives here.

Conventions (per ARCHITECTURE.md section 3):
- id = String UUID (uuid4 hex)
- every tenant entity carries org_id
- created_at/updated_at = UTC datetimes
- enums stored as plain strings, validated in Pydantic schemas
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )


class TenantMixin:
    org_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id"), index=True
    )


# ---------------------------------------------------------------------------
# 3.1 Tenancy & identity
# ---------------------------------------------------------------------------


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)
    plan: Mapped[str] = mapped_column(String, default="starter")  # starter|professional|enterprise
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base, TenantMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("org_id", "email", name="uq_users_org_email"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    full_name: Mapped[str] = mapped_column(String, default="")
    role: Mapped[str] = mapped_column(String, default="dispatcher", index=True)
    carrier_id: Mapped[str | None] = mapped_column(String, nullable=True)
    driver_id: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Role(Base, TenantMixin, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------------------
# 3.3 Core entities
# ---------------------------------------------------------------------------


class Customer(Base, TenantMixin, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, index=True)
    contact_name: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    street: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    zip: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str] = mapped_column(String, default="USA")
    credit_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String, nullable=True, default="Net 30")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Carrier(Base, TenantMixin, TimestampMixin):
    __tablename__ = "carriers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    legal_name: Mapped[str] = mapped_column(String, index=True)
    dba: Mapped[str | None] = mapped_column(String, nullable=True)
    mc_number: Mapped[str | None] = mapped_column(String, nullable=True)
    dot_number: Mapped[str | None] = mapped_column(String, nullable=True)
    street: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    zip: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    equipment_types: Mapped[list] = mapped_column(JSON, default=list)
    service_areas: Mapped[list] = mapped_column(JSON, default=list)
    lanes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    insurance_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    authority_status: Mapped[str | None] = mapped_column(String, nullable=True)
    compliance_status: Mapped[str] = mapped_column(String, default="compliant")  # compliant|warning|expired
    safety_rating: Mapped[str | None] = mapped_column(String, nullable=True)
    performance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    on_time_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    acceptance_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    claims_count: Mapped[int] = mapped_column(Integer, default=0)
    cancellations_count: Mapped[int] = mapped_column(Integer, default=0)
    total_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Driver(Base, TenantMixin, TimestampMixin):
    __tablename__ = "drivers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    carrier_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String, index=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    license_number: Mapped[str | None] = mapped_column(String, nullable=True)
    license_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, default="available", index=True)
    current_location: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    hours_available: Mapped[float | None] = mapped_column(Float, nullable=True)
    performance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Vehicle(Base, TenantMixin, TimestampMixin):
    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint("org_id", "unit_number", name="uq_vehicles_org_unit"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    vin: Mapped[str | None] = mapped_column(String, nullable=True)
    unit_number: Mapped[str] = mapped_column(String, index=True)
    license_plate: Mapped[str | None] = mapped_column(String, nullable=True)
    make: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vehicle_type: Mapped[str] = mapped_column(String, default="truck")  # truck|trailer|van|other
    capacity_lbs: Mapped[float | None] = mapped_column(Float, nullable=True)
    mileage: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_location: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    availability_status: Mapped[str] = mapped_column(String, default="available", index=True)
    driver_id: Mapped[str | None] = mapped_column(String, nullable=True)
    maintenance_status: Mapped[str | None] = mapped_column(String, nullable=True)
    insurance_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Shipment(Base, TenantMixin, TimestampMixin):
    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    reference_number: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft", index=True)  # draft|booked|in_progress|delivered|cancelled
    pickup_appointment: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivery_appointment: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    special_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)


class Load(Base, TenantMixin, TimestampMixin):
    __tablename__ = "loads"
    __table_args__ = (
        UniqueConstraint("org_id", "load_number", name="uq_loads_org_number"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    load_number: Mapped[str] = mapped_column(String, index=True)
    reference_number: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    carrier_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    driver_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    vehicle_id: Mapped[str | None] = mapped_column(String, nullable=True)
    origin: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {city,state,zip,lat,lng}
    destination: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pickup_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivery_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    equipment_type: Mapped[str] = mapped_column(String, default="dry_van")
    commodity: Mapped[str | None] = mapped_column(String, nullable=True)
    weight_lbs: Mapped[float | None] = mapped_column(Float, nullable=True)
    length_ft: Mapped[float | None] = mapped_column(Float, nullable=True)
    width_ft: Mapped[float | None] = mapped_column(Float, nullable=True)
    height_ft: Mapped[float | None] = mapped_column(Float, nullable=True)
    pallets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pieces: Mapped[int | None] = mapped_column(Integer, nullable=True)
    customer_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    carrier_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_miles: Mapped[float | None] = mapped_column(Float, nullable=True)
    hazmat: Mapped[bool] = mapped_column(Boolean, default=False)
    temp_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    temp_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    @property
    def margin(self) -> float | None:
        if self.customer_rate is None or self.carrier_rate is None:
            return None
        return self.customer_rate - self.carrier_rate

    @property
    def margin_pct(self) -> float | None:
        if self.customer_rate in (None, 0) or self.carrier_rate is None:
            return None
        return (self.customer_rate - self.carrier_rate) / self.customer_rate * 100


class Stop(Base):
    __tablename__ = "stops"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    load_id: Mapped[str] = mapped_column(String, ForeignKey("loads.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    stop_type: Mapped[str] = mapped_column(String, default="pickup")  # pickup|delivery
    location: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    appointment_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    appointment_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|arrived|completed|missed
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    load_id: Mapped[str] = mapped_column(String, ForeignKey("loads.id"), index=True)
    waypoints: Mapped[list] = mapped_column(JSON, default=list)
    total_miles: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    optimized: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Assignment(Base, TenantMixin):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    load_id: Mapped[str] = mapped_column(String, index=True)
    driver_id: Mapped[str] = mapped_column(String, index=True)
    vehicle_id: Mapped[str | None] = mapped_column(String, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    status: Mapped[str] = mapped_column(String, default="active")  # active|completed|cancelled
    assigned_by: Mapped[str | None] = mapped_column(String, nullable=True)


class Rate(Base, TenantMixin, TimestampMixin):
    __tablename__ = "rates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    origin_city: Mapped[str | None] = mapped_column(String, nullable=True)
    origin_state: Mapped[str | None] = mapped_column(String, nullable=True)
    dest_city: Mapped[str | None] = mapped_column(String, nullable=True)
    dest_state: Mapped[str | None] = mapped_column(String, nullable=True)
    equipment_type: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_rate: Mapped[float] = mapped_column(Float, default=0.0)
    carrier_rate: Mapped[float] = mapped_column(Float, default=0.0)
    rate_type: Mapped[str] = mapped_column(String, default="spot")  # spot|contract
    fuel_surcharge: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Invoice(Base, TenantMixin, TimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("org_id", "invoice_number", name="uq_invoices_org_number"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    invoice_number: Mapped[str] = mapped_column(String, index=True)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    load_id: Mapped[str | None] = mapped_column(String, nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    line_items: Mapped[list] = mapped_column(JSON, default=list)
    subtotal: Mapped[float] = mapped_column(Float, default=0.0)
    tax: Mapped[float] = mapped_column(Float, default=0.0)
    total: Mapped[float] = mapped_column(Float, default=0.0)
    amount_paid: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="draft", index=True)  # draft|issued|paid|overdue|void
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Payment(Base, TenantMixin):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    invoice_id: Mapped[str] = mapped_column(String, index=True)
    amount: Mapped[float] = mapped_column(Float)
    method: Mapped[str | None] = mapped_column(String, nullable=True)
    reference: Mapped[str | None] = mapped_column(String, nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Document(Base, TenantMixin):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    entity_type: Mapped[str] = mapped_column(String, index=True)
    entity_id: Mapped[str] = mapped_column(String, index=True)
    doc_type: Mapped[str] = mapped_column(String, default="other", index=True)
    filename: Mapped[str] = mapped_column(String)
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    storage_path: Mapped[str] = mapped_column(String)
    doc_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    uploaded_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Communication(Base, TenantMixin):
    __tablename__ = "communications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    thread_type: Mapped[str] = mapped_column(String, default="load", index=True)  # load|customer|carrier|driver
    thread_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String, default="in_app")  # email|sms|in_app
    direction: Mapped[str] = mapped_column(String, default="out")  # in|out
    sender: Mapped[str | None] = mapped_column(String, nullable=True)
    recipient: Mapped[str | None] = mapped_column(String, nullable=True)
    subject: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Notification(Base, TenantMixin):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    type: Mapped[str] = mapped_column(String, default="info", index=True)
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Exception(Base, TenantMixin, TimestampMixin):
    __tablename__ = "exceptions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    load_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    exception_type: Mapped[str] = mapped_column(String, index=True)
    severity: Mapped[str] = mapped_column(String, default="medium", index=True)  # low|medium|high|critical
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open", index=True)  # open|acknowledged|resolved
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    history: Mapped[list] = mapped_column(JSON, default=list)


class TrackingEvent(Base, TenantMixin):
    __tablename__ = "tracking_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    load_id: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str | None] = mapped_column(String, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    speed_mph: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class AuditLog(Base, TenantMixin):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    actor_type: Mapped[str] = mapped_column(String, default="user", index=True)  # user|agent|system
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    actor_name: Mapped[str] = mapped_column(String, default="")
    action: Mapped[str] = mapped_column(String, index=True)
    entity_type: Mapped[str] = mapped_column(String, index=True)
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


# ---------------------------------------------------------------------------
# 3.4 AI / governance entities (tables only — the AI control plane lives in
# backend/app/ai/, owned by a separate track)
# ---------------------------------------------------------------------------


class AIAgent(Base, TenantMixin, TimestampMixin):
    __tablename__ = "ai_agents"
    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_ai_agents_org_name"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[str | None] = mapped_column(String, nullable=True, default="1.0")
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    tools: Mapped[list] = mapped_column(JSON, default=list)
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="active")  # active|paused|disabled
    owner: Mapped[str | None] = mapped_column(String, nullable=True)
    risk_level: Mapped[str] = mapped_column(String, default="low")  # low|medium|high
    autonomy_level: Mapped[int] = mapped_column(Integer, default=1)  # 0-4
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class AITask(Base, TenantMixin, TimestampMixin):
    __tablename__ = "ai_tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    agent_name: Mapped[str] = mapped_column(String, index=True)
    task_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="queued")  # queued|running|completed|failed
    input: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class AIAction(Base, TenantMixin):
    __tablename__ = "ai_actions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    agent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    agent_name: Mapped[str] = mapped_column(String, index=True)
    action_type: Mapped[str] = mapped_column(String)
    entity_type: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    input: Mapped[dict] = mapped_column(JSON, default=dict)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    policy_id: Mapped[str | None] = mapped_column(String, nullable=True)
    decision: Mapped[str] = mapped_column(String, default="auto")  # auto|approved|rejected|denied
    approval_id: Mapped[str | None] = mapped_column(String, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Approval(Base, TenantMixin):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    agent_name: Mapped[str] = mapped_column(String)
    action_type: Mapped[str] = mapped_column(String)
    entity_type: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String, nullable=True, default="medium")
    required_role: Mapped[str] = mapped_column(String, default="dispatcher")
    status: Mapped[str] = mapped_column(String, default="pending", index=True)  # pending|approved|rejected|expired
    requested_by: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Policy(Base, TenantMixin, TimestampMixin):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule: Mapped[dict] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AutomationRule(Base, TenantMixin, TimestampMixin):
    __tablename__ = "automation_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String)
    event_name: Mapped[str] = mapped_column(String, index=True)
    conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    actions: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class EventsLog(Base, TenantMixin):
    __tablename__ = "events_log"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    event_name: Mapped[str] = mapped_column(String, index=True)
    entity_type: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class FeatureFlag(Base, TenantMixin):
    __tablename__ = "feature_flags"
    __table_args__ = (
        UniqueConstraint("org_id", "key", name="uq_feature_flags_org_key"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Integration(Base, TenantMixin):
    __tablename__ = "integrations"
    __table_args__ = (
        UniqueConstraint("org_id", "provider", name="uq_integrations_org_provider"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="mock")  # mock|connected|disabled
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    last_sync: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Forecast(Base, TenantMixin):
    __tablename__ = "forecasts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    forecast_type: Mapped[str] = mapped_column(String, index=True)  # volume|capacity|cost|lane_pricing|driver_demand
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class AIUsage(Base, TenantMixin):
    __tablename__ = "ai_usage"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    agent_name: Mapped[str] = mapped_column(String, index=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    est_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    task_type: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
