import React, { useState } from "react";
import "./LoginPage.css";

function LoginPage({ onLogin, onSwitchToRegister }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    setError("");

    // Validate email format
    if (!email.includes("@")) {
      setError("Please enter a valid email address with '@'.");
      return;
    }

    // Get users from localStorage
    const users = JSON.parse(localStorage.getItem("equirisk_users") || "[]");

    // Hard-coded demo credentials still work
    const DEMO_EMAIL = "test@equirisk.ai";
    const DEMO_PASSWORD = "test123";

    // Check if it's the demo account
    if (email === DEMO_EMAIL && password === DEMO_PASSWORD) {
      onLogin(true);
      return;
    }

    // Check registered users
    const user = users.find((u) => u.email === email && u.password === password);

    if (user) {
      onLogin(true);
    } else {
      setError("Invalid email or password. Please try again.");
    }
  };

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-header">
          <h1 className="login-logo">EquiRisk</h1>
          <p className="login-subtitle">Sign in to your account</p>
        </div>

        <form className="login-form" onSubmit={handleSubmit} noValidate>
          {error && <div className="login-error">{error}</div>}

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="test@equirisk.ai"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
            />
          </div>

          <button type="submit" className="login-button">
            Sign In
          </button>
        </form>

        <div className="login-footer">
          <p className="login-hint" style={{ marginTop: '8px' }}>
            Don't have an account?{" "}
            <button
              onClick={onSwitchToRegister}
              className="link-button"
              type="button"
            >
              Register here
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
