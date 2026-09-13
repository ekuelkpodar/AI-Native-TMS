import { useState } from "react";
import { dispatchApi, type Driver, type Load, type DispatchConflict } from "../api/client";
import { useFetch, useMutation } from "../lib/hooks";
import { fmtDateTime, fmtMoney, loc } from "../lib/format";
import { PageHeader, FormAlert } from "../components/Page";
import StatusPill from "../components/StatusPill";
import EmptyState from "../components/EmptyState";

export default function DispatchBoard() {
  const board = useFetch(() => dispatchApi.board(), []);
  const [dragLoad, setDragLoad] = useState<Load | null>(null);
  const assign = useMutation((args: { load_id: string; driver_id: string; vehicle_id?: string }) =>
    dispatchApi.assign(args.load_id, args.driver_id, args.vehicle_id)
  );

  const doAssign = async (load: Load, driver: Driver, vehicleId?: string) => {
    const r = await assign.run({ load_id: load.id, driver_id: driver.id, vehicle_id: vehicleId });
    if (r) {
      board.reload();
      setDragLoad(null);
      if (r.warnings && r.warnings.length > 0) {
        alert(`Assigned with warnings:\n${r.warnings.map((w: DispatchConflict) => `• ${w.message}`).join("\n")}`);
      }
    }
  };

  const conflicts = board.data?.conflicts || [];

  return (
    <div>
      <PageHeader
        title="Dispatch board"
        sub="Drag unassigned loads onto drivers"
        actions={<button className="btn btn-ghost" onClick={board.reload}>↻ Refresh</button>}
      />
      <FormAlert error={assign.error || board.error} />

      {conflicts.length > 0 && (
        <div className="card warn-card">
          <h3>⚠ Conflict warnings ({conflicts.length})</h3>
          <div className="card-list">
            {conflicts.map((c, i) => (
              <div key={i} className="list-row">
                <StatusPill status={c.severity} />
                <div className="list-main">
                  <div className="list-title">{c.type.replace(/_/g, " ")}</div>
                  <div className="muted small">{c.message}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {board.loading ? (
        <div className="dispatch-grid">
          <div className="skeleton-row" style={{ height: 400 }} />
          <div className="skeleton-row" style={{ height: 400 }} />
        </div>
      ) : (
        <div className="dispatch-grid">
          <div className="dispatch-col">
            <h3>Unassigned loads ({board.data?.unassigned_loads.length || 0})</h3>
            {!board.data || board.data.unassigned_loads.length === 0 ? (
              <EmptyState title="No unassigned loads" hint="Everything is dispatched." />
            ) : (
              board.data.unassigned_loads.map((l) => (
                <div
                  key={l.id}
                  className={`dispatch-card ${dragLoad?.id === l.id ? "dragging" : ""}`}
                  draggable
                  onDragStart={() => setDragLoad(l)}
                  onDragEnd={() => setDragLoad(null)}
                >
                  <div className="list-title">{l.load_number}</div>
                  <div className="muted small">{loc(l.origin)} → {loc(l.destination)}</div>
                  <div className="muted small">Pickup {fmtDateTime(l.pickup_datetime)}</div>
                  <div className="dispatch-meta">
                    <StatusPill status={l.status} />
                    <span className="muted small">{fmtMoney(l.customer_rate)}</span>
                  </div>
                </div>
              ))
            )}
          </div>
          <div className="dispatch-col">
            <h3>Available drivers ({board.data?.available_drivers.length || 0})</h3>
            {!board.data || board.data.available_drivers.length === 0 ? (
              <EmptyState title="No available drivers" />
            ) : (
              board.data.available_drivers.map((d) => (
                <div
                  key={d.id}
                  className={`dispatch-card driver-card ${dragLoad ? "drop-target" : ""}`}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => dragLoad && doAssign(dragLoad, d)}
                >
                  <div className="list-title">{d.full_name}</div>
                  <div className="muted small">
                    {d.current_location ? `${d.current_location.city}, ${d.current_location.state}` : "Location unknown"} ·{" "}
                    {d.hours_available}h available
                  </div>
                  <div className="dispatch-meta">
                    <StatusPill status={d.status} />
                    {dragLoad && (
                      <button
                        className="btn btn-primary btn-sm"
                        disabled={assign.loading}
                        onClick={() => doAssign(dragLoad, d)}
                      >
                        Assign {dragLoad.load_number}
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {board.data && board.data.available_vehicles.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Available vehicles</h3>
          <div className="pill-row">
            {board.data.available_vehicles.slice(0, 12).map((v) => (
              <span key={v.id} className="pill pill-gray">
                {v.unit_number} · {v.vehicle_type.replace(/_/g, " ")}
              </span>
            ))}
            {board.data.available_vehicles.length > 12 && (
              <span className="muted small">+{board.data.available_vehicles.length - 12} more</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
