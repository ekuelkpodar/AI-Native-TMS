import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { aiApi, loadsApi, customersApi, carriersApi, driversApi } from "../api/client";

interface Entry {
  kind: "load" | "customer" | "carrier" | "driver" | "action";
  label: string;
  sub?: string;
  go: () => void;
}

const QUICK_ACTIONS: { label: string; go: (nav: (p: string) => void) => void }[] = [
  { label: "Create load", go: (nav) => nav("/loads?new=1") },
  { label: "Create shipment", go: (nav) => nav("/shipments?new=1") },
  { label: "Get rate quote", go: (nav) => nav("/rates?quote=1") },
  { label: "Run exception scan", go: (nav) => nav("/ai?scan=1") },
  { label: "Open dispatch board", go: (nav) => nav("/dispatch") },
];

function fuzzy(hay: string, needle: string): boolean {
  hay = hay.toLowerCase();
  needle = needle.toLowerCase();
  let hi = 0;
  for (const ch of needle) {
    hi = hay.indexOf(ch, hi);
    if (hi === -1) return false;
    hi++;
  }
  return true;
}

export default function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [sel, setSel] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const [aiBusy, setAiBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setQ("");
    setSel(0);
    inputRef.current?.focus();
    let alive = true;
    (async () => {
      try {
        const [loads, customers, carriers, drivers] = await Promise.all([
          loadsApi.list({ page_size: 30 }),
          customersApi.list({ page_size: 20 }),
          carriersApi.list({ page_size: 20 }),
          driversApi.list({ page_size: 20 }),
        ]);
        if (!alive) return;
        setEntries([
          ...loads.items.map((l) => ({
            kind: "load" as const,
            label: `${l.load_number} — ${l.origin.city}, ${l.origin.state} → ${l.destination.city}, ${l.destination.state}`,
            sub: l.status.replace(/_/g, " "),
            go: () => navigate(`/loads/${l.id}`),
          })),
          ...customers.items.map((c) => ({
            kind: "customer" as const,
            label: c.name,
            sub: "customer",
            go: () => navigate(`/customers`),
          })),
          ...carriers.items.map((c) => ({
            kind: "carrier" as const,
            label: c.dba || c.legal_name,
            sub: "carrier",
            go: () => navigate(`/carriers`),
          })),
          ...drivers.items.map((d) => ({
            kind: "driver" as const,
            label: d.full_name,
            sub: "driver",
            go: () => navigate(`/drivers`),
          })),
        ]);
      } catch {
        /* API down: palette still offers quick actions */
      }
    })();
    return () => { alive = false; };
  }, [open, navigate]);

  const filtered = useMemo(() => {
    const qq = q.trim();
    const actions: Entry[] = QUICK_ACTIONS.filter((a) => !qq || fuzzy(a.label, qq)).map((a) => ({
      kind: "action" as const,
      label: a.label,
      sub: "action",
      go: () => a.go(navigate),
    }));
    if (!qq) return [...actions, ...entries.slice(0, 8)];
    return [...actions, ...entries.filter((e) => fuzzy(e.label, qq)).slice(0, 10)];
  }, [q, entries, navigate]);

  useEffect(() => setSel(0), [filtered.length]);

  const choose = (e: Entry) => {
    onClose();
    e.go();
  };

  const runAi = async () => {
    if (!q.trim() || aiBusy) return;
    setAiBusy(true);
    try {
      await aiApi.command(q.trim());
      onClose();
      navigate("/ai", { state: { message: q.trim() } });
    } catch {
      /* handled on /ai page */
    } finally {
      setAiBusy(false);
    }
  };

  if (!open) return null;
  return (
    <div className="cmd-backdrop" onClick={onClose}>
      <div className="cmd" onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          className="cmd-input"
          placeholder="Search loads, customers, carriers, drivers… or ask the AI"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") onClose();
            else if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, filtered.length - 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
            else if (e.key === "Enter") {
              if (filtered[sel]) choose(filtered[sel]);
            } else if (e.key === "Tab" && q.trim()) {
              e.preventDefault();
              runAi();
            }
          }}
        />
        <div className="cmd-list">
          {filtered.map((e, i) => (
            <div key={i} className={`cmd-item ${i === sel ? "sel" : ""}`} onClick={() => choose(e)} onMouseEnter={() => setSel(i)}>
              <span className={`cmd-kind kind-${e.kind}`}>{e.kind}</span>
              <span className="cmd-label">{e.label}</span>
              {e.sub && <span className="cmd-sub">{e.sub}</span>}
            </div>
          ))}
          {filtered.length === 0 && q.trim() && (
            <div className="cmd-item" onClick={runAi}>
              <span className="cmd-kind kind-action">ai</span>
              <span className="cmd-label">{aiBusy ? "Asking AI…" : `Ask AI: "${q.trim()}" (Tab)`}</span>
            </div>
          )}
        </div>
        <div className="cmd-foot">
          <span>↑↓ navigate</span><span>↵ open</span><span>Tab ask AI</span><span>esc close</span>
        </div>
      </div>
    </div>
  );
}
