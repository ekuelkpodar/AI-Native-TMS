"""Pydantic v2 request/response schemas. Enums validated via Literal."""

from datetime import date, datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


T = TypeVar("T")


class Page(BaseSchema, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------

Plan = Literal["starter", "professional", "enterprise"]

Role = Literal[
    "admin", "broker", "dispatcher", "carrier",
    "driver", "shipper", "finance", "ops_manager",
]

ExceptionType = Literal[
    "late_pickup", "late_delivery", "route_deviation", "excessive_idle",
    "driver_unavailable", "carrier_cancellation", "missed_appointment",
    "vehicle_issue", "capacity_shortage", "document_missing", "pod_missing",
    "rate_anomaly", "margin_anomaly",
]

ThreadType = Literal["load", "customer", "carrier", "driver"]


class OrganizationBase(BaseSchema):
    name: str | None = None
    slug: str | None = None
    plan: Plan | None = None
    settings: dict | None = None
    is_active: bool | None = None


class OrganizationCreate(OrganizationBase):
    name: str
    slug: str


class OrganizationUpdate(OrganizationBase):
    pass


class OrganizationOut(OrganizationBase):
    id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class UserBase(BaseSchema):
    email: str | None = None
    full_name: str | None = None
    role: Role | None = None
    carrier_id: str | None = None
    driver_id: str | None = None
    customer_id: str | None = None
    is_active: bool | None = None


class UserCreate(UserBase):
    email: str
    password: str
    full_name: str = ""
    role: Role = "dispatcher"


class UserUpdate(BaseSchema):
    email: str | None = None
    password: str | None = None
    full_name: str | None = None
    role: Role | None = None
    carrier_id: str | None = None
    driver_id: str | None = None
    customer_id: str | None = None
    is_active: bool | None = None


class UserOut(UserBase):
    id: str
    org_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MeResponse(BaseSchema):
    user: UserOut
    organization: OrganizationOut


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


class RoleBase(BaseSchema):
    name: str | None = None
    description: str | None = None
    permissions: list[str] | None = None
    is_active: bool | None = None


class RoleCreate(RoleBase):
    name: str


class RoleUpdate(RoleBase):
    pass


class RoleOut(RoleBase):
    id: str
    org_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------


class CustomerBase(BaseSchema):
    name: str | None = None
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str | None = None
    credit_limit: float | None = None
    payment_terms: str | None = None
    is_active: bool | None = None
    notes: str | None = None


class CustomerCreate(CustomerBase):
    name: str


class CustomerUpdate(CustomerBase):
    pass


class CustomerOut(CustomerBase):
    id: str
    org_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Carriers
# ---------------------------------------------------------------------------

ComplianceStatus = Literal["compliant", "warning", "expired"]


class CarrierBase(BaseSchema):
    legal_name: str | None = None
    dba: str | None = None
    mc_number: str | None = None
    dot_number: str | None = None
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    phone: str | None = None
    email: str | None = None
    equipment_types: list[str] | None = None
    service_areas: list[str] | None = None
    lanes: list | None = None
    insurance_expiry: date | None = None
    authority_status: str | None = None
    compliance_status: ComplianceStatus | None = None
    safety_rating: str | None = None
    performance_score: float | None = None
    on_time_pct: float | None = None
    acceptance_rate: float | None = None
    claims_count: int | None = None
    cancellations_count: int | None = None
    total_revenue: float | None = None
    notes: str | None = None
    is_active: bool | None = None


class CarrierCreate(CarrierBase):
    legal_name: str


class CarrierUpdate(CarrierBase):
    pass


class CarrierOut(CarrierBase):
    id: str
    org_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CarrierScoreFactor(BaseSchema):
    name: str
    weight: float
    value: float
    contribution: float


class CarrierScoreResponse(BaseSchema):
    carrier_id: str
    score: float
    factors: list[CarrierScoreFactor]
    explanation: str


# ---------------------------------------------------------------------------
# Drivers
# ---------------------------------------------------------------------------

DriverStatus = Literal[
    "available", "assigned", "en_route", "at_pickup", "loading",
    "in_transit", "at_delivery", "off_duty", "unavailable",
]


class DriverBase(BaseSchema):
    carrier_id: str | None = None
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    license_number: str | None = None
    license_expiry: date | None = None
    status: DriverStatus | None = None
    current_location: dict | None = None
    hours_available: float | None = None
    performance_score: float | None = None
    is_active: bool | None = None


class DriverCreate(DriverBase):
    full_name: str


class DriverUpdate(DriverBase):
    pass


class DriverOut(DriverBase):
    id: str
    org_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Vehicles
# ---------------------------------------------------------------------------

VehicleType = Literal["truck", "trailer", "van", "other"]
VehicleAvailability = Literal["available", "assigned", "maintenance", "out_of_service"]


class VehicleBase(BaseSchema):
    vin: str | None = None
    unit_number: str | None = None
    license_plate: str | None = None
    make: str | None = None
    model: str | None = None
    year: int | None = None
    vehicle_type: VehicleType | None = None
    capacity_lbs: float | None = None
    mileage: float | None = None
    current_location: dict | None = None
    availability_status: VehicleAvailability | None = None
    driver_id: str | None = None
    maintenance_status: str | None = None
    insurance_expiry: date | None = None
    is_active: bool | None = None


class VehicleCreate(VehicleBase):
    unit_number: str


class VehicleUpdate(VehicleBase):
    pass


class VehicleOut(VehicleBase):
    id: str
    org_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Shipments
# ---------------------------------------------------------------------------

ShipmentStatus = Literal["draft", "booked", "in_progress", "delivered", "cancelled"]


class ShipmentBase(BaseSchema):
    customer_id: str | None = None
    reference_number: str | None = None
    status: ShipmentStatus | None = None
    pickup_appointment: datetime | None = None
    delivery_appointment: datetime | None = None
    special_instructions: str | None = None


class ShipmentCreate(ShipmentBase):
    customer_id: str


class ShipmentUpdate(ShipmentBase):
    pass


class ShipmentOut(ShipmentBase):
    id: str
    org_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ShipmentStatusUpdate(BaseModel):
    status: ShipmentStatus


# ---------------------------------------------------------------------------
# Loads
# ---------------------------------------------------------------------------

LoadStatus = Literal[
    "draft", "quoted", "tendered", "available", "assigned", "confirmed",
    "dispatched", "at_pickup", "picked_up", "in_transit", "at_delivery",
    "delivered", "pod_received", "invoiced", "paid", "cancelled",
]
EquipmentType = Literal[
    "dry_van", "reefer", "flatbed", "step_deck", "tanker", "box_truck", "other"
]


class LoadBase(BaseSchema):
    reference_number: str | None = None
    customer_id: str | None = None
    carrier_id: str | None = None
    driver_id: str | None = None
    vehicle_id: str | None = None
    origin: dict | None = None
    destination: dict | None = None
    pickup_datetime: datetime | None = None
    delivery_datetime: datetime | None = None
    equipment_type: EquipmentType | None = None
    commodity: str | None = None
    weight_lbs: float | None = None
    length_ft: float | None = None
    width_ft: float | None = None
    height_ft: float | None = None
    pallets: int | None = None
    pieces: int | None = None
    customer_rate: float | None = None
    carrier_rate: float | None = None
    distance_miles: float | None = None
    hazmat: bool | None = None
    temp_min: float | None = None
    temp_max: float | None = None
    status: LoadStatus | None = None
    notes: str | None = None
    is_archived: bool | None = None


class LoadCreate(LoadBase):
    customer_id: str


class LoadUpdate(LoadBase):
    pass


class LoadOut(LoadBase):
    id: str
    org_id: str
    load_number: str
    margin: float | None = None
    margin_pct: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LoadStatusUpdate(BaseModel):
    status: LoadStatus


class LoadAssignRequest(BaseModel):
    carrier_id: str | None = None
    driver_id: str | None = None
    vehicle_id: str | None = None


# ---------------------------------------------------------------------------
# Stops
# ---------------------------------------------------------------------------

StopType = Literal["pickup", "delivery"]
StopStatus = Literal["pending", "arrived", "completed", "missed"]


class StopBase(BaseSchema):
    sequence: int | None = None
    stop_type: StopType | None = None
    location: dict | None = None
    appointment_start: datetime | None = None
    appointment_end: datetime | None = None
    status: StopStatus | None = None
    notes: str | None = None


class StopCreate(StopBase):
    pass


class StopUpdate(StopBase):
    pass


class StopOut(StopBase):
    id: str
    load_id: str


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------


class AssignmentOut(BaseSchema):
    id: str
    org_id: str
    load_id: str
    driver_id: str
    vehicle_id: str | None = None
    assigned_at: datetime | None = None
    status: str | None = None
    assigned_by: str | None = None


# ---------------------------------------------------------------------------
# Rates
# ---------------------------------------------------------------------------

RateType = Literal["spot", "contract"]


class RateBase(BaseSchema):
    origin_city: str | None = None
    origin_state: str | None = None
    dest_city: str | None = None
    dest_state: str | None = None
    equipment_type: str | None = None
    customer_rate: float | None = None
    carrier_rate: float | None = None
    rate_type: RateType | None = None
    fuel_surcharge: float | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None


class RateCreate(RateBase):
    customer_rate: float = 0.0
    carrier_rate: float = 0.0


class RateUpdate(RateBase):
    pass


class RateOut(RateBase):
    id: str
    org_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RateQuoteRequest(BaseModel):
    origin: dict
    destination: dict
    equipment_type: str = "dry_van"
    weight_lbs: float | None = None
    distance_miles: float | None = None


class RateQuoteResponse(BaseSchema):
    customer_rate: float
    carrier_rate: float
    margin: float
    margin_pct: float
    basis: str  # rate_card|estimated


# ---------------------------------------------------------------------------
# Invoices & payments
# ---------------------------------------------------------------------------

InvoiceStatus = Literal["draft", "issued", "paid", "overdue", "void"]


class InvoiceBase(BaseSchema):
    customer_id: str | None = None
    load_id: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    line_items: list | None = None
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None
    amount_paid: float | None = None
    status: InvoiceStatus | None = None
    notes: str | None = None


class InvoiceCreate(InvoiceBase):
    customer_id: str


class InvoiceUpdate(InvoiceBase):
    pass


class InvoiceOut(InvoiceBase):
    id: str
    org_id: str
    invoice_number: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InvoicePayRequest(BaseModel):
    amount: float = Field(gt=0)
    method: str | None = None
    reference: str | None = None


class PaymentOut(BaseSchema):
    id: str
    org_id: str
    invoice_id: str
    amount: float
    method: str | None = None
    reference: str | None = None
    paid_at: datetime | None = None


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

DocType = Literal[
    "bol", "pod", "rate_confirmation", "invoice", "carrier_agreement",
    "insurance", "compliance", "other",
]


class DocumentOut(BaseSchema):
    id: str
    org_id: str
    entity_type: str
    entity_id: str
    doc_type: str
    filename: str
    content_type: str | None = None
    size_bytes: int
    storage_path: str | None = None
    doc_metadata: dict | None = None
    version: int
    uploaded_by: str | None = None
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# Communications
# ---------------------------------------------------------------------------


class CommunicationBase(BaseSchema):
    thread_type: ThreadType | None = None
    thread_id: str | None = None
    channel: Literal["email", "sms", "in_app"] | None = None
    direction: Literal["in", "out"] | None = None
    sender: str | None = None
    recipient: str | None = None
    subject: str | None = None
    body: str | None = None


class CommunicationCreate(CommunicationBase):
    body: str = ""


class CommunicationUpdate(CommunicationBase):
    pass


class CommunicationOut(CommunicationBase):
    id: str
    org_id: str
    created_by: str | None = None
    sent_at: datetime | None = None
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class NotificationOut(BaseSchema):
    id: str
    org_id: str
    user_id: str | None = None
    type: str
    title: str
    body: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    is_read: bool
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

ExceptionSeverity = Literal["low", "medium", "high", "critical"]
ExceptionStatus = Literal["open", "acknowledged", "resolved"]


class ExceptionBase(BaseSchema):
    load_id: str | None = None
    exception_type: ExceptionType | None = None
    severity: ExceptionSeverity | None = None
    title: str | None = None
    description: str | None = None
    recommended_action: str | None = None
    owner_user_id: str | None = None
    status: ExceptionStatus | None = None
    resolution: str | None = None
    history: list | None = None


class ExceptionCreate(ExceptionBase):
    exception_type: ExceptionType
    title: str


class ExceptionUpdate(ExceptionBase):
    pass


class ExceptionOut(ExceptionBase):
    id: str
    org_id: str
    detected_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ExceptionResolveRequest(BaseModel):
    resolution: str


class ExceptionAssignRequest(BaseModel):
    user_id: str


# ---------------------------------------------------------------------------
# Tracking
# ---------------------------------------------------------------------------


class TrackingEventOut(BaseSchema):
    id: str
    org_id: str
    load_id: str
    event_type: str | None = None
    lat: float | None = None
    lng: float | None = None
    city: str | None = None
    speed_mph: float | None = None
    recorded_at: datetime | None = None
    meta: dict | None = None


class LivePosition(BaseSchema):
    load_id: str
    load_number: str
    status: str
    lat: float | None = None
    lng: float | None = None
    city: str | None = None
    state: str | None = None
    speed_mph: float | None = None
    recorded_at: datetime | None = None
    driver_id: str | None = None
    simulated: bool = False


class LoadTrackingDetail(BaseSchema):
    load: LoadOut
    route: dict | None = None
    events: list[TrackingEventOut] = []
    eta: datetime | None = None


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


class AuditLogOut(BaseSchema):
    id: str
    org_id: str
    actor_type: str
    actor_id: str | None = None
    actor_name: str
    action: str
    entity_type: str
    entity_id: str | None = None
    before: dict | None = None
    after: dict | None = None
    ip_address: str | None = None
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


class DispatchConflict(BaseSchema):
    type: str
    message: str
    load_id: str | None = None
    driver_id: str | None = None
    vehicle_id: str | None = None


class DispatchBoard(BaseSchema):
    unassigned_loads: list[LoadOut]
    available_drivers: list[DriverOut]
    available_vehicles: list[VehicleOut]
    conflicts: list[DispatchConflict]


class DispatchAssignRequest(BaseModel):
    load_id: str
    driver_id: str
    vehicle_id: str | None = None


class DispatchAssignResponse(BaseSchema):
    load: LoadOut
    warnings: list[str]


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class AnalyticsOverview(BaseSchema):
    total_loads: int
    active_loads: int
    in_transit_loads: int
    delivered_loads: int
    total_revenue: float
    total_cost: float
    margin: float
    margin_pct: float
    avg_margin_per_load: float
    on_time_pct: float | None
    open_exceptions: int
    critical_exceptions: int
    outstanding_invoices: float
    overdue_invoices: float
    loads_by_status: dict[str, int]


# ---------------------------------------------------------------------------
# Lanes
# ---------------------------------------------------------------------------


class LaneSummary(BaseSchema):
    id: str
    origin: dict
    destination: dict
    load_count: int
    total_revenue: float
    avg_customer_rate: float | None
    avg_carrier_rate: float | None
    avg_margin: float | None
    equipment_types: list[str]
    last_load_date: datetime | None = None


class LaneDetail(LaneSummary):
    recent_loads: list[LoadOut] = []


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


class PolicyBase(BaseSchema):
    name: str | None = None
    description: str | None = None
    rule: dict | None = None
    priority: int | None = None
    is_active: bool | None = None


class PolicyCreate(PolicyBase):
    name: str
    rule: dict = {}


class PolicyUpdate(PolicyBase):
    pass


class PolicyOut(PolicyBase):
    id: str
    org_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# AI agents registry (table CRUD only — AI control plane is a separate track)
# ---------------------------------------------------------------------------

AgentStatus = Literal["active", "paused", "disabled"]
RiskLevel = Literal["low", "medium", "high"]


class AIAgentBase(BaseSchema):
    name: str | None = None
    version: str | None = None
    model: str | None = None
    tools: list | None = None
    permissions: list | None = None
    status: AgentStatus | None = None
    owner: str | None = None
    risk_level: RiskLevel | None = None
    autonomy_level: int | None = None
    config: dict | None = None


class AIAgentCreate(AIAgentBase):
    name: str


class AIAgentUpdate(AIAgentBase):
    pass


class AIAgentOut(AIAgentBase):
    id: str
    org_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------

ApprovalStatus = Literal["pending", "approved", "rejected", "expired"]


class ApprovalOut(BaseSchema):
    id: str
    org_id: str
    agent_name: str
    action_type: str
    entity_type: str | None = None
    entity_id: str | None = None
    payload: dict
    reason: str | None = None
    risk_level: str | None = None
    required_role: str
    status: ApprovalStatus
    requested_by: str | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    created_at: datetime | None = None


class ApprovalRejectRequest(BaseModel):
    reason: str | None = None


class ApprovalDecisionResponse(BaseSchema):
    approval: ApprovalOut
    executed: bool
    execution_result: dict | None = None
    execution_error: str | None = None


# ---------------------------------------------------------------------------
# Automation rules
# ---------------------------------------------------------------------------


class AutomationRuleBase(BaseSchema):
    name: str | None = None
    event_name: str | None = None
    conditions: dict | None = None
    actions: list | None = None
    is_active: bool | None = None


class AutomationRuleCreate(AutomationRuleBase):
    name: str
    event_name: str


class AutomationRuleUpdate(AutomationRuleBase):
    pass


class AutomationRuleOut(AutomationRuleBase):
    id: str
    org_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------


class FeatureFlagUpsert(BaseModel):
    key: str
    enabled: bool = True
    config: dict | None = None


class FeatureFlagOut(BaseSchema):
    id: str
    org_id: str
    key: str
    enabled: bool
    config: dict | None = None


# ---------------------------------------------------------------------------
# Integrations
# ---------------------------------------------------------------------------

IntegrationStatus = Literal["mock", "connected", "disabled"]


class IntegrationBase(BaseSchema):
    provider: str | None = None
    status: IntegrationStatus | None = None
    config: dict | None = None


class IntegrationCreate(IntegrationBase):
    provider: str


class IntegrationUpdate(IntegrationBase):
    pass


class IntegrationOut(IntegrationBase):
    id: str
    org_id: str
    last_sync: datetime | None = None


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class SettingsUpdate(BaseModel):
    settings: dict


class SettingsResponse(BaseModel):
    settings: dict
