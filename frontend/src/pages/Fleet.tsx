import React, { useState } from "react";
import { vehiclesApi, type Vehicle } from "../api/client";
import { useFetch, useMutation } from "../lib/hooks";
import { fmtNum } from "../lib/format";
import { PageHeader, Field, FormAlert } from "../components/Page";
import DataTable, { type Column } from "../components/DataTable";
import StatusPill from "../components/StatusPill";
import Modal from "../components/Modal";

const VEH_TYPES = ["truck", "trailer", "van", "other"];
const AVAIL = ["available", "assigned", "maintenance", "out_of_service"];

function VehicleForm({ onDone, initial }: { onDone: () => void; initial?: Vehicle }) {
  const save = useMutation((d: Partial<Vehicle>) => (initial ? vehiclesApi.update(initial.id, d) : vehiclesApi.create(d)));
  const [form, setForm] = useState({
    unit_number: initial?.unit_number || "",
    vin: initial?.vin || "",
    license_plate: initial?.license_plate || "",
    make: initial?.make || "",
    model: initial?.model || "",
    year: initial?.year ? String(initial.year) : "",
    vehicle_type: initial?.vehicle_type || "truck",
    capacity_lbs: initial?.capacity_lbs ? String(initial.capacity_lbs) : "",
    mileage: initial?.mileage ? String(initial.mileage) : "",
    availability_status: initial?.availability_status || "available",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!form.unit_number.trim()) errs.unit_number = "Unit # required";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const r = await save.run({
      unit_number: form.unit_number.trim(),
      vin: form.vin.trim(),
      license_plate: form.license_plate.trim(),
      make: form.make.trim(),
      model: form.model.trim(),
      year: Number(form.year) || undefined,
      vehicle_type: form.vehicle_type,
      capacity_lbs: Number(form.capacity_lbs) || 0,
      mileage: Number(form.mileage) || 0,
      availability_status: form.availability_status,
    });
    if (r) onDone();
  };

  return (
    <form onSubmit={submit} className="form-grid">
      <div className="form-row">
        <Field label="Unit #" required error={errors.unit_number}>
          <input className="input" value={form.unit_number} onChange={(e) => set("unit_number", e.target.value)} />
        </Field>
        <Field label="Type">
          <select className="input" value={form.vehicle_type} onChange={(e) => set("vehicle_type", e.target.value)}>
            {VEH_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </Field>
        <Field label="Availability">
          <select className="input" value={form.availability_status} onChange={(e) => set("availability_status", e.target.value)}>
            {AVAIL.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
          </select>
        </Field>
      </div>
      <div className="form-row">
        <Field label="Make"><input className="input" value={form.make} onChange={(e) => set("make", e.target.value)} /></Field>
        <Field label="Model"><input className="input" value={form.model} onChange={(e) => set("model", e.target.value)} /></Field>
        <Field label="Year"><input type="number" className="input" value={form.year} onChange={(e) => set("year", e.target.value)} /></Field>
      </div>
      <div className="form-row">
        <Field label="VIN"><input className="input" value={form.vin} onChange={(e) => set("vin", e.target.value)} /></Field>
        <Field label="Plate"><input className="input" value={form.license_plate} onChange={(e) => set("license_plate", e.target.value)} /></Field>
      </div>
      <div className="form-row">
        <Field label="Capacity (lbs)"><input type="number" className="input" value={form.capacity_lbs} onChange={(e) => set("capacity_lbs", e.target.value)} /></Field>
        <Field label="Mileage"><input type="number" className="input" value={form.mileage} onChange={(e) => set("mileage", e.target.value)} /></Field>
      </div>
      <FormAlert error={save.error} />
      <div className="form-foot">
        <button className="btn btn-primary" type="submit" disabled={save.loading}>
          {save.loading ? "Saving…" : initial ? "Save changes" : "Add vehicle"}
        </button>
      </div>
    </form>
  );
}

export default function Fleet() {
  const [showNew, setShowNew] = useState(false);
  const [editing, setEditing] = useState<Vehicle | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const list = useFetch(() => vehiclesApi.list({ status: statusFilter || undefined, page_size: 50 }), [statusFilter]);

  const columns: Column<Vehicle>[] = [
    { key: "unit_number", header: "Unit", sortable: true, getValue: (v) => v.unit_number, render: (v) => <span className="strong">{v.unit_number}</span> },
    { key: "vehicle_type", header: "Type", render: (v) => v.vehicle_type },
    { key: "make", header: "Make/Model", render: (v) => [v.make, v.model, v.year].filter(Boolean).join(" ") || "—" },
    { key: "availability_status", header: "Status", render: (v) => <StatusPill status={v.availability_status} /> },
    { key: "capacity_lbs", header: "Capacity", sortable: true, getValue: (v) => v.capacity_lbs, render: (v) => v.capacity_lbs ? `${fmtNum(v.capacity_lbs)} lbs` : "—" },
    { key: "mileage", header: "Mileage", sortable: true, getValue: (v) => v.mileage, render: (v) => v.mileage ? `${fmtNum(v.mileage)} mi` : "—" },
    { key: "license_plate", header: "Plate", render: (v) => v.license_plate || "—" },
  ];

  return (
    <div>
      <PageHeader
        title="Fleet"
        sub="Tractors, trailers & equipment"
        actions={
          <>
            <select className="input inline" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              {AVAIL.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
            </select>
            <button className="btn btn-primary" onClick={() => setShowNew(true)}>+ Add vehicle</button>
          </>
        }
      />
      <DataTable
        columns={columns}
        rows={list.data?.items || []}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        searchKeys={["unit_number", "vin", "license_plate", "make", "model"]}
        emptyTitle="No vehicles"
        emptyHint="Add vehicles to your fleet."
        actions={(v) => (
          <button className="btn btn-ghost btn-sm" onClick={() => setEditing(v)}>Edit</button>
        )}
      />
      {showNew && (
        <Modal title="Add vehicle" onClose={() => setShowNew(false)} width={640}>
          <VehicleForm onDone={() => { setShowNew(false); list.reload(); }} />
        </Modal>
      )}
      {editing && (
        <Modal title={`Edit ${editing.unit_number}`} onClose={() => setEditing(null)} width={640}>
          <VehicleForm initial={editing} onDone={() => { setEditing(null); list.reload(); }} />
        </Modal>
      )}
    </div>
  );
}
