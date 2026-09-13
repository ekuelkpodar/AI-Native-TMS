// Hand-rolled SVG charts: bars, line, donut, sparkline. No dependencies.

const COLORS = ["#5b54e6", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#14b8a6", "#f97316"];

export function BarChart({
  data,
  width = 520,
  height = 180,
  color = "#5b54e6",
  formatY,
}: {
  data: { label: string; value: number }[];
  width?: number;
  height?: number;
  color?: string;
  formatY?: (v: number) => string;
}) {
  const padL = 44, padB = 26, padT = 8, padR = 8;
  const max = Math.max(1, ...data.map((d) => d.value));
  const innerW = width - padL - padR;
  const innerH = height - padT - padB;
  const bw = data.length ? innerW / data.length : 0;
  const ticks = [0, 0.5, 1].map((t) => t * max);
  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="chart" role="img">
      {ticks.map((t, i) => (
        <g key={i}>
          <line
            x1={padL} x2={width - padR}
            y1={padT + innerH - (t / max) * innerH}
            y2={padT + innerH - (t / max) * innerH}
            stroke="#e5e7eb" strokeWidth={1}
          />
          <text x={padL - 6} y={padT + innerH - (t / max) * innerH + 4} textAnchor="end" fontSize={10} fill="#6b7280">
            {formatY ? formatY(t) : Math.round(t)}
          </text>
        </g>
      ))}
      {data.map((d, i) => {
        const h = (d.value / max) * innerH;
        const x = padL + i * bw + bw * 0.2;
        return (
          <g key={i}>
            <rect
              x={x} y={padT + innerH - h}
              width={bw * 0.6} height={h}
              rx={3} fill={color} opacity={0.85}
            >
              <title>{`${d.label}: ${formatY ? formatY(d.value) : d.value}`}</title>
            </rect>
            <text
              x={padL + i * bw + bw / 2} y={height - 8}
              textAnchor="middle" fontSize={10} fill="#6b7280"
            >
              {d.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function LineChart({
  data,
  width = 520,
  height = 180,
  color = "#5b54e6",
  formatY,
}: {
  data: { label: string; value: number }[];
  width?: number;
  height?: number;
  color?: string;
  formatY?: (v: number) => string;
}) {
  const padL = 44, padB = 26, padT = 8, padR = 8;
  const max = Math.max(1, ...data.map((d) => d.value));
  const min = Math.min(0, ...data.map((d) => d.value));
  const innerW = width - padL - padR;
  const innerH = height - padT - padB;
  const x = (i: number) => padL + (data.length > 1 ? (i / (data.length - 1)) * innerW : innerW / 2);
  const y = (v: number) => padT + innerH - ((v - min) / (max - min || 1)) * innerH;
  const path = data.map((d, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(d.value).toFixed(1)}`).join(" ");
  const area = `${path} L${x(data.length - 1).toFixed(1)},${(padT + innerH).toFixed(1)} L${x(0).toFixed(1)},${(padT + innerH).toFixed(1)} Z`;
  const step = Math.max(1, Math.floor(data.length / 6));
  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="chart" role="img">
      {[0, 0.5, 1].map((t, i) => {
        const v = min + t * (max - min);
        return (
          <g key={i}>
            <line x1={padL} x2={width - padR} y1={y(v)} y2={y(v)} stroke="#e5e7eb" strokeWidth={1} />
            <text x={padL - 6} y={y(v) + 4} textAnchor="end" fontSize={10} fill="#6b7280">
              {formatY ? formatY(v) : Math.round(v)}
            </text>
          </g>
        );
      })}
      <path d={area} fill={color} opacity={0.12} />
      <path d={path} fill="none" stroke={color} strokeWidth={2.2} strokeLinejoin="round" />
      {data.map((d, i) =>
        i % step === 0 || i === data.length - 1 ? (
          <text key={i} x={x(i)} y={height - 8} textAnchor="middle" fontSize={10} fill="#6b7280">
            {d.label}
          </text>
        ) : null
      )}
      {data.map((d, i) => (
        <circle key={i} cx={x(i)} cy={y(d.value)} r={3} fill={color}>
          <title>{`${d.label}: ${formatY ? formatY(d.value) : d.value}`}</title>
        </circle>
      ))}
    </svg>
  );
}

export function DonutChart({
  data,
  size = 180,
  thickness = 28,
}: {
  data: { label: string; value: number }[];
  size?: number;
  thickness?: number;
}) {
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  const r = (size - thickness) / 2;
  const c = size / 2;
  let acc = 0;
  return (
    <div className="donut-wrap">
      <svg width={size} height={size} className="chart" role="img">
        <circle cx={c} cy={c} r={r} fill="none" stroke="#eef0f4" strokeWidth={thickness} />
        {data.map((d, i) => {
          const frac = d.value / total;
          const start = acc;
          acc += frac;
          const a0 = -Math.PI / 2 + start * 2 * Math.PI;
          const a1 = -Math.PI / 2 + acc * 2 * Math.PI;
          const x0 = c + r * Math.cos(a0), y0 = c + r * Math.sin(a0);
          const x1 = c + r * Math.cos(a1), y1 = c + r * Math.sin(a1);
          const large = frac > 0.5 ? 1 : 0;
          return (
            <path
              key={i}
              d={`M${x0},${y0} A${r},${r} 0 ${large} 1 ${x1},${y1}`}
              fill="none"
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={thickness}
            >
              <title>{`${d.label}: ${d.value}`}</title>
            </path>
          );
        })}
        <text x={c} y={c - 2} textAnchor="middle" fontSize={20} fontWeight={700} fill="#111827">
          {total}
        </text>
        <text x={c} y={c + 16} textAnchor="middle" fontSize={11} fill="#6b7280">
          total
        </text>
      </svg>
      <ul className="donut-legend">
        {data.map((d, i) => (
          <li key={i}>
            <span className="legend-swatch" style={{ background: COLORS[i % COLORS.length] }} />
            {d.label} <b>{d.value}</b>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Sparkline({ data, width = 120, height = 32, color = "#5b54e6" }: {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
}) {
  if (data.length < 2) return <span className="spark-empty">—</span>;
  const max = Math.max(...data), min = Math.min(...data);
  const x = (i: number) => (i / (data.length - 1)) * (width - 4) + 2;
  const y = (v: number) => height - 4 - ((v - min) / (max - min || 1)) * (height - 8);
  const path = data.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return (
    <svg width={width} height={height} className="spark" role="img" aria-label="trend">
      <path d={path} fill="none" stroke={color} strokeWidth={1.8} strokeLinejoin="round" />
    </svg>
  );
}
