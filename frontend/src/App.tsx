import React from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { getToken, getStoredUser } from "./api/client";
import Layout from "./components/Layout";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Dashboard from "./pages/Dashboard";
import Loads from "./pages/Loads";
import LoadDetail from "./pages/LoadDetail";
import Shipments from "./pages/Shipments";
import DispatchBoard from "./pages/DispatchBoard";
import Tracking from "./pages/Tracking";
import Exceptions from "./pages/Exceptions";
import Carriers from "./pages/Carriers";
import Drivers from "./pages/Drivers";
import Fleet from "./pages/Fleet";
import Customers from "./pages/Customers";
import Rates from "./pages/Rates";
import Invoices, { InvoiceDetail } from "./pages/Invoices";
import AICommand from "./pages/AICommand";
import Analytics from "./pages/Analytics";
import Lanes from "./pages/Lanes";
import Documents from "./pages/Documents";
import Inbox from "./pages/Inbox";
import DriverApp from "./pages/DriverApp";
import Admin from "./pages/Admin";
import EmptyState from "./components/EmptyState";

function RequireAuth() {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <Outlet />;
}

function RequireRoles({ roles, children }: { roles: string[]; children: React.ReactNode }) {
  const user = getStoredUser();
  if (!user || !roles.includes(user.role)) {
    return <EmptyState title="Not authorized" hint="Your role can't access this page." />;
  }
  return <>{children}</>;
}

function Home() {
  // Public landing page for visitors; signed-in users go straight to the app.
  if (getToken()) return <Navigate to="/dashboard" replace />;
  return <Landing />;
}

function NotFound() {
  return (
    <div style={{ padding: 48 }}>
      <EmptyState
        title="Page not found"
        hint="The page you're looking for doesn't exist."
        action={<a className="btn btn-primary" href="/">Go home</a>}
      />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route element={<RequireAuth />}>
          <Route element={<Layout />}>
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="loads" element={<Loads />} />
            <Route path="loads/:id" element={<LoadDetail />} />
            <Route path="shipments" element={<Shipments />} />
            <Route path="dispatch" element={<DispatchBoard />} />
            <Route path="tracking" element={<Tracking />} />
            <Route path="exceptions" element={<Exceptions />} />
            <Route path="carriers" element={<Carriers />} />
            <Route path="drivers" element={<Drivers />} />
            <Route path="fleet" element={<Fleet />} />
            <Route path="customers" element={<Customers />} />
            <Route path="rates" element={<Rates />} />
            <Route
              path="invoices"
              element={<RequireRoles roles={["admin", "finance", "broker", "ops_manager"]}><Invoices /></RequireRoles>}
            />
            <Route
              path="invoices/:id"
              element={<RequireRoles roles={["admin", "finance", "broker", "ops_manager"]}><InvoiceDetail /></RequireRoles>}
            />
            <Route path="ai" element={<AICommand />} />
            <Route
              path="analytics"
              element={<RequireRoles roles={["admin", "finance", "ops_manager", "broker", "dispatcher"]}><Analytics /></RequireRoles>}
            />
            <Route path="lanes" element={<Lanes />} />
            <Route path="documents" element={<Documents />} />
            <Route path="inbox" element={<Inbox />} />
            <Route
              path="driver"
              element={<RequireRoles roles={["admin", "dispatcher", "driver"]}><DriverApp /></RequireRoles>}
            />
            <Route
              path="admin/*"
              element={<RequireRoles roles={["admin"]}><Admin /></RequireRoles>}
            />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}
