import React, { useEffect, useState } from "react";
import "./LandingPage.css";

const CITY_IMAGES = [
  {
    url: "https://live.staticflickr.com/8655/16583960636_7042dbeb06_o.jpg",
    label: "London – South Bank",
  },
  {
    url: "https://live.staticflickr.com/2/1350885_4d9739561b_o.jpg",
    label: "Edinburgh – City skyline",
  },
  {
    url: "https://live.staticflickr.com/2/1672549_58639b9dc0_o.jpg",
    label: "Glasgow – Skyline from Ruchill Park",
  },
  {
    url: "https://live.staticflickr.com/8715/16722081113_511f8f0cb0_o.jpg",
    label: "Birmingham – Skyline from Snowhill",
  },
];

function LandingPage({ onGetStarted }) {
  const [cityIndex, setCityIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(
      () => setCityIndex((prev) => (prev + 1) % CITY_IMAGES.length),
      6000
    );
    return () => clearInterval(id);
  }, []);

  const currentCity = CITY_IMAGES[cityIndex];

  return (
    <div className="landing-page">
      {/* Header */}
      <header className="landing-header">
        <div className="header-content">
          <div className="logo">EquiRisk</div>
          <button
            className="btn-primary"
            onClick={() => onGetStarted("portfolio")}
          >
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
          {/* Removed the second Get Started button to avoid redundancy */}
        </div>

        <div className="hero-image">
          <img src={currentCity.url} alt={currentCity.label} />
          <div className="hero-city-chip">{currentCity.label}</div>
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
          <h2>About EquiRisk</h2>
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
        <button className="btn-cta" onClick={() => onGetStarted("portfolio")}>
          Start
        </button>
      </section>

      {/* Contact Section */}
      <section className="contact">
        <div className="contact-form">
          <h2>Get in touch</h2>
          <p>Now</p>
          <form onSubmit={(e) => e.preventDefault()}>
            <input type="text" placeholder="Name" />
            <input type="email" placeholder="Email" />
            <textarea placeholder="Message" rows="4" />
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