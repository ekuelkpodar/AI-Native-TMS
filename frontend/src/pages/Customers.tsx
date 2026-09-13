import React, { useState } from "react";
import { customersApi, type Customer } from "../api/client";
import { useFetch, useMutation } from "../lib/hooks";
import { fmtMoney } from "../lib/format";
import { PageHeader, Field, FormAlert } from "../components/Page";
import DataTable, { type Column } from "../components/DataTable";
import Modal from "../components/Modal";

function CustomerForm({ onDone, initial }: { onDone: () => void; initial?: Customer }) {
  const save = useMutation((d: Partial<Customer>) => (initial ? customersApi.update(initial.id, d) : customersApi.create(d)));
  const [form, setForm] = useState({
    name: initial?.name || "",
    contact_name: initial?.contact_name || "",
    email: initial?.email || "",
    phone: initial?.phone || "",
    street: initial?.street || "",
    city: initial?.city || "",
    state: initial?.state || "",
    zip: initial?.zip || "",
    credit_limit: initial?.credit_limit ? String(initial.credit_limit) : "",
    payment_terms: initial?.payment_terms || "Net 30",
    notes: initial?.notes || "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!form.name.trim()) errs.name = "Name required";
    if (form.email && !/^\S+@\S+\.\S+$/.test(form.email)) errs.email = "Invalid email";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const r = await save.run({
      name: form.name.trim(),
      contact_name: form.contact_name.trim(),
      email: form.email.trim(),
      phone: form.phone.trim(),
      street: form.street.trim(),
      city: form.city.trim(),
      state: form.state.trim(),
      zip: form.zip.trim(),
      credit_limit: Number(form.credit_limit) || 0,
      payment_terms: form.payment_terms,
      notes: form.notes,
    });
    if (r) onDone();
  };

  return (
    <form onSubmit={submit} className="form-grid">
      <Field label="Company name" required error={errors.name}>
        <input className="input" value={form.name} onChange={(e) => set("name", e.target.value)} />
      </Field>
      <div className="form-row">
        <Field label="Contact name"><input className="input" value={form.contact_name} onChange={(e) => set("contact_name", e.target.value)} /></Field>
        <Field label="Email" error={errors.email}><input type="email" className="input" value={form.email} onChange={(e) => set("email", e.target.value)} /></Field>
        <Field label="Phone"><input className="input" value={form.phone} onChange={(e) => set("phone", e.target.value)} /></Field>
      </div>
      <Field label="Street"><input className="input" value={form.street} onChange={(e) => set("street", e.target.value)} /></Field>
      <div className="form-row">
        <Field label="City"><input className="input" value={form.city} onChange={(e) => set("city", e.target.value)} /></Field>
        <Field label="State"><input className="input" value={form.state} onChange={(e) => set("state", e.target.value)} maxLength={2} /></Field>
        <Field label="ZIP"><input className="input" value={form.zip} onChange={(e) => set("zip", e.target.value)} /></Field>
      </div>
      <div className="form-row">
        <Field label="Credit limit ($)">
          <input type="number" step="0.01" className="input" value={form.credit_limit} onChange={(e) => set("credit_limit", e.target.value)} />
        </Field>
        <Field label="Payment terms">
          <select className="input" value={form.payment_terms} onChange={(e) => set("payment_terms", e.target.value)}>
            {["Net 15", "Net 30", "Net 45", "Net 60", "Due on receipt"].map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </Field>
      </div>
      <Field label="Notes"><textarea className="input" rows={2} value={form.notes} onChange={(e) => set("notes", e.target.value)} /></Field>
      <FormAlert error={save.error} />
      <div className="form-foot">
        <button className="btn btn-primary" type="submit" disabled={save.loading}>
          {save.loading ? "Saving…" : initial ? "Save changes" : "Add customer"}
        </button>
      </div>
    </form>
  );
}

export default function Customers() {
  const [showNew, setShowNew] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const list = useFetch(() => customersApi.list({ page_size: 50, sort_by: "name" }), []);

  const columns: Column<Customer>[] = [
    { key: "name", header: "Customer", sortable: true, getValue: (c) => c.name, render: (c) => <><span className="strong">{c.name}</span><div className="muted small">{c.contact_name}</div></> },
    { key: "email", header: "Contact", render: (c) => <>{c.email}<div className="muted small">{c.phone}</div></> },
    { key: "city", header: "Location", render: (c) => [c.city, c.state].filter(Boolean).join(", ") || "—" },
    { key: "credit_limit", header: "Credit limit", sortable: true, getValue: (c) => c.credit_limit, render: (c) => fmtMoney(c.credit_limit) },
    { key: "payment_terms", header: "Terms", render: (c) => c.payment_terms },
  ];

  return (
    <div>
      <PageHeader
        title="Customers"
        sub="Shippers & billing accounts"
        actions={<button className="btn btn-primary" onClick={() => setShowNew(true)}>+ Add customer</button>}
      />
      <DataTable
        columns={columns}
        rows={list.data?.items || []}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        searchKeys={["name", "contact_name", "email", "city"]}
        emptyTitle="No customers"
        emptyHint="Add customers to start booking freight."
        actions={(c) => (
          <button className="btn btn-ghost btn-sm" onClick={() => setEditing(c)}>Edit</button>
        )}
      />
      {showNew && (
        <Modal title="Add customer" onClose={() => setShowNew(false)} width={640}>
          <CustomerForm onDone={() => { setShowNew(false); list.reload(); }} />
        </Modal>
      )}
      {editing && (
        <Modal title={`Edit ${editing.name}`} onClose={() => setEditing(null)} width={640}>
          <CustomerForm initial={editing} onDone={() => { setEditing(null); list.reload(); }} />
        </Modal>
      )}
    </div>
  );
}
