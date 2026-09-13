import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { analyticsApi, exceptionsApi, loadsApi } from "../api/client";
import { useFetch } from "../lib/hooks";
import { fmtDateTime, fmtMoney, fmtPct, loc } from "../lib/format";
import { PageHeader } from "../components/Page";
import StatCard from "../components/StatCard";
import StatusPill from "../components/StatusPill";
import EmptyState from "../components/EmptyState";
import AIRecommendationCard from "../components/AIRecommendationCard";
import { LineChart, DonutChart } from "../components/Charts";

function Section({ title, to, children }: { title: string; to?: string; children: React.ReactNode }) {
  return (
    <section className="dash-section">
      <div className="section-head">
        <h2>{title}</h2>
        {to && <Link to={to} className="link">View all →</Link>}
      </div>
      {children}
    </section>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const overview = useFetch(() => analyticsApi.overview(), []);
  const critical = useFetch(
    () => exceptionsApi.list({ status: "open", page_size: 5, sort_by: "severity", sort_dir: "asc" }),
    []
  );
  const todayLoads = useFetch(() => loadsApi.list({ page_size: 8, sort_by: "pickup_datetime", sort_dir: "asc" }), []);
  const inTransit = useFetch(
    () => loadsApi.list({ status: "in_transit", page_size: 8, sort_by: "delivery_datetime", sort_dir: "asc" }),
    []
  );

  const o = overview.data;

  return (
    <div>
      <PageHeader
        title="Dashboard"
        sub="Operations at a glance"
        actions={
          <>
            <button className="btn btn-ghost" onClick={() => navigate("/ai")}>✦ Ask AI</button>
            <button className="btn btn-primary" onClick={() => navigate("/loads?new=1")}>+ New load</button>
          </>
        }
      />

      {overview.loading ? (
        <div className="stat-grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="stat-card skeleton-row" style={{ height: 96 }} />
          ))}
        </div>
      ) : overview.error ? (
        <EmptyState
          title="Couldn't load dashboard metrics"
          hint={overview.error}
          action={<button className="btn btn-primary" onClick={overview.reload}>Retry</button>}
        />
      ) : o && (
        <div className="stat-grid">
          <StatCard label="Active loads" value={o.active_loads} to="/loads" />
          <StatCard label="In transit" value={o.in_transit} to="/tracking" deltaTone="neutral" />
          <StatCard label="Open exceptions" value={o.open_exceptions} delta={o.critical_exceptions ? `${o.critical_exceptions} critical` : undefined} deltaTone={o.critical_exceptions ? "down" : "neutral"} to="/exceptions" />
          <StatCard label="Revenue MTD" value={fmtMoney(o.revenue_mtd)} to="/analytics" />
          <StatCard label="Margin MTD" value={fmtMoney(o.margin_mtd)} delta={fmtPct(o.margin_pct)} deltaTone="neutral" to="/analytics" />
          <StatCard label="On-time %" value={fmtPct(o.on_time_pct)} to="/analytics" />
        </div>
      )}

      <Section title="Attention required" to="/exceptions">
        {critical.loading ? (
          <div className="skeleton-row" />
        ) : critical.error ? (
          <div className="muted">Couldn't load exceptions.</div>
        ) : critical.data && critical.data.items.length > 0 ? (
          <div className="card-list">
            {critical.data.items.map((x) => (
              <div key={x.id} className="list-row" onClick={() => navigate("/exceptions")}>
                <StatusPill status={x.severity} />
                <div className="list-main">
                  <div className="list-title">{x.title}</div>
                  <div className="muted small">{x.description}</div>
                </div>
                <span className="muted small">{fmtDateTime(x.detected_at)}</span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="All clear" hint="No open exceptions right now." />
        )}
      </Section>

      <div className="two-col">
        <Section title="Today: pickups & deliveries" to="/loads">
          {todayLoads.loading ? (
            <div className="skeleton-row" />
          ) : todayLoads.data && todayLoads.data.items.length > 0 ? (
            <div className="card-list">
              {todayLoads.data.items.map((l) => (
                <div key={l.id} className="list-row" onClick={() => navigate(`/loads/${l.id}`)}>
                  <div className="list-main">
                    <div className="list-title">{l.load_number} · {loc(l.origin)} → {loc(l.destination)}</div>
                    <div className="muted small">Pickup {fmtDateTime(l.pickup_datetime)} · Delivery {fmtDateTime(l.delivery_datetime)}</div>
                  </div>
                  <StatusPill status={l.status} />
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="Nothing scheduled" hint="No loads due today." />
          )}
        </Section>

        <Section title="Active in transit" to="/tracking">
          {inTransit.loading ? (
            <div className="skeleton-row" />
          ) : inTransit.data && inTransit.data.items.length > 0 ? (
            <div className="card-list">
              {inTransit.data.items.map((l) => (
                <div key={l.id} className="list-row" onClick={() => navigate(`/loads/${l.id}`)}>
                  <div className="list-main">
                    <div className="list-title">{l.load_number} · {loc(l.origin)} → {loc(l.destination)}</div>
                    <div className="muted small">ETA {fmtDateTime(l.delivery_datetime)} · {fmtMoney(l.customer_rate)}</div>
                  </div>
                  <StatusPill status={l.status} />
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No in-transit loads" hint="Nothing moving right now." />
          )}
        </Section>
      </div>

      <Section title="AI recommendations">
        <div className="card-list">
          <AIRecommendationCard
            rec={{
              recommendation: "Run an exception scan to catch late pickups before they cascade.",
              reason: "Loads currently past their pickup appointment window create downstream delivery risk.",
              expected_impact: "Catch delays up to 2h earlier on average",
              confidence: 0.87,
              alternatives: ["Wait for driver check-calls"],
              risks: ["Scan produces false positives on loads with flexible appointments"],
              approval_required: false,
            }}
          />
        </div>
        <button className="btn btn-ghost" onClick={() => navigate("/ai")}>Open AI Command →</button>
      </Section>

      {o && (
        <Section title="Performance" to="/analytics">
          <div className="two-col">
            <div className="card">
              <h3>Revenue by day</h3>
              {o.revenue_by_day.length > 0 ? (
                <LineChart
                  data={o.revenue_by_day.slice(-14).map((r) => ({ label: r.date.slice(5), value: r.revenue }))}
                  formatY={(v) => fmtMoney(v)}
                />
              ) : (
                <EmptyState title="No revenue data" />
              )}
            </div>
            <div className="card">
              <h3>Loads by status</h3>
              {o.loads_by_status.length > 0 ? (
                <DonutChart data={o.loads_by_status.map((s) => ({ label: s.status.replace(/_/g, " "), value: s.count }))} />
              ) : (
                <EmptyState title="No load data" />
              )}
            </div>
          </div>
        </Section>
      )}
    </div>
  );
}
