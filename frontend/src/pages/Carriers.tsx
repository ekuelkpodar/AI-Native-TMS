import React, { useState } from "react";
import { carriersApi, type Carrier } from "../api/client";
import { useFetch, useMutation } from "../lib/hooks";
import { fmtPct } from "../lib/format";
import { PageHeader, Field, FormAlert } from "../components/Page";
import DataTable, { type Column } from "../components/DataTable";
import StatusPill from "../components/StatusPill";
import Modal from "../components/Modal";
import Drawer from "../components/Drawer";
import { BarChart } from "../components/Charts";

function CarrierForm({ onDone, initial }: { onDone: () => void; initial?: Carrier }) {
  const save = useMutation((d: Partial<Carrier>) => (initial ? carriersApi.update(initial.id, d) : carriersApi.create(d)));
  const [form, setForm] = useState({
    legal_name: initial?.legal_name || "",
    dba: initial?.dba || "",
    mc_number: initial?.mc_number || "",
    dot_number: initial?.dot_number || "",
    phone: initial?.phone || "",
    email: initial?.email || "",
    city: initial?.city || "",
    state: initial?.state || "",
    equipment_types: (initial?.equipment_types || []).join(", "),
    service_areas: (initial?.service_areas || []).join(", "),
    insurance_expiry: initial?.insurance_expiry ? initial.insurance_expiry.slice(0, 10) : "",
    compliance_status: initial?.compliance_status || "compliant",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!form.legal_name.trim()) errs.legal_name = "Legal name required";
    if (!form.mc_number.trim()) errs.mc_number = "MC number required";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const r = await save.run({
      legal_name: form.legal_name.trim(),
      dba: form.dba.trim(),
      mc_number: form.mc_number.trim(),
      dot_number: form.dot_number.trim(),
      phone: form.phone.trim(),
      email: form.email.trim(),
      city: form.city.trim(),
      state: form.state.trim(),
      equipment_types: form.equipment_types.split(",").map((s) => s.trim()).filter(Boolean),
      service_areas: form.service_areas.split(",").map((s) => s.trim()).filter(Boolean),
      insurance_expiry: form.insurance_expiry || undefined,
      compliance_status: form.compliance_status,
    });
    if (r) onDone();
  };

  return (
    <form onSubmit={submit} className="form-grid">
      <div className="form-row">
        <Field label="Legal name" required error={errors.legal_name}>
          <input className="input" value={form.legal_name} onChange={(e) => set("legal_name", e.target.value)} />
        </Field>
        <Field label="DBA">
          <input className="input" value={form.dba} onChange={(e) => set("dba", e.target.value)} />
        </Field>
      </div>
      <div className="form-row">
        <Field label="MC #" required error={errors.mc_number}>
          <input className="input" value={form.mc_number} onChange={(e) => set("mc_number", e.target.value)} />
        </Field>
        <Field label="DOT #">
          <input className="input" value={form.dot_number} onChange={(e) => set("dot_number", e.target.value)} />
        </Field>
      </div>
      <div className="form-row">
        <Field label="Phone"><input className="input" value={form.phone} onChange={(e) => set("phone", e.target.value)} /></Field>
        <Field label="Email"><input type="email" className="input" value={form.email} onChange={(e) => set("email", e.target.value)} /></Field>
      </div>
      <div className="form-row">
        <Field label="City"><input className="input" value={form.city} onChange={(e) => set("city", e.target.value)} /></Field>
        <Field label="State"><input className="input" value={form.state} onChange={(e) => set("state", e.target.value)} maxLength={2} /></Field>
        <Field label="Compliance">
          <select className="input" value={form.compliance_status} onChange={(e) => set("compliance_status", e.target.value)}>
            {["compliant", "warning", "expired"].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
      </div>
      <Field label="Equipment types (comma separated)">
        <input className="input" value={form.equipment_types} onChange={(e) => set("equipment_types", e.target.value)} placeholder="dry_van, reefer" />
      </Field>
      <Field label="Service areas (states, comma separated)">
        <input className="input" value={form.service_areas} onChange={(e) => set("service_areas", e.target.value)} placeholder="GA, TX, FL" />
      </Field>
      <Field label="Insurance expiry">
        <input type="date" className="input" value={form.insurance_expiry} onChange={(e) => set("insurance_expiry", e.target.value)} />
      </Field>
      <FormAlert error={save.error} />
      <div className="form-foot">
        <button className="btn btn-primary" type="submit" disabled={save.loading}>
          {save.loading ? "Saving…" : initial ? "Save changes" : "Add carrier"}
        </button>
      </div>
    </form>
  );
}

export default function Carriers() {
  const [showNew, setShowNew] = useState(false);
  const [editing, setEditing] = useState<Carrier | null>(null);
  const [scoring, setScoring] = useState<Carrier | null>(null);
  const list = useFetch(() => carriersApi.list({ page_size: 50, sort_by: "performance_score", sort_dir: "desc" }), []);

  const columns: Column<Carrier>[] = [
    { key: "legal_name", header: "Carrier", sortable: true, getValue: (c) => c.dba || c.legal_name, render: (c) => <><span className="strong">{c.dba || c.legal_name}</span><div className="muted small">MC {c.mc_number}</div></> },
    { key: "performance_score", header: "Score", sortable: true, getValue: (c) => c.performance_score, render: (c) => <b>{c.performance_score?.toFixed(0) ?? "—"}</b> },
    { key: "on_time_pct", header: "On-time", sortable: true, getValue: (c) => c.on_time_pct, render: (c) => fmtPct(c.on_time_pct) },
    { key: "acceptance_rate", header: "Accept", render: (c) => fmtPct(c.acceptance_rate) },
    { key: "compliance_status", header: "Compliance", render: (c) => <StatusPill status={c.compliance_status} /> },
    { key: "claims_count", header: "Claims", sortable: true, getValue: (c) => c.claims_count, render: (c) => c.claims_count },
  ];

  return (
    <div>
      <PageHeader
        title="Carriers"
        sub="Carrier network & performance"
        actions={<button className="btn btn-primary" onClick={() => setShowNew(true)}>+ Add carrier</button>}
      />
      <DataTable
        columns={columns}
        rows={list.data?.items || []}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        searchKeys={["legal_name", "dba", "mc_number", "dot_number"]}
        emptyTitle="No carriers"
        emptyHint="Add carriers to build your network."
        onRowClick={(c) => setScoring(c)}
        actions={(c) => (
          <button className="btn btn-ghost btn-sm" onClick={() => setEditing(c)}>Edit</button>
        )}
      />
      {showNew && (
        <Modal title="Add carrier" onClose={() => setShowNew(false)} width={640}>
          <CarrierForm onDone={() => { setShowNew(false); list.reload(); }} />
        </Modal>
      )}
      {editing && (
        <Modal title={`Edit ${editing.dba || editing.legal_name}`} onClose={() => setEditing(null)} width={640}>
          <CarrierForm initial={editing} onDone={() => { setEditing(null); list.reload(); }} />
        </Modal>
      )}
      {scoring && <ScoreDrawer carrier={scoring} onClose={() => setScoring(null)} />}
    </div>
  );
}

function ScoreDrawer({ carrier, onClose }: { carrier: Carrier; onClose: () => void }) {
  const score = useFetch(() => carriersApi.score(carrier.id), [carrier.id]);
  return (
    <Drawer title={`Score — ${carrier.dba || carrier.legal_name}`} onClose={onClose}>
      {score.loading ? <div className="skeleton-row" /> : score.error ? (
        <div className="muted">{score.error}</div>
      ) : score.data && (
        <>
          <div className="score-total">{score.data.score.toFixed(1)}<span className="muted">/100</span></div>
          <BarChart
            data={score.data.factors.map((f) => ({ label: f.name.replace(/_/g, " ").slice(0, 12), value: f.value }))}
            height={160}
          />
          <dl className="dl" style={{ marginTop: 12 }}>
            {score.data.factors.map((f, i) => (
              <React.Fragment key={i}>
                <dt>{f.name.replace(/_/g, " ")} <span className="muted">×{f.weight}</span></dt>
                <dd>{f.value.toFixed(1)} → {f.contribution.toFixed(1)}</dd>
              </React.Fragment>
            ))}
          </dl>
          {score.data.explanation && <p className="muted small">{score.data.explanation}</p>}
        </>
      )}
    </Drawer>
  );
}
