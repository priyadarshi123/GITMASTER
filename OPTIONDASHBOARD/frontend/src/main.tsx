import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";
import Layout from "./components/Layout";
import DashboardPage from "./pages/DashboardPage";
import AnalysePage from "./pages/AnalysePage";
import AlertsPage from "./pages/AlertsPage";
import GuidePage from "./pages/GuidePage";
import PositionsPage from "./pages/PositionsPage";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/analyse" element={<AnalysePage />} />
          <Route path="/positions" element={<Navigate to="/positions/real" replace />} />
          <Route path="/positions/:book" element={<PositionsPage />} />
          <Route path="/guide" element={<GuidePage />} />
          <Route path="/alerts" element={<AlertsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
