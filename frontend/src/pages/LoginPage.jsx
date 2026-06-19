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
              onFocus={(e) => { e.target.style.borderColor = "#B8564B"; e.target.style.boxShadow = "0 0 0 3px rgba(184,86,75,0.18)"; }}
              onBlur={(e) => { e.target.style.borderColor = "#DED7CC"; e.target.style.boxShadow = "none"; }}
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
                onFocus={(e) => { e.target.style.borderColor = "#B8564B"; e.target.style.boxShadow = "0 0 0 3px rgba(184,86,75,0.18)"; }}
                onBlur={(e) => { e.target.style.borderColor = "#DED7CC"; e.target.style.boxShadow = "none"; }}
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
            onMouseEnter={(e) => {
              if (loading || !email || !password) return;
              e.currentTarget.style.background = "#9A463D";
              e.currentTarget.style.transform = "translateY(-2px)";
              e.currentTarget.style.boxShadow = "0 12px 28px rgba(184,86,75,0.34)";
            }}
            onMouseLeave={(e) => {
              if (loading || !email || !password) return;
              e.currentTarget.style.background = "#B8564B";
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = "0 6px 18px rgba(184,86,75,0.28)";
            }}
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

const FONT_SANS = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
const FONT_SERIF = "'Playfair Display', Georgia, 'Times New Roman', serif";

const styles = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "linear-gradient(135deg, #F9F7F3 0%, #F3EFE8 100%)",
    padding: "24px 16px",
    position: "relative",
    overflow: "hidden",
    fontFamily: FONT_SANS,
  },
  bgAccent: {
    position: "absolute",
    top: -220,
    right: -180,
    width: 620,
    height: 620,
    borderRadius: "50%",
    background: "radial-gradient(circle, rgba(184,86,75,0.10) 0%, transparent 70%)",
    pointerEvents: "none",
  },
  card: {
    background: "#ffffff",
    borderRadius: 20,
    boxShadow: "0 2px 4px rgba(30,50,70,0.03), 0 18px 48px -24px rgba(30,50,70,0.22)",
    border: "1px solid #EAE5DE",
    padding: "40px 40px 32px",
    width: "100%",
    maxWidth: 440,
    position: "relative",
    zIndex: 1,
  },
  brandRow: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    marginBottom: 28,
  },
  brandBadge: {
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: "0.16em",
    textTransform: "uppercase",
    color: "#9A463D",
    background: "#F7E4D5",
    borderRadius: 999,
    padding: "4px 10px",
    lineHeight: 1.4,
  },
  heading: {
    fontFamily: FONT_SERIF,
    fontSize: 26,
    fontWeight: 600,
    color: "#1E3246",
    margin: "0 0 6px",
    letterSpacing: "-0.01em",
  },
  subheading: {
    fontSize: 14,
    color: "#6B6560",
    margin: "0 0 28px",
    lineHeight: 1.55,
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
    color: "#1E3246",
    letterSpacing: "0.01em",
  },
  input: {
    width: "100%",
    padding: "11px 14px",
    fontSize: 14,
    color: "#1E3246",
    background: "#fff",
    border: "1.5px solid #DED7CC",
    borderRadius: 10,
    transition: "border-color 0.2s, box-shadow 0.2s",
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
    color: "#8A847D",
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
    color: "#6B6560",
    cursor: "pointer",
    userSelect: "none",
  },
  checkbox: {
    width: 15,
    height: 15,
    accentColor: "#B8564B",
    cursor: "pointer",
  },
  errorBox: {
    background: "#F7E0DB",
    border: "1px solid #E8B9B1",
    borderRadius: 10,
    padding: "10px 14px",
    fontSize: 13,
    color: "#9A463D",
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  errorIcon: {
    fontSize: 14,
  },
  submitBtn: {
    width: "100%",
    padding: "13px 0",
    fontSize: 15,
    fontWeight: 600,
    color: "#ffffff",
    background: "#B8564B",
    border: "none",
    borderRadius: 50,
    cursor: "pointer",
    transition: "background 0.32s cubic-bezier(0.22,1,0.36,1), transform 0.32s cubic-bezier(0.22,1,0.36,1), box-shadow 0.32s cubic-bezier(0.22,1,0.36,1)",
    letterSpacing: "0.01em",
    marginTop: 4,
    boxShadow: "0 6px 18px rgba(184,86,75,0.28)",
  },
  submitBtnDisabled: {
    background: "#D8A59D",
    cursor: "not-allowed",
    boxShadow: "none",
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
    color: "#8A847D",
    textAlign: "center",
    lineHeight: 1.6,
    borderTop: "1px solid #EAE5DE",
    paddingTop: 20,
  },
};
