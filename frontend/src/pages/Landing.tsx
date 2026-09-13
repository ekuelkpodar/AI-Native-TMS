import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import "./Landing.css";

function useReveal() {
  useEffect(() => {
    const els = Array.from(document.querySelectorAll(".lp .rv"));
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("in");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.1 }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
}

function Nav() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <nav className={`lp-nav${scrolled ? " scrolled" : ""}`}>
      <div className="lp-nav-inner">
        <Link to="/" className="lp-logo">
          <span className="lp-logo-mark">◈</span>
          DispatchOS
        </Link>
        <div className="lp-links">
          <a href="#platform">Platform</a>
          <a href="#agents">AI Agents</a>
          <a href="#how">How it works</a>
          <a href="#pricing">Pricing</a>
        </div>
        <div className="lp-nav-cta">
          <Link to="/login" className="lp-btn lp-btn-ghost lp-btn-sm">
            Sign in
          </Link>
          <Link to="/signup" className="lp-btn lp-btn-primary lp-btn-sm">
            Get started →
          </Link>
        </div>
      </div>
    </nav>
  );
}

const BARS = [42, 68, 55, 80, 62, 92, 74, 88, 58, 96, 70, 84, 66, 90, 76, 100];

function HeroVisual() {
  return (
    <div className="lp-visual rv">
      <div className="lp-glowline" />
      <div className="lp-chip lp-chip-1">
        <span className="cd">✓</span>
        <span>
          Exception resolved
          <small>Dispatch Agent · 38s ago</small>
        </span>
      </div>
      <div className="lp-chip lp-chip-2">
        <span className="cd">◈</span>
        <span>
          Carrier reassigned
          <small>Approved by you · margin +4.2%</small>
        </span>
      </div>
      <div className="lp-mock">
        <div className="lp-mock-bar">
          <i /> <i /> <i />
          <span className="lp-mock-url">app.dispatchos.ai/dashboard</span>
        </div>
        <div className="lp-mock-body">
          <div className="lp-mock-left">
            <div className="lp-mock-title">Operations overview · today</div>
            <div className="lp-kpis">
              <div className="lp-kpi">
                <div className="k">Active loads</div>
                <div className="v">36</div>
              </div>
              <div className="lp-kpi">
                <div className="k">Revenue MTD</div>
                <div className="v">
                  $133k <span className="up">▲ 12%</span>
                </div>
              </div>
              <div className="lp-kpi">
                <div className="k">On-time</div>
                <div className="v">100%</div>
              </div>
              <div className="lp-kpi">
                <div className="k">In transit</div>
                <div className="v">27</div>
              </div>
              <div className="lp-kpi">
                <div className="k">Margin MTD</div>
                <div className="v">
                  16.5% <span className="up">▲ 1.8</span>
                </div>
              </div>
              <div className="lp-kpi">
                <div className="k">Exceptions</div>
                <div className="v">
                  80 <span className="warn">1 critical</span>
                </div>
              </div>
            </div>
            <div className="lp-mock-title">Revenue · last 16 weeks</div>
            <div className="lp-chart">
              {BARS.map((h, i) => (
                <i key={i} style={{ height: `${h}%`, animationDelay: `${i * 70}ms` }} />
              ))}
            </div>
          </div>
          <div className="lp-mock-right">
            <div className="lp-mock-title">AI activity</div>
            <div className="lp-feed">
              <span className="fi ai">◈</span>
              <span>
                <b>Carrier Matcher proposed a swap</b>
                <span>Load #4812 · saves $340, score 94 → awaiting approval</span>
              </span>
            </div>
            <div className="lp-feed">
              <span className="fi warn">⚠</span>
              <span>
                <b>Late delivery risk detected</b>
                <span>Load #4771 · ETA slipped 42 min · driver notified</span>
              </span>
            </div>
            <div className="lp-feed">
              <span className="fi ok">✓</span>
              <span>
                <b>POD validated → invoice issued</b>
                <span>Load #4690 · $2,850 · automation rule “pod-to-cash”</span>
              </span>
            </div>
            <div className="lp-feed">
              <span className="fi ai">◈</span>
              <span>
                <b>Forecast updated</b>
                <span>ATL→DAL lane · demand +18% next week</span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const TICKS = [
  ["ATL → DAL", "1,240 mi", "$2,850"],
  ["CHI → ATL", "720 mi", "$1,940"],
  ["LAX → PHX", "380 mi", "$1,120"],
  ["SEA → DEN", "1,320 mi", "$3,050"],
  ["MIA → ATL", "660 mi", "$1,780"],
  ["DAL → HOU", "240 mi", "$780"],
  ["NYC → CHI", "790 mi", "$2,150"],
  ["DEN → PHX", "830 mi", "$2,020"],
];

function Ticker() {
  const row = [...TICKS, ...TICKS];
  return (
    <div className="lp-ticker" aria-hidden>
      <div className="lp-ticker-track">
        {row.map(([lane, mi, rate], i) => (
          <span className="lp-tick" key={i}>
            <span className="live" />
            <b>{lane}</b> {mi} · {rate}
          </span>
        ))}
      </div>
    </div>
  );
}

const FEATURES: [string, string, string][] = [
  ["▤", "Load lifecycle, end to end", "Quote → tender → dispatch → POD → invoice → paid, with server-side status guards so nothing skips a step or slips through the cracks."],
  ["⤢", "Dispatch board", "Drag loads onto drivers with live conflict warnings — double-booking, appointment overlap, capacity, and compliance flags before you commit."],
  ["◎", "Live tracking", "GPS pings rendered along every lane, per-load route and ETA views, and automatic delay detection the moment a truck falls behind."],
  ["⚠", "Exception radar", "Late pickups, missing PODs, margin anomalies, route deviations — detected automatically, worked through acknowledge/resolve flows."],
  ["◍", "Carrier intelligence", "MC/DOT and insurance compliance plus a deterministic carrier score with per-factor explanations: rate, on-time %, lane history."],
  ["▦", "Finance & analytics", "Invoices with line items, payments, lane profitability, and financial analytics — know your margin on every load, every lane."],
];

function Features() {
  return (
    <section className="lp-section" id="platform">
      <div className="lp-center rv">
        <span className="lp-eyebrow">The platform</span>
        <h2 className="lp-h2">Everything a brokerage runs on.<br />Nothing it fights with.</h2>
        <p className="lp-lead">
          One system for the full freight lifecycle — built for brokers, dispatchers,
          carriers, and finance teams alike.
        </p>
      </div>
      <div className="lp-grid6">
        {FEATURES.map(([icon, title, body], i) => (
          <div className={`lp-card rv rv-d${(i % 3) + 1}`} key={title}>
            <div className="ic">{icon}</div>
            <h3>{title}</h3>
            <p>{body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

const AGENTS: { icon: string; name: string; desc: string; lvl: string; lvlLabel: string }[] = [
  { icon: "⤢", name: "Dispatch Agent", desc: "Assigns loads, resolves conflicts, and proposes swaps when a better option appears.", lvl: "l3", lvlLabel: "Autonomy L3" },
  { icon: "◍", name: "Carrier Matcher", desc: "Scores carriers per load across rate, reliability, and lane history — with explanations.", lvl: "l4", lvlLabel: "Autonomy L4" },
  { icon: "⚠", name: "Exception Watcher", desc: "Scans every load continuously for late risk, missing documents, and margin drift.", lvl: "l3", lvlLabel: "Autonomy L3" },
  { icon: "◈", name: "Rate Optimizer", desc: "Spot-quotes with live margin analysis and flags quotes that break your floor.", lvl: "l3", lvlLabel: "Autonomy L3" },
  { icon: "▦", name: "Document Parser", desc: "Reads BOLs and PODs, validates them, and triggers invoicing on clean POD.", lvl: "l4", lvlLabel: "Autonomy L4" },
  { icon: "◐", name: "Forecast Engine", desc: "Predicts lane demand and rate movement so you price next week with data.", lvl: "l2", lvlLabel: "Autonomy L2" },
];

function Agents() {
  return (
    <section className="lp-section" id="agents">
      <div className="rv">
        <span className="lp-eyebrow">Governed AI</span>
        <h2 className="lp-h2">Nine AI agents.<br />Zero unapproved surprises.</h2>
        <p className="lp-lead">
          Agents act inside a policy engine with autonomy levels 0–4. Anything financial,
          destructive, or cross-tenant lands in your approval queue first — every action
          fully audited: who, what, why, and under which policy.
        </p>
      </div>
      <div className="lp-agents">
        {AGENTS.map((a, i) => (
          <div className={`lp-card lp-agent rv rv-d${(i % 3) + 1}`} key={a.name}>
            <div className="lp-agent-top">
              <div className="ic">{a.icon}</div>
              <h3>{a.name}</h3>
              <span className={`lp-lvl ${a.lvl}`}>{a.lvlLabel}</span>
            </div>
            <p>{a.desc}</p>
          </div>
        ))}
      </div>
      <div className="lp-policy rv">
        <b>Policy engine</b>
        <span>Every agent action is evaluated:</span>
        <span className="tag allow">allow</span>
        <span className="tag approval">require_approval</span>
        <span className="tag deny">deny</span>
        <span>— with human approval gates for pricing changes, bulk outreach, and refunds.</span>
      </div>
    </section>
  );
}

function Stats() {
  return (
    <div className="lp-stats">
      <div className="lp-stats-inner">
        {[
          ["120", "loads under management", ""],
          ["9", "AI agents on duty", ""],
          ["16.5%", "average margin MTD", ""],
          ["100%", "on-time delivery", ""],
        ].map(([n, label]) => (
          <div className="lp-stat rv" key={label}>
            <div className="n">{n}</div>
            <div className="l">{label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

const STEPS: [string, string, string][] = [
  ["01", "Connect your operation", "Import customers, carriers, and drivers — or start from our realistic demo dataset and make it yours."],
  ["02", "Set your policies", "Define margin floors, approval thresholds, and automation rules. The AI learns your boundaries, not someone else's."],
  ["03", "Approve, don't babysit", "Agents handle the routine; you approve the exceptions. Every decision logged, every dollar traceable."],
];

function How() {
  return (
    <section className="lp-section" id="how">
      <div className="lp-center rv">
        <span className="lp-eyebrow">How it works</span>
        <h2 className="lp-h2">Live in an afternoon.</h2>
        <p className="lp-lead">No rip-and-replace. No six-month implementation.</p>
      </div>
      <div className="lp-steps">
        {STEPS.map(([num, title, body], i) => (
          <div className={`lp-card lp-step rv rv-d${i + 1}`} key={num}>
            <div className="num">{num}</div>
            <h3>{title}</h3>
            <p>{body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

const PLANS = [
  {
    plan: "Starter", amount: "$199", per: "/mo", desc: "For new brokerages getting organized.",
    features: ["Up to 50 active loads", "Core dispatch & tracking", "3 AI agents", "Invoicing & payments", "Email support"],
    cta: "Start free trial", featured: false,
  },
  {
    plan: "Professional", amount: "$599", per: "/mo", desc: "For growing teams that want leverage.",
    features: ["Unlimited loads", "Full dispatch board & automation rules", "All 9 AI agents", "Policy engine & approvals", "Carrier scorecards & analytics", "Priority support"],
    cta: "Start free trial", featured: true,
  },
  {
    plan: "Enterprise", amount: "Custom", per: "", desc: "For 3PLs with serious volume.",
    features: ["Everything in Professional", "SSO & custom roles", "Dedicated success manager", "Custom integrations (ELD, EDI)", "99.99% SLA"],
    cta: "Talk to sales", featured: false,
  },
];

function Pricing() {
  return (
    <section className="lp-section" id="pricing">
      <div className="lp-center rv">
        <span className="lp-eyebrow">Pricing</span>
        <h2 className="lp-h2">Pays for itself on<br />the first good week.</h2>
        <p className="lp-lead">Transparent per-month pricing. No per-load fees. Cancel anytime.</p>
      </div>
      <div className="lp-pricing">
        {PLANS.map((p, i) => (
          <div className={`lp-card lp-price${p.featured ? " featured" : ""} rv rv-d${i + 1}`} key={p.plan}>
            {p.featured && <span className="lp-flag">Most popular</span>}
            <div className="plan">{p.plan}</div>
            <div className="amount">{p.amount}<small>{p.per}</small></div>
            <div className="desc">{p.desc}</div>
            <ul>
              {p.features.map((f) => <li key={f}>{f}</li>)}
            </ul>
            <Link to="/signup" className={`lp-btn ${p.featured ? "lp-btn-primary" : "lp-btn-ghost"} btn-block`} style={{ width: "100%" }}>
              {p.cta}
            </Link>
          </div>
        ))}
      </div>
    </section>
  );
}

const QUOTES: [string, string, string, string][] = [
  ["DispatchOS caught a late delivery 40 minutes before our customer noticed. The agent had already notified the driver and proposed a recovery plan. That's the job.", "Marcus Webb", "Owner, Webb Logistics", "MW"],
  ["We went from spreadsheets and group chats to a system where the AI does the chasing and I just approve. Margin is up 3 points in two months.", "Priya Raman", "Broker, Apex Freight Co.", "PR"],
  ["The approval queue is the killer feature. The agents are fast, but I'm always the one who says yes on money. Total control, none of the busywork.", "Dana Whitfield", "Dispatcher, BlueLine 3PL", "DW"],
];

function Testimonials() {
  return (
    <section className="lp-section">
      <div className="lp-center rv">
        <span className="lp-eyebrow">Loved by operators</span>
        <h2 className="lp-h2">Brokers who sleep<br />through the night shift.</h2>
      </div>
      <div className="lp-quotes">
        {QUOTES.map(([quote, name, role, initials], i) => (
          <div className={`lp-card lp-quote rv rv-d${i + 1}`} key={name}>
            <p>“{quote}”</p>
            <div className="who">
              <span className="lp-avatar">{initials}</span>
              <span><b>{name}</b><span>{role}</span></span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="lp-footer">
      <div className="lp-footer-inner">
        <div>
          <Link to="/" className="lp-logo" style={{ marginBottom: 16 }}>
            <span className="lp-logo-mark">◈</span>
            DispatchOS
          </Link>
          <p>The AI-native transportation management system. Freight runs on autopilot — you run the business.</p>
        </div>
        <div>
          <h4>Product</h4>
          <ul>
            <li><a href="#platform">Platform</a></li>
            <li><a href="#agents">AI Agents</a></li>
            <li><a href="#pricing">Pricing</a></li>
            <li><Link to="/signup">Get started</Link></li>
          </ul>
        </div>
        <div>
          <h4>Company</h4>
          <ul>
            <li><a href="#how">How it works</a></li>
            <li><Link to="/login">Sign in</Link></li>
            <li><Link to="/signup">Sign up</Link></li>
          </ul>
        </div>
        <div>
          <h4>Resources</h4>
          <ul>
            <li><a href="#platform">Documentation</a></li>
            <li><a href="#agents">API reference</a></li>
            <li><a href="#pricing">Status</a></li>
          </ul>
        </div>
      </div>
      <div className="lp-copy">
        <span>© 2026 DispatchOS. All rights reserved.</span>
        <span>Built for the people who move the world.</span>
      </div>
    </footer>
  );
}

export default function Landing() {
  useReveal();
  return (
    <div className="lp">
      <div className="lp-aurora" aria-hidden><i /><i /><i /><i /></div>
      <div className="lp-grid" aria-hidden />
      <Nav />
      <main className="lp-main">
        <section className="lp-hero">
          <span className="lp-badge rv"><span className="dot" /> AI-native TMS · now with 9 governed agents</span>
          <h1 className="rv rv-d1">
            Freight runs on autopilot.<br />
            <span className="lp-grad">You run the business.</span>
          </h1>
          <p className="lp-sub rv rv-d2">
            DispatchOS is the transportation management system with an AI operations
            layer built in — dispatching loads, watching exceptions, and optimizing
            margin around the clock, under policies you control.
          </p>
          <div className="lp-hero-ctas rv rv-d3">
            <Link to="/signup" className="lp-btn lp-btn-primary lp-btn-lg">Start free trial →</Link>
            <Link to="/login" className="lp-btn lp-btn-ghost lp-btn-lg">Sign in</Link>
          </div>
          <p className="lp-hero-note rv rv-d3">
            No credit card required · Or explore the live demo — <code>admin@demo.tms</code> / <code>Demo1234!</code>
          </p>
        </section>
        <HeroVisual />
        <Ticker />
        <Features />
        <Agents />
        <Stats />
        <How />
        <Pricing />
        <Testimonials />
        <div className="lp-cta">
          <div className="lp-cta-box rv">
            <h2>Put your brokerage<br />on <span className="lp-grad">autopilot</span>.</h2>
            <p>Join the operators running freight with AI they can actually trust.</p>
            <div className="lp-hero-ctas">
              <Link to="/signup" className="lp-btn lp-btn-primary lp-btn-lg">Get started free →</Link>
              <Link to="/login" className="lp-btn lp-btn-ghost lp-btn-lg">Sign in</Link>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
