import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { documentsApi, driversApi, loadsApi, getStoredUser } from "../api/client";
import { useFetch, useMutation } from "../lib/hooks";
import { fmtDateTime, fmtMoney, loc } from "../lib/format";
import { FormAlert } from "../components/Page";
import StatusPill from "../components/StatusPill";
import EmptyState from "../components/EmptyState";

const STATUS_ACTIONS: { status: string; label: string }[] = [
  { status: "at_pickup", label: "Arrived at pickup" },
  { status: "picked_up", label: "Picked up" },
  { status: "in_transit", label: "In transit" },
  { status: "at_delivery", label: "Arrived at delivery" },
  { status: "delivered", label: "Delivered" },
];

export default function DriverApp() {
  const navigate = useNavigate();
  const user = getStoredUser();
  const [pickId, setPickId] = useState("");
  const driverId = user?.driver_id || pickId;
  const [podFile, setPodFile] = useState<File | null>(null);

  const allDrivers = useFetch(() => driversApi.list({ page_size: 100 }), []);
  const driver = useFetch(
    () => (driverId ? driversApi.get(driverId) : Promise.reject(new Error("Select a driver"))),
    [driverId]
  );
  const loads = useFetch(
    () => loadsApi.list({ driver_id: driverId || undefined, status: undefined, page_size: 20 }).catch(() => loadsApi.list({ page_size: 20 })),
    [driverId]
  );
  const setStatus = useMutation((args: { id: string; status: string }) => loadsApi.setStatus(args.id, args.status));
  const podUpload = useMutation((args: { file: File; loadId: string }) => documentsApi.upload(args.file, "load", args.loadId, "pod"));

  const active = (loads.data?.items || []).find((l) =>
    ["dispatched", "at_pickup", "picked_up", "in_transit", "at_delivery"].includes(l.status)
  ) || (loads.data?.items || [])[0];

  const doStatus = async (loadId: string, status: string) => {
    const r = await setStatus.run({ id: loadId, status });
    if (r) loads.reload();
  };

  const doPod = async (loadId: string) => {
    if (!podFile) return;
    const r = await podUpload.run({ file: podFile, loadId });
    if (r) setPodFile(null);
  };

  if (!driverId) {
    return (
      <div className="driver-page">
        <header className="driver-head">
          <div>
            <div className="muted small">DRIVER APP</div>
            <h1>Select driver</h1>
          </div>
          <button className="icon-btn" onClick={() => navigate("/")}>✕</button>
        </header>
        <div className="card">
          <label className="field">
            <span className="field-label">Driver profile</span>
            <select className="input" value={pickId} onChange={(e) => setPickId(e.target.value)}>
              <option value="">Choose…</option>
              {allDrivers.data?.items.map((d) => (
                <option key={d.id} value={d.id}>{d.full_name}</option>
              ))}
            </select>
          </label>
          <div className="muted small">This account isn't linked to a driver profile — pick one to preview the driver view, or ask dispatch to link your user.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="driver-page">
      <header className="driver-head">
        <div>
          <div className="muted small">DRIVER APP</div>
          <h1>{driver.data?.full_name || user?.full_name}</h1>
        </div>
        <button className="icon-btn" onClick={() => navigate("/")}>✕</button>
      </header>

      {loads.loading ? (
        <div className="skeleton-row" style={{ height: 200 }} />
      ) : loads.error ? (
        <EmptyState title="Couldn't load assignments" hint={loads.error} action={<button className="btn btn-primary" onClick={loads.reload}>Retry</button>} />
      ) : !active ? (
        <EmptyState title="No active assignment" hint="You're clear. Check with dispatch for new work." />
      ) : (
        <div className="driver-card-main">
          <div className="card">
            <div className="btn-row">
              <h2 style={{ margin: 0 }}>{active.load_number}</h2>
              <StatusPill status={active.status} />
            </div>
            <div className="route-line">
              <div><span className="muted small">PICKUP</span><div className="strong">{loc(active.origin)}</div><div className="muted small">{fmtDateTime(active.pickup_datetime)}</div></div>
              <div className="route-arrow">→</div>
              <div><span className="muted small">DELIVERY</span><div className="strong">{loc(active.destination)}</div><div className="muted small">{fmtDateTime(active.delivery_datetime)}</div></div>
            </div>
            <dl className="dl">
              <dt>Commodity</dt><dd>{active.commodity || "—"}</dd>
              <dt>Weight</dt><dd>{active.weight_lbs?.toLocaleString()} lbs</dd>
              <dt>Equipment</dt><dd>{active.equipment_type.replace(/_/g, " ")}</dd>
              <dt>Rate</dt><dd>{fmtMoney(active.customer_rate)}</dd>
            </dl>
          </div>

          <div className="card">
            <h3>Update status</h3>
            <FormAlert error={setStatus.error} success={setStatus.success} />
            <div className="driver-actions">
              {STATUS_ACTIONS.map((a) => (
                <button
                  key={a.status}
                  className={`btn ${active.status === a.status ? "btn-primary" : "btn-ghost"} btn-block`}
                  disabled={setStatus.loading}
                  onClick={() => doStatus(active.id, a.status)}
                >
                  {a.label}
                </button>
              ))}
            </div>
          </div>

          <div className="card">
            <h3>Proof of delivery</h3>
            <input type="file" accept="image/*,.pdf" onChange={(e) => setPodFile(e.target.files?.[0] || null)} />
            <div style={{ marginTop: 8 }}>
              <button className="btn btn-primary btn-block" disabled={!podFile || podUpload.loading} onClick={() => doPod(active.id)}>
                {podUpload.loading ? "Uploading…" : "Upload POD"}
              </button>
            </div>
            <FormAlert error={podUpload.error} success={podUpload.success} />
          </div>
        </div>
      )}
    </div>
  );
}
