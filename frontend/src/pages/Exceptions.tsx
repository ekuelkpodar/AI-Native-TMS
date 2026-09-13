import React, { useState } from "react";
import { Link } from "react-router-dom";
import { exceptionsApi, usersApi, type ExceptionItem } from "../api/client";
import { useFetch, useMutation } from "../lib/hooks";
import { fmtDateTime } from "../lib/format";
import { PageHeader, Field, FormAlert } from "../components/Page";
import DataTable, { type Column } from "../components/DataTable";
import StatusPill from "../components/StatusPill";
import Modal from "../components/Modal";

const SEVERITIES = ["critical", "high", "medium", "low"];
const EXC_STATUSES = ["open", "acknowledged", "resolved"];

export default function Exceptions() {
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<ExceptionItem | null>(null);
  const list = useFetch(
    () => exceptionsApi.list({ severity: severity || undefined, status: status || undefined, page_size: 50, sort_by: "detected_at", sort_dir: "desc" }),
    [severity, status]
  );
  const ack = useMutation((id: string) => exceptionsApi.acknowledge(id));
  const resolve = useMutation((args: { id: string; resolution: string }) => exceptionsApi.resolve(args.id, args.resolution));

  const columns: Column<ExceptionItem>[] = [
    { key: "severity", header: "Severity", sortable: true, getValue: (x) => SEVERITIES.indexOf(x.severity), render: (x) => <StatusPill status={x.severity} /> },
    { key: "title", header: "Title", sortable: true, getValue: (x) => x.title, render: (x) => <span className="strong">{x.title}</span> },
    { key: "status", header: "Status", render: (x) => <StatusPill status={x.status} /> },
    { key: "load_id", header: "Load", render: (x) => x.load_id ? <Link className="link" to={`/loads/${x.load_id}`}>View load</Link> : "—" },
    { key: "detected_at", header: "Detected", sortable: true, getValue: (x) => x.detected_at, render: (x) => fmtDateTime(x.detected_at) },
  ];

  return (
    <div>
      <PageHeader
        title="Exceptions"
        sub="Detection, triage, and resolution"
        actions={
          <>
            <select className="input inline" value={severity} onChange={(e) => setSeverity(e.target.value)}>
              <option value="">All severities</option>
              {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <select className="input inline" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All statuses</option>
              {EXC_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </>
        }
      />
      <DataTable
        columns={columns}
        rows={list.data?.items || []}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        searchKeys={["title", "description", "exception_type"]}
        emptyTitle="No exceptions"
        emptyHint="The AI detection engine hasn't flagged anything."
        onRowClick={(x) => setSelected(x)}
        actions={(x) => (
          <div className="btn-row">
            {x.status === "open" && (
              <button className="btn btn-ghost btn-sm" onClick={async () => { await ack.run(x.id); list.reload(); }}>Ack</button>
            )}
            {x.status !== "resolved" && (
              <button className="btn btn-ghost btn-sm" onClick={() => setSelected(x)}>Resolve</button>
            )}
          </div>
        )}
      />
      {selected && (
        <ExceptionDrawer
          exc={selected}
          onClose={() => setSelected(null)}
          onDone={() => { setSelected(null); list.reload(); }}
          resolve={resolve}
        />
      )}
      <FormAlert error={ack.error} />
    </div>
  );
}

function ExceptionDrawer({
  exc, onClose, onDone, resolve,
}: {
  exc: ExceptionItem;
  onClose: () => void;
  onDone: () => void;
  resolve: ReturnType<typeof useMutation<[args: { id: string; resolution: string }], ExceptionItem>>;
}) {
  const [resolution, setResolution] = useState("");
  const [assignee, setAssignee] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const users = useFetch(() => usersApi.list({ page_size: 50 }), []);

  const doResolve = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resolution.trim()) { setErr("Resolution notes are required."); return; }
    const r = await resolve.run({ id: exc.id, resolution: resolution.trim() });
    if (r) onDone();
  };

  const doAssign = async () => {
    if (!assignee) return;
    try {
      await exceptionsApi.assign(exc.id, assignee);
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Assign failed");
    }
  };

  return (
    <Modal title={exc.title} onClose={onClose}>
      <div className="btn-row" style={{ marginBottom: 12 }}>
        <StatusPill status={exc.severity} />
        <StatusPill status={exc.status} />
        <span className="muted small">{exc.exception_type.replace(/_/g, " ")}</span>
      </div>
      <p>{exc.description}</p>
      {exc.recommended_action && (
        <div className="card" style={{ marginBottom: 12 }}>
          <b>Recommended action:</b> {exc.recommended_action}
        </div>
      )}
      {exc.history && exc.history.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <h4>History</h4>
          <ul className="history-list">
            {exc.history.map((h, i) => (
              <li key={i}>{fmtDateTime(h.at)} — {h.action}{h.by ? ` by ${h.by}` : ""}</li>
            ))}
          </ul>
        </div>
      )}
      {exc.status !== "resolved" && (
        <form onSubmit={doResolve}>
          <Field label="Assign to">
            <div className="assign-row">
              <select className="input" value={assignee} onChange={(e) => setAssignee(e.target.value)}>
                <option value="">Select user…</option>
                {users.data?.items.map((u) => <option key={u.id} value={u.id}>{u.full_name} ({u.role})</option>)}
              </select>
              <button type="button" className="btn btn-ghost btn-sm" onClick={doAssign} disabled={!assignee}>Assign</button>
            </div>
          </Field>
          <Field label="Resolution notes" required error={err || undefined}>
            <textarea className="input" rows={3} value={resolution} onChange={(e) => setResolution(e.target.value)} placeholder="How was this resolved?" />
          </Field>
          <FormAlert error={resolve.error} />
          <div className="form-foot">
            <button className="btn btn-primary" type="submit" disabled={resolve.loading}>
              {resolve.loading ? "Resolving…" : "Mark resolved"}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}

