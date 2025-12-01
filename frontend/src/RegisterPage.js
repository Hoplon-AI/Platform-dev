import React, { useState } from "react";
import "./LoginPage.css"; // Reuse the same styles

function RegisterPage({ onRegister, onSwitchToLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    // Validate email format
    if (!email.includes("@")) {
      setError("Please enter a valid email address with '@'.");
      return;
    }

    // Validate password length
    if (password.length < 6) {
      setError("Password must be at least 6 characters long.");
      return;
    }

    // Validate password match
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    // Get existing users from localStorage
    const existingUsers = JSON.parse(localStorage.getItem("equirisk_users") || "[]");

    // Check if user already exists
    if (existingUsers.find((user) => user.email === email)) {
      setError("An account with this email already exists.");
      return;
    }

    // Add new user
    const newUser = {
      email,
      password, // In production, this should be hashed!
      createdAt: new Date().toISOString(),
    };

    existingUsers.push(newUser);
    localStorage.setItem("equirisk_users", JSON.stringify(existingUsers));

    setSuccess("Account created successfully! Redirecting to login...");

    // Redirect to login after 2 seconds
    setTimeout(() => {
      onRegister();
    }, 2000);
  };

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-header">
          <h1 className="login-logo">EquiRisk</h1>
          <p className="login-subtitle">Create your account</p>
        </div>

        <form className="login-form" onSubmit={handleSubmit} noValidate>
          {error && <div className="login-error">{error}</div>}
          {success && <div className="login-success">{success}</div>}

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
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
              placeholder="At least 6 characters"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">Confirm Password</label>
            <input
              type="password"
              id="confirmPassword"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Re-enter your password"
              required
            />
          </div>

          <button type="submit" className="login-button">
            Create Account
          </button>
        </form>

        <div className="login-footer">
          <p className="login-hint">
            Already have an account?{" "}
            <button
              onClick={onSwitchToLogin}
              className="link-button"
              type="button"
            >
              Sign in here
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}

export default RegisterPage;

