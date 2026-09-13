import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import CommandPalette from "./CommandPalette";
import { clearAuth, getStoredUser, notificationsApi, type Notification } from "../api/client";

interface NavItem {
  to: string;
  label: string;
  icon: string;
  roles?: string[]; // undefined = all
  adminOnly?: boolean;
}

const NAV: NavItem[] = [
  { to: "/", label: "Dashboard", icon: "◈" },
  { to: "/loads", label: "Loads", icon: "▤" },
  { to: "/shipments", label: "Shipments", icon: "▦" },
  { to: "/dispatch", label: "Dispatch", icon: "⤢" },
  { to: "/tracking", label: "Tracking", icon: "◎" },
  { to: "/exceptions", label: "Exceptions", icon: "⚠" },
  { to: "/carriers", label: "Carriers", icon: "◍" },
  { to: "/drivers", label: "Drivers", icon: "◐" },
  { to: "/fleet", label: "Fleet", icon: "⬓" },
  { to: "/customers", label: "Customers", icon: "◒" },
  { to: "/rates", label: "Rates", icon: "$" },
  { to: "/invoices", label: "Invoices", icon: "▧", roles: ["admin", "finance", "broker", "ops_manager"] },
  { to: "/ai", label: "AI Command", icon: "✦" },
  { to: "/analytics", label: "Analytics", icon: "▥", roles: ["admin", "finance", "ops_manager", "broker", "dispatcher"] },
  { to: "/lanes", label: "Lanes", icon: "⇄" },
  { to: "/documents", label: "Documents", icon: "▭" },
  { to: "/inbox", label: "Inbox", icon: "✉" },
  { to: "/driver", label: "Driver App", icon: "☰", roles: ["admin", "dispatcher", "driver"] },
  { to: "/admin/users", label: "Admin", icon: "⚙", adminOnly: true },
];

export default function Layout() {
  const navigate = useNavigate();
  const user = getStoredUser();
  const [palette, setPalette] = useState(false);
  const [notifs, setNotifs] = useState<Notification[]>([]);
  const [showNotif, setShowNotif] = useState(false);
  const [showUser, setShowUser] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPalette((p) => !p);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    let alive = true;
    notificationsApi.list({ page_size: 10 }).then((r) => {
      if (alive) setNotifs(r.items);
    }).catch(() => {});
    const t = setInterval(() => {
      notificationsApi.list({ page_size: 10 }).then((r) => {
        if (alive) setNotifs(r.items);
      }).catch(() => {});
    }, 60000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const unread = notifs.filter((n) => !n.is_read).length;

  const visibleNav = NAV.filter((n) => {
    if (n.adminOnly) return user?.role === "admin";
    if (n.roles) return user && n.roles.includes(user.role);
    return true;
  });

  const logout = () => {
    clearAuth();
    navigate("/login");
  };

  return (
    <div className={`app-shell ${collapsed ? "collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">◈</div>
          {!collapsed && <div className="brand-name">DispatchOS</div>}
        </div>
        <nav className="nav">
          {visibleNav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
              title={n.label}
            >
              <span className="nav-icon">{n.icon}</span>
              {!collapsed && <span className="nav-label">{n.label}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <button className="icon-btn" onClick={() => setCollapsed((c) => !c)} aria-label="Toggle sidebar">
            {collapsed ? "»" : "«"}
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <button className="search-trigger" onClick={() => setPalette(true)}>
            <span className="search-icon">⌕</span>
            <span className="search-hint">Search or ask AI…</span>
            <kbd>⌘K</kbd>
          </button>
          <div className="topbar-right">
            <div className="notif-wrap">
              <button className="icon-btn notif-btn" onClick={() => { setShowNotif((s) => !s); setShowUser(false); }}>
                🔔
                {unread > 0 && <span className="notif-dot">{unread > 9 ? "9+" : unread}</span>}
              </button>
              {showNotif && (
                <div className="dropdown notif-dropdown">
                  <div className="dropdown-head">Notifications</div>
                  {notifs.length === 0 && <div className="dropdown-empty">No notifications</div>}
                  {notifs.slice(0, 8).map((n) => (
                    <div key={n.id} className={`notif-item ${n.is_read ? "" : "unread"}`}>
                      <div className="notif-title">{n.title}</div>
                      <div className="notif-body">{n.body}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="user-wrap">
              <button className="user-btn" onClick={() => { setShowUser((s) => !s); setShowNotif(false); }}>
                <span className="avatar">{(user?.full_name || user?.email || "?").slice(0, 1).toUpperCase()}</span>
                {!collapsed && <span className="user-name">{user?.full_name || user?.email}</span>}
              </button>
              {showUser && (
                <div className="dropdown user-dropdown">
                  <div className="dropdown-head">{user?.email}<br /><span className="muted">{user?.role}</span></div>
                  <button className="dropdown-item" onClick={() => { setShowUser(false); navigate("/admin/settings"); }}>Settings</button>
                  <button className="dropdown-item" onClick={logout}>Log out</button>
                </div>
              )}
            </div>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
      <CommandPalette open={palette} onClose={() => setPalette(false)} />
    </div>
  );
}
