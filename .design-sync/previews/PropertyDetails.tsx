import { PropertyDetails } from 'equirisk-frontend';

const glasgowBlock = {
  address_line_1: "14 Caledonian Road",
  address_2: "Block A",
  address_3: "Glasgow",
  postcode: "G20 7AB",
  block_reference: "CATHCART_BLOCK_01",
  sum_insured: 3850000,
  property_type: "Flat",
  occupancy_type: "Rented",
  height_max_m: 12.4,
  storeys: 4,
  units: 24,
  year_of_build: 1975,
  uprn: "906700011234",
  uprn_confidence: "HIGH",
  uprn_confidence_reason: "Exact address match via OS Places",
  epc_rating: "C",
  flood_risk_band: "Very low",
  listed_grade: null,
  wall_construction: "Brick",
  roof_construction: "Pitched — Slate",
};

const withFireDocs = {
  ...glasgowBlock,
  latest_fra: {
    risk_rating: "Moderate",
    rag_status: "AMBER",
    assessment_date: "2024-06-15",
    total_action_count: 5,
    overdue_action_count: 2,
    outstanding_action_count: 3,
    has_sprinkler_system: false,
    has_fire_alarm_system: true,
    has_fire_doors: true,
  },
  latest_fraew: {
    building_risk_rating: "Low",
    rag_status: "GREEN",
    has_combustible_cladding: false,
    building_height_m: 12.4,
  },
};

export const WithProperty = () => (
  <div style={{ width: 380, background: "var(--panel)", borderRadius: 16, overflow: "hidden" }}>
    <PropertyDetails property={glasgowBlock} />
  </div>
);

export const WithFireRisk = () => (
  <div style={{ width: 380, background: "var(--panel)", borderRadius: 16, overflow: "hidden" }}>
    <PropertyDetails property={withFireDocs} />
  </div>
);

export const EmptyState = () => (
  <div style={{ width: 380, background: "var(--panel)", borderRadius: 16, overflow: "hidden" }}>
    <PropertyDetails />
  </div>
);
