import React, { useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export default function LoginPage({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showPassword, setShowPassword] = useState(false);

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

  return (
    <div style={styles.page}>
      {/* Background pattern */}
      <div style={styles.bgAccent} />

      <div style={styles.card}>
        {/* Brand */}
        <div style={styles.brandRow}>
          <img src="/logo.png" alt="EquiRisk" style={{ height: 40, width: "auto", display: "block", marginBottom: 8 }} />
          <span style={styles.brandBadge}>UNDERWRITER PORTAL</span>
        </div>

        <h1 style={styles.heading}>Sign in to your account</h1>
        <p style={styles.subheading}>
          Secure access to housing association risk portfolios
        </p>

        <form onSubmit={handleSubmit} style={styles.form}>
          {/* Email */}
          <div style={styles.field}>
            <label style={styles.label} htmlFor="email">
              Email address
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={styles.input}
              placeholder="you@organisation.com"
              disabled={loading}
            />
          </div>

          {/* Password */}
          <div style={styles.field}>
            <label style={styles.label} htmlFor="password">
              Password
            </label>
            <div style={styles.passwordWrapper}>
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{ ...styles.input, paddingRight: 44 }}
                placeholder="••••••••"
                disabled={loading}
              />
              <button
                type="button"
                style={styles.eyeBtn}
                onClick={() => setShowPassword((v) => !v)}
                tabIndex={-1}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <EyeOffIcon />
                ) : (
                  <EyeIcon />
                )}
              </button>
            </div>
          </div>

          {/* Remember me */}
          <div style={styles.rememberRow}>
            <label style={styles.checkLabel}>
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                style={styles.checkbox}
                disabled={loading}
              />
              Remember me for 8 hours
            </label>
          </div>

          {/* Error */}
          {error && (
            <div style={styles.errorBox}>
              <span style={styles.errorIcon}>&#9888;</span> {error}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading || !email || !password}
            style={{
              ...styles.submitBtn,
              ...(loading || !email || !password ? styles.submitBtnDisabled : {}),
            }}
          >
            {loading ? (
              <span style={styles.spinnerRow}>
                <Spinner /> Signing in…
              </span>
            ) : (
              "Sign in"
            )}
          </button>
        </form>

        <p style={styles.footer}>
          Access is granted by your insurance broker or housing association contact.
          <br />
          Contact <strong>support@equirisk.ai</strong> for access requests.
        </p>
      </div>
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

function Spinner() {
  return (
    <span style={{
      display: "inline-block",
      width: 14,
      height: 14,
      border: "2px solid rgba(255,255,255,0.4)",
      borderTopColor: "#fff",
      borderRadius: "50%",
      animation: "spin 0.7s linear infinite",
      marginRight: 8,
    }} />
  );
}

// ── Styles ────────────────────────────────────────────────────────

const styles = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "linear-gradient(135deg, #f0f6ff 0%, #f5f7fb 60%, #eef2f7 100%)",
    padding: "24px 16px",
    position: "relative",
    overflow: "hidden",
  },
  bgAccent: {
    position: "absolute",
    top: -200,
    right: -200,
    width: 600,
    height: 600,
    borderRadius: "50%",
    background: "radial-gradient(circle, rgba(37,99,235,0.06) 0%, transparent 70%)",
    pointerEvents: "none",
  },
  card: {
    background: "#ffffff",
    borderRadius: 16,
    boxShadow: "0 4px 32px rgba(15,23,42,0.10), 0 1px 4px rgba(15,23,42,0.06)",
    padding: "40px 40px 32px",
    width: "100%",
    maxWidth: 440,
    position: "relative",
    zIndex: 1,
  },
  brandRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    marginBottom: 28,
  },
  brandName: {
    fontSize: 26,
    fontWeight: 800,
    letterSpacing: "-0.04em",
    color: "#2563eb",
    lineHeight: 1,
  },
  brandBadge: {
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: "0.08em",
    color: "#2563eb",
    background: "#dbeafe",
    borderRadius: 4,
    padding: "3px 7px",
    lineHeight: 1.4,
  },
  heading: {
    fontSize: 20,
    fontWeight: 700,
    color: "#0f172a",
    margin: "0 0 6px",
    letterSpacing: "-0.02em",
  },
  subheading: {
    fontSize: 14,
    color: "#64748b",
    margin: "0 0 28px",
    lineHeight: 1.5,
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: 18,
  },
  field: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
  label: {
    fontSize: 13,
    fontWeight: 600,
    color: "#374151",
    letterSpacing: "0.01em",
  },
  input: {
    width: "100%",
    padding: "10px 14px",
    fontSize: 14,
    color: "#0f172a",
    background: "#f8fafc",
    border: "1.5px solid #e2e8f0",
    borderRadius: 8,
    outline: "none",
    transition: "border-color 0.15s",
    boxSizing: "border-box",
  },
  passwordWrapper: {
    position: "relative",
    display: "flex",
    alignItems: "center",
  },
  eyeBtn: {
    position: "absolute",
    right: 12,
    background: "none",
    border: "none",
    cursor: "pointer",
    color: "#94a3b8",
    padding: 2,
    display: "flex",
    alignItems: "center",
  },
  rememberRow: {
    display: "flex",
    alignItems: "center",
  },
  checkLabel: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: 13,
    color: "#475569",
    cursor: "pointer",
    userSelect: "none",
  },
  checkbox: {
    width: 15,
    height: 15,
    accentColor: "#2563eb",
    cursor: "pointer",
  },
  errorBox: {
    background: "#fee2e2",
    border: "1px solid #fecaca",
    borderRadius: 8,
    padding: "10px 14px",
    fontSize: 13,
    color: "#b91c1c",
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  errorIcon: {
    fontSize: 14,
  },
  submitBtn: {
    width: "100%",
    padding: "12px 0",
    fontSize: 15,
    fontWeight: 700,
    color: "#ffffff",
    background: "#2563eb",
    border: "none",
    borderRadius: 8,
    cursor: "pointer",
    transition: "background 0.15s",
    letterSpacing: "0.01em",
    marginTop: 4,
  },
  submitBtnDisabled: {
    background: "#93c5fd",
    cursor: "not-allowed",
  },
  spinnerRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 0,
  },
  footer: {
    marginTop: 24,
    fontSize: 12,
    color: "#94a3b8",
    textAlign: "center",
    lineHeight: 1.6,
    borderTop: "1px solid #f1f5f9",
    paddingTop: 20,
  },
};
