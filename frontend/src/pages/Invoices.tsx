import React, { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { invoicesApi, customersApi, loadsApi, type Invoice } from "../api/client";
import { useFetch, useMutation } from "../lib/hooks";
import { fmtDate, fmtMoney } from "../lib/format";
import { PageHeader, Field, FormAlert } from "../components/Page";
import DataTable, { type Column } from "../components/DataTable";
import StatusPill from "../components/StatusPill";
import Modal from "../components/Modal";
import EmptyState from "../components/EmptyState";

function InvoiceForm({ onDone }: { onDone: () => void }) {
  const customers = useFetch(() => customersApi.list({ page_size: 100 }), []);
  const loads = useFetch(() => loadsApi.list({ page_size: 100, sort_by: "created_at", sort_dir: "desc" }), []);
  const create = useMutation((d: Partial<Invoice>) => invoicesApi.create(d));
  const [form, setForm] = useState({
    customer_id: "", load_id: "", due_date: "", notes: "",
    items: [{ description: "", amount: "" }],
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const setItem = (i: number, k: string, v: string) =>
    setForm((f) => ({ ...f, items: f.items.map((it, j) => (j === i ? { ...it, [k]: v } : it)) }));

  const subtotal = form.items.reduce((s, it) => s + (Number(it.amount) || 0), 0);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!form.customer_id) errs.customer_id = "Customer required";
    if (!form.due_date) errs.due_date = "Due date required";
    if (!form.items.some((it) => it.description.trim() && Number(it.amount) > 0))
      errs.items = "Add at least one line item with a description and amount";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const r = await create.run({
      customer_id: form.customer_id,
      load_id: form.load_id || undefined,
      due_date: new Date(form.due_date).toISOString(),
      issue_date: new Date().toISOString(),
      line_items: form.items.filter((it) => it.description.trim()).map((it) => ({ description: it.description.trim(), amount: Number(it.amount) || 0 })),
      subtotal,
      tax: 0,
      total: subtotal,
      notes: form.notes,
    });
    if (r) onDone();
  };

  return (
    <form onSubmit={submit} className="form-grid">
      <div className="form-row">
        <Field label="Customer" required error={errors.customer_id}>
          <select className="input" value={form.customer_id} onChange={(e) => set("customer_id", e.target.value)}>
            <option value="">Select…</option>
            {customers.data?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </Field>
        <Field label="Load (optional)">
          <select className="input" value={form.load_id} onChange={(e) => set("load_id", e.target.value)}>
            <option value="">None</option>
            {loads.data?.items.map((l) => <option key={l.id} value={l.id}>{l.load_number}</option>)}
          </select>
        </Field>
        <Field label="Due date" required error={errors.due_date}>
          <input type="date" className="input" value={form.due_date} onChange={(e) => set("due_date", e.target.value)} />
        </Field>
      </div>
      <div>
        <span className="field-label">Line items</span>
        {errors.items && <div className="field-error">{errors.items}</div>}
        {form.items.map((it, i) => (
          <div key={i} className="line-item-row">
            <input className="input" placeholder="Description" value={it.description} onChange={(e) => setItem(i, "description", e.target.value)} />
            <input type="number" step="0.01" className="input" placeholder="Amount" value={it.amount} onChange={(e) => setItem(i, "amount", e.target.value)} />
            <button type="button" className="icon-btn" onClick={() => setForm((f) => ({ ...f, items: f.items.filter((_, j) => j !== i) }))}>✕</button>
          </div>
        ))}
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setForm((f) => ({ ...f, items: [...f.items, { description: "", amount: "" }] }))}>
          + Add line
        </button>
        <div className="muted small" style={{ marginTop: 6 }}>Subtotal: {fmtMoney(subtotal, 2)}</div>
      </div>
      <Field label="Notes"><textarea className="input" rows={2} value={form.notes} onChange={(e) => set("notes", e.target.value)} /></Field>
      <FormAlert error={create.error} />
      <div className="form-foot">
        <button className="btn btn-primary" type="submit" disabled={create.loading}>
          {create.loading ? "Creating…" : "Create invoice"}
        </button>
      </div>
    </form>
  );
}

export default function Invoices() {
  const navigate = useNavigate();
  const [showNew, setShowNew] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const list = useFetch(
    () => invoicesApi.list({ status: statusFilter || undefined, page_size: 50, sort_by: "created_at", sort_dir: "desc" }),
    [statusFilter]
  );

  const columns: Column<Invoice>[] = [
    { key: "invoice_number", header: "Invoice", sortable: true, getValue: (i) => i.invoice_number, render: (i) => <span className="strong">{i.invoice_number}</span> },
    { key: "status", header: "Status", render: (i) => <StatusPill status={i.status} /> },
    { key: "total", header: "Total", sortable: true, getValue: (i) => i.total, render: (i) => fmtMoney(i.total, 2) },
    { key: "amount_paid", header: "Paid", render: (i) => fmtMoney(i.amount_paid, 2) },
    { key: "due_date", header: "Due", sortable: true, getValue: (i) => i.due_date, render: (i) => fmtDate(i.due_date) },
  ];

  return (
    <div>
      <PageHeader
        title="Invoices"
        sub="Billing & receivables"
        actions={
          <>
            <select className="input inline" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              {["draft", "issued", "paid", "overdue", "void"].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <button className="btn btn-primary" onClick={() => setShowNew(true)}>+ New invoice</button>
          </>
        }
      />
      <DataTable
        columns={columns}
        rows={list.data?.items || []}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        searchKeys={["invoice_number", "notes"]}
        emptyTitle="No invoices"
        emptyHint="Create an invoice from a delivered load."
        onRowClick={(i) => navigate(`/invoices/${i.id}`)}
      />
      {showNew && (
        <Modal title="New invoice" onClose={() => setShowNew(false)} width={680}>
          <InvoiceForm onDone={() => { setShowNew(false); list.reload(); }} />
        </Modal>
      )}
    </div>
  );
}

export function InvoiceDetail() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const inv = useFetch(() => invoicesApi.get(id), [id]);
  const [payOpen, setPayOpen] = useState(false);
  const issue = useMutation(() => invoicesApi.issue(id));

  if (inv.loading) return <div className="skeleton-row" style={{ height: 200 }} />;
  if (inv.error || !inv.data) {
    return (
      <EmptyState title="Invoice not found" hint={inv.error || undefined}
        action={<button className="btn btn-primary" onClick={() => navigate("/invoices")}>Back to invoices</button>} />
    );
  }
  const i = inv.data;
  const balance = i.total - i.amount_paid;

  return (
    <div>
      <PageHeader
        title={i.invoice_number}
        sub={`Issued ${fmtDate(i.issue_date)} · Due ${fmtDate(i.due_date)}`}
        actions={
          <>
            <StatusPill status={i.status} />
            {i.status === "draft" && (
              <button className="btn btn-ghost" disabled={issue.loading} onClick={async () => { const r = await issue.run(); if (r) inv.reload(); }}>
                {issue.loading ? "Issuing…" : "Issue invoice"}
              </button>
            )}
            {balance > 0 && i.status !== "void" && (
              <button className="btn btn-primary" onClick={() => setPayOpen(true)}>Record payment</button>
            )}
          </>
        }
      />
      <FormAlert error={issue.error} />
      <div className="detail-grid">
        <div className="card">
          <h3>Line items</h3>
          {i.line_items.length === 0 ? <div className="muted">No line items.</div> : (
            <table className="table">
              <thead><tr><th>Description</th><th style={{ textAlign: "right" }}>Amount</th></tr></thead>
              <tbody>
                {i.line_items.map((li, idx) => (
                  <tr key={idx}><td>{li.description}</td><td style={{ textAlign: "right" }}>{fmtMoney(li.amount, 2)}</td></tr>
                ))}
              </tbody>
            </table>
          )}
          <dl className="dl" style={{ marginTop: 12 }}>
            <dt>Subtotal</dt><dd>{fmtMoney(i.subtotal, 2)}</dd>
            <dt>Tax</dt><dd>{fmtMoney(i.tax, 2)}</dd>
            <dt>Total</dt><dd><b>{fmtMoney(i.total, 2)}</b></dd>
            <dt>Paid</dt><dd>{fmtMoney(i.amount_paid, 2)}</dd>
            <dt>Balance</dt><dd className={balance > 0 ? "neg" : "pos"}><b>{fmtMoney(balance, 2)}</b></dd>
          </dl>
        </div>
        <div className="card">
          <h3>Details</h3>
          <dl className="dl">
            <dt>Status</dt><dd><StatusPill status={i.status} /></dd>
            {i.load_id && <><dt>Load</dt><dd><span className="link" onClick={() => navigate(`/loads/${i.load_id}`)}>View load →</span></dd></>}
            {i.notes && <><dt>Notes</dt><dd>{i.notes}</dd></>}
          </dl>
        </div>
      </div>
      {payOpen && (
        <PayModal invoiceId={id} balance={balance} onClose={() => setPayOpen(false)} onDone={() => { setPayOpen(false); inv.reload(); }} />
      )}
    </div>
  );
}

function PayModal({ invoiceId, balance, onClose, onDone }: { invoiceId: string; balance: number; onClose: () => void; onDone: () => void }) {
  const [amount, setAmount] = useState(balance > 0 ? balance.toFixed(2) : "");
  const [method, setMethod] = useState("ach");
  const [err, setErr] = useState<string | null>(null);
  const pay = useMutation((d: { amount: number; method: string }) => invoicesApi.pay(invoiceId, d.amount, d.method));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const a = Number(amount);
    if (!(a > 0)) { setErr("Amount must be greater than 0"); return; }
    if (a > balance + 0.001) { setErr(`Amount exceeds balance of ${fmtMoney(balance, 2)}`); return; }
    const r = await pay.run({ amount: a, method });
    if (r) onDone();
  };

  return (
    <Modal title="Record payment" onClose={onClose}>
      <form onSubmit={submit} className="form-grid">
        <div className="form-row">
          <Field label="Amount ($)" required error={err || undefined}>
            <input type="number" step="0.01" className="input" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </Field>
          <Field label="Method">
            <select className="input" value={method} onChange={(e) => setMethod(e.target.value)}>
              {["ach", "wire", "check", "card", "cash"].map((m) => <option key={m} value={m}>{m.toUpperCase()}</option>)}
            </select>
          </Field>
        </div>
        <FormAlert error={pay.error} />
        <div className="form-foot">
          <button className="btn btn-primary" type="submit" disabled={pay.loading}>
            {pay.loading ? "Recording…" : "Record payment"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
