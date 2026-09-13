import React from "react";
import { Link } from "react-router-dom";

export default function StatCard({
  label,
  value,
  delta,
  deltaTone = "neutral",
  icon,
  to,
}: {
  label: string;
  value: string | number;
  delta?: string;
  deltaTone?: "up" | "down" | "neutral";
  icon?: React.ReactNode;
  to?: string;
}) {
  const inner = (
    <>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {delta && <div className={`stat-delta delta-${deltaTone}`}>{delta}</div>}
    </>
  );
  return (
    <div className="stat-card">
      {icon && <div className="stat-icon">{icon}</div>}
      {to ? <Link className="stat-link" to={to}>{inner}</Link> : inner}
    </div>
  );
}
