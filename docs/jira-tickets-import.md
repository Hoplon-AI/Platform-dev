# Jira Tickets for MVP 3-Month Roadmap

This document contains all tasks from the roadmap formatted for Jira ticket creation.

## Import Instructions

### Option 1: CSV Import (Recommended)
1. Export the CSV file (see below)
2. In Jira: Project Settings → Import → CSV Import
3. Upload the CSV file
4. Map fields and create tickets

### Option 2: Manual Creation
Use the ticket details below to create tickets manually in Jira

### Option 3: Jira REST API
Use the JSON structure below with Jira REST API to create tickets programmatically

---

## Epics

### Epic 1: Frontend Infrastructure Setup (Week 1-2)
**Epic Name:** Frontend Infrastructure & UPRN Mapping Service  
**Epic Key:** KAN-EPIC-1  
**Description:** Set up React frontend application, base components, and implement UPRN mapping service using OS DataHub API

### Epic 2: Portfolio Overview Dashboard (Week 3-4)
**Epic Name:** Portfolio Overview Dashboard  
**Epic Key:** KAN-EPIC-2  
**Description:** Create the main portfolio overview dashboard with metrics, KPIs, and readiness indicators

### Epic 3: Block View Dashboard (Week 5-6)
**Epic Name:** Block View Implementation  
**Epic Key:** KAN-EPIC-3  
**Description:** Implement comprehensive block view with filtering, summary panels, and missing info gaps

### Epic 4: HA Profile & Property Map (Week 7-8)
**Epic Name:** HA Profile Page with Interactive Map  
**Epic Key:** KAN-EPIC-4  
**Description:** Create housing association profile page with interactive property map using Leaflet/Mapbox

### Epic 5: Analytics Dashboard (Week 9-10)
**Epic Name:** Analytics & Reporting Dashboard  
**Epic Key:** KAN-EPIC-5  
**Description:** Create analytics dashboard with charts, trends, and export capabilities

### Epic 6: Excel Table Views (Week 11-12)
**Epic Name:** Excel Table Views Integration (Doc A & Doc B)  
**Epic Key:** KAN-EPIC-6  
**Description:** Integrate existing Excel-based data views (Property Schedule and EPC Data) into UI

---

## Stories and Tasks

### Epic 1: Frontend Infrastructure Setup (Week 1-2)

#### Story 1.1: React Application Setup
**Story Key:** KAN-1  
**Story Type:** Story  
**Summary:** Set up React application scaffold  
**Description:** Create React application using Vite or Create React App with TypeScript configuration  
**Acceptance Criteria:**
- React 18+ application created
- TypeScript configured with strict mode
- Build tooling (Vite) set up
- Development server runs successfully
- Hot module replacement works

**Tasks:**
- KAN-1.1: Create React project with Vite
- KAN-1.2: Configure TypeScript with strict mode
- KAN-1.3: Set up ESLint and Prettier
- KAN-1.4: Configure build scripts and environment variables

---

#### Story 1.2: API Client & Authentication
**Story Key:** KAN-2  
**Story Type:** Story  
**Summary:** Establish API client and authentication flow  
**Description:** Create API client wrapper with axios/fetch, implement JWT token management, and authentication context  
**Acceptance Criteria:**
- API client created with axios/fetch wrapper
- JWT token storage and refresh logic implemented
- Authentication context/provider created
- Token expiration handling works
- API error handling implemented

**Tasks:**
- KAN-2.1: Create API client with axios wrapper
- KAN-2.2: Implement JWT token storage (localStorage/sessionStorage)
- KAN-2.3: Create authentication context and provider
- KAN-2.4: Implement token refresh logic
- KAN-2.5: Add API error handling and retry logic

---

#### Story 1.3: Base Component Library
**Story Key:** KAN-3  
**Story Type:** Story  
**Summary:** Create base UI component library  
**Description:** Build reusable UI components (buttons, inputs, tables, cards) with design system tokens  
**Acceptance Criteria:**
- Base components created (Button, Input, Table, Card)
- Design system tokens defined (colors, typography, spacing)
- Components are accessible (keyboard navigation, ARIA labels)
- Components are responsive
- Storybook or component documentation created

**Tasks:**
- KAN-3.1: Define design system tokens (colors, typography, spacing)
- KAN-3.2: Create Button component with variants
- KAN-3.3: Create Input component with validation states
- KAN-3.4: Create Card component
- KAN-3.5: Create Table component skeleton
- KAN-3.6: Set up Tailwind CSS or Material-UI theme

---

#### Story 1.4: Routing & State Management
**Story Key:** KAN-4  
**Story Type:** Story  
**Summary:** Set up routing and state management  
**Description:** Configure React Router for navigation and set up state management (Context API or Zustand)  
**Acceptance Criteria:**
- React Router v6 configured
- Route structure defined
- Protected routes implemented (require authentication)
- State management library chosen and configured
- Global state stores created for user/auth

**Tasks:**
- KAN-4.1: Install and configure React Router v6
- KAN-4.2: Create route structure and components
- KAN-4.3: Implement protected route wrapper
- KAN-4.4: Set up Zustand or Context API for global state
- KAN-4.5: Create auth store/context

---

#### Story 1.5: UPRN Mapping Service - OS DataHub Integration
**Story Key:** KAN-5  
**Story Type:** Story  
**Summary:** Implement UPRN mapping service using Ordnance Survey DataHub API  
**Description:** Create service to map addresses to UPRN during ingestion using OS DataHub API with caching and error handling  
**Acceptance Criteria:**
- OS DataHub API client created
- Address normalization function implemented
- Single and batch UPRN lookup functions work
- Caching layer implemented (Redis or in-memory)
- Error handling and retry logic implemented
- Integration with upload pipeline complete
- Mapping success rate > 90% for valid UK addresses

**Tasks:**
- KAN-5.1: Set up OS DataHub API credentials and test connection
- KAN-5.2: Create OSDataHubClient with authentication
- KAN-5.3: Implement address normalization function
- KAN-5.4: Create UPRNMappingService with lookup methods
- KAN-5.5: Add caching layer (Redis or in-memory)
- KAN-5.6: Implement error handling and retry with exponential backoff
- KAN-5.7: Integrate into upload processing pipeline
- KAN-5.8: Create database table for UPRN mappings
- KAN-5.9: Create API endpoints for manual UPRN lookup
- KAN-5.10: Add logging and monitoring for mapping success/failure rates
- KAN-5.11: Write unit tests for mapping service

---

#### Story 1.6: UPRN Mapping Integration
**Story Key:** KAN-6  
**Story Type:** Story  
**Summary:** Integrate UPRN mapping into ingestion pipeline  
**Description:** Automatically map addresses to UPRN during CSV/Excel upload, store mappings, and link to submissions  
**Acceptance Criteria:**
- Addresses automatically mapped during upload
- UPRN stored in property records
- UPRN linked to upload submissions for lineage
- Failed mappings logged for manual review
- Integration doesn't slow upload significantly (< 2s per 100 addresses)

**Tasks:**
- KAN-6.1: Hook UPRN mapping into CSV/Excel upload processing
- KAN-6.2: Store UPRN in property records during ingestion
- KAN-6.3: Link UPRN to upload submissions in lineage tracking
- KAN-6.4: Create manual review queue for failed mappings
- KAN-6.5: Add UPRN mapping status to upload response
- KAN-6.6: Write integration tests for UPRN mapping in upload flow

---

### Epic 2: Portfolio Overview Dashboard (Week 3-4)

#### Story 2.1: Portfolio Summary Cards
**Story Key:** KAN-7  
**Story Type:** Story  
**Summary:** Create portfolio summary cards component  
**Description:** Display high-level metrics: total blocks, units, properties  
**Acceptance Criteria:**
- Summary cards display correct metrics
- Cards update when filters change
- Cards are responsive
- Loading states shown during data fetch

**Tasks:**
- KAN-7.1: Create SummaryCards component
- KAN-7.2: Create backend API endpoint for portfolio summary
- KAN-7.3: Integrate API call with React Query
- KAN-7.4: Add loading and error states
- KAN-7.5: Style cards with design system

---

#### Story 2.2: Risk Distribution Chart
**Story Key:** KAN-8  
**Story Type:** Story  
**Summary:** Create risk distribution chart (E/D/C/B ratings)  
**Description:** Display risk rating distribution as a bar chart or pie chart  
**Acceptance Criteria:**
- Chart displays risk distribution correctly
- Chart updates with filters
- Chart is interactive (tooltips, hover states)
- Chart is responsive

**Tasks:**
- KAN-8.1: Install and configure charting library (Recharts)
- KAN-8.2: Create RiskDistributionChart component
- KAN-8.3: Create backend API endpoint for risk distribution
- KAN-8.4: Add chart interactivity (tooltips, legends)
- KAN-8.5: Style chart to match design system

---

#### Story 2.3: Readiness Progress Bars
**Story Key:** KAN-9  
**Story Type:** Story  
**Summary:** Create legislation & market readiness progress bars  
**Description:** Display statutory readiness, insurance readiness, and data completeness percentages  
**Acceptance Criteria:**
- Progress bars display correct percentages
- Bars update with filters
- Color coding based on percentage thresholds
- Responsive design

**Tasks:**
- KAN-9.1: Create ReadinessProgressBars component
- KAN-9.2: Create backend API endpoint for readiness metrics
- KAN-9.3: Implement percentage calculation logic
- KAN-9.4: Add color coding (green/yellow/red thresholds)
- KAN-9.5: Style progress bars

---

#### Story 2.4: Recent Activity Feed
**Story Key:** KAN-10  
**Story Type:** Story  
**Summary:** Create recent activity feed component  
**Description:** Display recent uploads, processing events, and user actions  
**Acceptance Criteria:**
- Activity feed displays recent events
- Events are sorted by timestamp (newest first)
- Feed updates in real-time or on refresh
- Clickable items navigate to relevant pages

**Tasks:**
- KAN-10.1: Create ActivityFeed component
- KAN-10.2: Create backend API endpoint for recent activity
- KAN-10.3: Format activity items with timestamps
- KAN-10.4: Add navigation links to activity items
- KAN-10.5: Style activity feed

---

#### Story 2.5: Dashboard Filters & Actions
**Story Key:** KAN-11  
**Story Type:** Story  
**Summary:** Add filters and quick action buttons to dashboard  
**Description:** Implement jurisdiction filter, time period selector, and quick action buttons (Upload, Export)  
**Acceptance Criteria:**
- Filters update dashboard data
- Time period selector works
- Quick action buttons navigate correctly
- Filters persist in URL or state

**Tasks:**
- KAN-11.1: Create jurisdiction filter (England/Scotland tabs)
- KAN-11.2: Create time period selector component
- KAN-11.3: Implement filter state management
- KAN-11.4: Add quick action buttons (Upload, Export)
- KAN-11.5: Connect filters to API calls

---

#### Story 2.6: Portfolio Overview Dashboard Integration
**Story Key:** KAN-12  
**Story Type:** Story  
**Summary:** Integrate all components into Portfolio Overview Dashboard  
**Description:** Combine all components into complete dashboard page with layout and routing  
**Acceptance Criteria:**
- Dashboard page loads all components
- All components work together
- Layout is responsive
- Dashboard route is protected

**Tasks:**
- KAN-12.1: Create PortfolioOverviewDashboard page component
- KAN-12.2: Layout all components in grid/flex layout
- KAN-12.3: Add route for dashboard
- KAN-12.4: Test complete dashboard functionality
- KAN-12.5: Add responsive breakpoints

---

### Epic 3: Block View Dashboard (Week 5-6)

#### Story 3.1: Blocks Table Component
**Story Key:** KAN-13  
**Story Type:** Story  
**Summary:** Create blocks table with all required columns  
**Description:** Display blocks in table format with columns: Jurisdiction, Block Name, Units, Height, Build, Construction, EWS/Cladding, Remediation To-Do  
**Acceptance Criteria:**
- Table displays all columns correctly
- Table is sortable
- Table supports pagination (50-100 blocks per page)
- "View details" link works for each block
- Table is responsive (horizontal scroll on mobile)

**Tasks:**
- KAN-13.1: Create BlocksTable component using TanStack Table
- KAN-13.2: Define table columns and data structure
- KAN-13.3: Implement sorting functionality
- KAN-13.4: Implement pagination
- KAN-13.5: Add "View details" navigation links
- KAN-13.6: Style table with design system
- KAN-13.7: Add responsive behavior

---

#### Story 3.2: Block Filtering System
**Story Key:** KAN-14  
**Story Type:** Story  
**Summary:** Implement comprehensive filtering system for blocks  
**Description:** Create filters for jurisdiction, I-Rating, confidence, height, SBA in-scope, and search by block name  
**Acceptance Criteria:**
- All filters work independently and in combination
- Search filters blocks in real-time
- Filters update table data
- Filter state persists

**Tasks:**
- KAN-14.1: Create BlockFilters component
- KAN-14.2: Implement jurisdiction filter (England/Scotland tabs)
- KAN-14.3: Create I-Rating dropdown filter
- KAN-14.4: Create confidence level filter
- KAN-14.5: Create height range filter
- KAN-14.6: Create SBA in-scope filter
- KAN-14.7: Implement search by block name
- KAN-14.8: Connect filters to API calls
- KAN-14.9: Style filter components

---

#### Story 3.3: Block Summary Panel
**Story Key:** KAN-15  
**Story Type:** Story  
**Summary:** Create block summary panel with risk distribution and readiness metrics  
**Description:** Display risk rating distribution chart and legislation & market readiness progress bars in side panel  
**Acceptance Criteria:**
- Summary panel updates based on filtered data
- Risk distribution chart displays correctly
- Readiness progress bars show correct percentages
- Panel is responsive

**Tasks:**
- KAN-15.1: Create BlockSummaryPanel component
- KAN-15.2: Create risk distribution chart for filtered blocks
- KAN-15.3: Create readiness progress bars for filtered blocks
- KAN-15.4: Create backend API endpoint for block summary
- KAN-15.5: Style summary panel
- KAN-15.6: Add responsive layout

---

#### Story 3.4: Missing Info Gaps Panel
**Story Key:** KAN-16  
**Story Type:** Story  
**Summary:** Create missing info gaps panel with statutory and insurance tabs  
**Description:** Display list of missing information with timestamps, clickable items, and tabs for Statutory and Insurance  
**Acceptance Criteria:**
- Missing info gaps display correctly
- Tabs switch between Statutory and Insurance
- Timestamps show relative time (e.g., "6 days ago")
- Clickable items navigate to relevant pages
- List updates based on portfolio data

**Tasks:**
- KAN-16.1: Create MissingInfoGaps component
- KAN-16.2: Implement tab switching (Statutory/Insurance)
- KAN-16.3: Format timestamps as relative time
- KAN-16.4: Create backend API endpoint for missing info gaps
- KAN-16.5: Add navigation links to gap items
- KAN-16.6: Style missing info gaps list

---

#### Story 3.5: Remediation To-Do Cell
**Story Key:** KAN-17  
**Story Type:** Story  
**Summary:** Create remediation to-do cell component for blocks table  
**Description:** Display remediation tasks summary (P1 + X • Y open) and next action due date  
**Acceptance Criteria:**
- Cell displays task summary correctly
- Priority levels (P1, P2) shown
- Open tasks count displayed
- Next action due date shown with color coding (overdue/upcoming)
- Cell is clickable to view details

**Tasks:**
- KAN-17.1: Create RemediationToDoCell component
- KAN-17.2: Parse and format task summary data
- KAN-17.3: Add color coding for due dates
- KAN-17.4: Add click handler for details view
- KAN-17.5: Style cell component

---

#### Story 3.6: Block View Dashboard Integration
**Story Key:** KAN-18  
**Story Type:** Story  
**Summary:** Integrate all components into Block View Dashboard  
**Description:** Combine table, filters, and panels into complete dashboard page  
**Acceptance Criteria:**
- Dashboard page loads all components
- Components work together
- Layout is responsive
- Dashboard route is protected

**Tasks:**
- KAN-18.1: Create BlockViewDashboard page component
- KAN-18.2: Layout components (table left, panels right)
- KAN-18.3: Add route for block view dashboard
- KAN-18.4: Test complete dashboard functionality
- KAN-18.5: Add responsive breakpoints

---

### Epic 4: HA Profile & Property Map (Week 7-8)

#### Story 4.1: HA Header Section
**Story Key:** KAN-19  
**Story Type:** Story  
**Summary:** Create HA header with name, logo, contact info, and portfolio selector  
**Description:** Display housing association information, contact details, and portfolio dropdown  
**Acceptance Criteria:**
- HA name and logo display correctly
- Contact information shown
- Portfolio selector dropdown works
- Quick stats (total blocks, units, properties) displayed
- Header is responsive

**Tasks:**
- KAN-19.1: Create HAHeader component
- KAN-19.2: Create backend API endpoint for HA details
- KAN-19.3: Implement portfolio selector dropdown
- KAN-19.4: Display quick stats
- KAN-19.5: Style header component

---

#### Story 4.2: Interactive Property Map
**Story Key:** KAN-20  
**Story Type:** Story  
**Summary:** Create interactive property map using Leaflet or Mapbox  
**Description:** Display properties on map with markers, clustering, click handlers, and filtering  
**Acceptance Criteria:**
- Map loads with all properties
- Markers are clickable and show property info
- Marker clustering works for large datasets
- Map filters work correctly
- Map performance is acceptable (< 3s load for 1000+ properties)
- Map is responsive

**Tasks:**
- KAN-20.1: Install and configure Leaflet or Mapbox GL JS
- KAN-20.2: Create PropertyMap component
- KAN-20.3: Create PropertyMarker component
- KAN-20.4: Implement marker clustering
- KAN-20.5: Add click handlers for markers
- KAN-20.6: Create property info popup/tooltip
- KAN-20.7: Implement map filters (risk rating, height, etc.)
- KAN-20.8: Add layer toggles
- KAN-20.9: Implement zoom to portfolio bounds
- KAN-20.10: Optimize map performance
- KAN-20.11: Style map controls

---

#### Story 4.3: Property List Panel
**Story Key:** KAN-21  
**Story Type:** Story  
**Summary:** Create property list panel that syncs with map  
**Description:** Display list of properties with key details, click to highlight on map, and filter/search  
**Acceptance Criteria:**
- Property list displays all properties
- Clicking list item highlights marker on map
- Filter and search work
- List updates when map filters change
- Panel is responsive

**Tasks:**
- KAN-21.1: Create PropertyListPanel component
- KAN-21.2: Implement click handler to highlight map marker
- KAN-21.3: Add filter and search functionality
- KAN-21.4: Sync list with map filters
- KAN-21.5: Style property list

---

#### Story 4.4: HA Summary Tabs
**Story Key:** KAN-22  
**Story Type:** Story  
**Summary:** Create HA summary tabs (Overview, Properties, Documents, Compliance)  
**Description:** Display different views of HA data in tabbed interface  
**Acceptance Criteria:**
- Tabs switch between views
- Overview tab shows general stats
- Properties tab shows list view
- Documents tab shows uploaded files
- Compliance tab shows readiness metrics
- Tabs are accessible (keyboard navigation)

**Tasks:**
- KAN-22.1: Create HASummaryTabs component
- KAN-22.2: Create Overview tab content
- KAN-22.3: Create Properties tab (list view)
- KAN-22.4: Create Documents tab
- KAN-22.5: Create Compliance tab
- KAN-22.6: Style tabs component

---

#### Story 4.5: HA Profile Page Integration
**Story Key:** KAN-23  
**Story Type:** Story  
**Summary:** Integrate all components into HA Profile Page  
**Description:** Combine header, map, list panel, and tabs into complete profile page  
**Acceptance Criteria:**
- Profile page loads all components
- Components work together
- Layout is responsive (map full-width on desktop, stacked on mobile)
- Profile page route is protected

**Tasks:**
- KAN-23.1: Create HAProfilePage component
- KAN-23.2: Layout all components
- KAN-23.3: Add route for HA profile page
- KAN-23.4: Test complete page functionality
- KAN-23.5: Add responsive breakpoints

---

### Epic 5: Analytics Dashboard (Week 9-10)

#### Story 5.1: Key Metrics Cards
**Story Key:** KAN-24  
**Story Type:** Story  
**Summary:** Create key metrics cards for analytics dashboard  
**Description:** Display total remediation tasks, overdue actions count, compliance score trends, and data quality score  
**Acceptance Criteria:**
- Metrics cards display correct data
- Cards update with date range filter
- Cards show trends (up/down indicators)
- Cards are responsive

**Tasks:**
- KAN-24.1: Create MetricsCards component
- KAN-24.2: Create backend API endpoint for key metrics
- KAN-24.3: Implement trend calculation logic
- KAN-24.4: Add up/down indicators
- KAN-24.5: Style metrics cards

---

#### Story 5.2: Charts & Visualizations
**Story Key:** KAN-25  
**Story Type:** Story  
**Summary:** Create charts and visualizations for analytics  
**Description:** Display risk rating distribution over time, height distribution histogram, construction type breakdown, remediation completion timeline, and jurisdiction comparison  
**Acceptance Criteria:**
- All charts render with real data
- Charts update with date range filter
- Charts are interactive (tooltips, zoom)
- Charts are responsive

**Tasks:**
- KAN-25.1: Create TrendChart component (risk distribution over time)
- KAN-25.2: Create DistributionChart component (height histogram)
- KAN-25.3: Create pie chart for construction type breakdown
- KAN-25.4: Create timeline chart for remediation completion
- KAN-25.5: Create comparison chart for jurisdictions
- KAN-25.6: Create backend API endpoints for chart data
- KAN-25.7: Add chart interactivity
- KAN-25.8: Style all charts

---

#### Story 5.3: Export Functionality
**Story Key:** KAN-26  
**Story Type:** Story  
**Summary:** Implement export functionality for analytics dashboard  
**Description:** Enable export to Excel/CSV and generate PDF reports, including Underwriter Pack export  
**Acceptance Criteria:**
- Export to Excel/CSV works
- PDF reports generate correctly
- Export Underwriter Pack works
- Export includes filtered data
- Export files are downloadable

**Tasks:**
- KAN-26.1: Create ExportButton component
- KAN-26.2: Implement Excel/CSV export functionality
- KAN-26.3: Create backend API endpoint for Excel export
- KAN-26.4: Implement PDF report generation
- KAN-26.5: Create backend API endpoint for PDF export
- KAN-26.6: Implement Underwriter Pack export
- KAN-26.7: Add export progress indicator

---

#### Story 5.4: Date Range Selector
**Story Key:** KAN-27  
**Story Type:** Story  
**Summary:** Create date range selector for filtering analytics  
**Description:** Allow users to filter all metrics and charts by date range and compare periods  
**Acceptance Criteria:**
- Date range selector works
- All metrics update with date range
- Period comparison works
- Date range persists in state/URL

**Tasks:**
- KAN-27.1: Create DateRangePicker component
- KAN-27.2: Implement date range state management
- KAN-27.3: Connect date range to all API calls
- KAN-27.4: Add period comparison functionality
- KAN-27.5: Style date range picker

---

#### Story 5.5: Analytics Dashboard Integration
**Story Key:** KAN-28  
**Story Type:** Story  
**Summary:** Integrate all components into Analytics Dashboard  
**Description:** Combine metrics, charts, and export into complete dashboard page  
**Acceptance Criteria:**
- Dashboard page loads all components
- All components work together
- Dashboard loads in < 3 seconds
- Layout is responsive

**Tasks:**
- KAN-28.1: Create AnalyticsDashboard page component
- KAN-28.2: Layout all components
- KAN-28.3: Add route for analytics dashboard
- KAN-28.4: Optimize dashboard load time
- KAN-28.5: Test complete dashboard functionality

---

### Epic 6: Excel Table Views (Week 11-12)

#### Story 6.1: Doc A View - Property Schedule Table
**Story Key:** KAN-29  
**Story Type:** Story  
**Summary:** Create Doc A view (Property Schedule Table)  
**Description:** Display property schedule data in tabular format matching Excel format with all required columns  
**Acceptance Criteria:**
- Table displays all columns correctly
- Table is sortable and filterable
- Virtual scrolling handles 10,000+ rows smoothly
- Inline editing works (if permissions allow)
- Export to Excel maintains format
- Import from Excel works with validation

**Tasks:**
- KAN-29.1: Create DocAView component
- KAN-29.2: Create DataTable component using TanStack Table
- KAN-29.3: Define property schedule columns
- KAN-29.4: Implement virtual scrolling
- KAN-29.5: Implement column sorting
- KAN-29.6: Implement column filtering
- KAN-29.7: Add column resizing and reordering
- KAN-29.8: Implement inline editing (if allowed)
- KAN-29.9: Create backend API endpoint for property schedule data
- KAN-29.10: Style table to match Excel format

---

#### Story 6.2: Doc B View - EPC Data Table
**Story Key:** KAN-30  
**Story Type:** Story  
**Summary:** Create Doc B view (EPC Data Table)  
**Description:** Display EPC data in tabular format with linking to property schedule via UPRN  
**Acceptance Criteria:**
- Table displays all EPC columns correctly
- Table is sortable and filterable
- UPRN links to property schedule
- Filter by EPC rating works
- Export to Excel works
- Import from Excel works

**Tasks:**
- KAN-30.1: Create DocBView component
- KAN-30.2: Define EPC data columns
- KAN-30.3: Implement UPRN linking to property schedule
- KAN-30.4: Add EPC rating filter
- KAN-30.5: Create backend API endpoint for EPC data
- KAN-30.6: Style table to match Excel format

---

#### Story 6.3: Table Features (Shared)
**Story Key:** KAN-31  
**Story Type:** Story  
**Summary:** Implement shared table features for Doc A and Doc B  
**Description:** Add column visibility toggle, search/filter per column, row selection, bulk actions, and pagination  
**Acceptance Criteria:**
- Column visibility toggle works
- Search/filter per column works
- Row selection (checkbox) works
- Bulk actions bar appears when rows selected
- Pagination or infinite scroll works

**Tasks:**
- KAN-31.1: Create TableFilters component
- KAN-31.2: Implement column visibility toggle
- KAN-31.3: Implement per-column search/filter
- KAN-31.4: Add row selection with checkboxes
- KAN-31.5: Create BulkActionsBar component
- KAN-31.6: Implement pagination or infinite scroll
- KAN-31.7: Style table features

---

#### Story 6.4: Excel Import/Export
**Story Key:** KAN-32  
**Story Type:** Story  
**Summary:** Implement Excel import and export functionality  
**Description:** Enable importing property schedule and EPC data from Excel, and exporting to Excel maintaining format  
**Acceptance Criteria:**
- Export generates Excel file matching original format
- Import validates data and shows errors clearly
- Import supports both .xlsx and .xls formats
- Import maintains column order
- Export selected rows works

**Tasks:**
- KAN-32.1: Install and configure SheetJS (xlsx) library
- KAN-32.2: Create ExportMenu component
- KAN-32.3: Implement Excel export functionality
- KAN-32.4: Create ImportDialog component
- KAN-32.5: Implement Excel import with validation
- KAN-32.6: Create backend API endpoints for import/export
- KAN-32.7: Add import error display
- KAN-32.8: Test with sample Excel files

---

#### Story 6.5: Excel Table Views Integration
**Story Key:** KAN-33  
**Story Type:** Story  
**Summary:** Integrate Doc A and Doc B views into application  
**Description:** Add routes, navigation, and complete integration of Excel table views  
**Acceptance Criteria:**
- Doc A and Doc B views are accessible via routes
- Navigation links work
- Views are responsive (horizontal scroll on mobile)
- Views are protected routes

**Tasks:**
- KAN-33.1: Add routes for Doc A and Doc B views
- KAN-33.2: Add navigation links in main menu
- KAN-33.3: Test complete import/export flow
- KAN-33.4: Add responsive behavior
- KAN-33.5: Final testing and bug fixes

---

## Backend API Tasks

### API Endpoints to Implement

#### Portfolio Endpoints
- KAN-API-1: `GET /api/v1/portfolios` - List portfolios
- KAN-API-2: `GET /api/v1/portfolios/{id}` - Get portfolio details
- KAN-API-3: `GET /api/v1/portfolios/{id}/summary` - Portfolio summary
- KAN-API-4: `GET /api/v1/portfolios/{id}/blocks` - List blocks with filters
- KAN-API-5: `GET /api/v1/portfolios/{id}/analytics` - Analytics data
- KAN-API-6: `GET /api/v1/portfolios/{id}/readiness` - Readiness metrics
- KAN-API-7: `GET /api/v1/portfolios/{id}/risk-distribution` - Risk distribution
- KAN-API-8: `GET /api/v1/portfolios/{id}/recent-activity` - Recent activity

#### Block Endpoints
- KAN-API-9: `GET /api/v1/blocks/{id}` - Get block details
- KAN-API-10: `GET /api/v1/blocks/{id}/properties` - Get properties in block
- KAN-API-11: `GET /api/v1/portfolios/{id}/blocks/summary` - Block summary

#### Property Endpoints
- KAN-API-12: `GET /api/v1/properties` - List properties (with filters)
- KAN-API-13: `GET /api/v1/properties/{id}` - Get property details
- KAN-API-14: `GET /api/v1/properties/export` - Export property schedule
- KAN-API-15: `POST /api/v1/properties/import` - Import property schedule
- KAN-API-16: `PUT /api/v1/properties/{id}` - Update property (if editing allowed)
- KAN-API-17: `POST /api/v1/properties/bulk-update` - Bulk update properties

#### EPC Data Endpoints
- KAN-API-18: `GET /api/v1/epc-data` - List EPC records
- KAN-API-19: `GET /api/v1/epc-data/export` - Export EPC data

#### HA Endpoints
- KAN-API-20: `GET /api/v1/housing-associations/{id}/properties` - Get properties with coordinates
- KAN-API-21: `GET /api/v1/housing-associations/{id}/summary` - HA summary
- KAN-API-22: `GET /api/v1/housing-associations/{id}/portfolios` - List HA portfolios

#### UPRN Mapping Endpoints
- KAN-API-23: `POST /api/v1/mapping/uprn/lookup` - Single address to UPRN lookup
- KAN-API-24: `POST /api/v1/mapping/uprn/batch-lookup` - Batch address to UPRN lookup
- KAN-API-25: `GET /api/v1/mapping/uprn/{uprn}/validate` - Validate UPRN exists
- KAN-API-26: `GET /api/v1/mapping/uprn/{uprn}/details` - Get UPRN details

#### Export Endpoints
- KAN-API-27: `POST /api/v1/portfolios/{id}/export-underwriter-pack` - Generate PDF pack

#### Missing Info Gaps Endpoints
- KAN-API-28: `GET /api/v1/portfolios/{id}/missing-info-gaps` - Get missing info gaps

---

## Database Tasks

### Schema Extensions
- KAN-DB-1: Create `properties` table (Silver layer)
- KAN-DB-2: Create `blocks` table
- KAN-DB-3: Create `epc_data` table
- KAN-DB-4: Create `portfolios` table
- KAN-DB-5: Create `uprn_mappings` table
- KAN-DB-6: Create indexes for performance
- KAN-DB-7: Run database migrations
- KAN-DB-8: Test database schema

---

## Testing Tasks

### Unit Tests
- KAN-TEST-1: Write unit tests for UPRN mapping service
- KAN-TEST-2: Write unit tests for API endpoints
- KAN-TEST-3: Write unit tests for React components
- KAN-TEST-4: Write unit tests for utility functions

### Integration Tests
- KAN-TEST-5: Write integration tests for upload with UPRN mapping
- KAN-TEST-6: Write integration tests for dashboard data flow
- KAN-TEST-7: Write integration tests for Excel import/export

### E2E Tests
- KAN-TEST-8: Write E2E tests for complete user workflows
- KAN-TEST-9: Write E2E tests for dashboard interactions

---

## Documentation Tasks

- KAN-DOC-1: Update API documentation (OpenAPI/Swagger)
- KAN-DOC-2: Create component documentation (Storybook)
- KAN-DOC-3: Update README with new features
- KAN-DOC-4: Create user guide for dashboards
- KAN-DOC-5: Create developer setup guide

---

## Total Ticket Count

- **Epics:** 6
- **Stories:** 33
- **Tasks:** ~150+
- **API Endpoints:** 28
- **Database Tasks:** 8
- **Testing Tasks:** 9
- **Documentation Tasks:** 5

**Grand Total: ~200+ tickets**

---

## Priority Levels

- **P0 (Critical):** Epic 1 (Infrastructure), Epic 2 (Portfolio Dashboard)
- **P1 (High):** Epic 3 (Block View), Epic 4 (HA Profile)
- **P2 (Medium):** Epic 5 (Analytics), Epic 6 (Excel Views)

---

## Sprint Planning Suggestions

### Sprint 1 (Week 1-2): Infrastructure
- Epic 1: Frontend Infrastructure & UPRN Mapping

### Sprint 2 (Week 3-4): First Dashboard
- Epic 2: Portfolio Overview Dashboard

### Sprint 3 (Week 5-6): Block View
- Epic 3: Block View Implementation

### Sprint 4 (Week 7-8): Maps & Profile
- Epic 4: HA Profile & Property Map

### Sprint 5 (Week 9-10): Analytics
- Epic 5: Analytics Dashboard

### Sprint 6 (Week 11-12): Excel Integration
- Epic 6: Excel Table Views

---

## Notes for Jira Import

1. **Epic Links:** Link all stories to their respective epics
2. **Labels:** Add labels like `frontend`, `backend`, `api`, `database`, `testing`
3. **Components:** Create components for: Frontend, Backend, API, Database, Testing
4. **Fix Versions:** Create versions for each sprint (Sprint 1, Sprint 2, etc.)
5. **Story Points:** Estimate story points for each story (1-8 points)
6. **Assignees:** Assign tickets to team members based on expertise
7. **Dependencies:** Link dependent tasks (e.g., API endpoints before frontend integration)
