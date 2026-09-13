import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { trackingApi } from "../api/client";
import { useFetch } from "../lib/hooks";
import { fmtDateTime } from "../lib/format";
import { PageHeader } from "../components/Page";
import MapView, { type MapPoint } from "../components/MapView";
import StatusPill from "../components/StatusPill";
import EmptyState from "../components/EmptyState";

export default function Tracking() {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const positions = useFetch(() => trackingApi.positions(), []);

  const filtered = (positions.data || []).filter(
    (p) => !statusFilter || p.status === statusFilter
  );

  const points: MapPoint[] = filtered.map((p) => ({
    lat: p.lat,
    lng: p.lng,
    label: p.load_number,
    status: p.status,
    sub: `${p.city}, ${p.state}${p.eta ? ` · ETA ${fmtDateTime(p.eta)}` : ""}`,
  }));

  return (
    <div>
      <PageHeader
        title="Tracking"
        sub="Live positions of in-transit loads"
        actions={
          <>
            <select className="input inline" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              {["dispatched", "at_pickup", "picked_up", "in_transit", "at_delivery"].map((s) => (
                <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
              ))}
            </select>
            <button className="btn btn-ghost" onClick={positions.reload}>↻ Refresh</button>
          </>
        }
      />
      {positions.loading ? (
        <div className="skeleton-row" style={{ height: 420 }} />
      ) : positions.error ? (
        <EmptyState title="Couldn't load positions" hint={positions.error} action={<button className="btn btn-primary" onClick={positions.reload}>Retry</button>} />
      ) : filtered.length === 0 ? (
        <EmptyState title="No active positions" hint="No loads are currently being tracked." />
      ) : (
        <MapView points={points} selected={selected} onSelect={setSelected} />
      )}

      <div className="card" style={{ marginTop: 16 }}>
        <h3>Load ETAs</h3>
        {positions.loading ? <div className="skeleton-row" /> : filtered.length === 0 ? (
          <EmptyState title="No loads" />
        ) : (
          <div className="card-list">
            {filtered.slice(0, 15).map((p) => (
              <div key={p.load_id} className="list-row" onClick={() => navigate(`/loads/${p.load_id}`)}>
                <div className="list-main">
                  <div className="list-title">{p.load_number}</div>
                  <div className="muted small">{p.city}, {p.state}{p.speed_mph != null ? ` · ${p.speed_mph} mph` : ""}</div>
                </div>
                <span className="muted small">ETA {fmtDateTime(p.eta)}</span>
                <StatusPill status={p.status} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
