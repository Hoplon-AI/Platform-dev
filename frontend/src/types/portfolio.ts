export type Portfolio = {
  portfolio_id: string;
  ha_id: string;
  name: string;
  renewal_year: number | null;
  created_at: string;
  updated_at: string;
};

export type PortfolioSummary = {
  portfolio_id: string;
  ha_id: string;
  portfolio_name: string;
  renewal_year: number | null;
  total_blocks: number;
  total_units: number;
  total_properties: number;
  computed_at: string;
};

export type PortfolioReadiness = {
  portfolio_id: string;
  ha_id: string;
  total_properties: number;
  pct_has_uprn: string;
  pct_has_postcode: string;
  pct_has_geo: string;
  pct_has_height: string;
  pct_has_build_year: string;
  pct_has_construction: string;
  pct_has_risk_rating: string;
  computed_at: string;
};

export type PortfolioRiskDistributionRow = {
  risk_rating: string;
  property_count: number;
};

export type RecentActivityRow = {
  ha_id: string;
  event_id: string;
  event_type: string;
  file_type: string;
  filename: string;
  actor_id: string;
  created_at: string;
  status: string;
  metadata: string | null;
};

