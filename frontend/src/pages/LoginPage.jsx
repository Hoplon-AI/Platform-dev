import React, { useState } from "react";
import "./LoginPage.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export default function LoginPage({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showPassword, setShowPassword] = useState(false);
  const [capsOn, setCapsOn] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data?.detail || "Invalid email or password.");
      }

      const storage = rememberMe ? localStorage : sessionStorage;
      storage.setItem("equirisk_token", data.access_token);
      storage.setItem("equirisk_user", JSON.stringify({
        email: email.trim().toLowerCase(),
        full_name: data.full_name,
        organisation: data.organisation,
        user_type: data.user_type,
        ha_ids: data.ha_ids,
      }));

      onLogin({
        token: data.access_token,
        full_name: data.full_name,
        organisation: data.organisation,
        user_type: data.user_type,
        ha_ids: data.ha_ids,
        email: email.trim().toLowerCase(),
      });
    } catch (err) {
      setError(err.message || "Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const trackCaps = (e) => {
    if (typeof e.getModifierState === "function") {
      setCapsOn(e.getModifierState("CapsLock"));
    }
  };

  return (
    <div className="login-page">
      {/* ── Brand / narrative panel (rose break-band) ── */}
      <aside className="login-panel">
        <div className="login-panel-content">
          <span className="login-brand-mark">
            <img src="/logo.png" alt="EquiRisk" />
          </span>

          <div className="login-panel-center">
          <span className="login-kicker">Social-housing risk intelligence</span>

          <h1 className="login-headline">
            Every block accounted for. Every risk <em>in view</em>.
          </h1>

          <p className="login-sub">
            Sign in to your housing-association risk portfolios.<br />
            Per-unit and per-block schedules,<br />
            enriched and evidence-backed.
          </p>

          <ul className="login-trust">
            <li><CheckIcon /> SoV, FRA &amp; FRAEW evidence in one schedule</li>
            <li><CheckIcon /> Per-block and per-unit risk, priced to underwrite</li>
            <li><CheckIcon /> Built for UK social-housing portfolios</li>
          </ul>
        </div>

          <span className="login-pi">
            <span className="pi-p">Premium</span>
            <span className="pi-i">Intelligence</span>
          </span>
        </div>

        <div className="login-photo" role="img" aria-label="A corten-clad social-housing block" />
      </aside>

      {/* ── Sign-in form ── */}
      <main className="login-form-pane">
        <div className="login-mid">
          <span className="login-form-kicker">Underwriter portal</span>
          <h2 className="login-heading">Sign in</h2>
          <p className="login-subheading">
            Secure access to housing association risk portfolios.
          </p>

          <form onSubmit={handleSubmit} className="login-form" noValidate>
            {/* Email */}
            <div className="login-field">
              <label className="login-label" htmlFor="email">Email address</label>
              <input
                id="email"
                className="login-input"
                type="email"
                autoComplete="email"
                autoFocus
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@organisation.com"
                disabled={loading}
              />
            </div>

            {/* Password */}
            <div className="login-field">
              <label className="login-label" htmlFor="password">Password</label>
              <div className="login-pass-wrap">
                <input
                  id="password"
                  className="login-input"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyUp={trackCaps}
                  onKeyDown={trackCaps}
                  onBlur={() => setCapsOn(false)}
                  placeholder="••••••••"
                  disabled={loading}
                />
                <button
                  type="button"
                  className="login-eye"
                  onClick={() => setShowPassword((v) => !v)}
                  tabIndex={-1}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                </button>
              </div>
              {capsOn && (
                <span className="login-capslock">
                  <WarnIcon /> Caps Lock is on
                </span>
              )}
            </div>

            {/* Remember me */}
            <div className="login-remember">
              <label className="login-check">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  disabled={loading}
                />
                Remember me for 8 hours
              </label>
            </div>

            {/* Error */}
            {error && (
              <div className="login-error" role="alert" aria-live="assertive">
                <WarnIcon /> {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              className="login-submit"
              disabled={loading || !email || !password}
              aria-busy={loading}
            >
              {loading ? (
                <span className="login-spinner-row">
                  <span className="login-spinner" /> Signing in…
                </span>
              ) : (
                <>
                  Sign in
                  <ArrowIcon />
                </>
              )}
            </button>
          </form>
        </div>

        <p className="login-footer">
          Access is granted by your insurance broker or housing association contact.
          <br />
          Contact <strong>support@equirisk.ai</strong> for access requests.
        </p>
      </main>
    </div>
  );
}

// ── Inline icons ──────────────────────────────────────────────────

function EyeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg className="login-arrow" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function WarnIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}
