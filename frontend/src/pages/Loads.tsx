import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { loadsApi, customersApi, type Load } from "../api/client";
import { useFetch, useMutation } from "../lib/hooks";
import { fmtDateTime, fmtMoney, loc } from "../lib/format";
import { PageHeader, Field, FormAlert } from "../components/Page";
import DataTable, { type Column } from "../components/DataTable";
import StatusPill from "../components/StatusPill";
import Modal from "../components/Modal";

const EQUIPMENT = ["dry_van", "reefer", "flatbed", "step_deck", "tanker", "box_truck", "other"];

export function LoadForm({ onDone, initial }: { onDone: () => void; initial?: Partial<Load> }) {
  const customers = useFetch(() => customersApi.list({ page_size: 100 }), []);
  const create = useMutation((d: Partial<Load>) => (initial?.id ? loadsApi.update(initial.id, d) : loadsApi.create(d)));
  const [form, setForm] = useState<Record<string, string>>({
    customer_id: initial?.customer_id || "",
    origin_city: initial?.origin?.city || "",
    origin_state: initial?.origin?.state || "",
    origin_zip: initial?.origin?.zip || "",
    dest_city: initial?.destination?.city || "",
    dest_state: initial?.destination?.state || "",
    dest_zip: initial?.destination?.zip || "",
    pickup_datetime: initial?.pickup_datetime ? initial.pickup_datetime.slice(0, 16) : "",
    delivery_datetime: initial?.delivery_datetime ? initial.delivery_datetime.slice(0, 16) : "",
    equipment_type: initial?.equipment_type || "dry_van",
    commodity: initial?.commodity || "",
    weight_lbs: initial?.weight_lbs ? String(initial.weight_lbs) : "",
    customer_rate: initial?.customer_rate ? String(initial.customer_rate) : "",
    carrier_rate: initial?.carrier_rate ? String(initial.carrier_rate) : "",
    distance_miles: initial?.distance_miles ? String(initial.distance_miles) : "",
    notes: initial?.notes || "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!form.customer_id) errs.customer_id = "Customer is required";
    if (!form.origin_city || !form.origin_state) errs.origin_city = "Origin city/state required";
    if (!form.dest_city || !form.dest_state) errs.dest_city = "Destination city/state required";
    if (!form.pickup_datetime) errs.pickup_datetime = "Pickup time required";
    if (!form.delivery_datetime) errs.delivery_datetime = "Delivery time required";
    if (form.weight_lbs && Number(form.weight_lbs) <= 0) errs.weight_lbs = "Must be positive";
    setErrors(errs);
    if (Object.keys(errs).length) return;

    const payload: Partial<Load> = {
      customer_id: form.customer_id,
      origin: { city: form.origin_city, state: form.origin_state, zip: form.origin_zip, lat: 0, lng: 0 },
      destination: { city: form.dest_city, state: form.dest_state, zip: form.dest_zip, lat: 0, lng: 0 },
      pickup_datetime: new Date(form.pickup_datetime).toISOString(),
      delivery_datetime: new Date(form.delivery_datetime).toISOString(),
      equipment_type: form.equipment_type,
      commodity: form.commodity,
      weight_lbs: Number(form.weight_lbs) || 0,
      customer_rate: Number(form.customer_rate) || 0,
      carrier_rate: Number(form.carrier_rate) || 0,
      distance_miles: Number(form.distance_miles) || 0,
      notes: form.notes,
    };
    const r = await create.run(payload);
    if (r) onDone();
  };

  return (
    <form onSubmit={submit} className="form-grid">
      <Field label="Customer" required error={errors.customer_id}>
        <select className="input" value={form.customer_id} onChange={(e) => set("customer_id", e.target.value)}>
          <option value="">Select…</option>
          {customers.data?.items.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </Field>
      <Field label="Equipment" error={errors.equipment_type}>
        <select className="input" value={form.equipment_type} onChange={(e) => set("equipment_type", e.target.value)}>
          {EQUIPMENT.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
        </select>
      </Field>
      <div className="form-row">
        <Field label="Origin city" required error={errors.origin_city}>
          <input className="input" value={form.origin_city} onChange={(e) => set("origin_city", e.target.value)} />
        </Field>
        <Field label="State" required>
          <input className="input" value={form.origin_state} onChange={(e) => set("origin_state", e.target.value)} maxLength={2} />
        </Field>
        <Field label="ZIP">
          <input className="input" value={form.origin_zip} onChange={(e) => set("origin_zip", e.target.value)} />
        </Field>
      </div>
      <div className="form-row">
        <Field label="Destination city" required error={errors.dest_city}>
          <input className="input" value={form.dest_city} onChange={(e) => set("dest_city", e.target.value)} />
        </Field>
        <Field label="State" required>
          <input className="input" value={form.dest_state} onChange={(e) => set("dest_state", e.target.value)} maxLength={2} />
        </Field>
        <Field label="ZIP">
          <input className="input" value={form.dest_zip} onChange={(e) => set("dest_zip", e.target.value)} />
        </Field>
      </div>
      <div className="form-row">
        <Field label="Pickup" required error={errors.pickup_datetime}>
          <input type="datetime-local" className="input" value={form.pickup_datetime} onChange={(e) => set("pickup_datetime", e.target.value)} />
        </Field>
        <Field label="Delivery" required error={errors.delivery_datetime}>
          <input type="datetime-local" className="input" value={form.delivery_datetime} onChange={(e) => set("delivery_datetime", e.target.value)} />
        </Field>
      </div>
      <div className="form-row">
        <Field label="Commodity">
          <input className="input" value={form.commodity} onChange={(e) => set("commodity", e.target.value)} />
        </Field>
        <Field label="Weight (lbs)" error={errors.weight_lbs}>
          <input type="number" className="input" value={form.weight_lbs} onChange={(e) => set("weight_lbs", e.target.value)} />
        </Field>
        <Field label="Distance (mi)">
          <input type="number" className="input" value={form.distance_miles} onChange={(e) => set("distance_miles", e.target.value)} />
        </Field>
      </div>
      <div className="form-row">
        <Field label="Customer rate ($)">
          <input type="number" step="0.01" className="input" value={form.customer_rate} onChange={(e) => set("customer_rate", e.target.value)} />
        </Field>
        <Field label="Carrier rate ($)">
          <input type="number" step="0.01" className="input" value={form.carrier_rate} onChange={(e) => set("carrier_rate", e.target.value)} />
        </Field>
      </div>
      <Field label="Notes">
        <textarea className="input" rows={2} value={form.notes} onChange={(e) => set("notes", e.target.value)} />
      </Field>
      <FormAlert error={create.error} success={create.success} />
      <div className="form-foot">
        <button type="submit" className="btn btn-primary" disabled={create.loading}>
          {create.loading ? "Saving…" : initial?.id ? "Save changes" : "Create load"}
        </button>
      </div>
    </form>
  );
}

export default function Loads() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [showNew, setShowNew] = useState(params.get("new") === "1");
  const [statusFilter, setStatusFilter] = useState("");
  const list = useFetch(
    () => loadsApi.list({ status: statusFilter || undefined, page_size: 50, sort_by: "created_at", sort_dir: "desc" }),
    [statusFilter]
  );

  const columns: Column<Load>[] = [
    { key: "load_number", header: "Load", sortable: true, render: (l) => <Link to={`/loads/${l.id}`} className="link strong">{l.load_number}</Link> },
    { key: "lane", header: "Lane", sortable: true, getValue: (l) => `${l.origin.city} ${l.destination.city}`, render: (l) => `${loc(l.origin)} → ${loc(l.destination)}` },
    { key: "status", header: "Status", render: (l) => <StatusPill status={l.status} /> },
    { key: "pickup_datetime", header: "Pickup", sortable: true, getValue: (l) => l.pickup_datetime, render: (l) => fmtDateTime(l.pickup_datetime) },
    { key: "delivery_datetime", header: "Delivery", sortable: true, getValue: (l) => l.delivery_datetime, render: (l) => fmtDateTime(l.delivery_datetime) },
    { key: "equipment_type", header: "Equipment", render: (l) => l.equipment_type.replace(/_/g, " ") },
    { key: "customer_rate", header: "Rate", sortable: true, getValue: (l) => l.customer_rate, render: (l) => fmtMoney(l.customer_rate) },
  ];

  return (
    <div>
      <PageHeader
        title="Loads"
        sub="All freight in the network"
        actions={
          <>
            <select className="input inline" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              {["draft", "quoted", "tendered", "available", "assigned", "confirmed", "dispatched", "at_pickup", "picked_up", "in_transit", "at_delivery", "delivered", "pod_received", "invoiced", "paid", "cancelled"].map((s) => (
                <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
              ))}
            </select>
            <button className="btn btn-primary" onClick={() => setShowNew(true)}>+ New load</button>
          </>
        }
      />
      <DataTable
        columns={columns}
        rows={list.data?.items || []}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        searchKeys={["load_number", "reference_number", "commodity"]}
        emptyTitle="No loads yet"
        emptyHint="Create your first load to get started."
        onRowClick={(l) => navigate(`/loads/${l.id}`)}
      />
      {showNew && (
        <Modal title="New load" onClose={() => setShowNew(false)} width={640}>
          <LoadForm onDone={() => { setShowNew(false); list.reload(); }} />
        </Modal>
      )}
    </div>
  );
}
