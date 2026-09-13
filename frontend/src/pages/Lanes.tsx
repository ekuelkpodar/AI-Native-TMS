import { lanesApi } from "../api/client";
import { useFetch } from "../lib/hooks";
import { fmtMoney, fmtPct } from "../lib/format";
import { PageHeader } from "../components/Page";
import DataTable, { type Column } from "../components/DataTable";
import { BarChart } from "../components/Charts";
import type { Lane } from "../api/client";

export default function Lanes() {
  // Contract doesn't specify whether /lanes is paged — accept both shapes.
  const list = useFetch(async () => {
    const r = await lanesApi.list();
    return Array.isArray(r) ? r : (r as { items: Lane[] }).items || [];
  }, []);

  const columns: Column<Lane>[] = [
    { key: "origin_city", header: "Lane", sortable: true, getValue: (l) => `${l.origin_city} ${l.dest_city}`, render: (l) => <><span className="strong">{l.origin_city}, {l.origin_state} → {l.dest_city}, {l.dest_state}</span><div className="muted small">{l.equipment_type?.replace(/_/g, " ")}</div></> },
    { key: "loads", header: "Loads", sortable: true, getValue: (l) => l.loads, render: (l) => l.loads },
    { key: "revenue", header: "Revenue", sortable: true, getValue: (l) => l.revenue, render: (l) => fmtMoney(l.revenue) },
    { key: "avg_rate", header: "Avg rate", sortable: true, getValue: (l) => l.avg_rate, render: (l) => fmtMoney(l.avg_rate) },
    { key: "avg_margin", header: "Avg margin", sortable: true, getValue: (l) => l.avg_margin, render: (l) => <span className={l.avg_margin < 0 ? "neg" : "pos"}>{fmtMoney(l.avg_margin)} ({fmtPct(l.avg_rate ? (l.avg_margin / l.avg_rate) * 100 : 0)})</span> },
  ];

  const top = (list.data || []).slice(0, 10);

  return (
    <div>
      <PageHeader title="Lanes" sub="Aggregated lane performance" />
      {top.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Top lanes by revenue</h3>
          <BarChart data={top.map((l) => ({ label: `${l.origin_city.slice(0, 8)}→${l.dest_city.slice(0, 8)}`, value: l.revenue }))} formatY={(v) => fmtMoney(v)} />
        </div>
      )}
      <DataTable
        columns={columns}
        rows={list.data || []}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        searchKeys={["origin_city", "dest_city", "origin_state", "dest_state"]}
        emptyTitle="No lane data"
        emptyHint="Lane stats appear once loads are moving."
      />
    </div>
  );
}
