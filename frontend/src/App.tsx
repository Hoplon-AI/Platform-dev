import { Navigate, Route, Routes } from "react-router-dom";

import { IngestionLandingPage } from "./pages/IngestionLandingPage";
import { PortfolioOverviewPage } from "./pages/LandingPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<IngestionLandingPage />} />
      <Route path="/portfolio" element={<PortfolioOverviewPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

