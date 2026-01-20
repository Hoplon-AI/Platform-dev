import { apiFetch } from "./apiClient";
import type {
  Portfolio,
  PortfolioReadiness,
  PortfolioRiskDistributionRow,
  PortfolioSummary,
  RecentActivityRow,
} from "../types/portfolio";

export async function listPortfolios(): Promise<Portfolio[]> {
  const res = await apiFetch("/api/v1/portfolios");
  return (await res.json()) as Portfolio[];
}

export async function getPortfolioSummary(
  portfolioId: string,
): Promise<PortfolioSummary> {
  const res = await apiFetch(`/api/v1/portfolios/${portfolioId}/summary`);
  return (await res.json()) as PortfolioSummary;
}

export async function getPortfolioReadiness(
  portfolioId: string,
): Promise<PortfolioReadiness> {
  const res = await apiFetch(`/api/v1/portfolios/${portfolioId}/readiness`);
  return (await res.json()) as PortfolioReadiness;
}

export async function getPortfolioRiskDistribution(
  portfolioId: string,
): Promise<PortfolioRiskDistributionRow[]> {
  const res = await apiFetch(
    `/api/v1/portfolios/${portfolioId}/risk-distribution`,
  );
  return (await res.json()) as PortfolioRiskDistributionRow[];
}

export async function getPortfolioRecentActivity(
  portfolioId: string,
  limit = 10,
): Promise<RecentActivityRow[]> {
  const res = await apiFetch(
    `/api/v1/portfolios/${portfolioId}/recent-activity?limit=${limit}`,
  );
  return (await res.json()) as RecentActivityRow[];
}

