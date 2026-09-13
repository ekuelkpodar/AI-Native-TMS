import React, { useState } from "react";
import {
  usersApi, policiesApi, agentsApi, approvalsApi, flagsApi, integrationsApi,
  auditApi, settingsApi, getStoredUser,
  type User, type Policy, type Agent, type Approval, type FeatureFlag, type Integration,
} from "../api/client";
import { useFetch, useMutation } from "../lib/hooks";
import { fmtDateTime } from "../lib/format";
import { PageHeader, Field, FormAlert, Tabs } from "../components/Page";
import DataTable, { type Column } from "../components/DataTable";
import StatusPill from "../components/StatusPill";
import Modal from "../components/Modal";
import EmptyState from "../components/EmptyState";

type AdminTab = "users" | "roles" | "policies" | "agents" | "approvals" | "flags" | "integrations" | "audit" | "settings";

// Role → scopes from ARCHITECTURE.md §3.2 (enforced server-side)
const ROLE_MATRIX: { role: string; scopes: string }[] = [
  { role: "admin", scopes: "all" },
  { role: "broker", scopes: "loads, shipments, customers, carriers, rates, dispatch:write, documents, communications, exceptions:read, ai:use, invoices:read" },
  { role: "dispatcher", scopes: "loads:read/write(assign,status), shipments, drivers, fleet, dispatch:write, tracking, exceptions:*, communications, ai:use" },
  { role: "carrier", scopes: "loads:read (assigned), loads:write(status accept/decline), documents:write, communications" },
  { role: "driver", scopes: "assignments:read, loads:write(status own), documents:write (POD)" },
  { role: "shipper", scopes: "shipments:* (own), loads:read (own), invoices:read (own), documents:read" },
  { role: "finance", scopes: "invoices:*, payments, rates:read, analytics:read(financial)" },
  { role: "ops_manager", scopes: "analytics:read, exceptions:*, policies:read, lanes:read, ai:use" },
];

export default function Admin() {
  const user = getStoredUser();
  const [tab, setTab] = useState<AdminTab>("users");
  if (user?.role !== "admin") {
    return <EmptyState title="Not authorized" hint="Admin role required." />;
  }
  return (
    <div>
      <PageHeader title="Admin" sub="Organization configuration & governance" />
      <Tabs
        tabs={[
          { key: "users", label: "Users" },
          { key: "roles", label: "Roles" },
          { key: "policies", label: "Policies" },
          { key: "agents", label: "Agents" },
          { key: "approvals", label: "Approvals" },
          { key: "flags", label: "Feature flags" },
          { key: "integrations", label: "Integrations" },
          { key: "audit", label: "Audit log" },
          { key: "settings", label: "Settings" },
        ]}
        active={tab}
        onChange={setTab}
      />
      {tab === "users" && <UsersTab />}
      {tab === "roles" && <RolesTab />}
      {tab === "policies" && <PoliciesTab />}
      {tab === "agents" && <AgentsTab />}
      {tab === "approvals" && <ApprovalsTab />}
      {tab === "flags" && <FlagsTab />}
      {tab === "integrations" && <IntegrationsTab />}
      {tab === "audit" && <AuditTab />}
      {tab === "settings" && <SettingsTab />}
    </div>
  );
}

/* ------------------------------ Users ---------------------------------- */

const USER_ROLES = ["admin", "broker", "dispatcher", "carrier", "driver", "shipper", "finance", "ops_manager"];

function UsersTab() {
  const [showNew, setShowNew] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const list = useFetch(() => usersApi.list({ page_size: 50 }), []);

  const columns: Column<User>[] = [
    { key: "full_name", header: "Name", sortable: true, getValue: (u) => u.full_name, render: (u) => <span className="strong">{u.full_name}</span> },
    { key: "email", header: "Email", sortable: true, getValue: (u) => u.email, render: (u) => u.email },
    { key: "role", header: "Role", render: (u) => <span className="pill pill-indigo">{u.role}</span> },
    { key: "is_active", header: "Active", render: (u) => <StatusPill status={u.is_active ? "active" : "disabled"} /> },
  ];

  return (
    <div>
      <div className="tab-actions"><button className="btn btn-primary" onClick={() => setShowNew(true)}>+ Add user</button></div>
      <DataTable
        columns={columns}
        rows={list.data?.items || []}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        searchKeys={["full_name", "email", "role"]}
        emptyTitle="No users"
        actions={(u) => (
          <div className="btn-row">
            <button className="btn btn-ghost btn-sm" onClick={() => setEditing(u)}>Edit</button>
            <button className="btn btn-ghost btn-sm danger" onClick={async () => { if (confirm(`Delete ${u.email}?`)) { await usersApi.remove(u.id); list.reload(); } }}>Delete</button>
          </div>
        )}
      />
      {showNew && (
        <Modal title="Add user" onClose={() => setShowNew(false)}>
          <UserForm onDone={() => { setShowNew(false); list.reload(); }} />
        </Modal>
      )}
      {editing && (
        <Modal title={`Edit ${editing.full_name}`} onClose={() => setEditing(null)}>
          <UserForm initial={editing} onDone={() => { setEditing(null); list.reload(); }} />
        </Modal>
      )}
    </div>
  );
}

function UserForm({ onDone, initial }: { onDone: () => void; initial?: User }) {
  const save = useMutation((d: Partial<User> & { password?: string }) =>
    initial ? usersApi.update(initial.id, d) : usersApi.create(d as Partial<User> & { password: string })
  );
  const [form, setForm] = useState({
    full_name: initial?.full_name || "",
    email: initial?.email || "",
    role: initial?.role || "dispatcher",
    password: "",
    is_active: initial?.is_active ?? true,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (k: string, v: string | boolean) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!form.full_name.trim()) errs.full_name = "Name required";
    if (!/^\S+@\S+\.\S+$/.test(form.email)) errs.email = "Invalid email";
    if (!initial && form.password.length < 8) errs.password = "Min 8 characters";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const payload: Partial<User> & { password?: string } = {
      full_name: form.full_name.trim(),
      email: form.email.trim(),
      role: form.role,
      is_active: form.is_active,
    };
    if (form.password) payload.password = form.password;
    const r = await save.run(payload);
    if (r) onDone();
  };

  return (
    <form onSubmit={submit} className="form-grid">
      <Field label="Full name" required error={errors.full_name}>
        <input className="input" value={form.full_name} onChange={(e) => set("full_name", e.target.value)} />
      </Field>
      <Field label="Email" required error={errors.email}>
        <input type="email" className="input" value={form.email} onChange={(e) => set("email", e.target.value)} />
      </Field>
      <div className="form-row">
        <Field label="Role">
          <select className="input" value={form.role} onChange={(e) => set("role", e.target.value)}>
            {USER_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </Field>
        <Field label="Password" required={!initial} error={errors.password}>
          <input type="password" className="input" value={form.password} onChange={(e) => set("password", e.target.value)} placeholder={initial ? "(leave blank to keep)" : ""} />
        </Field>
      </div>
      <Field label="Active">
        <input type="checkbox" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} />
      </Field>
      <FormAlert error={save.error} />
      <div className="form-foot">
        <button className="btn btn-primary" type="submit" disabled={save.loading}>
          {save.loading ? "Saving…" : initial ? "Save changes" : "Create user"}
        </button>
      </div>
    </form>
  );
}

/* ------------------------------ Roles ---------------------------------- */

function RolesTab() {
  return (
    <div className="card">
      <h3>Role matrix</h3>
      <p className="muted small">Defined by the platform (ARCHITECTURE.md §3.2). Enforced server-side; scoped roles additionally filter to their own records.</p>
      <table className="table">
        <thead><tr><th>Role</th><th>Scopes</th></tr></thead>
        <tbody>
          {ROLE_MATRIX.map((r) => (
            <tr key={r.role}>
              <td><span className="pill pill-indigo">{r.role}</span></td>
              <td className="small">{r.scopes}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ----------------------------- Policies -------------------------------- */

function PoliciesTab() {
  const [showNew, setShowNew] = useState(false);
  const [editing, setEditing] = useState<Policy | null>(null);
  const list = useFetch(() => policiesApi.list({ page_size: 50, sort_by: "priority" }), []);

  const columns: Column<Policy>[] = [
    { key: "priority", header: "Priority", sortable: true, getValue: (p) => p.priority, render: (p) => p.priority },
    { key: "name", header: "Policy", sortable: true, getValue: (p) => p.name, render: (p) => <><span className="strong">{p.name}</span><div className="muted small">{p.description}</div></> },
    { key: "effect", header: "Effect", render: (p) => <StatusPill status={p.rule?.effect} /> },
    { key: "is_active", header: "Active", render: (p) => <StatusPill status={p.is_active ? "active" : "disabled"} /> },
  ];

  return (
    <div>
      <div className="tab-actions"><button className="btn btn-primary" onClick={() => setShowNew(true)}>+ Add policy</button></div>
      <DataTable
        columns={columns}
        rows={list.data?.items || []}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        searchKeys={["name", "description"]}
        emptyTitle="No policies"
        emptyHint="Policies gate every AI action (allow / require_approval / deny / notify)."
        actions={(p) => (
          <div className="btn-row">
            <button className="btn btn-ghost btn-sm" onClick={() => setEditing(p)}>Edit</button>
            <button className="btn btn-ghost btn-sm danger" onClick={async () => { if (confirm(`Delete ${p.name}?`)) { await policiesApi.remove(p.id); list.reload(); } }}>Delete</button>
          </div>
        )}
      />
      {(showNew || editing) && (
        <Modal title={editing ? `Edit ${editing.name}` : "New policy"} onClose={() => { setShowNew(false); setEditing(null); }} width={640}>
          <PolicyForm
            initial={editing || undefined}
            onDone={() => { setShowNew(false); setEditing(null); list.reload(); }}
          />
        </Modal>
      )}
    </div>
  );
}

function PolicyForm({ onDone, initial }: { onDone: () => void; initial?: Policy }) {
  const save = useMutation((d: Partial<Policy>) => (initial ? policiesApi.update(initial.id, d) : policiesApi.create(d)));
  const [form, setForm] = useState({
    name: initial?.name || "",
    description: initial?.description || "",
    priority: initial?.priority ? String(initial.priority) : "100",
    effect: initial?.rule?.effect || "require_approval",
    conditions: JSON.stringify(initial?.rule?.conditions || [{ field: "", op: "==", value: "" }], null, 2),
    is_active: initial?.is_active ?? true,
  });
  const [err, setErr] = useState<string | null>(null);
  const set = (k: string, v: string | boolean) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    let conditions: { field: string; op: string; value: unknown }[] = [];
    try {
      conditions = JSON.parse(form.conditions);
      if (!Array.isArray(conditions)) throw new Error("must be an array");
    } catch (e) {
      setErr(`Conditions must be valid JSON: ${e instanceof Error ? e.message : ""}`);
      return;
    }
    if (!form.name.trim()) { setErr("Name is required."); return; }
    const r = await save.run({
      name: form.name.trim(),
      description: form.description.trim(),
      priority: Number(form.priority) || 0,
      rule: { conditions, effect: form.effect },
      is_active: form.is_active,
    });
    if (r) onDone();
  };

  return (
    <form onSubmit={submit} className="form-grid">
      <div className="form-row">
        <Field label="Name" required><input className="input" value={form.name} onChange={(e) => set("name", e.target.value)} /></Field>
        <Field label="Priority"><input type="number" className="input" value={form.priority} onChange={(e) => set("priority", e.target.value)} /></Field>
      </div>
      <Field label="Description"><textarea className="input" rows={2} value={form.description} onChange={(e) => set("description", e.target.value)} /></Field>
      <Field label="Effect">
        <select className="input" value={form.effect} onChange={(e) => set("effect", e.target.value)}>
          {["allow", "require_approval", "deny", "notify"].map((x) => <option key={x} value={x}>{x}</option>)}
        </select>
      </Field>
      <Field label="Conditions (JSON array of {field, op, value})">
        <textarea className="input mono" rows={5} value={form.conditions} onChange={(e) => set("conditions", e.target.value)} />
      </Field>
      <Field label="Active"><input type="checkbox" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} /></Field>
      <FormAlert error={err || save.error} />
      <div className="form-foot">
        <button className="btn btn-primary" type="submit" disabled={save.loading}>
          {save.loading ? "Saving…" : initial ? "Save changes" : "Create policy"}
        </button>
      </div>
    </form>
  );
}

/* ------------------------------ Agents --------------------------------- */

function AgentsTab() {
  const list = useFetch(() => agentsApi.list(), []);
  const toggle = useMutation((a: Agent) =>
    agentsApi.update(a.id, { status: a.status === "active" ? "paused" : "active" })
  );

  return (
    <div className="card-list">
      {list.loading ? <div className="skeleton-row" /> : list.error ? (
        <EmptyState title="Couldn't load agents" hint={list.error} action={<button className="btn btn-primary" onClick={list.reload}>Retry</button>} />
      ) : list.data && list.data.length > 0 ? list.data.map((a) => (
        <div key={a.id} className="list-row">
          <div className="list-main">
            <div className="list-title">{a.name} <span className="muted small">v{a.version} · {a.model}</span></div>
            <div className="muted small">Autonomy L{a.autonomy_level} · Risk {a.risk_level} · Tools: {a.tools.join(", ") || "—"}</div>
          </div>
          <StatusPill status={a.status} />
          <button
            className="btn btn-ghost btn-sm"
            disabled={toggle.loading}
            onClick={async () => { await toggle.run(a); list.reload(); }}
          >
            {a.status === "active" ? "Pause" : "Activate"}
          </button>
        </div>
      )) : <EmptyState title="No agents registered" />}
      <FormAlert error={toggle.error} />
    </div>
  );
}

/* ---------------------------- Approvals -------------------------------- */

function ApprovalsTab() {
  const [status, setStatus] = useState("pending");
  const list = useFetch(() => approvalsApi.list({ status: status || undefined, page_size: 50 }), [status]);
  const act = useMutation((args: { id: string; kind: "approve" | "reject" }) =>
    args.kind === "approve" ? approvalsApi.approve(args.id) : approvalsApi.reject(args.id)
  );

  return (
    <div>
      <div className="tab-actions">
        <select className="input inline" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="pending">Pending</option>
          <option value="">All</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="expired">Expired</option>
        </select>
      </div>
      {list.loading ? <div className="skeleton-row" /> : list.error ? (
        <EmptyState title="Couldn't load approvals" hint={list.error} action={<button className="btn btn-primary" onClick={list.reload}>Retry</button>} />
      ) : list.data && list.data.items.length > 0 ? (
        <div className="card-list">
          {list.data.items.map((a) => (
            <ApprovalRow key={a.id} a={a} act={act} onDone={list.reload} />
          ))}
        </div>
      ) : <EmptyState title="No approvals" hint="Approval-gated AI actions will queue here." />}
      <FormAlert error={act.error} />
    </div>
  );
}

function ApprovalRow({ a, act, onDone }: {
  a: Approval;
  act: ReturnType<typeof useMutation<[args: { id: string; kind: "approve" | "reject" }], Approval>>;
  onDone: () => void;
}) {
  return (
    <div className="list-row">
      <StatusPill status={a.risk_level} />
      <div className="list-main">
        <div className="list-title">{a.action_type} <span className="muted small">by {a.agent_name}</span></div>
        <div className="muted small">{a.reason}</div>
        <details className="small" style={{ marginTop: 4 }}>
          <summary className="muted">Payload</summary>
          <pre>{JSON.stringify(a.payload, null, 2)}</pre>
        </details>
      </div>
      <StatusPill status={a.status} />
      {a.status === "pending" && (
        <div className="btn-row">
          <button className="btn btn-primary btn-sm" disabled={act.loading} onClick={async () => { const r = await act.run({ id: a.id, kind: "approve" }); if (r) onDone(); }}>Approve</button>
          <button className="btn btn-ghost btn-sm" disabled={act.loading} onClick={async () => { const r = await act.run({ id: a.id, kind: "reject" }); if (r) onDone(); }}>Reject</button>
        </div>
      )}
    </div>
  );
}

/* --------------------------- Feature flags ----------------------------- */

function FlagsTab() {
  const list = useFetch(() => flagsApi.list(), []);
  const save = useMutation((f: FeatureFlag) => flagsApi.update(f.key, { enabled: !f.enabled }));

  return (
    <div className="card-list">
      {list.loading ? <div className="skeleton-row" /> : list.error ? (
        <EmptyState title="Couldn't load flags" hint={list.error} action={<button className="btn btn-primary" onClick={list.reload}>Retry</button>} />
      ) : list.data && list.data.length > 0 ? list.data.map((f) => (
        <div key={f.id} className="list-row">
          <div className="list-main">
            <div className="list-title mono">{f.key}</div>
            {f.config && <div className="muted small"><pre>{JSON.stringify(f.config)}</pre></div>}
          </div>
          <StatusPill status={f.enabled ? "active" : "disabled"} />
          <button className="btn btn-ghost btn-sm" disabled={save.loading} onClick={async () => { await save.run(f); list.reload(); }}>
            {f.enabled ? "Disable" : "Enable"}
          </button>
        </div>
      )) : <EmptyState title="No feature flags" />}
      <FormAlert error={save.error} />
    </div>
  );
}

/* ---------------------------- Integrations ----------------------------- */

function IntegrationsTab() {
  const list = useFetch(() => integrationsApi.list(), []);
  const save = useMutation((i: Integration) =>
    integrationsApi.update(i.id, { status: i.status === "connected" ? "disabled" : "connected" })
  );

  return (
    <div className="card-list">
      {list.loading ? <div className="skeleton-row" /> : list.error ? (
        <EmptyState title="Couldn't load integrations" hint={list.error} action={<button className="btn btn-primary" onClick={list.reload}>Retry</button>} />
      ) : list.data && list.data.length > 0 ? list.data.map((i) => (
        <div key={i.id} className="list-row">
          <div className="list-main">
            <div className="list-title">{i.provider}</div>
            <div className="muted small">{i.last_sync ? `Last sync ${fmtDateTime(i.last_sync)}` : "Never synced"}</div>
          </div>
          <StatusPill status={i.status} />
          <button className="btn btn-ghost btn-sm" disabled={save.loading} onClick={async () => { await save.run(i); list.reload(); }}>
            {i.status === "connected" ? "Disable" : "Connect"}
          </button>
        </div>
      )) : <EmptyState title="No integrations" />}
      <FormAlert error={save.error} />
    </div>
  );
}

/* ------------------------------ Audit log ------------------------------ */

function AuditTab() {
  const [action, setAction] = useState("");
  const list = useFetch(() => auditApi.list({ search: action || undefined, page_size: 50, sort_by: "created_at", sort_dir: "desc" }), [action]);

  const columns: Column<import("../api/client").AuditLog>[] = [
    { key: "created_at", header: "Time", sortable: true, getValue: (a) => a.created_at, render: (a) => fmtDateTime(a.created_at) },
    { key: "actor_name", header: "Actor", render: (a) => <>{a.actor_name}<div className="muted small">{a.actor_type}</div></> },
    { key: "action", header: "Action", sortable: true, getValue: (a) => a.action, render: (a) => <span className="mono small">{a.action}</span> },
    { key: "entity_type", header: "Entity", render: (a) => <>{a.entity_type}<div className="muted small">{a.entity_id ? String(a.entity_id).slice(0, 8) : ""}</div></> },
  ];

  return (
    <div>
      <div className="tab-actions">
        <input className="input inline" placeholder="Filter action/actor…" value={action} onChange={(e) => setAction(e.target.value)} />
      </div>
      <DataTable
        columns={columns}
        rows={list.data?.items || []}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        searchKeys={["action", "actor_name", "entity_type"]}
        emptyTitle="No audit entries"
      />
    </div>
  );
}

/* ------------------------------ Settings ------------------------------- */

function SettingsTab() {
  const state = useFetch(() => settingsApi.get(), []);
  const [json, setJson] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const save = useMutation((d: Record<string, unknown>) => settingsApi.update(d));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (json == null) return;
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(json);
    } catch {
      setErr("Settings must be valid JSON.");
      return;
    }
    const r = await save.run(parsed);
    if (r) { setErr(null); state.reload(); }
  };

  return (
    <div className="card">
      <h3>Organization settings</h3>
      {state.loading ? <div className="skeleton-row" /> : state.error ? (
        <EmptyState title="Couldn't load settings" hint={state.error} action={<button className="btn btn-primary" onClick={state.reload}>Retry</button>} />
      ) : (
        <form onSubmit={submit}>
          <Field label="Settings (JSON)">
            <textarea
              className="input mono"
              rows={14}
              value={json ?? JSON.stringify(state.data, null, 2)}
              onChange={(e) => setJson(e.target.value)}
            />
          </Field>
          <FormAlert error={err || save.error} success={save.success} />
          <div className="form-foot">
            <button className="btn btn-primary" type="submit" disabled={save.loading}>
              {save.loading ? "Saving…" : "Save settings"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
