import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi, setToken, setStoredUser } from "../api/client";
import "./Landing.css";

export default function Signup() {
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [company, setCompany] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim() || !company.trim() || !email.trim() || !password) {
      setError("Please fill in every field.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await authApi.register({
        full_name: fullName.trim(),
        company_name: company.trim(),
        email: email.trim(),
        password,
      });
      setToken(res.access_token);
      setStoredUser(res.user);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign up failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="lp">
      <div className="lp-aurora" aria-hidden><i /><i /><i /><i /></div>
      <div className="lp-grid" aria-hidden />
      <nav className="lp-nav scrolled">
        <div className="lp-nav-inner">
          <Link to="/" className="lp-logo">
            <span className="lp-logo-mark">◈</span>
            DispatchOS
          </Link>
          <div className="lp-nav-cta">
            <Link to="/login" className="lp-btn lp-btn-ghost lp-btn-sm">Sign in</Link>
          </div>
        </div>
      </nav>
      <div className="lp-auth">
        <div className="lp-auth-card">
          <Link to="/" className="lp-logo">
            <span className="lp-logo-mark">◈</span>
            DispatchOS
          </Link>
          <h1>Create your workspace</h1>
          <p className="sub">
            Start your free trial. Your organization, your data, your policies —
            up and running in under a minute.
          </p>
          <form onSubmit={submit}>
            <label className="lp-field">
              <span>Full name</span>
              <input
                className="lp-input"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Ava Mitchell"
                autoComplete="name"
              />
            </label>
            <label className="lp-field">
              <span>Company name</span>
              <input
                className="lp-input"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Demo Logistics Co"
                autoComplete="organization"
              />
            </label>
            <label className="lp-field">
              <span>Work email</span>
              <input
                className="lp-input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                autoComplete="email"
              />
            </label>
            <label className="lp-field">
              <span>Password</span>
              <input
                className="lp-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                autoComplete="new-password"
              />
            </label>
            {error && <div className="lp-err">{error}</div>}
            <button className="lp-btn lp-btn-primary btn-block" style={{ width: "100%" }} type="submit" disabled={loading}>
              {loading ? "Creating your workspace…" : "Start free trial →"}
            </button>
          </form>
          <div className="lp-auth-foot">
            Already have an account? <Link to="/login">Sign in</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
