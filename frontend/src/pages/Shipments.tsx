import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { shipmentsApi, customersApi, type Shipment } from "../api/client";
import { useFetch, useMutation } from "../lib/hooks";
import { fmtDateTime } from "../lib/format";
import { PageHeader, Field, FormAlert } from "../components/Page";
import DataTable, { type Column } from "../components/DataTable";
import StatusPill from "../components/StatusPill";
import Modal from "../components/Modal";

const SHIP_STATUSES = ["draft", "booked", "in_progress", "delivered", "cancelled"];

function ShipmentForm({ onDone, initial }: { onDone: () => void; initial?: Shipment }) {
  const customers = useFetch(() => customersApi.list({ page_size: 100 }), []);
  const save = useMutation((d: Partial<Shipment>) => (initial ? shipmentsApi.update(initial.id, d) : shipmentsApi.create(d)));
  const [form, setForm] = useState({
    customer_id: initial?.customer_id || "",
    reference_number: initial?.reference_number || "",
    pickup_appointment: initial?.pickup_appointment ? initial.pickup_appointment.slice(0, 16) : "",
    delivery_appointment: initial?.delivery_appointment ? initial.delivery_appointment.slice(0, 16) : "",
    special_instructions: initial?.special_instructions || "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!form.customer_id) errs.customer_id = "Customer required";
    if (!form.reference_number.trim()) errs.reference_number = "Reference required";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const r = await save.run({
      customer_id: form.customer_id,
      reference_number: form.reference_number.trim(),
      pickup_appointment: form.pickup_appointment ? new Date(form.pickup_appointment).toISOString() : undefined,
      delivery_appointment: form.delivery_appointment ? new Date(form.delivery_appointment).toISOString() : undefined,
      special_instructions: form.special_instructions,
    });
    if (r) onDone();
  };

  return (
    <form onSubmit={submit} className="form-grid">
      <Field label="Customer" required error={errors.customer_id}>
        <select className="input" value={form.customer_id} onChange={(e) => set("customer_id", e.target.value)}>
          <option value="">Select…</option>
          {customers.data?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </Field>
      <Field label="Reference #" required error={errors.reference_number}>
        <input className="input" value={form.reference_number} onChange={(e) => set("reference_number", e.target.value)} />
      </Field>
      <div className="form-row">
        <Field label="Pickup appointment">
          <input type="datetime-local" className="input" value={form.pickup_appointment} onChange={(e) => set("pickup_appointment", e.target.value)} />
        </Field>
        <Field label="Delivery appointment">
          <input type="datetime-local" className="input" value={form.delivery_appointment} onChange={(e) => set("delivery_appointment", e.target.value)} />
        </Field>
      </div>
      <Field label="Special instructions">
        <textarea className="input" rows={2} value={form.special_instructions} onChange={(e) => set("special_instructions", e.target.value)} />
      </Field>
      <FormAlert error={save.error} />
      <div className="form-foot">
        <button className="btn btn-primary" type="submit" disabled={save.loading}>
          {save.loading ? "Saving…" : initial ? "Save changes" : "Create shipment"}
        </button>
      </div>
    </form>
  );
}

export default function Shipments() {
  const navigate = useNavigate();
  const [showNew, setShowNew] = useState(false);
  const [editing, setEditing] = useState<Shipment | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const list = useFetch(() => shipmentsApi.list({ status: statusFilter || undefined, page_size: 50 }), [statusFilter]);
  const setStatus = useMutation((args: { id: string; status: string }) => shipmentsApi.setStatus(args.id, args.status));

  const columns: Column<Shipment>[] = [
    { key: "reference_number", header: "Reference", sortable: true, render: (s) => <span className="link strong" onClick={() => setEditing(s)}>{s.reference_number}</span> },
    { key: "status", header: "Status", render: (s) => <StatusPill status={s.status} /> },
    { key: "pickup_appointment", header: "Pickup", render: (s) => fmtDateTime(s.pickup_appointment) },
    { key: "delivery_appointment", header: "Delivery", render: (s) => fmtDateTime(s.delivery_appointment) },
    { key: "special_instructions", header: "Instructions", render: (s) => s.special_instructions || "—" },
  ];

  return (
    <div>
      <PageHeader
        title="Shipments"
        sub="Customer shipment orders"
        actions={
          <>
            <select className="input inline" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              {SHIP_STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
            </select>
            <button className="btn btn-primary" onClick={() => setShowNew(true)}>+ New shipment</button>
          </>
        }
      />
      <DataTable
        columns={columns}
        rows={list.data?.items || []}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        searchKeys={["reference_number", "special_instructions"]}
        emptyTitle="No shipments"
        emptyHint="Create a shipment to track customer orders."
        onRowClick={(s) => setEditing(s)}
      />
      {showNew && (
        <Modal title="New shipment" onClose={() => setShowNew(false)}>
          <ShipmentForm onDone={() => { setShowNew(false); list.reload(); }} />
        </Modal>
      )}
      {editing && (
        <Modal title={editing.reference_number} onClose={() => setEditing(null)} width={640}>
          <ShipmentForm initial={editing} onDone={() => { setEditing(null); list.reload(); }} />
          <div className="form-foot" style={{ borderTop: "1px solid var(--border)", marginTop: 16, paddingTop: 16 }}>
            <span className="muted small">Status:</span>
            <div className="btn-row">
              {SHIP_STATUSES.map((s) => (
                <button key={s} className={`btn btn-sm ${editing.status === s ? "btn-primary" : "btn-ghost"}`}
                  disabled={setStatus.loading}
                  onClick={async () => { const r = await setStatus.run({ id: editing.id, status: s }); if (r) { setEditing(null); list.reload(); } }}>
                  {s.replace(/_/g, " ")}
                </button>
              ))}
            </div>
            <FormAlert error={setStatus.error} />
          </div>
          <ShipmentLoads id={editing.id} onOpenLoad={(lid) => navigate(`/loads/${lid}`)} />
        </Modal>
      )}
    </div>
  );
}

function ShipmentLoads({ id, onOpenLoad }: { id: string; onOpenLoad: (lid: string) => void }) {
  const loads = useFetch(() => shipmentsApi.loads(id), [id]);
  return (
    <div style={{ marginTop: 16 }}>
      <h4>Loads</h4>
      {loads.loading ? <div className="skeleton-row" /> :
        loads.data && loads.data.length > 0 ? (
          <div className="card-list">
            {loads.data.map((l) => (
              <div key={l.id} className="list-row" onClick={() => onOpenLoad(l.id)}>
                <div className="list-main"><div className="list-title">{l.load_number}</div></div>
                <StatusPill status={l.status} />
              </div>
            ))}
          </div>
        ) : <div className="muted small">No loads linked to this shipment.</div>}
    </div>
  );
}
