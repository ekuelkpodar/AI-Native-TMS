// Typed API client for the AI-Native TMS backend.
// Shapes follow ARCHITECTURE.md section 5 exactly.

export const API_BASE: string =
  import.meta.env.VITE_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000/api/v1";

const TOKEN_KEY = "tms_access_token";
const USER_KEY = "tms_user";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}
export function setStoredUser(u: User) {
  localStorage.setItem(USER_KEY, JSON.stringify(u));
}
export function getStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  path: string,
  opts: { method?: string; body?: unknown; form?: FormData } = {}
): Promise<T> {
  const headers: Record<string, string> = {};
  if (!opts.form) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method || "GET",
    headers,
    body: opts.form ? opts.form : opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 401) {
    clearAuth();
    window.location.href = "/login";
    throw new ApiError(401, "Session expired");
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const j = await res.json();
      if (typeof j?.detail === "string") detail = j.detail;
      else if (Array.isArray(j?.detail))
        detail = j.detail.map((d: { msg?: string }) => d.msg || "Validation error").join("; ");
    } catch {
      /* keep default */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return (await res.json()) as T;
  return undefined as T;
}

export const get = <T,>(p: string) => request<T>(p);
export const post = <T,>(p: string, body?: unknown) => request<T>(p, { method: "POST", body });
export const put = <T,>(p: string, body?: unknown) => request<T>(p, { method: "PUT", body });
export const del = <T,>(p: string) => request<T>(p, { method: "DELETE" });
export const upload = <T,>(p: string, form: FormData) =>
  request<T>(p, { method: "POST", form });

/* ------------------------------------------------------------------ types */

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface User {
  id: string;
  org_id: string;
  email: string;
  full_name: string;
  role: string;
  carrier_id: string | null;
  driver_id: string | null;
  customer_id: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  plan: string;
  settings: Record<string, unknown>;
  is_active: boolean;
}

export interface Role {
  id: string;
  org_id: string;
  name: string;
  description: string;
  permissions: string[];
  is_active: boolean;
}

export interface Customer {
  id: string;
  org_id: string;
  name: string;
  contact_name: string;
  email: string;
  phone: string;
  street: string;
  city: string;
  state: string;
  zip: string;
  country: string;
  credit_limit: number;
  payment_terms: string;
  is_active: boolean;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface Carrier {
  id: string;
  org_id: string;
  legal_name: string;
  dba: string;
  mc_number: string;
  dot_number: string;
  street: string;
  city: string;
  state: string;
  zip: string;
  phone: string;
  email: string;
  equipment_types: string[];
  service_areas: string[];
  lanes: unknown[];
  insurance_expiry: string;
  authority_status: string;
  compliance_status: string;
  safety_rating: string;
  performance_score: number;
  on_time_pct: number;
  acceptance_rate: number;
  claims_count: number;
  cancellations_count: number;
  total_revenue: number;
  notes: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CarrierScoreFactor {
  name: string;
  weight: number;
  value: number;
  contribution: number;
}
export interface CarrierScore {
  score: number;
  factors: CarrierScoreFactor[];
  explanation: string;
}

export interface Driver {
  id: string;
  org_id: string;
  carrier_id: string | null;
  full_name: string;
  phone: string;
  email: string;
  license_number: string;
  license_expiry: string;
  status: string;
  current_location: { lat: number; lng: number; city: string; state: string } | null;
  hours_available: number;
  performance_score: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Vehicle {
  id: string;
  org_id: string;
  vin: string;
  unit_number: string;
  license_plate: string;
  make: string;
  model: string;
  year: number;
  vehicle_type: string;
  capacity_lbs: number;
  mileage: number;
  current_location: { lat: number; lng: number } | null;
  availability_status: string;
  driver_id: string | null;
  maintenance_status: string;
  insurance_expiry: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LoadLocation {
  city: string;
  state: string;
  zip: string;
  lat: number;
  lng: number;
}

export interface Load {
  id: string;
  org_id: string;
  load_number: string;
  reference_number: string;
  customer_id: string;
  carrier_id: string | null;
  driver_id: string | null;
  vehicle_id: string | null;
  origin: LoadLocation;
  destination: LoadLocation;
  pickup_datetime: string;
  delivery_datetime: string;
  equipment_type: string;
  commodity: string;
  weight_lbs: number;
  length_ft: number;
  width_ft: number;
  height_ft: number | null;
  pallets: number;
  pieces: number;
  customer_rate: number;
  carrier_rate: number;
  distance_miles: number;
  hazmat: boolean;
  temp_min: number | null;
  temp_max: number | null;
  status: string;
  notes: string;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  margin?: number;
  margin_pct?: number;
}

export interface Shipment {
  id: string;
  org_id: string;
  customer_id: string;
  reference_number: string;
  status: string;
  pickup_appointment: string;
  delivery_appointment: string;
  special_instructions: string;
  created_at: string;
  updated_at: string;
}

export interface Stop {
  id: string;
  load_id: string;
  sequence: number;
  stop_type: string;
  location: LoadLocation & { street?: string };
  appointment_start: string | null;
  appointment_end: string | null;
  status: string;
  notes: string;
}

export interface DispatchConflict {
  type: string;
  severity: string;
  message: string;
  load_id?: string;
  driver_id?: string;
}

export interface DispatchBoard {
  unassigned_loads: Load[];
  available_drivers: Driver[];
  available_vehicles: Vehicle[];
  conflicts: DispatchConflict[];
}

export interface TrackingPosition {
  load_id: string;
  load_number: string;
  lat: number;
  lng: number;
  city: string;
  state: string;
  speed_mph: number | null;
  status: string;
  eta: string | null;
}

export interface TrackingDetail {
  load: Load;
  events: TrackingEvent[];
  eta: string | null;
  route: { waypoints: unknown[]; total_miles: number; total_minutes: number } | null;
}

export interface TrackingEvent {
  id: string;
  org_id: string;
  load_id: string;
  event_type: string;
  lat: number;
  lng: number;
  city: string | null;
  speed_mph: number | null;
  recorded_at: string;
  meta: Record<string, unknown> | null;
}

export interface Rate {
  id: string;
  org_id: string;
  origin_city: string;
  origin_state: string;
  dest_city: string;
  dest_state: string;
  equipment_type: string;
  customer_rate: number;
  carrier_rate: number;
  rate_type: string;
  fuel_surcharge: number;
  effective_from: string | null;
  effective_to: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface QuoteResult {
  customer_rate: number;
  carrier_rate: number;
  margin: number;
  margin_pct: number;
  basis: string;
}

export interface Invoice {
  id: string;
  org_id: string;
  invoice_number: string;
  customer_id: string;
  load_id: string | null;
  issue_date: string;
  due_date: string;
  line_items: { description: string; amount: number; qty?: number }[];
  subtotal: number;
  tax: number;
  total: number;
  amount_paid: number;
  status: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface ExceptionItem {
  id: string;
  org_id: string;
  load_id: string | null;
  exception_type: string;
  severity: string;
  title: string;
  description: string;
  detected_at: string;
  recommended_action: string | null;
  owner_user_id: string | null;
  status: string;
  resolution: string | null;
  resolved_at: string | null;
  history: { action: string; at: string; by?: string }[];
  created_at: string;
  updated_at: string;
}

export interface Document {
  id: string;
  org_id: string;
  entity_type: string;
  entity_id: string;
  doc_type: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  storage_path: string;
  doc_metadata: Record<string, unknown>;
  version: number;
  uploaded_by: string;
  created_at: string;
}

export interface Communication {
  id: string;
  org_id: string;
  thread_type: string;
  thread_id: string;
  channel: string;
  direction: string;
  sender: string;
  recipient: string;
  subject: string | null;
  body: string;
  created_by: string | null;
  created_at: string;
}

export interface Notification {
  id: string;
  org_id: string;
  user_id: string | null;
  type: string;
  title: string;
  body: string;
  entity_type: string | null;
  entity_id: string | null;
  is_read: boolean;
  created_at: string;
}

export interface AnalyticsOverview {
  active_loads: number;
  in_transit: number;
  delivered_today: number;
  open_exceptions: number;
  critical_exceptions: number;
  revenue_mtd: number;
  margin_mtd: number;
  margin_pct: number;
  on_time_pct: number;
  loads_by_status: { status: string; count: number }[];
  revenue_by_day: { date: string; revenue: number }[];
  exceptions_by_severity: { severity: string; count: number }[];
  top_lanes: { origin: string; destination: string; loads: number; revenue: number }[];
}

export interface Lane {
  id: string;
  origin_city: string;
  origin_state: string;
  dest_city: string;
  dest_state: string;
  equipment_type: string;
  loads: number;
  revenue: number;
  avg_rate: number;
  avg_margin: number;
}

export interface AuditLog {
  id: string;
  org_id: string;
  actor_type: string;
  actor_id: string | null;
  actor_name: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface Policy {
  id: string;
  org_id: string;
  name: string;
  description: string;
  rule: {
    conditions: { field: string; op: string; value: unknown }[];
    effect: string;
  };
  priority: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Agent {
  id: string;
  org_id: string;
  name: string;
  version: string;
  model: string;
  tools: string[];
  permissions: string[];
  status: string;
  owner: string;
  risk_level: string;
  autonomy_level: number;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Approval {
  id: string;
  org_id: string;
  agent_name: string;
  action_type: string;
  entity_type: string | null;
  entity_id: string | null;
  payload: Record<string, unknown>;
  reason: string;
  risk_level: string;
  required_role: string;
  status: string;
  requested_by: string;
  decided_by: string | null;
  decided_at: string | null;
  created_at: string;
}

export interface FeatureFlag {
  id: string;
  org_id: string;
  key: string;
  enabled: boolean;
  config: Record<string, unknown> | null;
}

export interface Integration {
  id: string;
  org_id: string;
  provider: string;
  status: string;
  config: Record<string, unknown>;
  last_sync: string | null;
}

export interface AIRecommendation {
  recommendation: string;
  reason: string;
  expected_impact: string;
  confidence: number;
  alternatives: string[];
  risks: string[];
  approval_required: boolean;
}

export interface AIAction {
  type: string;
  label: string;
  payload: Record<string, unknown>;
}

export interface AICommandResponse {
  answer: string;
  data: Record<string, unknown>;
  recommendations: AIRecommendation[];
  actions: AIAction[];
  confidence: number;
  approval_required: boolean;
}

export interface CarrierMatch {
  carrier_id: string;
  carrier_name: string;
  score: number;
  explanation: string;
}

export interface RouteOptimization {
  current: { miles: number; minutes: number };
  optimized: { miles: number; minutes: number };
  savings: { miles: number; minutes: number; fuel_usd: number; cost_usd: number };
  approval_required: boolean;
}

export interface ForecastResponse {
  historical: { period: string; value: number }[];
  current: number;
  forecast: { period: string; value: number }[];
  confidence: number;
}

export interface ProposeActionResponse {
  decision: string;
  approval_id: string | null;
  action_id: string;
  result: Record<string, unknown> | null;
}

export interface AIUsage {
  agent_name: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  est_cost_usd: number;
  task_type: string | null;
  created_at: string;
}

/* ------------------------------------------------------------------ helpers */

export interface ListParams {
  search?: string;
  status?: string;
  sort_by?: string;
  sort_dir?: string;
  page?: number;
  page_size?: number;
  date_from?: string;
  date_to?: string;
  [k: string]: string | number | undefined;
}

function qs(p?: ListParams): string {
  if (!p) return "";
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(p)) if (v !== undefined && v !== "") q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : "";
}

export const authApi = {
  login: (email: string, password: string) =>
    post<LoginResponse>("/auth/login", { email, password }),
  register: (data: {
    full_name: string;
    company_name: string;
    email: string;
    password: string;
  }) => post<LoginResponse & { organization: Organization }>("/auth/register", data),
  me: () => get<User & { org: Organization }>("/auth/me"),
};

export const orgApi = {
  me: () => get<Organization>("/organizations/me"),
  update: (data: Partial<Organization>) => put<Organization>("/organizations/me", data),
};

export const usersApi = {
  list: (p?: ListParams) => get<Page<User>>(`/users${qs(p)}`),
  create: (data: Partial<User> & { password: string }) => post<User>("/users", data),
  get: (id: string) => get<User>(`/users/${id}`),
  update: (id: string, data: Partial<User>) => put<User>(`/users/${id}`, data),
  remove: (id: string) => del<void>(`/users/${id}`),
};

export const customersApi = {
  list: (p?: ListParams) => get<Page<Customer>>(`/customers${qs(p)}`),
  create: (data: Partial<Customer>) => post<Customer>("/customers", data),
  get: (id: string) => get<Customer>(`/customers/${id}`),
  update: (id: string, data: Partial<Customer>) => put<Customer>(`/customers/${id}`, data),
  remove: (id: string) => del<void>(`/customers/${id}`),
};

export const carriersApi = {
  list: (p?: ListParams) => get<Page<Carrier>>(`/carriers${qs(p)}`),
  create: (data: Partial<Carrier>) => post<Carrier>("/carriers", data),
  get: (id: string) => get<Carrier>(`/carriers/${id}`),
  update: (id: string, data: Partial<Carrier>) => put<Carrier>(`/carriers/${id}`, data),
  remove: (id: string) => del<void>(`/carriers/${id}`),
  score: (id: string) => get<CarrierScore>(`/carriers/${id}/score`),
};

export const driversApi = {
  list: (p?: ListParams) => get<Page<Driver>>(`/drivers${qs(p)}`),
  create: (data: Partial<Driver>) => post<Driver>("/drivers", data),
  get: (id: string) => get<Driver>(`/drivers/${id}`),
  update: (id: string, data: Partial<Driver>) => put<Driver>(`/drivers/${id}`, data),
  remove: (id: string) => del<void>(`/drivers/${id}`),
};

export const vehiclesApi = {
  list: (p?: ListParams) => get<Page<Vehicle>>(`/vehicles${qs(p)}`),
  create: (data: Partial<Vehicle>) => post<Vehicle>("/vehicles", data),
  get: (id: string) => get<Vehicle>(`/vehicles/${id}`),
  update: (id: string, data: Partial<Vehicle>) => put<Vehicle>(`/vehicles/${id}`, data),
  remove: (id: string) => del<void>(`/vehicles/${id}`),
};

export const loadsApi = {
  list: (p?: ListParams) => get<Page<Load>>(`/loads${qs(p)}`),
  create: (data: Partial<Load>) => post<Load>("/loads", data),
  get: (id: string) => get<Load>(`/loads/${id}`),
  update: (id: string, data: Partial<Load>) => put<Load>(`/loads/${id}`, data),
  remove: (id: string) => del<void>(`/loads/${id}`),
  duplicate: (id: string) => post<Load>(`/loads/${id}/duplicate`),
  cancel: (id: string) => post<Load>(`/loads/${id}/cancel`),
  assign: (id: string, data: { carrier_id?: string; driver_id?: string; vehicle_id?: string }) =>
    post<Load>(`/loads/${id}/assign`, data),
  setStatus: (id: string, status: string) => post<Load>(`/loads/${id}/status`, { status }),
  stops: (id: string) => get<Stop[]>(`/loads/${id}/stops`),
  createStop: (id: string, data: Partial<Stop>) => post<Stop>(`/loads/${id}/stops`, data),
};

export const stopsApi = {
  update: (id: string, data: Partial<Stop>) => put<Stop>(`/stops/${id}`, data),
  remove: (id: string) => del<void>(`/stops/${id}`),
};

export const shipmentsApi = {
  list: (p?: ListParams) => get<Page<Shipment>>(`/shipments${qs(p)}`),
  create: (data: Partial<Shipment>) => post<Shipment>("/shipments", data),
  get: (id: string) => get<Shipment>(`/shipments/${id}`),
  update: (id: string, data: Partial<Shipment>) => put<Shipment>(`/shipments/${id}`, data),
  remove: (id: string) => del<void>(`/shipments/${id}`),
  setStatus: (id: string, status: string) => post<Shipment>(`/shipments/${id}/status`, { status }),
  loads: (id: string) => get<Load[]>(`/shipments/${id}/loads`),
};

export const dispatchApi = {
  board: () => get<DispatchBoard>("/dispatch/board"),
  assign: (load_id: string, driver_id: string, vehicle_id?: string) =>
    post<{ assignment: unknown; warnings: DispatchConflict[] }>("/dispatch/assign", {
      load_id,
      driver_id,
      vehicle_id,
    }),
};

export const trackingApi = {
  positions: () => get<TrackingPosition[]>("/tracking/positions"),
  detail: (id: string) => get<TrackingDetail>(`/tracking/loads/${id}`),
};

export const ratesApi = {
  list: (p?: ListParams) => get<Page<Rate>>(`/rates${qs(p)}`),
  create: (data: Partial<Rate>) => post<Rate>("/rates", data),
  get: (id: string) => get<Rate>(`/rates/${id}`),
  update: (id: string, data: Partial<Rate>) => put<Rate>(`/rates/${id}`, data),
  remove: (id: string) => del<void>(`/rates/${id}`),
  quote: (data: {
    origin: string;
    destination: string;
    equipment_type: string;
    weight_lbs?: number;
    distance_miles?: number;
  }) => post<QuoteResult>("/rates/quote", data),
};

export const invoicesApi = {
  list: (p?: ListParams) => get<Page<Invoice>>(`/invoices${qs(p)}`),
  create: (data: Partial<Invoice>) => post<Invoice>("/invoices", data),
  get: (id: string) => get<Invoice>(`/invoices/${id}`),
  update: (id: string, data: Partial<Invoice>) => put<Invoice>(`/invoices/${id}`, data),
  issue: (id: string) => post<Invoice>(`/invoices/${id}/issue`),
  pay: (id: string, amount: number, method: string) =>
    post<Invoice>(`/invoices/${id}/pay`, { amount, method }),
};

export const documentsApi = {
  list: (p?: ListParams) => get<Page<Document>>(`/documents${qs(p)}`),
  upload: (file: File, entity_type: string, entity_id: string, doc_type: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("entity_type", entity_type);
    form.append("entity_id", entity_id);
    form.append("doc_type", doc_type);
    return upload<Document>("/documents/upload", form);
  },
};

/** Authenticated file download (a plain <a> would miss the Bearer token). */
export async function downloadDocument(d: Document): Promise<void> {
  const token = getToken();
  const res = await fetch(`${API_BASE}/documents/${d.id}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status, `Download failed (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = d.filename || "download";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

export const commsApi = {
  list: (p?: ListParams) => get<Page<Communication>>(`/communications${qs(p)}`),
  create: (data: Partial<Communication>) => post<Communication>("/communications", data),
  thread: (type: string, id: string) => get<Communication[]>(`/communications/thread/${type}/${id}`),
};

export const exceptionsApi = {
  list: (p?: ListParams) => get<Page<ExceptionItem>>(`/exceptions${qs(p)}`),
  acknowledge: (id: string) => post<ExceptionItem>(`/exceptions/${id}/acknowledge`),
  resolve: (id: string, resolution: string) =>
    post<ExceptionItem>(`/exceptions/${id}/resolve`, { resolution }),
  assign: (id: string, user_id: string) => post<ExceptionItem>(`/exceptions/${id}/assign`, { user_id }),
};

export const notificationsApi = {
  list: (p?: ListParams) => get<Page<Notification>>(`/notifications${qs(p)}`),
  read: (id: string) => post<void>(`/notifications/${id}/read`),
  readAll: () => post<void>("/notifications/read-all"),
};

export const analyticsApi = {
  overview: () => get<AnalyticsOverview>("/analytics/overview"),
  financial: (p?: ListParams) => get<Record<string, unknown>>(`/analytics/financial${qs(p)}`),
  operational: (p?: ListParams) => get<Record<string, unknown>>(`/analytics/operational${qs(p)}`),
  carrier: (p?: ListParams) => get<Record<string, unknown>>(`/analytics/carrier${qs(p)}`),
  customer: (p?: ListParams) => get<Record<string, unknown>>(`/analytics/customer${qs(p)}`),
};

export const lanesApi = {
  list: (p?: ListParams) => get<Lane[]>("/lanes" + qs(p)),
  get: (id: string) => get<Lane>(`/lanes/${id}`),
};

export const auditApi = {
  list: (p?: ListParams) => get<Page<AuditLog>>(`/audit${qs(p)}`),
};

export const policiesApi = {
  list: (p?: ListParams) => get<Page<Policy>>(`/policies${qs(p)}`),
  create: (data: Partial<Policy>) => post<Policy>("/policies", data),
  get: (id: string) => get<Policy>(`/policies/${id}`),
  update: (id: string, data: Partial<Policy>) => put<Policy>(`/policies/${id}`, data),
  remove: (id: string) => del<void>(`/policies/${id}`),
};

export const agentsApi = {
  list: () => get<Agent[]>("/agents"),
  update: (id: string, data: Partial<Agent>) => put<Agent>(`/agents/${id}`, data),
};

export const approvalsApi = {
  list: (p?: ListParams) => get<Page<Approval>>(`/approvals${qs(p)}`),
  approve: (id: string) => post<Approval>(`/approvals/${id}/approve`),
  reject: (id: string, reason?: string) => post<Approval>(`/approvals/${id}/reject`, { reason }),
};

export const flagsApi = {
  list: () => get<FeatureFlag[]>("/feature-flags"),
  update: (key: string, data: Partial<FeatureFlag>) => put<FeatureFlag>(`/feature-flags`, { key, ...data }),
};

export const integrationsApi = {
  list: () => get<Integration[]>("/integrations"),
  update: (id: string, data: Partial<Integration>) => put<Integration>(`/integrations/${id}`, data),
};

export const settingsApi = {
  get: () => get<Record<string, unknown>>("/settings"),
  update: (data: Record<string, unknown>) => put<Record<string, unknown>>("/settings", data),
};

export const aiApi = {
  command: (message: string) => post<AICommandResponse>("/ai/command", { message }),
  matchCarriers: (load_id: string, top_n?: number) =>
    post<CarrierMatch[]>("/ai/match-carriers", { load_id, top_n }),
  optimizeRoute: (load_id: string) => post<RouteOptimization>("/ai/optimize-route", { load_id }),
  scanExceptions: () => post<{ created: ExceptionItem[] }>("/ai/exceptions/scan"),
  forecast: (type: string, periods?: number) =>
    post<ForecastResponse>("/ai/forecast", { type, periods }),
  proposeAction: (data: {
    agent: string;
    action_type: string;
    entity_type?: string;
    entity_id?: string;
    payload: Record<string, unknown>;
  }) => post<ProposeActionResponse>("/ai/actions/propose", data),
  usage: () => get<AIUsage[]>("/ai/usage"),
};
