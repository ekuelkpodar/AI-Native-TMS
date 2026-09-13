# AI-Native TMS

A multi-tenant, AI-native Transportation Management System: full freight-broker
workflows (loads, dispatch, tracking, carriers, invoicing) under a governed AI
operations layer — policy engine, approval gates, automation rules, and an
agent registry.

## Product preview

![DispatchOS landing page — 2026-style marketing site with live lane ticker and product preview](docs/screenshot-landing.png)

![DispatchOS operations dashboard — KPIs, attention-required exceptions, pickups & deliveries, in-transit loads](docs/screenshot-dashboard.png)

The public site (`/`) is a full marketing landing page with **Sign up** and
**Sign in** in the nav. Self-serve signup (`/signup` →
`POST /api/v1/auth/register`) provisions a brand-new organization with its first
admin user. The app itself lives behind auth, with the dashboard at `/dashboard`.

## Product summary

For freight brokerages and 3PLs that want an AI copilot inside their TMS rather
than bolted on next to it:

- **Load lifecycle** — quote → tender → assign → dispatch → in-transit →
  delivered → POD → invoiced → paid, with server-side status-transition guards.
- **Dispatch board** — drag-and-drop loads onto drivers with conflict warnings
  (double-booking, appointment overlap, capacity, compliance).
- **Live tracking** — GPS pings along the lane, positions map, per-load
  route + ETA view.
- **Carrier management** — MC/DOT, insurance & authority compliance, and a
  deterministic carrier score with factor explanations
  (rate competitiveness, on-time %, acceptance, lane history, compliance,
  equipment match).
- **Exceptions** — automatic detection (late pickup/delivery, POD missing,
  margin anomalies, cancellations, route deviation) with acknowledge/resolve
  workflows and history.
- **Finance** — invoices with line items, issue/pay flows, payment records,
  financial analytics.
- **AI control plane** — agent registry (9 seeded agents), tool registry with
  scope checks, policy engine (`allow | require_approval | deny | notify`),
  autonomy levels 0–4, human approval queue, and full audit of every AI action
  (who / what / why / input / decision / policy / result).
- **Automation** — WHEN/IF/THEN rules evaluated on every domain event
  (e.g. delay > 30 min → exception + notification; POD uploaded → validate →
  invoice → notify).
- **Multi-tenant** — every record carries `org_id`; the JWT carries the org;
  all queries are org-scoped.

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────────┐
│  React SPA  │────▶│ FastAPI (/api/v1)                             │
│  Vite :5173 │     │  routers → services → SQLAlchemy 2.0         │
└─────────────┘     │  JWT auth (HS256, 8h) + RBAC + org scoping    │
                    │  in-process EventBus → events_log            │
                    │  automation rules engine (on every event)    │
                    │  AI control plane (backend/app/ai, mounted   │
                    │  best-effort): providers, registry, policy,  │
                    │  approvals — mock provider by default        │
                    └──────────────────────┬───────────────────────┘
                                           │ SQLAlchemy (same models)
                                  SQLite (default) · Postgres (env)
```

- **Stack** — Python 3.12, FastAPI, SQLAlchemy 2.0 (typed `Mapped` models),
  Pydantic v2, `python-jose` JWT, `passlib`+bcrypt, `uvicorn`;
  Vite 6 + React 18 + TypeScript 5 + react-router-dom 6, plain CSS, hand-rolled
  SVG charts. pytest + httpx for tests.
- **Data model** — see `ARCHITECTURE.md` §3 (source of truth) and
  `backend/app/models.py`. Core: organizations, users/roles, customers,
  carriers, drivers, vehicles, shipments, loads, stops, routes, assignments,
  rates, invoices, payments, documents, communications, notifications,
  exceptions, tracking_events, audit_logs. Governance: ai_agents, ai_tasks,
  ai_actions, approvals, policies, automation_rules, events_log,
  feature_flags, integrations, forecasts, ai_usage. IDs are UUID hex strings;
  enums are plain strings.
- **Event flow** — domain actions emit events (`LOAD_CREATED`,
  `LOAD_ASSIGNED`, `SHIPMENT_DELAYED`, `POD_UPLOADED`, … — full list in
  `ARCHITECTURE.md` §3.5). The in-process `EventBus` persists each emission to
  `events_log`; `automation.py` evaluates active `automation_rules` on every
  event and fires actions (`create_exception`, `create_notification`,
  `update_load_status`, `trigger_agent`, `send_communication`).
- **Tenant isolation** — `get_current_user` decodes the JWT (`sub`, `org_id`,
  `role`); every data query filters `org_id == token.org_id` with no
  exceptions; `require_roles(...)` enforces RBAC; scoped roles (driver,
  carrier, shipper) additionally filter to their own records.
- **AI governance** — policies are evaluated in priority order; autonomy
  levels gate what agents may do (0 observe → 4 auto-within-policy, with a
  hard deny list for financial mutation, deletions, cross-tenant access).
  Anything requiring approval lands in the approvals queue; approving executes
  the action via the tool registry and records the result. `AI_PROVIDER`
  selects `mock` (default, deterministic) or the OpenAI/Anthropic providers,
  which raise unless API keys are configured.

## Quickstart

### Backend

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python seed.py        # idempotent demo data (see below)
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

API base: `http://localhost:8000/api/v1` · interactive docs:
`http://localhost:8000/docs` · health: `http://localhost:8000/health`

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 — /api is proxied to localhost:8000
```

Production build: `npm run build` → `frontend/dist/`
(`VITE_API_URL` env var sets the API base URL at build time;
default `http://localhost:8000/api/v1`).

### Tests

```bash
cd backend
.venv/bin/python -m pytest tests/ -q
```

(The `tests/` suite — 52 tests covering auth, tenant isolation, RBAC matrix,
load transitions, carrier-score math, rates, policy/approval flow,
exceptions, and API smoke — runs with the command above.)

### Demo credentials

All seed users share the password **`Demo1234!`**. Sign in at `/login`
or `POST /api/v1/auth/login`.
Prefer your own workspace? Create one at `/signup` — it calls
`POST /api/v1/auth/register` and provisions a fresh organization with you as admin.

| Email | Name | Role | Sees |
|---|---|---|---|
| admin@demo.tms | Ava Mitchell | admin | everything + admin pages |
| broker@demo.tms | Brian Torres | broker | loads, customers, carriers, rates, dispatch |
| dispatcher@demo.tms | Dana Whitfield | dispatcher | dispatch board, loads, drivers, fleet, exceptions |
| carrier@demo.tms | Carlos Vega | carrier | own assigned loads only (carrier-scoped) |
| driver@demo.tms | Derek Nolan | driver | own assignments + driver mobile view (driver-scoped) |
| shipper@demo.tms | Sara Hensley | shipper | own customer's shipments/invoices (shipper-scoped) |
| finance@demo.tms | Fiona Clarke | finance | invoices, payments, financial analytics |
| ops@demo.tms | Omar Reyes | ops_manager | analytics, exceptions, policies, lanes |

### Seed data

`backend/seed.py` (stdlib + SQLAlchemy only) builds the demo org
**Demo Logistics Co** (`slug: "demo"`, plan `professional`):

- 8 users, 12 customers, 28 carriers (2 with expired insurance, 3 warnings),
  45 drivers, 35 vehicles
- 120 loads across 18 US lanes (Atlanta↔Dallas, Chicago↔Atlanta,
  LA↔Phoenix, Seattle↔Denver, Miami↔Atlanta, …): 25 available, 8 assigned,
  7 dispatched, 20 in-transit (7 at-risk, past appointment), 22 delivered,
  18 pod_received, 6 invoiced, 4 paid, plus quoted/tendered/cancelled;
  28 multi-stop rows; 176 tracking pings; realistic per-mile rates with
  10–24% margins (one 6% margin-anomaly demo)
- 22 exceptions (late pickup/delivery, POD missing, margin anomaly, document
  missing, carrier cancellation, route deviation, missed appointment —
  8 resolved with history, 3 acknowledged)
- 40 invoices (draft/issued/paid/overdue) with line items + 6 payments
- 15 documents — real text BOL / POD / rate-confirmation / insurance files
  under `backend/storage/seed/`
- 7 communications across load, customer, and carrier threads
- 3 automation rules, 3 policies (block carriers scoring < 80; price changes
  > $500 need approval; loads > $10k need approval), 9 AI agents,
  6 feature flags, 13 integrations (all `mock`), 3 approvals (1 pending:
  AI-proposed carrier reassignment), 3 AI actions (auto / approved / denied),
  6 notifications, 2 forecasts

Idempotent: re-running prints `already seeded` and exits 0.
`python seed.py --reset` drops all tables and reseeds from scratch.

## Demo walkthrough (14 scenarios)

1. **Role tour** — `/login` · `POST /api/v1/auth/login` — sign in as each of
   the 8 users; scoped roles (carrier/driver/shipper) see only their records.
2. **Dashboard KPIs** — `/` · `GET /api/v1/analytics/overview` — revenue,
   margin, on-time %, open/critical exceptions, outstanding invoices.
3. **Loads board** — `/loads` · `GET /api/v1/loads?status=in_transit` —
   search, filter, sort, paginate the 120 seeded loads.
4. **Load detail + documents** — `/loads/:id` ·
   `GET /api/v1/documents?entity_id=…` + `…/documents/{id}/download` —
   download a real BOL / POD / rate-confirmation text file.
5. **Dispatch board** — `/dispatch` · `GET /api/v1/dispatch/board`,
   `POST /api/v1/dispatch/assign` — drag loads onto drivers; conflict
   warnings (double-booking, compliance) are returned, not blocking.
6. **Live tracking** — `/tracking` · `GET /api/v1/tracking/positions`,
   `GET /api/v1/tracking/loads/{id}` — simulated GPS pings along each lane.
7. **Exceptions queue** — `/exceptions` · `GET /api/v1/exceptions`,
   `POST /api/v1/exceptions/{id}/acknowledge|resolve` — work the at-risk
   late-delivery exceptions.
8. **Carrier scorecard** — `/carriers` ·
   `GET /api/v1/carriers/{id}/score` — deterministic score with per-factor
   contributions and explanation.
9. **Rate quote** — `/rates` · `POST /api/v1/rates/quote` — spot quote with
   customer rate, carrier rate, margin, margin %.
10. **Invoicing** — `/invoices` · `POST /api/v1/invoices/{id}/issue|pay` —
    issue a draft invoice, record a payment, watch status transitions.
11. **Inbox threads** — `/inbox` ·
    `GET /api/v1/communications/thread/load/{id}` — the delayed-load SMS
    thread, customer quote emails, carrier tender exchange.
12. **Policies + approvals** — `/admin` · `GET /api/v1/policies`,
    `GET /api/v1/approvals`, `POST /api/v1/approvals/{id}/approve` — approve
    the pending Dispatch Agent carrier reassignment; the action executes and
    is logged as an `ai_action`.
13. **Agents, flags, integrations** — `/admin` · `GET /api/v1/agents`,
    `GET /api/v1/feature-flags`, `GET /api/v1/integrations` — 9 registered
    agents, carrier-score weights, all 13 integrations in `mock` status.
14. **Analytics + lanes** — `/analytics`, `/lanes` ·
    `GET /api/v1/analytics/financial|operational|carrier|customer`,
    `GET /api/v1/lanes` — lane stats and filtered KPI bundles.

(The AI command console at `/ai` is live: all `/api/v1/ai/*` endpoints are
mounted — command center, carrier matching, route optimization, exception
scan, forecasting, action proposals with human approval, and AI usage/cost
tracking.)

## Switching to Postgres

No code changes needed — the same SQLAlchemy models run on both:

```bash
cd backend
.venv/bin/pip install psycopg2-binary
export DATABASE_URL="postgresql+psycopg2://tms:tms@localhost:5432/tms"
.venv/bin/python seed.py
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

All config is env-driven — see `.env.example` (`JWT_SECRET`, `CORS_ORIGINS`,
`AI_PROVIDER`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `STORAGE_DIR`,
`VITE_API_URL`).

## Live demo deploy

One-command production image: the FastAPI backend serves the built Vite SPA
(single service, same-origin `/api/v1`). See [DEPLOY.md](DEPLOY.md).

- **Render (free):** Dashboard → New → Blueprint → select this repo → Apply.
  `render.yaml` builds the Docker image and seeds demo data on first boot.
  Demo login: `admin@demo.tms` / `Demo1234!`
- **Docker:** `docker build -t ai-native-tms . && docker run -p 8000:8000 ai-native-tms`

## Docker (UNVERIFIED)

`docker-compose.yml` defines `api` (port 8000, Postgres via
`DATABASE_URL`), `web` (nginx serving the frontend build, port 8080),
`postgres:16` (volume `pgdata`), and `redis:7` (volume `redisdata`, reserved
for a future job queue — nothing connects to it yet).

> **UNVERIFIED — docker was not installed on the build VM.** The compose file
> has never been built or run. For a verified path, use the root `Dockerfile`
> (single-service demo image) per [DEPLOY.md](DEPLOY.md).

## Known limitations

- **LLM providers need keys.** `AI_PROVIDER` defaults to `mock`
  (deterministic, no network). The OpenAI/Anthropic providers raise
  `ProviderNotConfigured` unless `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` are set.
- **External integrations are mock adapters.** Maps, ELD (Samsara/Motive),
  project44, FourKites, DAT, Truckstop, QuickBooks, Stripe, Twilio, SendGrid —
  all seeded with status `mock`; they return plausible data but touch no real
  services.
- **No Alembic.** `Base.metadata.create_all()` runs on startup; schema
  changes mean dropping/recreating (or migrating by hand).
- **`/api/v1/ai/*` endpoints are mounted and working** (`backend/app/ai/`:
  provider abstraction with deterministic mock default, agent/tool
  registries, policy engine with autonomy levels 0–4, approval workflows,
  9 heuristic agents). Real LLM providers (OpenAI/Anthropic) are stubbed
  adapters — they raise unless API keys are configured, and are never
  called without keys.
- **Dev JWT secret.** The default `JWT_SECRET=dev-secret-change-me` prints a
  startup warning — set a real secret outside local dev.
- File uploads are stored under `STORAGE_DIR` (default `./storage/`), outside
  any web root.

## Repository tree

```
ai-native-tms/
  ARCHITECTURE.md        # source of truth (stack, data model, AI plane, API)
  README.md              # this file
  docker-compose.yml     # UNVERIFIED prod layout sketch
  .env.example
  backend/
    requirements.txt
    seed.py              # idempotent demo seeder (stdlib + SQLAlchemy)
    storage/seed/        # seeded BOL / POD / rate-con / insurance text files
    tms.db               # SQLite DB created by seed.py / app startup
    app/
      main.py            # create_app() factory + uvicorn entry
      config.py          # env config
      database.py        # engine, SessionLocal, Base
      models.py          # all SQLAlchemy models (ARCHITECTURE.md §3)
      schemas.py         # Pydantic v2 schemas
      security.py        # bcrypt + JWT
      deps.py            # auth, RBAC, org scoping
      events.py          # EventBus + events_log
      automation.py      # WHEN/IF/THEN rules engine
      notifications.py   # notification service
      audit.py           # audit log helper
      routers/           # one module per domain (auth, loads, dispatch,
                         # tracking, carriers, …, policies, approvals, agents)
      ai/                # AI control plane: providers, registry, policy,
                         # approvals, heuristic agents, /ai routes
  frontend/
    package.json         # scripts: dev / build / preview
    vite.config.ts       # dev on :5173, /api proxied to :8000
    index.html
    src/
      main.tsx  App.tsx  styles.css
      api/client.ts      # fetch wrapper (VITE_API_URL, token)
      lib/               # format, hooks
      components/        # Layout, DataTable, Modal, Drawer, StatCard, Charts,
                         # MapView, CommandPalette, StatusPill, EmptyState,
                         # AIRecommendationCard, Page
      pages/             # Login, Dashboard, Loads, LoadDetail, Shipments,
                         # DispatchBoard, Tracking, Exceptions, Carriers,
                         # Drivers, Fleet, Customers, Rates, Invoices,
                         # AICommand, Analytics, Lanes, Documents, Inbox,
                         # DriverApp, Admin
```

See `ARCHITECTURE.md` for the full specification this repo implements.
