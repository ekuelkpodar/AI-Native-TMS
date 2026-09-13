import React, { useState } from "react";
import { aiApi, analyticsApi, type ForecastResponse } from "../api/client";
import { useFetch, useMutation } from "../lib/hooks";
import { fmtMoney, fmtPct } from "../lib/format";
import { PageHeader, FormAlert, Tabs } from "../components/Page";
import { BarChart, LineChart } from "../components/Charts";
import EmptyState from "../components/EmptyState";

type Tab = "financial" | "operational" | "carrier" | "customer" | "forecast";

export default function Analytics() {
  const [tab, setTab] = useState<Tab>("financial");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const q = {
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    page_size: 100,
  };

  const financial = useFetch(() => analyticsApi.financial(q), [tab, dateFrom, dateTo]);
  const operational = useFetch(() => analyticsApi.operational(q), [tab, dateFrom, dateTo]);
  const carrier = useFetch(() => analyticsApi.carrier(q), [tab, dateFrom, dateTo]);
  const customer = useFetch(() => analyticsApi.customer(q), [tab, dateFrom, dateTo]);

  return (
    <div>
      <PageHeader
        title="Analytics"
        sub="Financial, operational & network intelligence"
        actions={
          <>
            <input type="date" className="input inline" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            <input type="date" className="input inline" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </>
        }
      />
      <Tabs
        tabs={[
          { key: "financial", label: "Financial" },
          { key: "operational", label: "Operational" },
          { key: "carrier", label: "Carrier" },
          { key: "customer", label: "Customer" },
          { key: "forecast", label: "Forecast" },
        ]}
        active={tab}
        onChange={setTab}
      />
      {tab === "financial" && <GenericPanel state={financial} kind="money" />}
      {tab === "operational" && <GenericPanel state={operational} kind="num" />}
      {tab === "carrier" && <GenericPanel state={carrier} kind="num" />}
      {tab === "customer" && <GenericPanel state={customer} kind="num" />}
      {tab === "forecast" && <ForecastPanel />}
    </div>
  );
}

interface PanelState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

function GenericPanel({ state, kind }: { state: PanelState<Record<string, unknown>>; kind: "money" | "num" }) {
  const { data, loading, error, reload } = state;
  if (loading) return <div className="skeleton-row" style={{ height: 200 }} />;
  if (error) return <EmptyState title="Couldn't load analytics" hint={error} action={<button className="btn btn-primary" onClick={reload}>Retry</button>} />;
  if (!data || Object.keys(data).length === 0) return <EmptyState title="No data" hint="Nothing to report for this period." />;

  const scalars: [string, unknown][] = [];
  const series: { key: string; data: { label: string; value: number }[] }[] = [];
  for (const [k, v] of Object.entries(data)) {
    if (typeof v === "number" || typeof v === "string" || typeof v === "boolean") scalars.push([k, v]);
    else if (Array.isArray(v) && v.length > 0 && typeof v[0] === "object") {
      const first = v[0] as Record<string, unknown>;
      const labelKey = ["label", "date", "name", "status", "period"].find((kk) => kk in first);
      const valueKey = ["value", "revenue", "count", "loads", "total"].find((kk) => kk in first);
      if (labelKey && valueKey) {
        series.push({
          key: k,
          data: (v as Record<string, unknown>[]).map((r) => ({
            label: String(r[labelKey]).slice(0, 12),
            value: Number(r[valueKey]) || 0,
          })),
        });
      }
    }
  }

  const fmt = (k: string, v: unknown) => {
    if (typeof v === "number") {
      if (k.toLowerCase().includes("pct") || k.toLowerCase().includes("percent")) return fmtPct(v);
      return kind === "money" ? fmtMoney(v) : v.toLocaleString("en-US");
    }
    return String(v);
  };

  return (
    <div>
      {scalars.length > 0 && (
        <div className="stat-grid">
          {scalars.map(([k, v]) => (
            <div key={k} className="stat-card">
              <div className="stat-label">{k.replace(/_/g, " ")}</div>
              <div className="stat-value">{fmt(k, v)}</div>
            </div>
          ))}
        </div>
      )}
      {series.length > 0 && (
        <div className="two-col" style={{ marginTop: 16 }}>
          {series.slice(0, 6).map((s) => (
            <div key={s.key} className="card">
              <h3>{s.key.replace(/_/g, " ")}</h3>
              <BarChart data={s.data.slice(0, 14)} formatY={kind === "money" ? (v) => fmtMoney(v) : undefined} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const FORECAST_TYPES = ["volume", "capacity", "cost", "lane_pricing", "driver_demand"];

function ForecastPanel() {
  const [type, setType] = useState("volume");
  const [periods, setPeriods] = useState("12");
  const [result, setResult] = useState<ForecastResponse | null>(null);
  const run = useMutation(() => aiApi.forecast(type, Number(periods) || 12));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const r = await run.run();
    if (r) setResult(r);
  };

  return (
    <div className="card">
      <form onSubmit={submit} className="form-row" style={{ alignItems: "end" }}>
        <label className="field">
          <span className="field-label">Forecast type</span>
          <select className="input" value={type} onChange={(e) => setType(e.target.value)}>
            {FORECAST_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
          </select>
        </label>
        <label className="field">
          <span className="field-label">Periods</span>
          <input type="number" className="input" value={periods} onChange={(e) => setPeriods(e.target.value)} min={1} max={52} />
        </label>
        <button className="btn btn-primary" type="submit" disabled={run.loading}>
          {run.loading ? "Forecasting…" : "Run forecast"}
        </button>
      </form>
      <FormAlert error={run.error} />
      {result ? (
        <div style={{ marginTop: 16 }}>
          <div className="muted small">Confidence: {fmtPct(result.confidence * 100)} · Current: {result.current}</div>
          <h4>Forecast</h4>
          <LineChart data={[...result.historical.slice(-12), ...result.forecast].map((p) => ({
            label: p.period.slice(5),
            value: p.value,
          }))} />
          <div className="card-list" style={{ marginTop: 12 }}>
            {result.forecast.map((f, i) => (
              <div key={i} className="list-row">
                <div className="list-main"><div className="list-title">{f.period}</div></div>
                <b>{f.value.toLocaleString()}</b>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <EmptyState title="No forecast yet" hint="Choose a type and run a forecast." />
      )}
    </div>
  );
}
