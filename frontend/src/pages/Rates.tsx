import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ratesApi, type Rate, type QuoteResult } from "../api/client";
import { useFetch, useMutation } from "../lib/hooks";
import { fmtMoney, fmtPct } from "../lib/format";
import { PageHeader, Field, FormAlert } from "../components/Page";
import DataTable, { type Column } from "../components/DataTable";
import StatusPill from "../components/StatusPill";
import Modal from "../components/Modal";

function RateForm({ onDone, initial }: { onDone: () => void; initial?: Rate }) {
  const save = useMutation((d: Partial<Rate>) => (initial ? ratesApi.update(initial.id, d) : ratesApi.create(d)));
  const [form, setForm] = useState({
    origin_city: initial?.origin_city || "",
    origin_state: initial?.origin_state || "",
    dest_city: initial?.dest_city || "",
    dest_state: initial?.dest_state || "",
    equipment_type: initial?.equipment_type || "dry_van",
    customer_rate: initial?.customer_rate ? String(initial.customer_rate) : "",
    carrier_rate: initial?.carrier_rate ? String(initial.carrier_rate) : "",
    rate_type: initial?.rate_type || "spot",
    fuel_surcharge: initial?.fuel_surcharge ? String(initial.fuel_surcharge) : "",
    effective_from: initial?.effective_from ? initial.effective_from.slice(0, 10) : "",
    effective_to: initial?.effective_to ? initial.effective_to.slice(0, 10) : "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!form.origin_city || !form.origin_state) errs.origin = "Origin city/state required";
    if (!form.dest_city || !form.dest_state) errs.dest = "Destination city/state required";
    if (Number(form.customer_rate) <= 0) errs.customer_rate = "Customer rate must be positive";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const r = await save.run({
      origin_city: form.origin_city, origin_state: form.origin_state,
      dest_city: form.dest_city, dest_state: form.dest_state,
      equipment_type: form.equipment_type,
      customer_rate: Number(form.customer_rate),
      carrier_rate: Number(form.carrier_rate) || 0,
      rate_type: form.rate_type,
      fuel_surcharge: Number(form.fuel_surcharge) || 0,
      effective_from: form.effective_from || undefined,
      effective_to: form.effective_to || undefined,
    });
    if (r) onDone();
  };

  return (
    <form onSubmit={submit} className="form-grid">
      <div className="form-row">
        <Field label="Origin city" required error={errors.origin}>
          <input className="input" value={form.origin_city} onChange={(e) => set("origin_city", e.target.value)} />
        </Field>
        <Field label="State" required><input className="input" value={form.origin_state} onChange={(e) => set("origin_state", e.target.value)} maxLength={2} /></Field>
        <Field label="Dest city" required error={errors.dest}>
          <input className="input" value={form.dest_city} onChange={(e) => set("dest_city", e.target.value)} />
        </Field>
        <Field label="State" required><input className="input" value={form.dest_state} onChange={(e) => set("dest_state", e.target.value)} maxLength={2} /></Field>
      </div>
      <div className="form-row">
        <Field label="Equipment">
          <select className="input" value={form.equipment_type} onChange={(e) => set("equipment_type", e.target.value)}>
            {["dry_van", "reefer", "flatbed", "step_deck", "tanker", "box_truck", "other"].map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
          </select>
        </Field>
        <Field label="Type">
          <select className="input" value={form.rate_type} onChange={(e) => set("rate_type", e.target.value)}>
            <option value="spot">Spot</option>
            <option value="contract">Contract</option>
          </select>
        </Field>
      </div>
      <div className="form-row">
        <Field label="Customer rate ($)" required error={errors.customer_rate}>
          <input type="number" step="0.01" className="input" value={form.customer_rate} onChange={(e) => set("customer_rate", e.target.value)} />
        </Field>
        <Field label="Carrier rate ($)">
          <input type="number" step="0.01" className="input" value={form.carrier_rate} onChange={(e) => set("carrier_rate", e.target.value)} />
        </Field>
        <Field label="Fuel surcharge ($)">
          <input type="number" step="0.01" className="input" value={form.fuel_surcharge} onChange={(e) => set("fuel_surcharge", e.target.value)} />
        </Field>
      </div>
      <div className="form-row">
        <Field label="Effective from"><input type="date" className="input" value={form.effective_from} onChange={(e) => set("effective_from", e.target.value)} /></Field>
        <Field label="Effective to"><input type="date" className="input" value={form.effective_to} onChange={(e) => set("effective_to", e.target.value)} /></Field>
      </div>
      <FormAlert error={save.error} />
      <div className="form-foot">
        <button className="btn btn-primary" type="submit" disabled={save.loading}>
          {save.loading ? "Saving…" : initial ? "Save changes" : "Add rate"}
        </button>
      </div>
    </form>
  );
}

export default function Rates() {
  const [params] = useSearchParams();
  const [showNew, setShowNew] = useState(false);
  const [editing, setEditing] = useState<Rate | null>(null);
  const [showQuote, setShowQuote] = useState(params.get("quote") === "1");
  const list = useFetch(() => ratesApi.list({ page_size: 50 }), []);

  const columns: Column<Rate>[] = [
    { key: "lane", header: "Lane", sortable: true, getValue: (r) => `${r.origin_city} ${r.dest_city}`, render: (r) => <><span className="strong">{r.origin_city}, {r.origin_state} → {r.dest_city}, {r.dest_state}</span><div className="muted small">{r.equipment_type.replace(/_/g, " ")}</div></> },
    { key: "rate_type", header: "Type", render: (r) => <StatusPill status={r.rate_type} /> },
    { key: "customer_rate", header: "Customer", sortable: true, getValue: (r) => r.customer_rate, render: (r) => fmtMoney(r.customer_rate) },
    { key: "carrier_rate", header: "Carrier", sortable: true, getValue: (r) => r.carrier_rate, render: (r) => fmtMoney(r.carrier_rate) },
    { key: "margin", header: "Margin", render: (r) => {
      const m = r.customer_rate - r.carrier_rate;
      const pct = r.customer_rate ? (m / r.customer_rate) * 100 : 0;
      return <span className={m < 0 ? "neg" : "pos"}>{fmtMoney(m)} ({fmtPct(pct)})</span>;
    } },
  ];

  return (
    <div>
      <PageHeader
        title="Rates"
        sub="Lane pricing book & quote calculator"
        actions={
          <>
            <button className="btn btn-ghost" onClick={() => setShowQuote(true)}>$ Quote calculator</button>
            <button className="btn btn-primary" onClick={() => setShowNew(true)}>+ Add rate</button>
          </>
        }
      />
      <DataTable
        columns={columns}
        rows={list.data?.items || []}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        searchKeys={["origin_city", "dest_city", "origin_state", "dest_state"]}
        emptyTitle="No rates"
        emptyHint="Add lane rates or get a quote."
        actions={(r) => (
          <button className="btn btn-ghost btn-sm" onClick={() => setEditing(r)}>Edit</button>
        )}
      />
      {showNew && (
        <Modal title="Add rate" onClose={() => setShowNew(false)} width={640}>
          <RateForm onDone={() => { setShowNew(false); list.reload(); }} />
        </Modal>
      )}
      {editing && (
        <Modal title="Edit rate" onClose={() => setEditing(null)} width={640}>
          <RateForm initial={editing} onDone={() => { setEditing(null); list.reload(); }} />
        </Modal>
      )}
      {showQuote && <QuoteModal onClose={() => setShowQuote(false)} />}
    </div>
  );
}

function QuoteModal({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState({ origin: "", destination: "", equipment_type: "dry_van", weight_lbs: "", distance_miles: "" });
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [result, setResult] = useState<QuoteResult | null>(null);
  const quote = useMutation((d: Parameters<typeof ratesApi.quote>[0]) => ratesApi.quote(d));
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!form.origin.trim()) errs.origin = "Origin required";
    if (!form.destination.trim()) errs.destination = "Destination required";
    setErrs(errs);
    if (Object.keys(errs).length) return;
    const r = await quote.run({
      origin: form.origin.trim(),
      destination: form.destination.trim(),
      equipment_type: form.equipment_type,
      weight_lbs: Number(form.weight_lbs) || undefined,
      distance_miles: Number(form.distance_miles) || undefined,
    });
    if (r) setResult(r);
  };

  return (
    <Modal title="Rate quote calculator" onClose={onClose}>
      <form onSubmit={submit} className="form-grid">
        <div className="form-row">
          <Field label="Origin" required error={errs.origin}>
            <input className="input" value={form.origin} onChange={(e) => set("origin", e.target.value)} placeholder="Atlanta, GA" />
          </Field>
          <Field label="Destination" required error={errs.destination}>
            <input className="input" value={form.destination} onChange={(e) => set("destination", e.target.value)} placeholder="Dallas, TX" />
          </Field>
        </div>
        <div className="form-row">
          <Field label="Equipment">
            <select className="input" value={form.equipment_type} onChange={(e) => set("equipment_type", e.target.value)}>
              {["dry_van", "reefer", "flatbed", "step_deck", "tanker", "box_truck", "other"].map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
            </select>
          </Field>
          <Field label="Weight (lbs)"><input type="number" className="input" value={form.weight_lbs} onChange={(e) => set("weight_lbs", e.target.value)} /></Field>
          <Field label="Distance (mi)"><input type="number" className="input" value={form.distance_miles} onChange={(e) => set("distance_miles", e.target.value)} /></Field>
        </div>
        <FormAlert error={quote.error} />
        <div className="form-foot">
          <button className="btn btn-primary" type="submit" disabled={quote.loading}>
            {quote.loading ? "Quoting…" : "Get quote"}
          </button>
        </div>
      </form>
      {result && (
        <div className="card" style={{ marginTop: 16 }}>
          <dl className="dl">
            <dt>Customer rate</dt><dd>{fmtMoney(result.customer_rate)}</dd>
            <dt>Carrier rate</dt><dd>{fmtMoney(result.carrier_rate)}</dd>
            <dt>Margin</dt><dd className={result.margin < 0 ? "neg" : "pos"}>{fmtMoney(result.margin)} ({fmtPct(result.margin_pct)})</dd>
            <dt>Basis</dt><dd className="muted small">{result.basis}</dd>
          </dl>
        </div>
      )}
    </Modal>
  );
}
