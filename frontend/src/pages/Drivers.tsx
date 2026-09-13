import React, { useState } from "react";
import { driversApi, type Driver } from "../api/client";
import { useFetch, useMutation } from "../lib/hooks";
import { fmtPct } from "../lib/format";
import { PageHeader, Field, FormAlert } from "../components/Page";
import DataTable, { type Column } from "../components/DataTable";
import StatusPill from "../components/StatusPill";
import Modal from "../components/Modal";

const DRIVER_STATUSES = ["available", "assigned", "en_route", "at_pickup", "loading", "in_transit", "at_delivery", "off_duty", "unavailable"];

function DriverForm({ onDone, initial }: { onDone: () => void; initial?: Driver }) {
  const save = useMutation((d: Partial<Driver>) => (initial ? driversApi.update(initial.id, d) : driversApi.create(d)));
  const [form, setForm] = useState({
    full_name: initial?.full_name || "",
    phone: initial?.phone || "",
    email: initial?.email || "",
    license_number: initial?.license_number || "",
    license_expiry: initial?.license_expiry ? initial.license_expiry.slice(0, 10) : "",
    status: initial?.status || "available",
    hours_available: initial?.hours_available != null ? String(initial.hours_available) : "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!form.full_name.trim()) errs.full_name = "Name required";
    if (!form.license_number.trim()) errs.license_number = "License # required";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const r = await save.run({
      full_name: form.full_name.trim(),
      phone: form.phone.trim(),
      email: form.email.trim(),
      license_number: form.license_number.trim(),
      license_expiry: form.license_expiry || undefined,
      status: form.status,
      hours_available: Number(form.hours_available) || 0,
    });
    if (r) onDone();
  };

  return (
    <form onSubmit={submit} className="form-grid">
      <Field label="Full name" required error={errors.full_name}>
        <input className="input" value={form.full_name} onChange={(e) => set("full_name", e.target.value)} />
      </Field>
      <div className="form-row">
        <Field label="Phone"><input className="input" value={form.phone} onChange={(e) => set("phone", e.target.value)} /></Field>
        <Field label="Email"><input type="email" className="input" value={form.email} onChange={(e) => set("email", e.target.value)} /></Field>
      </div>
      <div className="form-row">
        <Field label="License #" required error={errors.license_number}>
          <input className="input" value={form.license_number} onChange={(e) => set("license_number", e.target.value)} />
        </Field>
        <Field label="License expiry">
          <input type="date" className="input" value={form.license_expiry} onChange={(e) => set("license_expiry", e.target.value)} />
        </Field>
      </div>
      <div className="form-row">
        <Field label="Status">
          <select className="input" value={form.status} onChange={(e) => set("status", e.target.value)}>
            {DRIVER_STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
          </select>
        </Field>
        <Field label="Hours available">
          <input type="number" step="0.5" className="input" value={form.hours_available} onChange={(e) => set("hours_available", e.target.value)} />
        </Field>
      </div>
      <FormAlert error={save.error} />
      <div className="form-foot">
        <button className="btn btn-primary" type="submit" disabled={save.loading}>
          {save.loading ? "Saving…" : initial ? "Save changes" : "Add driver"}
        </button>
      </div>
    </form>
  );
}

export default function Drivers() {
  const [showNew, setShowNew] = useState(false);
  const [editing, setEditing] = useState<Driver | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const list = useFetch(() => driversApi.list({ status: statusFilter || undefined, page_size: 50 }), [statusFilter]);

  const columns: Column<Driver>[] = [
    { key: "full_name", header: "Driver", sortable: true, getValue: (d) => d.full_name, render: (d) => <span className="strong">{d.full_name}</span> },
    { key: "status", header: "Status", render: (d) => <StatusPill status={d.status} /> },
    { key: "current_location", header: "Location", render: (d) => d.current_location ? `${d.current_location.city}, ${d.current_location.state}` : "—" },
    { key: "hours_available", header: "Hours", sortable: true, getValue: (d) => d.hours_available, render: (d) => d.hours_available },
    { key: "performance_score", header: "Score", sortable: true, getValue: (d) => d.performance_score, render: (d) => fmtPct(d.performance_score) },
    { key: "phone", header: "Phone", render: (d) => d.phone || "—" },
  ];

  return (
    <div>
      <PageHeader
        title="Drivers"
        sub="Driver roster & availability"
        actions={
          <>
            <select className="input inline" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              {DRIVER_STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
            </select>
            <button className="btn btn-primary" onClick={() => setShowNew(true)}>+ Add driver</button>
          </>
        }
      />
      <DataTable
        columns={columns}
        rows={list.data?.items || []}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        searchKeys={["full_name", "phone", "email", "license_number"]}
        emptyTitle="No drivers"
        emptyHint="Add drivers to staff your fleet."
        actions={(d) => (
          <button className="btn btn-ghost btn-sm" onClick={() => setEditing(d)}>Edit</button>
        )}
      />
      {showNew && (
        <Modal title="Add driver" onClose={() => setShowNew(false)}>
          <DriverForm onDone={() => { setShowNew(false); list.reload(); }} />
        </Modal>
      )}
      {editing && (
        <Modal title={`Edit ${editing.full_name}`} onClose={() => setEditing(null)}>
          <DriverForm initial={editing} onDone={() => { setEditing(null); list.reload(); }} />
        </Modal>
      )}
    </div>
  );
}
