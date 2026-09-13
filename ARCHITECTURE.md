# AI-Native TMS — Architecture

## 1. Overview

Monorepo for an AI-Native Transportation Management & Autonomous Dispatch Platform:
a multi-tenant SaaS TMS with a governed AI operations layer.

```
ai-native-tms/
  ARCHITECTURE.md          # this file — source of truth
  README.md                # run instructions, demo creds, limitations
  docker-compose.yml       # prod layout (UNVERIFIED — docker not on build VM)
  .env.example
  backend/                 # FastAPI + SQLAlchemy 2.0 + Pydantic v2
    requirements.txt
    app/
      __init__.py
      main.py              # create_app() factory + uvicorn entry
      config.py            # env config (DATABASE_URL, JWT_SECRET, CORS)
      database.py          # engine, SessionLocal, Base, get_db
      models.py            # ALL SQLAlchemy models (section 3)
      schemas.py           # Pydantic v2 request/response schemas
      security.py          # bcrypt hashing, JWT create/verify
      deps.py              # get_current_user, require_roles, org scoping
      events.py            # in-process event bus + events_log writes
      automation.py        # WHEN/IF/THEN rules engine
      notifications.py     # notification service
      audit.py             # audit log helper
      routers/             # one module per domain (section 5)
      ai/                  # AI control plane (section 6)
    seed.py                # demo data (section 8)
    tests/                 # pytest suite (section 9)
  frontend/                # Vite + React + TS + react-router (section 7)
```

## 2. Stack (locked)

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (typed `Mapped` models),
  Pydantic v2, `python-jose[cryptography]` JWT, `passlib[bcrypt]`,
  `python-multipart`, `uvicorn[standard]`.
- **DB:** SQLite by default (`DATABASE_URL=sqlite:///./tms.db`). Same SQLAlchemy
  models work on Postgres — switch via env, document in README. `Base.metadata.create_all`
  on startup (no Alembic for the demo; noted in README).
- **Frontend:** Vite 6 + React 18 + TypeScript 5 + react-router-dom 6.
  Plain CSS only (no UI kit). A tiny hand-written SVG chart helper.
- **Tests:** pytest + httpx TestClient.
- **Infra (unverified):** docker-compose with api / web(nginx) / postgres:16 / redis:7.

**Rules:** env vars for config, never hard-code secrets; no dead code;
no fake functionality — external integrations are adapter interfaces with
mock providers, clearly labeled.

## 3. Data model

Conventions: `id` = String UUID (`uuid4().hex`); `org_id` = String FK on every
tenant entity; `created_at`/`updated_at` = DateTime UTC defaults; soft delete
via `is_active`/`is_archived` booleans where listed. Enums stored as plain
strings; validated in Pydantic schemas with `Literal`/Enum.

### 3.1 Tenancy & identity

- `organizations`: id, name, slug (unique), plan
  (`starter|professional|enterprise`), settings (JSON), is_active, timestamps.
- `users`: id, org_id, email, password_hash, full_name, role (see 3.2),
  carrier_id NULL, driver_id NULL, customer_id NULL (scoped roles),
  is_active, timestamps. Unique index (org_id, email).
- `roles`: id, org_id, name, description, permissions (JSON list of scope
  strings), is_active, timestamps.

### 3.2 Roles (RBAC)

`admin, broker, dispatcher, carrier, driver, shipper, finance, ops_manager`

Scope strings (examples): `loads:read/write`, `shipments:*`, `dispatch:write`,
`customers:*`, `carriers:*`, `drivers:*`, `fleet:*`, `rates:*`, `invoices:*`,
`documents:*`, `communications:*`, `exceptions:*`, `analytics:read`,
`ai:use`, `admin:*`, `policies:*`, `audit:read`.

Role → scopes (minimum; backend enforces via `deps.require_roles` and
scope checks):
- admin: all
- broker: loads, shipments, customers, carriers, rates, dispatch:write, documents, communications, exceptions:read, ai:use, invoices:read
- dispatcher: loads:read/write(assign,status), shipments, drivers, fleet, dispatch:write, tracking, exceptions:*, communications, ai:use
- carrier: loads:read (assigned only), loads:write(status accept/decline), documents:write, communications
- driver: assignments:read, loads:write(status own), documents:write (POD)
- shipper: shipments:* (own customer), loads:read (own), invoices:read (own), documents:read
- finance: invoices:*, payments, rates:read, analytics:read(financial)
- ops_manager: analytics:read, exceptions:*, policies:read, lanes:read, ai:use

Scoped roles filter to own records: driver → own driver_id; carrier → own
carrier_id; shipper → own customer_id.

### 3.3 Core entities (all carry org_id)

- `customers`: id, org_id, name, contact_name, email, phone, street, city,
  state, zip, country, credit_limit (Float), payment_terms (str),
  is_active, notes, timestamps.
- `carriers`: id, org_id, legal_name, dba, mc_number, dot_number, street,
  city, state, zip, phone, email, equipment_types (JSON list),
  service_areas (JSON list of states), lanes (JSON), insurance_expiry (Date),
  authority_status, compliance_status (`compliant|warning|expired`),
  safety_rating, performance_score (Float 0-100), on_time_pct,
  acceptance_rate, claims_count, cancellations_count, total_revenue,
  notes, is_active, timestamps.
- `drivers`: id, org_id, carrier_id NULL, full_name, phone, email,
  license_number, license_expiry (Date),
  status (`available|assigned|en_route|at_pickup|loading|in_transit|at_delivery|off_duty|unavailable`),
  current_location (JSON {lat,lng,city,state}), hours_available (Float),
  performance_score, is_active, timestamps.
- `vehicles`: id, org_id, vin, unit_number (unique per org), license_plate,
  make, model, year (int), vehicle_type (`truck|trailer|van|other`),
  capacity_lbs (Float), mileage (Float), current_location (JSON),
  availability_status (`available|assigned|maintenance|out_of_service`),
  driver_id NULL, maintenance_status, insurance_expiry (Date), is_active, timestamps.
- `shipments`: id, org_id, customer_id, reference_number,
  status (`draft|booked|in_progress|delivered|cancelled`),
  pickup_appointment (DateTime), delivery_appointment (DateTime),
  special_instructions, timestamps.
- `loads`: id, org_id, load_number (unique per org, e.g. "LD-10001"),
  reference_number, customer_id, carrier_id NULL, driver_id NULL,
  vehicle_id NULL, origin (JSON {city,state,zip,lat,lng}),
  destination (JSON), pickup_datetime, delivery_datetime,
  equipment_type (`dry_van|reefer|flatbed|step_deck|tanker|box_truck|other`),
  commodity, weight_lbs (Float), length_ft, width_ft, height_ft (Float NULL),
  pallets (int), pieces (int), customer_rate (Float), carrier_rate (Float),
  distance_miles (Float), hazmat (bool), temp_min/temp_max (Float NULL),
  status — `draft|quoted|tendered|available|assigned|confirmed|dispatched|at_pickup|picked_up|in_transit|at_delivery|delivered|pod_received|invoiced|paid|cancelled`,
  notes, is_archived (bool), timestamps.
  Computed (schema-level): `margin = customer_rate - carrier_rate`,
  `margin_pct = margin / customer_rate * 100`.
- `stops`: id, load_id, sequence (int), stop_type (`pickup|delivery`),
  location (JSON), appointment_start/end (DateTime NULL),
  status (`pending|arrived|completed|missed`), notes.
- `routes`: id, load_id, waypoints (JSON list), total_miles (Float),
  total_minutes (Float), optimized (bool), created_at.
- `assignments`: id, org_id, load_id, driver_id, vehicle_id NULL,
  assigned_at, status (`active|completed|cancelled`), assigned_by (user id).
- `rates`: id, org_id, origin_city, origin_state, dest_city, dest_state,
  equipment_type, customer_rate, carrier_rate, rate_type (`spot|contract`),
  fuel_surcharge (Float), effective_from/to (Date NULL), is_active, timestamps.
- `invoices`: id, org_id, invoice_number (unique per org), customer_id,
  load_id NULL, issue_date, due_date, line_items (JSON list),
  subtotal, tax, total, amount_paid (Float, default 0),
  status (`draft|issued|paid|overdue|void`), notes, timestamps.
- `payments`: id, org_id, invoice_id, amount, method, reference, paid_at.
- `documents`: id, org_id, entity_type, entity_id, doc_type
  (`bol|pod|rate_confirmation|invoice|carrier_agreement|insurance|compliance|other`),
  filename, content_type, size_bytes, storage_path (local `./storage/`),
  doc_metadata (JSON), version (int), uploaded_by, created_at.
- `communications`: id, org_id, thread_type (`load|customer|carrier|driver`),
  thread_id, channel (`email|sms|in_app`), direction (`in|out`),
  sender, recipient, subject NULL, body, created_by NULL, sent_at/created_at.
- `notifications`: id, org_id, user_id NULL, type
  (`delay|assignment|acceptance|pickup|delivery|exception|document|approval|ai_recommendation|info`),
  title, body, entity_type NULL, entity_id NULL, is_read (bool), created_at.
- `exceptions`: id, org_id, load_id NULL, exception_type
  (`late_pickup|late_delivery|route_deviation|excessive_idle|driver_unavailable|carrier_cancellation|missed_appointment|vehicle_issue|capacity_shortage|document_missing|pod_missing|rate_anomaly|margin_anomaly`),
  severity (`low|medium|high|critical`), title, description, detected_at,
  recommended_action NULL, owner_user_id NULL,
  status (`open|acknowledged|resolved`), resolution NULL, resolved_at NULL,
  history (JSON list), timestamps.
- `tracking_events`: id, org_id, load_id, event_type, lat, lng, city NULL,
  speed_mph (Float NULL), recorded_at, meta (JSON NULL).
- `audit_logs`: id, org_id, actor_type (`user|agent|system`),
  actor_id NULL, actor_name, action, entity_type, entity_id NULL,
  before (JSON NULL), after (JSON NULL), ip_address NULL, created_at.

### 3.4 AI / governance entities

- `ai_agents`: id, org_id, name (unique per org), version, model,
  tools (JSON list), permissions (JSON list), status (`active|paused|disabled`),
  owner, risk_level (`low|medium|high`), autonomy_level (int 0-4),
  config (JSON), timestamps.
- `ai_tasks`: id, org_id, agent_name, task_type, status
  (`queued|running|completed|failed`), input (JSON), result (JSON NULL),
  created_at, updated_at.
- `ai_actions`: id, org_id, agent_id NULL, agent_name, action_type,
  entity_type NULL, entity_id NULL, input (JSON), output (JSON NULL),
  policy_id NULL, decision (`auto|approved|rejected|denied`),
  approval_id NULL, result (JSON NULL), created_at.
- `approvals`: id, org_id, agent_name, action_type, entity_type NULL,
  entity_id NULL, payload (JSON), reason, risk_level,
  required_role (default `dispatcher`), status (`pending|approved|rejected|expired`),
  requested_by, decided_by NULL, decided_at NULL, created_at.
- `policies`: id, org_id, name, description, rule (JSON:
  `{conditions:[{field,op,value}], effect:"allow|require_approval|deny|notify"}`),
  priority (int), is_active, timestamps.
- `automation_rules`: id, org_id, name, event_name, conditions (JSON),
  actions (JSON list of `{type, params}`), is_active, timestamps.
- `events_log`: id, org_id, event_name, entity_type NULL, entity_id NULL,
  payload (JSON), created_at.
- `feature_flags`: id, org_id, key (unique per org), enabled (bool),
  config (JSON NULL).
- `integrations`: id, org_id, provider
  (`maps|eld_samsara|eld_motive|project44|fourkites|dat|truckstop|quickbooks|stripe|twilio|sendgrid|openai|anthropic|aws|gcp|azure`),
  status (`mock|connected|disabled`), config (JSON), last_sync NULL.
- `forecasts`: id, org_id, forecast_type (`volume|capacity|cost|lane_pricing|driver_demand`),
  period_start/end (Date), values (JSON), confidence (Float NULL), created_at.
- `ai_usage`: id, org_id, agent_name, model, tokens_in, tokens_out,
  est_cost_usd (Float), task_type NULL, created_at.

### 3.5 Domain events (exact names)

`LOAD_CREATED, LOAD_ASSIGNED, LOAD_ACCEPTED, DRIVER_DISPATCHED,
PICKUP_COMPLETED, SHIPMENT_IN_TRANSIT, ETA_CHANGED, SHIPMENT_DELAYED,
EXCEPTION_CREATED, EXCEPTION_RESOLVED, DELIVERY_COMPLETED, POD_UPLOADED,
INVOICE_CREATED, PAYMENT_RECEIVED, RATE_UPDATED, DOCUMENT_UPLOADED,
CARRIER_SCORED, AI_ACTION_PROPOSED, AI_ACTION_APPROVED, AI_ACTION_REJECTED,
AI_ACTION_EXECUTED, POLICY_VIOLATION`

## 4. Auth & tenant isolation

- `POST /api/v1/auth/login` {email,password} →
  `{access_token, token_type:"bearer", user: UserOut}`.
  JWT: `{sub: user_id, org_id, role, exp: 8h}` signed HS256.
- `GET /api/v1/auth/me` → current user + org.
- All data routes: `get_current_user` dep → `org_id` from token;
  **every query filters `org_id == token.org_id`**. No exceptions.
- `require_roles("admin","dispatcher",...)` dep; scoped roles
  (driver/carrier/shipper) additionally filter to own records.
- Passwords: bcrypt via passlib. Seed demo password `Demo1234!`.
- Audit: `audit.log()` helper writes audit_logs on every mutation;
  AI actions always logged with who/what/why/input/decision/policy/result.

## 5. API contract (base `/api/v1`)

List responses: `{items:[], total, page, page_size}`.
Query params: `search, status, sort_by, sort_dir, page, page_size, date_from, date_to`
(where relevant). Errors: FastAPI default `{detail}`.

| Method & path | Notes |
|---|---|
| POST /auth/login, GET /auth/me | |
| GET /organizations/me, PUT /organizations/me | admin |
| GET/POST /users, GET/PUT/DELETE /users/{id} | admin |
| GET/POST /customers, GET/PUT/DELETE /customers/{id} | |
| GET/POST /carriers, GET/PUT/DELETE /carriers/{id}, GET /carriers/{id}/score | score → {score, factors:[{name,weight,value,contribution}], explanation} |
| GET/POST /drivers, GET/PUT/DELETE /drivers/{id} | |
| GET/POST /vehicles, GET/PUT/DELETE /vehicles/{id} | |
| GET/POST /loads, GET/PUT/DELETE /loads/{id}, POST /loads/{id}/duplicate, POST /loads/{id}/cancel, POST /loads/{id}/assign {carrier_id?,driver_id?,vehicle_id?}, POST /loads/{id}/status {status} | assign fires LOAD_ASSIGNED; status transitions validated |
| GET/POST /shipments, GET/PUT/DELETE /shipments/{id}, POST /shipments/{id}/status {status}, GET /shipments/{id}/loads | |
| GET /loads/{id}/stops, POST /loads/{id}/stops, PUT/DELETE /stops/{id} | |
| GET /dispatch/board | {unassigned_loads, available_drivers, available_vehicles, conflicts[]} |
| POST /dispatch/assign {load_id, driver_id, vehicle_id?} | conflict warnings returned, not blocking (warnings list) |
| GET /tracking/positions | simulated live positions of in-transit loads |
| GET /tracking/loads/{id} | route + events + ETA |
| GET/POST /rates, GET/PUT/DELETE /rates/{id}, POST /rates/quote {origin,destination,equipment_type,weight_lbs?,distance_miles?} | quote → {customer_rate, carrier_rate, margin, margin_pct, basis} |
| GET/POST /invoices, GET/PUT /invoices/{id}, POST /invoices/{id}/issue, POST /invoices/{id}/pay {amount,method} | |
| POST /documents/upload (multipart: file, entity_type, entity_id, doc_type), GET /documents, GET /documents/{id}/download | local storage `./storage/` |
| GET/POST /communications, GET /communications/thread/{type}/{id} | |
| GET /exceptions, POST /exceptions/{id}/acknowledge, POST /exceptions/{id}/resolve {resolution}, POST /exceptions/{id}/assign {user_id} | |
| GET /notifications, POST /notifications/{id}/read, POST /notifications/read-all | |
| GET /analytics/overview | KPI bundle (section 7 dashboard) |
| GET /analytics/financial, /analytics/operational, /analytics/carrier, /analytics/customer | date/customer/carrier/driver/lane filters |
| GET /lanes, GET /lanes/{id} | aggregated lane stats |
| GET /audit | filterable audit log (admin, ops_manager) |
| GET/POST /policies, GET/PUT/DELETE /policies/{id} | admin |
| GET /agents, PUT /agents/{id} | agent registry (admin) |
| GET /approvals, POST /approvals/{id}/approve, POST /approvals/{id}/reject {reason?} | |
| GET/PUT /feature-flags | admin |
| GET /integrations, PUT /integrations/{id} | status mock/connected/disabled |
| GET /settings, PUT /settings | org settings (admin) |
| **AI** | |
| POST /ai/command {message} | → {answer, data, recommendations[], actions[], confidence, approval_required} |
| POST /ai/match-carriers {load_id, top_n?} | ranked carriers + explanations |
| POST /ai/optimize-route {load_id} | {current, optimized, savings{miles,minutes,fuel_usd,cost_usd}, approval_required} |
| POST /ai/exceptions/scan | run detection now → created exceptions |
| POST /ai/forecast {type, periods?} | {historical[], current, forecast[], confidence} |
| POST /ai/actions/propose {agent, action_type, entity_type?, entity_id?, payload} | policy eval → auto-executed OR approval created |
| GET /ai/usage | AI cost tracking |

Status transition guard for loads (allowed map enforced server-side):
draft→quoted|cancelled, quoted→tendered|cancelled, tendered→available|cancelled,
available→assigned|cancelled, assigned→confirmed|dispatched|cancelled,
confirmed→dispatched, dispatched→at_pickup, at_pickup→picked_up,
picked_up→in_transit, in_transit→at_delivery, at_delivery→delivered,
delivered→pod_received, pod_received→invoiced, invoiced→paid.

## 6. AI control plane (backend/app/ai/)

- `providers.py`: `AIProvider` base (`complete(prompt, **kw)`);
  `MockProvider` (default, deterministic); `OpenAIProvider`, `AnthropicProvider`
  stubs — raise `ProviderNotConfigured` unless env keys present; never called
  without keys. Selected via `AI_PROVIDER` env (default `mock`).
- `registry.py`: Agent Registry + Tool Registry. Tools are named functions
  with `{name, description, required_scopes, handler}`; tool calls check
  the invoking user's scopes before execution.
- `policy.py`: Policy Engine. `evaluate(action, context)` loads org policies
  (ordered by priority) → decision `allow|require_approval|deny|notify`.
  Autonomy level gates: level 0 observe-only; 1 recommend; 2 approval-gated;
  3 low-risk auto (risk=low + policy allow); 4 auto within policy (never for
  financial mutation, deletions, cross-tenant — hard deny list).
- `approvals.py`: create/list/approve/reject; on approve, execute the action
  via tool registry, record result, fire `AI_ACTION_EXECUTED`.
- Heuristic agents in `agents/`: `dispatch_agent, routing_agent,
  carrier_agent, customer_service_agent, exception_agent, pricing_agent,
  finance_agent, compliance_agent, ops_analyst_agent`. Deterministic,
  explainable; each returns `{recommendation, reason, expected_impact,
  confidence, alternatives, risks, approval_required}`.
- Every AI action writes `ai_actions` row with who/what/why/input/decision/
  policy/result/timestamp.

Carrier score (deterministic, weights configurable via feature flag
`carrier_score_weights`):
`0.30*rate_competitiveness + 0.25*on_time + 0.15*acceptance + 0.15*lane_history
+ 0.10*compliance + 0.05*equipment_match`, each 0-100 normalized.

## 7. Frontend

Routes: `/login`, `/` (dashboard), `/loads`, `/loads/:id`, `/shipments`,
`/shipments/:id`, `/dispatch`, `/tracking`, `/exceptions`, `/carriers`,
`/drivers`, `/fleet`, `/customers`, `/rates`, `/invoices`, `/invoices/:id`,
`/ai`, `/analytics`, `/lanes`, `/documents`, `/inbox`, `/driver`,
`/admin/*` (users, roles, policies, agents, flags, integrations, audit, settings).

- `src/api/client.ts`: fetch wrapper (base `VITE_API_URL` default
  `http://localhost:8000/api/v1`), token from localStorage, typed helpers.
- `src/components/`: Layout (sidebar+topbar), DataTable (search/filter/sort/
  pagination), Modal, Drawer, StatCard, Charts (SVG bars/line/donut),
  MapView (SVG US map w/ simulated positions), CommandPalette (Cmd+K),
  StatusPill, EmptyState, AIRecommendationCard.
- Dashboard sections: ATTENTION REQUIRED (critical exceptions),
  TODAY (pickups/deliveries), ACTIVE (in-transit), AI RECOMMENDATIONS,
  PERFORMANCE (KPIs + charts).
- Dispatch board: two-column drag-and-drop (HTML5 DnD) loads→drivers with
  conflict warnings (double-booking, appointment overlap, capacity, compliance).
- Driver view `/driver`: mobile-first, current assignment, status buttons,
  POD upload.
- Every view: loading / empty / error states. Forms: validation + error/success.

## 8. Seed data (backend/seed.py)

One org `demo` ("Demo Logistics Co"), 8 demo users (all password `Demo1234!`):
admin/broker/dispatcher/carrier/driver/shipper/finance/ops @demo.tms.
12 customers, 28 carriers, 45 drivers, 35 vehicles, 120 loads across realistic
US lanes (e.g. Atlanta↔Dallas, Chicago↔Atlanta, LA↔Phoenix) with mixed statuses
(active/in-transit/delivered/delayed), 20+ exceptions, 40 invoices,
documents (generated text files), communications threads, 3 automation rules,
default policies (e.g. carrier score < 80 blocks assignment; price change >
$500 requires approval), 9 AI agents registered, feature flags, integrations
(all `mock`), a few sample approvals + ai_actions + recommendations.
Idempotent-ish: skip if demo org exists (or `--reset`).

## 9. Tests (backend/tests/)

pytest + httpx TestClient, isolated SQLite per test with fresh seed-lite
fixture (2 orgs to prove isolation):
- test_auth.py — login success/fail, /me, missing/invalid token → 401
- test_tenant_isolation.py — org A cannot read/mutate org B records (loads,
  customers, audit)
- test_rbac.py — role matrix: driver blocked from admin endpoints;
  shipper sees only own customer; 403s
- test_loads.py — CRUD, duplicate, cancel, assign, invalid status transition → 422
- test_carrier_matching.py — deterministic score math on fixtures
- test_rates.py — quote math: revenue − cost = profit; margin %
- test_policy_approval.py — propose action → policy require_approval creates
  approval; approve executes; deny policy blocks; hard-deny list (financial
  mutation at autonomy 4 still needs approval)
- test_exceptions.py — detection creates exceptions; resolve flow
- test_api_smoke.py — dashboard overview keys; dispatch board shape; lanes

## 10. Events & automation

In-process `EventBus` (sync pub/sub) + every emission persisted to
`events_log`. `automation.py` evaluates active `automation_rules` on each
event: conditions (JSON path ops) → actions (`create_exception`,
`create_notification`, `update_load_status`, `trigger_agent`, `send_communication`).
Seeded rules: delay>30min → exception+notify+AI eval; POD uploaded →
validate→invoice→notify finance.

## 11. Config & security notes

- `backend/app/config.py`: `DATABASE_URL` (default `sqlite:///./tms.db`),
  `JWT_SECRET` (default `dev-secret-change-me` + startup warning),
  `JWT_EXPIRE_HOURS=8`, `CORS_ORIGINS`, `AI_PROVIDER=mock`,
  `STORAGE_DIR=./storage`.
- Never log secrets; error responses never include tracebacks or keys;
  input validation via Pydantic; SQL via SQLAlchemy (no string SQL);
  file uploads: size/type checks, stored outside web root.
- Postgres switch: set `DATABASE_URL=postgresql+psycopg2://...`, add
  `psycopg2-binary` — no code changes needed.

## 12. Docker (UNVERIFIED)

`docker-compose.yml`: `api` (build ./backend, env file), `web` (build
./frontend → nginx), `postgres:16`, `redis:7` (reserved for future queue).
Docker is not installed on the build VM — compose file is delivered
unverified and marked as such in README.
