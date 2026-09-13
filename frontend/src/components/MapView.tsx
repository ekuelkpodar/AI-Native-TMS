// Stylized SVG map of the contiguous US. Plots lat/lng positions and
// routes with status colors. Purely decorative base (not to scale).

import { useMemo } from "react";
import { statusColor } from "./StatusPill";

export interface MapPoint {
  lat: number;
  lng: number;
  label: string;
  status?: string;
  sub?: string;
}

export interface MapRoute {
  from: { lat: number; lng: number };
  to: { lat: number; lng: number };
  color?: string;
}

// contiguous US bounds approx: lat 24.5–49.5, lng -125–-66.5
function project(lat: number, lng: number, w: number, h: number) {
  const x = ((lng + 125) / (-66.5 + 125)) * (w - 40) + 20;
  const y = (1 - (lat - 24.5) / (49.5 - 24.5)) * (h - 40) + 20;
  return { x, y };
}

// rough US outline (stylized polygon)
const US_PATH =
  "M68,168 L92,150 L150,146 L196,132 L238,128 L300,120 L360,116 L420,110 L470,104 L520,104 L560,110 L600,120 L640,132 L676,148 L700,168 L688,190 L660,205 L620,210 L580,218 L540,232 L500,244 L460,254 L420,258 L380,258 L340,250 L300,240 L260,238 L220,240 L180,238 L140,230 L100,214 L76,196 Z";

const STATUS_HEX: Record<string, string> = {
  gray: "#9ca3af", blue: "#3b82f6", cyan: "#06b6d4", indigo: "#6366f1",
  violet: "#8b5cf6", amber: "#f59e0b", sky: "#0ea5e9", green: "#10b981",
  teal: "#14b8a6", red: "#ef4444", orange: "#f97316",
};

export default function MapView({
  points = [],
  routes = [],
  selected,
  onSelect,
  height = 420,
}: {
  points?: MapPoint[];
  routes?: MapRoute[];
  selected?: string | null;
  onSelect?: (label: string) => void;
  height?: number;
}) {
  const w = 760;
  const h = height;
  const plotted = useMemo(
    () =>
      points.map((p) => {
        const { x, y } = project(p.lat, p.lng, w, h);
        return { ...p, x, y };
      }),
    [points, h]
  );
  return (
    <div className="map-wrap">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} role="img" aria-label="US tracking map">
        <rect x={0} y={0} width={w} height={h} rx={10} fill="#eef4f8" />
        <path d={US_PATH} fill="#dbe6ee" stroke="#9db4c4" strokeWidth={1.5} />
        {routes.map((r, i) => {
          const a = project(r.from.lat, r.from.lng, w, h);
          const b = project(r.to.lat, r.to.lng, w, h);
          const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2 - 24;
          return (
            <path
              key={i}
              d={`M${a.x},${a.y} Q${mx},${my} ${b.x},${b.y}`}
              fill="none"
              stroke={r.color || "#5b54e6"}
              strokeWidth={1.6}
              strokeDasharray="6 4"
              opacity={0.8}
            />
          );
        })}
        {plotted.map((p, i) => {
          const hex = STATUS_HEX[statusColor(p.status)] || STATUS_HEX.gray;
          const isSel = selected === p.label;
          return (
            <g
              key={i}
              transform={`translate(${p.x},${p.y})`}
              onClick={() => onSelect?.(p.label)}
              className={onSelect ? "map-point-click" : ""}
              style={{ cursor: onSelect ? "pointer" : "default" }}
            >
              {isSel && <circle r={14} fill={hex} opacity={0.25} />}
              <circle r={6.5} fill={hex} stroke="#fff" strokeWidth={2} />
              {(isSel || plotted.length < 30) && (
                <text y={-11} textAnchor="middle" fontSize={10.5} fill="#1f2937" fontWeight={600}>
                  {p.label}
                </text>
              )}
              {isSel && p.sub && (
                <text y={22} textAnchor="middle" fontSize={10} fill="#4b5563">
                  {p.sub}
                </text>
              )}
              <title>{`${p.label}${p.sub ? ` — ${p.sub}` : ""}`}</title>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
