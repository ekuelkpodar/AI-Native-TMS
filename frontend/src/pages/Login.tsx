import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { authApi, setToken, setStoredUser } from "../api/client";
import { FormAlert } from "../components/Page";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError("Email and password are required.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await authApi.login(email.trim(), password);
      setToken(res.access_token);
      setStoredUser(res.user);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <div className="brand-mark lg">◈</div>
          <div>
            <div className="login-title">DispatchOS</div>
            <div className="muted">AI-Native Transportation Management</div>
          </div>
        </div>
        <form onSubmit={submit} className="login-form">
          <label className="field">
            <span className="field-label">Work email</span>
            <input
              className="input"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
            />
          </label>
          <label className="field">
            <span className="field-label">Password</span>
            <input
              className="input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </label>
          <FormAlert error={error} />
          <button className="btn btn-primary btn-block" type="submit" disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <div className="login-foot muted">SSO is configured per organization by your admin.</div>
      </div>
    </div>
  );
}
