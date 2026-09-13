import React, { useState } from "react";
import { documentsApi, downloadDocument, loadsApi, type Document } from "../api/client";
import { useFetch, useMutation } from "../lib/hooks";
import { fmtDateTime } from "../lib/format";
import { PageHeader, Field, FormAlert } from "../components/Page";
import DataTable, { type Column } from "../components/DataTable";
import Modal from "../components/Modal";

const DOC_TYPES = ["bol", "pod", "rate_confirmation", "invoice", "carrier_agreement", "insurance", "compliance", "other"];

export default function Documents() {
  const [showUpload, setShowUpload] = useState(false);
  const [docType, setDocType] = useState("");
  const [dlError, setDlError] = useState<string | null>(null);
  const list = useFetch(
    () => documentsApi.list({ doc_type: docType || undefined, page_size: 50, sort_by: "created_at", sort_dir: "desc" }),
    [docType]
  );

  const doDownload = async (d: Document) => {
    setDlError(null);
    try {
      await downloadDocument(d);
    } catch (e) {
      setDlError(e instanceof Error ? e.message : "Download failed");
    }
  };

  const columns: Column<Document>[] = [
    { key: "filename", header: "File", sortable: true, getValue: (d) => d.filename, render: (d) => <span className="strong">{d.filename}</span> },
    { key: "doc_type", header: "Type", render: (d) => d.doc_type.replace(/_/g, " ") },
    { key: "entity_type", header: "Entity", render: (d) => <>{d.entity_type} <span className="muted small">{String(d.entity_id).slice(0, 8)}…</span></> },
    { key: "size_bytes", header: "Size", sortable: true, getValue: (d) => d.size_bytes, render: (d) => `${(d.size_bytes / 1024).toFixed(1)} KB` },
    { key: "created_at", header: "Uploaded", sortable: true, getValue: (d) => d.created_at, render: (d) => fmtDateTime(d.created_at) },
  ];

  return (
    <div>
      <PageHeader
        title="Documents"
        sub="BOLs, PODs, rate confirmations & compliance"
        actions={
          <>
            <select className="input inline" value={docType} onChange={(e) => setDocType(e.target.value)}>
              <option value="">All types</option>
              {DOC_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
            </select>
            <button className="btn btn-primary" onClick={() => setShowUpload(true)}>+ Upload</button>
          </>
        }
      />
      {dlError && <FormAlert error={dlError} />}
      <DataTable
        columns={columns}
        rows={list.data?.items || []}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        searchKeys={["filename"]}
        emptyTitle="No documents"
        emptyHint="Upload freight documents here."
        actions={(d) => (
          <button className="btn btn-ghost btn-sm" onClick={() => doDownload(d)}>Download</button>
        )}
      />
      {showUpload && (
        <UploadModal onClose={() => setShowUpload(false)} onDone={() => { setShowUpload(false); list.reload(); }} />
      )}
    </div>
  );
}

function UploadModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const loads = useFetch(() => loadsApi.list({ page_size: 50 }), []);
  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState("bol");
  const [loadId, setLoadId] = useState("");
  const up = useMutation((f: File) => documentsApi.upload(f, "load", loadId, docType));
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) { setErr("Choose a file to upload."); return; }
    if (!loadId) { setErr("Select the load this document belongs to."); return; }
    const r = await up.run(file);
    if (r) onDone();
  };

  return (
    <Modal title="Upload document" onClose={onClose}>
      <form onSubmit={submit} className="form-grid">
        <Field label="File" required>
          <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </Field>
        <div className="form-row">
          <Field label="Load" required>
            <select className="input" value={loadId} onChange={(e) => setLoadId(e.target.value)}>
              <option value="">Select…</option>
              {loads.data?.items.map((l) => <option key={l.id} value={l.id}>{l.load_number}</option>)}
            </select>
          </Field>
          <Field label="Type">
            <select className="input" value={docType} onChange={(e) => setDocType(e.target.value)}>
              {DOC_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
            </select>
          </Field>
        </div>
        <FormAlert error={err || up.error} />
        <div className="form-foot">
          <button className="btn btn-primary" type="submit" disabled={up.loading}>
            {up.loading ? "Uploading…" : "Upload"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
