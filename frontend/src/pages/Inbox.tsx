import React, { useState } from "react";
import { commsApi, type Communication } from "../api/client";
import { useFetch, useMutation } from "../lib/hooks";
import { fmtDateTime } from "../lib/format";
import { PageHeader, Field, FormAlert } from "../components/Page";
import EmptyState from "../components/EmptyState";
import Modal from "../components/Modal";

const CHANNELS = ["email", "sms", "in_app"];
const THREADS = ["load", "customer", "carrier", "driver"];

export default function Inbox() {
  const [channel, setChannel] = useState("");
  const [selected, setSelected] = useState<Communication | null>(null);
  const [showNew, setShowNew] = useState(false);
  const list = useFetch(
    () => commsApi.list({ channel: channel || undefined, page_size: 50, sort_by: "created_at", sort_dir: "desc" }),
    [channel]
  );

  return (
    <div>
      <PageHeader
        title="Inbox"
        sub="All communications — email, SMS, in-app"
        actions={
          <>
            <select className="input inline" value={channel} onChange={(e) => setChannel(e.target.value)}>
              <option value="">All channels</option>
              {CHANNELS.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
            </select>
            <button className="btn btn-primary" onClick={() => setShowNew(true)}>+ New message</button>
          </>
        }
      />
      {list.loading ? (
        <div className="skeleton-row" style={{ height: 200 }} />
      ) : list.error ? (
        <EmptyState title="Couldn't load messages" hint={list.error} action={<button className="btn btn-primary" onClick={list.reload}>Retry</button>} />
      ) : list.data && list.data.items.length > 0 ? (
        <div className="card-list">
          {list.data.items.map((c) => (
            <div key={c.id} className="list-row" onClick={() => setSelected(c)}>
              <span className={`pill pill-${c.channel === "email" ? "blue" : c.channel === "sms" ? "green" : "indigo"}`}>{c.channel}</span>
              <div className="list-main">
                <div className="list-title">{c.subject || "(no subject)"}</div>
                <div className="muted small">{c.sender} → {c.recipient} · {c.thread_type}</div>
              </div>
              <span className="muted small">{fmtDateTime(c.created_at)}</span>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title="No messages" hint="Communications will appear here." />
      )}
      {selected && (
        <Modal title={selected.subject || "Message"} onClose={() => setSelected(null)}>
          <dl className="dl">
            <dt>Channel</dt><dd>{selected.channel}</dd>
            <dt>Direction</dt><dd>{selected.direction}</dd>
            <dt>From</dt><dd>{selected.sender}</dd>
            <dt>To</dt><dd>{selected.recipient}</dd>
            <dt>Sent</dt><dd>{fmtDateTime(selected.created_at)}</dd>
          </dl>
          <p style={{ marginTop: 12, whiteSpace: "pre-wrap" }}>{selected.body}</p>
        </Modal>
      )}
      {showNew && (
        <ComposeModal onClose={() => setShowNew(false)} onDone={() => { setShowNew(false); list.reload(); }} />
      )}
    </div>
  );
}

function ComposeModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [form, setForm] = useState({ channel: "email", thread_type: "load", thread_id: "", recipient: "", subject: "", body: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const send = useMutation((d: Partial<Communication>) => commsApi.create(d));
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!form.recipient.trim()) errs.recipient = "Recipient required";
    if (!form.body.trim()) errs.body = "Message body required";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const r = await send.run({
      channel: form.channel,
      thread_type: form.thread_type,
      thread_id: form.thread_id || "general",
      direction: "out",
      sender: "dispatch",
      recipient: form.recipient.trim(),
      subject: form.subject.trim() || null,
      body: form.body.trim(),
    });
    if (r) onDone();
  };

  return (
    <Modal title="New message" onClose={onClose}>
      <form onSubmit={submit} className="form-grid">
        <div className="form-row">
          <Field label="Channel">
            <select className="input" value={form.channel} onChange={(e) => set("channel", e.target.value)}>
              {CHANNELS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </Field>
          <Field label="Thread">
            <select className="input" value={form.thread_type} onChange={(e) => set("thread_type", e.target.value)}>
              {THREADS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </Field>
        </div>
        <Field label="Recipient" required error={errors.recipient}>
          <input className="input" value={form.recipient} onChange={(e) => set("recipient", e.target.value)} placeholder="driver@carrier.com or +15551234567" />
        </Field>
        <Field label="Subject">
          <input className="input" value={form.subject} onChange={(e) => set("subject", e.target.value)} />
        </Field>
        <Field label="Message" required error={errors.body}>
          <textarea className="input" rows={4} value={form.body} onChange={(e) => set("body", e.target.value)} />
        </Field>
        <FormAlert error={send.error} />
        <div className="form-foot">
          <button className="btn btn-primary" type="submit" disabled={send.loading}>
            {send.loading ? "Sending…" : "Send"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
