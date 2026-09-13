import React, { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { aiApi, commsApi, documentsApi, downloadDocument, loadsApi, type RouteOptimization, type Stop } from "../api/client";
import { useFetch, useMutation } from "../lib/hooks";
import { fmtDateTime, fmtMoney, loc } from "../lib/format";
import { PageHeader, Field, FormAlert, Tabs } from "../components/Page";
import StatusPill from "../components/StatusPill";
import EmptyState from "../components/EmptyState";
import Modal from "../components/Modal";
import Drawer from "../components/Drawer";
import { LoadForm } from "./Loads";

const TRANSITIONS: Record<string, string[]> = {
  draft: ["quoted", "cancelled"], quoted: ["tendered", "cancelled"], tendered: ["available", "cancelled"],
  available: ["assigned", "cancelled"], assigned: ["confirmed", "dispatched", "cancelled"],
  confirmed: ["dispatched"], dispatched: ["at_pickup"], at_pickup: ["picked_up"],
  picked_up: ["in_transit"], in_transit: ["at_delivery"], at_delivery: ["delivered"],
  delivered: ["pod_received"], pod_received: ["invoiced"], invoiced: ["paid"],
};

export default function LoadDetail() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [tab, setTab] = useState<"stops" | "docs" | "comms" | "ai">("stops");
  const [showEdit, setShowEdit] = useState(false);
  const [showAssign, setShowAssign] = useState(false);
  const load = useFetch(() => loadsApi.get(id), [id]);
  const stops = useFetch(() => loadsApi.stops(id), [id, tab]);
  const docs = useFetch(() => documentsApi.list({ entity_type: "load", entity_id: id, page_size: 20 }), [id, tab]);
  const comms = useFetch(() => commsApi.thread("load", id), [id, tab]);

  const setStatus = useMutation((s: string) => loadsApi.setStatus(id, s));
  const duplicate = useMutation(() => loadsApi.duplicate(id));
  const cancel = useMutation(() => loadsApi.cancel(id));
  const assign = useMutation((d: { carrier_id?: string; driver_id?: string }) => loadsApi.assign(id, d));
  const matches = useFetch(() => aiApi.matchCarriers(id), []);
  const [optResult, setOptResult] = useState<RouteOptimization | null>(null);
  const optimize = useMutation(() => aiApi.optimizeRoute(id));

  const reloadAll = () => { load.reload(); stops.reload(); };

  if (load.loading) return <div className="skeleton-row" style={{ height: 200 }} />;
  if (load.error || !load.data) {
    return (
      <EmptyState
        title="Load not found"
        hint={load.error || undefined}
        action={<button className="btn btn-primary" onClick={() => navigate("/loads")}>Back to loads</button>}
      />
    );
  }
  const l = load.data;
  const margin = l.customer_rate - l.carrier_rate;
  const marginPct = l.customer_rate ? (margin / l.customer_rate) * 100 : 0;
  const nextStatuses = TRANSITIONS[l.status] || [];

  return (
    <div>
      <PageHeader
        title={l.load_number}
        sub={`${loc(l.origin)} → ${loc(l.destination)}`}
        actions={
          <>
            <StatusPill status={l.status} />
            <button className="btn btn-ghost" onClick={() => setShowEdit(true)}>Edit</button>
            <button className="btn btn-ghost" onClick={() => setShowAssign(true)}>Assign</button>
            <button className="btn btn-ghost" onClick={async () => { const r = await duplicate.run(); if (r) navigate(`/loads/${r.id}`); }}>Duplicate</button>
            <button className="btn btn-danger" onClick={async () => { if (confirm("Cancel this load?")) { const r = await cancel.run(); if (r) load.reload(); } }}>Cancel</button>
          </>
        }
      />
      <FormAlert error={setStatus.error || duplicate.error || cancel.error || assign.error} success={setStatus.success} />

      <div className="detail-grid">
        <div className="card">
          <h3>Overview</h3>
          <dl className="dl">
            <dt>Reference</dt><dd>{l.reference_number || "—"}</dd>
            <dt>Pickup</dt><dd>{fmtDateTime(l.pickup_datetime)}</dd>
            <dt>Delivery</dt><dd>{fmtDateTime(l.delivery_datetime)}</dd>
            <dt>Equipment</dt><dd>{l.equipment_type.replace(/_/g, " ")}</dd>
            <dt>Commodity</dt><dd>{l.commodity || "—"}</dd>
            <dt>Weight</dt><dd>{l.weight_lbs?.toLocaleString()} lbs</dd>
            <dt>Distance</dt><dd>{l.distance_miles?.toLocaleString()} mi</dd>
            {l.notes && <><dt>Notes</dt><dd>{l.notes}</dd></>}
          </dl>
        </div>
        <div className="card">
          <h3>Financials</h3>
          <dl className="dl">
            <dt>Customer rate</dt><dd>{fmtMoney(l.customer_rate)}</dd>
            <dt>Carrier rate</dt><dd>{fmtMoney(l.carrier_rate)}</dd>
            <dt>Margin</dt><dd className={margin < 0 ? "neg" : "pos"}>{fmtMoney(margin)}</dd>
            <dt>Margin %</dt><dd className={marginPct < 0 ? "neg" : "pos"}>{marginPct.toFixed(1)}%</dd>
          </dl>
        </div>
        <div className="card">
          <h3>Status transition</h3>
          {nextStatuses.length === 0 ? (
            <div className="muted">No further transitions available.</div>
          ) : (
            <div className="btn-row">
              {nextStatuses.map((s) => (
                <button key={s} className="btn btn-ghost btn-sm" disabled={setStatus.loading} onClick={async () => { const r = await setStatus.run(s); if (r) load.reload(); }}>
                  → {s.replace(/_/g, " ")}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <Tabs
        tabs={[{ key: "stops", label: "Stops" }, { key: "docs", label: "Documents" }, { key: "comms", label: "Communications" }, { key: "ai", label: "AI tools" }]}
        active={tab}
        onChange={setTab}
      />

      {tab === "stops" && (
        <div className="timeline">
          {stops.loading ? <div className="skeleton-row" /> :
            stops.data && stops.data.length > 0 ? stops.data.sort((a: Stop, b: Stop) => a.sequence - b.sequence).map((s: Stop) => (
              <div key={s.id} className="timeline-item">
                <div className="timeline-dot" />
                <div className="timeline-body">
                  <div className="timeline-head">
                    <b>Stop {s.sequence} · {s.stop_type}</b> <StatusPill status={s.status} />
                  </div>
                  <div className="muted small">{loc(s.location)}{s.location.zip ? ` ${s.location.zip}` : ""}</div>
                  {(s.appointment_start || s.appointment_end) && (
                    <div className="muted small">{fmtDateTime(s.appointment_start)} – {fmtDateTime(s.appointment_end)}</div>
                  )}
                  {s.notes && <div className="small">{s.notes}</div>}
                </div>
              </div>
            )) : <EmptyState title="No stops" hint="Stops will appear here once added." />}
        </div>
      )}

      {tab === "docs" && (
        <DocsTab docs={docs} loadId={id} onUpload={() => docs.reload()} />
      )}

      {tab === "comms" && (
        <div className="card-list">
          {comms.loading ? <div className="skeleton-row" /> :
            comms.data && comms.data.length > 0 ? comms.data.map((c) => (
              <div key={c.id} className="list-row">
                <div className="list-main">
                  <div className="list-title">{c.subject || c.channel} <span className="muted">· {c.direction}</span></div>
                  <div className="muted small">{c.sender} → {c.recipient}</div>
                  <div className="small">{c.body}</div>
                </div>
                <span className="muted small">{fmtDateTime(c.created_at)}</span>
              </div>
            )) : <EmptyState title="No messages" hint="Communication about this load will appear here." />}
        </div>
      )}

      {tab === "ai" && (
        <div className="two-col">
          <div className="card">
            <h3>Carrier matching</h3>
            {matches.loading ? <div className="skeleton-row" /> : matches.error ? <div className="muted">{matches.error}</div> :
              matches.data && matches.data.length > 0 ? matches.data.map((m, i) => (
                <div key={i} className="list-row">
                  <div className="list-main">
                    <div className="list-title">{m.carrier_name}</div>
                    <div className="muted small">{m.explanation}</div>
                  </div>
                  <b>{m.score.toFixed(0)}</b>
                </div>
              )) : <EmptyState title="No matches" hint="No carriers matched this load." />}
          </div>
          <div className="card">
            <h3>Route optimization</h3>
            <button className="btn btn-ghost" disabled={optimize.loading} onClick={async () => { const r = await optimize.run(); if (r) setOptResult(r); }}>
              {optimize.loading ? "Optimizing…" : "Optimize route"}
            </button>
            <FormAlert error={optimize.error} />
            {optResult && (
              <dl className="dl" style={{ marginTop: 12 }}>
                <dt>Miles saved</dt><dd>{optResult.savings.miles.toFixed(0)} mi</dd>
                <dt>Minutes saved</dt><dd>{optResult.savings.minutes.toFixed(0)} min</dd>
                <dt>Fuel saved</dt><dd>{fmtMoney(optResult.savings.fuel_usd, 2)}</dd>
                <dt>Cost saved</dt><dd>{fmtMoney(optResult.savings.cost_usd, 2)}</dd>
              </dl>
            )}
          </div>
        </div>
      )}

      {showEdit && (
        <Modal title={`Edit ${l.load_number}`} onClose={() => setShowEdit(false)} width={640}>
          <LoadForm initial={l} onDone={() => { setShowEdit(false); load.reload(); }} />
        </Modal>
      )}
      {showAssign && (
        <AssignDrawer loadId={id} onClose={() => setShowAssign(false)} onDone={reloadAll} />
      )}
    </div>
  );
}

function AssignDrawer({ loadId, onClose, onDone }: { loadId: string; onClose: () => void; onDone: () => void }) {
  const assign = useMutation((d: { carrier_id?: string; driver_id?: string }) => loadsApi.assign(loadId, d));
  const carriers = useFetch(() => aiApi.matchCarriers(loadId, 10), []);
  const [carrierId, setCarrierId] = useState("");
  const [driverId, setDriverId] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const r = await assign.run({ carrier_id: carrierId || undefined, driver_id: driverId || undefined });
    if (r) { onDone(); onClose(); }
  };

  return (
    <Drawer title="Assign load" onClose={onClose}>
      <form onSubmit={submit}>
        <Field label="Carrier (AI-ranked)">
          <select className="input" value={carrierId} onChange={(e) => setCarrierId(e.target.value)}>
            <option value="">Select…</option>
            {carriers.data?.map((m) => (
              <option key={m.carrier_id} value={m.carrier_id}>{m.carrier_name} (score {m.score.toFixed(0)})</option>
            ))}
          </select>
        </Field>
        <Field label="Driver ID">
          <input className="input" value={driverId} onChange={(e) => setDriverId(e.target.value)} placeholder="driver id" />
        </Field>
        <FormAlert error={assign.error} />
        <div className="form-foot">
          <button className="btn btn-primary" type="submit" disabled={assign.loading}>
            {assign.loading ? "Assigning…" : "Assign"}
          </button>
        </div>
      </form>
    </Drawer>
  );
}

export function DocsTab({ docs, loadId, onUpload }: { docs: { data: { items: import("../api/client").Document[] } | null; loading: boolean }; loadId: string; onUpload: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState("bol");
  const [dlError, setDlError] = useState<string | null>(null);
  const up = useMutation((f: File) => documentsApi.upload(f, "load", loadId, docType));

  const doDownload = async (d: import("../api/client").Document) => {
    setDlError(null);
    try {
      await downloadDocument(d);
    } catch (e) {
      setDlError(e instanceof Error ? e.message : "Download failed");
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    const r = await up.run(file);
    if (r) { setFile(null); onUpload(); }
  };

  return (
    <div>
      <form onSubmit={submit} className="upload-row">
        <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        <select className="input inline" value={docType} onChange={(e) => setDocType(e.target.value)}>
          {["bol", "pod", "rate_confirmation", "invoice", "other"].map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
        </select>
        <button className="btn btn-primary btn-sm" type="submit" disabled={!file || up.loading}>
          {up.loading ? "Uploading…" : "Upload"}
        </button>
      </form>
      <FormAlert error={up.error || dlError} success={up.success} />
      {docs.loading ? <div className="skeleton-row" /> :
        docs.data && docs.data.items.length > 0 ? (
          <div className="card-list">
            {docs.data.items.map((d) => (
              <div key={d.id} className="list-row">
                <div className="list-main">
                  <div className="list-title">{d.filename}</div>
                  <div className="muted small">{d.doc_type.replace(/_/g, " ")} · {(d.size_bytes / 1024).toFixed(1)} KB · v{d.version}</div>
                </div>
                <button className="btn btn-ghost btn-sm" onClick={() => doDownload(d)}>Download</button>
              </div>
            ))}
          </div>
        ) : <EmptyState title="No documents" hint="Upload BOLs, PODs, or rate confirmations." />}
    </div>
  );
}
