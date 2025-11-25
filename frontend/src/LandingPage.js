import React from "react";
import "./LandingPage.css";

function LandingPage(props) {
  return (
    <div className="landing-page">
      {/* Header */}
      <header className="landing-header">
        <div className="header-content">
          <div className="logo">EquiRisk</div>
          <button className="btn-primary" onClick={props.onGetStarted}>
            Get Started
          </button>
        </div>
      </header>

      {/* Hero Section */}
      <section className="hero">
        <div className="hero-content">
          <h1 className="hero-title">EquiRisk</h1>
          <p className="hero-description">
            AI-powered insights for social housing insurance.
          </p>
          <button className="btn-hero" onClick={props.onGetStarted}>Get Started</button>
        </div>
        <div className="hero-image">
          <img
            src="https://equirisk.ai/wp-content/uploads/2025/11/iStock-526834951-1.jpg"
            alt="City skyline"
          />
        </div>
      </section>

      {/* Services Section */}
      <section className="services">
        <div className="section-header">
          <h2>Smart Coverage</h2>
          <p>
            AI-powered insights that sharpen social housing insurance decisions.
          </p>
        </div>
        <div className="image-grid">
          <img
            src="https://equirisk.ai/wp-content/uploads/2025/11/iStock-1424081499.jpg"
            alt="Family"
          />
          <img
            src="https://equirisk.ai/wp-content/uploads/2025/11/iStock-175139990.jpg"
            alt="Housing"
          />
        </div>
      </section>

      {/* About Section */}
      <section className="about">
        <div className="section-header">
          <h2>About equirisk</h2>
          <p>
            We bring AI-driven insight to social housing insurance, making risk
            clearer and more manageable for you.
          </p>
          <button className="btn-secondary">Learn More</button>
        </div>
        <div className="image-grid">
          <img
            src="https://equirisk.ai/wp-content/uploads/2025/11/iStock-1289432415.jpg"
            alt="City"
          />
          <img
            src="https://equirisk.ai/wp-content/uploads/2025/11/iStock-1408723366-1.jpg"
            alt="Houses"
          />
        </div>
      </section>

      {/* CTA Section */}
      <section className="cta">
        <h2>Insure Smarter</h2>
        <p>
          Harness AI-driven insights to manage social housing risks clearly and
          confidently.
        </p>
        <button className="btn-cta">Start</button>
      </section>

      {/* Contact Section */}
      <section className="contact">
        <div className="contact-form">
          <h2>Get in touch</h2>
          <p>Now</p>
          <form>
            <input type="text" placeholder="Name" />
            <input type="email" placeholder="Email" />
            <textarea placeholder="Message" rows="4"></textarea>
            <button type="submit" className="btn-primary">
              Send
            </button>
          </form>
        </div>
        <div className="contact-image">
          <img
            src="https://equirisk.ai/wp-content/uploads/2025/11/iStock-532569674.jpg"
            alt="Couple"
          />
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <p>&copy; 2025 EquiRisk. All rights reserved.</p>
      </footer>
    </div>
  );
}

export default LandingPage;