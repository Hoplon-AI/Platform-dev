# EquiRisk Platform MVP - 3-Month Roadmap

**Document Version:** 1.0  
**Date:** 2025-01-27  
**Scope:** MVP UI/UX Implementation - Dashboards, Block View, HA Profile, and Data Views

---

## Executive Summary

This roadmap outlines the 3-month implementation plan for the EquiRisk Platform MVP user interface, focusing on four core dashboards, block-level portfolio management, housing association profile pages with property mapping, and integration of existing Excel-based data views (Doc A and Doc B).

**Current State:**
- ✅ Bronze layer data ingestion (CSV/Excel/PDF uploads)
- ✅ File type auto-detection
- ✅ Audit logging and data lineage
- ✅ Backend API infrastructure (FastAPI)
- ✅ Database schema (Bronze layer tables)

**Target State:**
- ✅ 4 comprehensive dashboards
- ✅ Block view with filtering and summary panels
- ✅ HA profile page with interactive property map
- ✅ Excel table views (Doc A and Doc B) integrated into UI
- ✅ Complete end-to-end user workflow

---

## Month 1: Foundation & Core Dashboards

### Week 1-2: Frontend Infrastructure Setup & UPRN Mapping Service

**Objectives:**
- Set up React frontend application
- Configure build tooling and development environment
- Establish API client and authentication flow
- Create base component library and design system
- **Implement UPRN mapping service using Ordnance Survey DataHub data**

**Deliverables:**
- [ ] React application scaffold (Vite/Create React App)
- [ ] TypeScript configuration
- [ ] API client with axios/fetch wrapper
- [ ] Authentication context and JWT token management
- [ ] Base UI component library (buttons, inputs, tables, cards)
- [ ] Routing setup (React Router)
- [ ] State management (Context API or Zustand)
- [ ] Design system tokens (colors, typography, spacing)
- [ ] **UPRN Mapping Service (Backend)**
  - [ ] OS DataHub dataset download
  - [ ] Create necessary SQL tables
  - [ ] Narrow columns import
  - [ ] Add indexing 
  - [ ] Address-to-UPRN mapping function
  - [ ] Batch processing for multiple addresses
  - [ ] Error handling and fallback strategies
  - [ ] Caching layer for UPRN lookups
  - [ ] Integration with ingestion pipeline
- [ ] **UPRN Mapping Integration**
  - [ ] Auto-map addresses during CSV/Excel upload
  - [ ] Store UPRN mappings in database
  - [ ] Link UPRN to upload submissions
  - [ ] Handle missing/invalid addresses gracefully

**Technical Stack:**
- React 18+ with TypeScript
- React Router v6
- Tailwind CSS or Material-UI for styling
- Axios for API calls
- React Query for data fetching/caching

**Dependencies:**
- Backend API endpoints (already available)
- Design mockups/wireframes
- **Ordnance Survey DataHub API credentials and subscription**
- **OS DataHub API documentation and endpoint access**

---

#### UPRN Mapping Service Details

**Service Architecture:**
- **Location:** `backend/core/mapping/uprn_service.py`
- **Purpose:** Map property addresses to UPRN (Unique Property Reference Number) during ingestion
- **API:** Ordnance Survey DataHub bulk download

**Features:**
- [ ] **Address Normalization:**
  - Standardize address formats before lookup
  - Handle variations (street vs st, road vs rd, etc.)
  - Clean and validate postcodes
- [ ] **UPRN Lookup:**
  - Single address lookup
  - Batch address lookup (for efficiency)
  - Postcode + address line matching
  - Fallback to fuzzy matching if exact match fails
- [ ] **Caching Strategy:**
  - Cache successful UPRN lookups (address → UPRN)
  - LRU in mem with a finite number of addresses
  - Invalidate cache on address updates
- [ ] **Error Handling:**
  - Log mapping failures for manual review
- [ ] **Integration Points:**
  - Hook into CSV/Excel upload processing
  - Automatically map addresses during property schedule ingestion
  - Store UPRN in property records
  - Link UPRN to upload submission for lineage tracking

**API Endpoints Required:**
- `POST /api/v1/mapping/uprn/lookup` - Single address lookup
- `POST /api/v1/mapping/uprn/batch-lookup` - Batch address lookup
- `GET /api/v1/mapping/uprn/{uprn}/validate` - Validate UPRN exists

**Components:**
- `UPRNMappingService` class
- `AddressNormalizer` utility
- `OSDataHubClient` API client wrapper
- `UPRNCache` caching layer
- Integration hooks in `upload_router.py`

**Data Model:**
```python
class UPRNMapping:
    uprn: str  # 12-digit UPRN
    address: str  # Normalized address
    postcode: str
    confidence: float  # 0.0-1.0 (match confidence)
    source: str  # 'os_datahub' or 'manual'
    mapped_at: datetime
    ha_id: str
```

**OS DataHub API Integration:**

**Implementation Steps:**
1. Download OS DataHub API bulk GB-wide open dataset
3. Implement address normalization function
4. Create `UPRNMappingService` with lookup methods
5. Add caching layer (Redis or in-memory)
6. Integrate into upload processing pipeline
7. Add database table for UPRN mappings (if not exists)
8. Create API endpoints for manual UPRN lookup
9. Add logging and monitoring for mapping success/failure rates
10. Write unit tests for mapping service

**Acceptance Criteria:**
- Addresses are automatically mapped to UPRN during ingestion
- Mapping success rate > 90% for valid UK addresses
- Failed mappings are logged for manual review
- Caching reduces API calls by > 50%
- Service handles API rate limits gracefully
- Integration doesn't slow down upload process significantly (< 2s per 100 addresses)

---

### Week 3-4: Dashboard 1 - Portfolio Overview Dashboard

**Objectives:**
- Create the main portfolio overview dashboard
- Display high-level metrics and KPIs
- Show portfolio-level statistics

**Features:**
- [ ] Portfolio summary cards (total blocks, units, properties)
- [ ] Risk distribution chart (E/D/C/B ratings)
- [ ] Legislation & Market Readiness progress bars:
  - Statutory readiness percentage
  - Insurance readiness percentage
  - Data completeness percentage
- [ ] Recent activity feed
- [ ] Quick action buttons (Upload, Export)
- [ ] Filter by jurisdiction (England/Scotland)
- [ ] Time period selector (2024, 2025, etc.)

**API Endpoints Required:**
- `GET /api/v1/portfolios/{portfolio_id}/summary`
- `GET /api/v1/portfolios/{portfolio_id}/readiness`
- `GET /api/v1/portfolios/{portfolio_id}/risk-distribution`
- `GET /api/v1/portfolios/{portfolio_id}/recent-activity`

**Components:**
- `PortfolioOverviewDashboard.tsx`
- `SummaryCards.tsx`
- `RiskDistributionChart.tsx` (using Chart.js or Recharts)
- `ReadinessProgressBars.tsx`
- `ActivityFeed.tsx`

**Acceptance Criteria:**
- Dashboard loads with real data from backend
- All metrics display correctly
- Filters update data dynamically
- Responsive design (mobile/tablet/desktop)

---

## Month 2: Block View & HA Profile

### Week 5-6: Dashboard 2 - Block View Implementation

**Objectives:**
- Implement the comprehensive block view as shown in the design
- Create filtering and search functionality
- Build summary panels and missing info gaps

**Features:**
- [ ] **Blocks Table:**
  - Columns: Jurisdiction, Block Name, Units, Height, Build, Construction, EWS/Cladding, Remediation To-Do
  - Sortable columns
  - Pagination (50-100 blocks per page)
  - "View details" link for each block
- [ ] **Filtering System:**
  - Jurisdiction filter (England/Scotland tabs)
  - I-Rating dropdown filter
  - Confidence level filter
  - Height range filter
  - SBA in-scope filter
  - Search by block name
- [ ] **Block Summary Panel (Right Side):**
  - Risk rating distribution chart (E/D/C/B with counts)
  - Legislation & Market Readiness progress bars
- [ ] **Missing Info Gaps Panel:**
  - Tabs: "Statutory" and "Insurance"
  - List of missing information with timestamps
  - Clickable items to navigate to relevant pages
- [ ] **Action Buttons:**
  - "Upload evidence" button
  - "Export Underwriter Pack" button

**API Endpoints Required:**
- `GET /api/v1/portfolios/{portfolio_id}/blocks` (with query params for filtering)
- `GET /api/v1/portfolios/{portfolio_id}/blocks/summary`
- `GET /api/v1/portfolios/{portfolio_id}/missing-info-gaps`
- `GET /api/v1/portfolios/{portfolio_id}/blocks/{block_id}`

**Components:**
- `BlockViewDashboard.tsx`
- `BlocksTable.tsx`
- `BlockFilters.tsx`
- `BlockSummaryPanel.tsx`
- `MissingInfoGaps.tsx`
- `RemediationToDoCell.tsx`

**Data Model:**
```typescript
interface Block {
  id: string;
  name: string;
  jurisdiction: 'ENG' | 'SCO';
  units: number;
  height: number;
  heightCategory: '<11m' | '11-16m' | '16m+';
  buildYear: number;
  construction: ConstructionDetails;
  ewsCladding: EWSCladdingStatus;
  remediationToDo: RemediationTasks;
  riskRating: 'E' | 'D' | 'C' | 'B' | 'A';
}
```

**Acceptance Criteria:**
- All table columns render correctly
- Filters work independently and in combination
- Search filters blocks in real-time
- Summary panel updates based on filtered data
- Missing info gaps show correct timestamps
- Responsive layout (table scrolls horizontally on mobile)

---

### Week 7-8: Dashboard 3 - HA Profile Page with Property Map

**Objectives:**
- Create housing association profile page
- Implement interactive map showing property locations
- Display HA-level statistics and information

**Features:**
- [ ] **HA Header Section:**
  - HA name and logo
  - Contact information
  - Portfolio selector dropdown
  - Quick stats (total blocks, total units, total properties)
- [ ] **Interactive Property Map:**
  - Light map (using Leaflet or Mapbox GL)
  - Property markers/clusters
  - Click markers to see property details
  - Filter markers by risk rating, height, etc.
  - Toggle layers (jurisdiction, construction type)
  - Zoom to portfolio bounds
- [ ] **Property List Panel:**
  - List of properties with key details
  - Click to highlight on map
  - Filter and search
- [ ] **HA Summary Tabs:**
  - Overview (general stats)
  - Properties (list view)
  - Documents (uploaded files)
  - Compliance (readiness metrics)

**API Endpoints Required:**
- `GET /api/v1/housing-associations/{ha_id}`
- `GET /api/v1/housing-associations/{ha_id}/properties` (with lat/lng)
- `GET /api/v1/housing-associations/{ha_id}/summary`
- `GET /api/v1/housing-associations/{ha_id}/portfolios`

**Components:**
- `HAProfilePage.tsx`
- `PropertyMap.tsx` (Leaflet/Mapbox wrapper)
- `PropertyMarker.tsx`
- `PropertyListPanel.tsx`
- `HASummaryTabs.tsx`
- `HAHeader.tsx`

**Map Library:**
- **Option 1:** Leaflet (open source, lightweight)
- **Option 2:** Mapbox GL JS (better performance, requires API key)
- **Option 3:** Google Maps API (familiar, requires API key)

**Data Model:**
```typescript
interface Property {
  id: string;
  blockId: string;
  blockName: string;
  address: string;
  postcode: string;
  uprn: string;
  latitude: number;
  longitude: number;
  riskRating: string;
  height: number;
  units: number;
}
```

**Acceptance Criteria:**
- Map loads with all properties
- Markers are clickable and show property info
- Map filters work correctly
- Property list syncs with map selection
- Responsive design (map full-width on desktop, stacked on mobile)
- Performance: Map loads in < 2 seconds with 1000+ properties

---

## Month 3: Data Views & Integration

### Week 9-10: Dashboard 4 - Analytics & Reporting Dashboard

**Objectives:**
- Create analytics dashboard with charts and insights
- Provide export capabilities
- Show trends over time

**Features:**
- [ ] **Key Metrics Cards:**
  - Total remediation tasks
  - Overdue actions count
  - Compliance score trends
  - Data quality score
- [ ] **Charts & Visualizations:**
  - Risk rating distribution over time
  - Height distribution histogram
  - Construction type breakdown (pie chart)
  - Remediation completion timeline
  - Jurisdiction comparison
- [ ] **Export Functionality:**
  - Export to Excel/CSV
  - Generate PDF reports
  - Export Underwriter Pack
- [ ] **Date Range Selector:**
  - Filter all metrics by date range
  - Compare periods

**API Endpoints Required:**
- `GET /api/v1/portfolios/{portfolio_id}/analytics`
- `GET /api/v1/portfolios/{portfolio_id}/trends`
- `POST /api/v1/portfolios/{portfolio_id}/export`
- `POST /api/v1/portfolios/{portfolio_id}/export-underwriter-pack`

**Components:**
- `AnalyticsDashboard.tsx`
- `MetricsCards.tsx`
- `TrendChart.tsx`
- `DistributionChart.tsx`
- `ExportButton.tsx`
- `DateRangePicker.tsx`

**Chart Library:**
- Recharts (React-friendly, good documentation)
- Chart.js with react-chartjs-2
- Victory (by Formidable Labs)

**Acceptance Criteria:**
- All charts render with real data
- Date range filtering works
- Export functions generate correct files
- Charts are responsive and interactive
- Performance: Dashboard loads in < 3 seconds

---

### Week 11-12: Excel Table Views Integration (Doc A & Doc B)

**Objectives:**
- Integrate existing Excel-based data views into the UI
- Create table views that match Excel format
- Enable editing and export capabilities

**Features:**
- [ ] **Doc A View - Property Schedule Table:**
  - Display property schedule data in tabular format
  - Columns: Property ID, Address, Postcode, UPRN, Block Name, Units, Height, Build Year, Construction, Risk Rating, etc.
  - Sortable and filterable columns
  - Inline editing (if permissions allow)
  - Bulk actions (select multiple rows)
  - Export to Excel (maintains format)
  - Import from Excel (with validation)
- [ ] **Doc B View - EPC Data Table:**
  - Display EPC data in tabular format
  - Columns: UPRN, Property Address, EPC Rating, EPC Date, Energy Efficiency, Environmental Impact, etc.
  - Link to property schedule (via UPRN)
  - Filter by EPC rating
  - Export to Excel
  - Import from Excel
- [ ] **Table Features:**
  - Virtual scrolling for large datasets (1000+ rows)
  - Column resizing
  - Column reordering
  - Column visibility toggle
  - Search/filter per column
  - Pagination or infinite scroll
  - Row selection (checkbox)
  - Export selected rows

**API Endpoints Required:**
- `GET /api/v1/properties` (property schedule data)
- `GET /api/v1/epc-data`
- `PUT /api/v1/properties/{property_id}` (if editing allowed)
- `POST /api/v1/properties/bulk-update`
- `POST /api/v1/properties/export`
- `POST /api/v1/epc-data/export`
- `POST /api/v1/properties/import` (Excel upload)

**Components:**
- `DocAView.tsx` (Property Schedule Table)
- `DocBView.tsx` (EPC Data Table)
- `DataTable.tsx` (reusable table component)
- `TableFilters.tsx`
- `ExportMenu.tsx`
- `ImportDialog.tsx`
- `BulkActionsBar.tsx`

**Table Library Options:**
- **Option 1:** TanStack Table (React Table v8) - Most flexible, headless
- **Option 2:** AG Grid - Feature-rich, commercial license for advanced features
- **Option 3:** Material-UI DataGrid - Good for Material Design apps

**Data Model:**
```typescript
// Doc A - Property Schedule
interface PropertyScheduleRow {
  propertyId: string;
  address: string;
  postcode: string;
  uprn: string;
  blockName: string;
  units: number;
  height: number;
  buildYear: number;
  construction: string;
  riskRating: string;
  // ... other fields
}

// Doc B - EPC Data
interface EPCDataRow {
  uprn: string;
  propertyAddress: string;
  epcRating: 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G';
  epcDate: string;
  energyEfficiency: number;
  environmentalImpact: number;
  // ... other fields
}
```

**Excel Integration:**
- Use `xlsx` library (SheetJS) for Excel parsing/generation
- Maintain original Excel column order and formatting where possible
- Support both `.xlsx` and `.xls` formats
- Validate data on import (required fields, data types, UPRN format)

**Acceptance Criteria:**
- Tables display all columns correctly
- Sorting works on all sortable columns
- Filters work independently and together
- Virtual scrolling handles 10,000+ rows smoothly
- Export generates Excel file matching original format
- Import validates and shows errors clearly
- Responsive design (horizontal scroll on mobile)

---

## Technical Architecture

### Frontend Stack

```
React 18+ (TypeScript)
├── Routing: React Router v6
├── State Management: Zustand or Context API
├── Data Fetching: React Query (TanStack Query)
├── Styling: Tailwind CSS + Headless UI
├── Tables: TanStack Table v8
├── Charts: Recharts
├── Maps: Leaflet or Mapbox GL JS
├── Forms: React Hook Form
├── Excel: SheetJS (xlsx)
└── Build Tool: Vite
```

### Backend API Extensions Needed

**New Endpoints to Implement:**

1. **Portfolio Endpoints:**
   - `GET /api/v1/portfolios` - List portfolios
   - `GET /api/v1/portfolios/{id}` - Get portfolio details
   - `GET /api/v1/portfolios/{id}/summary` - Portfolio summary
   - `GET /api/v1/portfolios/{id}/blocks` - List blocks with filters
   - `GET /api/v1/portfolios/{id}/analytics` - Analytics data

2. **Block Endpoints:**
   - `GET /api/v1/blocks/{id}` - Get block details
   - `GET /api/v1/blocks/{id}/properties` - Get properties in block

3. **Property Endpoints:**
   - `GET /api/v1/properties` - List properties (with filters)
   - `GET /api/v1/properties/{id}` - Get property details
   - `GET /api/v1/properties/export` - Export property schedule
   - `POST /api/v1/properties/import` - Import property schedule

4. **EPC Data Endpoints:**
   - `GET /api/v1/epc-data` - List EPC records
   - `GET /api/v1/epc-data/export` - Export EPC data

5. **HA Endpoints:**
   - `GET /api/v1/housing-associations/{id}/properties` - Get properties with coordinates
   - `GET /api/v1/housing-associations/{id}/summary` - HA summary

6. **UPRN Mapping Endpoints:**
   - `POST /api/v1/mapping/uprn/lookup` - Single address to UPRN lookup
   - `POST /api/v1/mapping/uprn/batch-lookup` - Batch address to UPRN lookup
   - `GET /api/v1/mapping/uprn/{uprn}/validate` - Validate UPRN exists
   - `GET /api/v1/mapping/uprn/{uprn}/details` - Get UPRN details (address, coordinates)

7. **Export Endpoints:**
   - `POST /api/v1/portfolios/{id}/export-underwriter-pack` - Generate PDF pack

### Database Schema Extensions

**New Tables Needed (Silver Layer):**

```sql
-- Properties table (from property schedules)
CREATE TABLE properties (
    property_id UUID PRIMARY KEY,
    ha_id VARCHAR(50) REFERENCES housing_associations(ha_id),
    block_id UUID REFERENCES blocks(block_id),
    uprn VARCHAR(12) UNIQUE,
    address TEXT NOT NULL,
    postcode VARCHAR(10),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    units INTEGER,
    height DECIMAL(5, 2),
    build_year INTEGER,
    construction_type VARCHAR(50),
    risk_rating VARCHAR(1),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Blocks table
CREATE TABLE blocks (
    block_id UUID PRIMARY KEY,
    ha_id VARCHAR(50) REFERENCES housing_associations(ha_id),
    portfolio_id UUID,
    name VARCHAR(255) NOT NULL,
    jurisdiction VARCHAR(10), -- 'ENG' or 'SCO'
    total_units INTEGER,
    height_category VARCHAR(10), -- '<11m', '11-16m', '16m+'
    build_year INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- EPC data table
CREATE TABLE epc_data (
    epc_id UUID PRIMARY KEY,
    uprn VARCHAR(12) REFERENCES properties(uprn),
    epc_rating VARCHAR(1),
    epc_date DATE,
    energy_efficiency INTEGER,
    environmental_impact INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Portfolios table
CREATE TABLE portfolios (
    portfolio_id UUID PRIMARY KEY,
    ha_id VARCHAR(50) REFERENCES housing_associations(ha_id),
    name VARCHAR(255) NOT NULL,
    renewal_year INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- UPRN mappings table (for caching and tracking)
CREATE TABLE uprn_mappings (
    mapping_id UUID PRIMARY KEY,
    uprn VARCHAR(12) NOT NULL,
    address TEXT NOT NULL,
    postcode VARCHAR(10),
    normalized_address TEXT,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    confidence DECIMAL(3, 2), -- 0.00 to 1.00
    source VARCHAR(50) DEFAULT 'os_datahub',
    ha_id VARCHAR(50) REFERENCES housing_associations(ha_id),
    mapped_at TIMESTAMP DEFAULT NOW(),
    last_verified_at TIMESTAMP,
    UNIQUE(uprn, address, ha_id)
);

CREATE INDEX idx_uprn_mappings_uprn ON uprn_mappings(uprn);
CREATE INDEX idx_uprn_mappings_address ON uprn_mappings(normalized_address);
CREATE INDEX idx_uprn_mappings_ha_id ON uprn_mappings(ha_id);
```

---

## Dependencies & Prerequisites

### External Services

1. **Ordnance Survey DataHub API:**
   - **Service:** AddressBase Premium or UPRN Lookup API
   - **Purpose:** Map addresses to UPRN during ingestion
   - **Authentication:** API key or OAuth2 (subscription-dependent)
   - **Rate Limits:** 100-1000 requests/minute (varies by subscription tier)
   - **Cost:** Subscription-based (check OS DataHub pricing)
   - **Documentation:** https://osdatahub.os.uk/

2. **Map Service:**
   - Leaflet (free, open source) OR
   - Mapbox GL JS (requires API key, better performance)
   - Need to geocode addresses to get lat/lng if not in data
   - **Note:** UPRN mapping service can also provide coordinates from OS DataHub

3. **PDF Generation:**
   - Backend: ReportLab or WeasyPrint (already in requirements.txt)
   - For "Export Underwriter Pack" functionality

4. **Excel Processing:**
   - Frontend: SheetJS (xlsx) library
   - Backend: openpyxl (already in requirements.txt)

### Data Requirements

1. **Property Coordinates:**
   - Need latitude/longitude for each property
   - **UPRN mapping service (OS DataHub) provides coordinates** as part of UPRN lookup
   - Can geocode from address/postcode if UPRN lookup fails
   - Fallback to Google Geocoding API if OS DataHub unavailable

2. **UPRN Mapping:**
   - **Address-to-UPRN mapping via OS DataHub dataset** (Week 1-2)
   - UPRN is critical for data lineage and property identification
   - Store UPRN mappings in database for future lookups
   - Handle cases where UPRN cannot be found (manual review queue)

3. **Block Data:**
   - Need to aggregate property data into blocks
   - Block names and associations must be in property schedule
   - UPRN can help link properties to blocks if block data is incomplete

4. **Risk Ratings:**
   - Need to calculate or import risk ratings (E/D/C/B/A)
   - May come from processing/analysis (future Phase 2)

---

## Risk Mitigation

### Technical Risks

1. **Performance with Large Datasets:**
   - **Risk:** Tables with 10,000+ rows may be slow
   - **Mitigation:** Implement virtual scrolling, pagination, server-side filtering

2. **Map Performance:**
   - **Risk:** Rendering 1000+ markers on map may lag
   - **Mitigation:** Use marker clustering, limit initial view, lazy load markers

3. **Excel Format Compatibility:**
   - **Risk:** Exported Excel may not match original format exactly
   - **Mitigation:** Test with sample files, use SheetJS formatting options

4. **OS DataHub API Availability:**
   - **Risk:** API downtime or rate limits could block ingestion
   - **Mitigation:** Implement caching layer, graceful degradation (skip UPRN mapping if API unavailable), retry logic with exponential backoff, queue failed mappings for later processing

5. **UPRN Mapping Accuracy:**
   - **Risk:** Some addresses may not match to UPRN (new builds, non-standard addresses)
   - **Mitigation:** Implement confidence scoring, manual review queue for low-confidence matches, allow manual UPRN entry, fuzzy matching fallback

### Timeline Risks

1. **Scope Creep:**
   - **Risk:** Adding features beyond MVP scope
   - **Mitigation:** Strict prioritization, weekly reviews, document changes

2. **Backend API Delays:**
   - **Risk:** Frontend ready but APIs not available
   - **Mitigation:** Mock API responses, parallel development, API contracts defined early

3. **Design Changes:**
   - **Risk:** UI/UX changes mid-development
   - **Mitigation:** Design review before development, component-based architecture for easy changes

---

## Success Metrics

### Functional Metrics

- ✅ All 4 dashboards load and display data correctly
- ✅ Block view filters work as expected
- ✅ Property map displays all properties accurately
- ✅ Excel table views match original format
- ✅ Export functions generate correct files
- ✅ Import functions validate and process data correctly

### Performance Metrics

- Dashboard load time: < 2 seconds
- Table render time (1000 rows): < 1 second
- Map load time (1000 markers): < 3 seconds
- Export generation: < 5 seconds for 1000 rows

### User Experience Metrics

- Responsive design works on mobile/tablet/desktop
- All interactive elements are accessible (keyboard navigation, screen readers)
- Error messages are clear and actionable
- Loading states are shown for async operations

---

## Deliverables Checklist

### Month 1
- [ ] React application setup
- [ ] Base component library
- [ ] **UPRN Mapping Service (OS DataHub dataset import and integration)**
- [ ] **Address-to-UPRN mapping during ingestion**
- [ ] Portfolio Overview Dashboard
- [ ] API integration layer

### Month 2
- [ ] Block View Dashboard
- [ ] HA Profile Page
- [ ] Property Map with markers
- [ ] Filtering and search functionality

### Month 3
- [ ] Analytics Dashboard
- [ ] Doc A View (Property Schedule Table)
- [ ] Doc B View (EPC Data Table)
- [ ] Export/Import functionality
- [ ] End-to-end testing

---

## Next Steps

1. **Week 1 Kickoff:**
   - Review this roadmap with stakeholders
   - Set up development environment
   - Create GitHub repository for frontend
   - Set up project management board (Jira/Trello/GitHub Projects)

2. **Design Review:**
   - Review UI mockups/wireframes
   - Confirm color scheme and branding
   - Validate component designs

3. **API Contract Definition:**
   - Define all API endpoints with request/response schemas
   - Create OpenAPI/Swagger documentation
   - Set up API mocking for frontend development

4. **Development Sprint Planning:**
   - Break down each week into tasks
   - Assign developers to components
   - Set up daily standups and weekly reviews

---

## Appendix

### Component Hierarchy

```
App
├── Router
│   ├── Dashboard Routes
│   │   ├── PortfolioOverviewDashboard
│   │   ├── BlockViewDashboard
│   │   ├── AnalyticsDashboard
│   │   └── HAProfilePage
│   └── Data View Routes
│       ├── DocAView (Property Schedule)
│       └── DocBView (EPC Data)
├── Layout
│   ├── Header (with navigation)
│   ├── Sidebar (optional)
│   └── Footer
└── Shared Components
    ├── DataTable
    ├── Charts
    ├── Maps
    └── Forms
```

### Key Libraries to Install

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "@tanstack/react-query": "^5.0.0",
    "@tanstack/react-table": "^8.10.0",
    "recharts": "^2.10.0",
    "leaflet": "^1.9.4",
    "react-leaflet": "^4.2.1",
    "xlsx": "^0.18.5",
    "react-hook-form": "^7.48.0",
    "zustand": "^4.4.0",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/leaflet": "^1.9.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "tailwindcss": "^3.3.0"
  }
}
```
---

**Document Owner:** Development Team  
**Last Updated:** 2025-01-27  
**Review Date:** Weekly during implementation
