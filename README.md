# Platform-dev

A full-stack property portfolio management and analytics dashboard application built with React and FastAPI.

## Overview

This project is a web-based platform for property portfolio management, data ingestion, and analytics. It provides functionality for uploading CSV/Excel files, visualizing property data on interactive maps, exploring portfolios with advanced filtering, and generating analytics reports.

## Project Structure

The project is organized across multiple development branches, each containing different components and features:

### Branch Structure

- **`main`**: Main branch (currently minimal, ready for integration)
- **`Igor`**: Full-stack implementation with complete backend and frontend
- **`Kanishka`**: Frontend-focused work with React components and styling

### Directory Structure (Igor Branch)

```
Platform-dev/
├── frontend/              # React frontend application
│   ├── src/
│   │   ├── App.js        # Main application component
│   │   ├── LandingPage.js
│   │   ├── LoginPage.js
│   │   ├── RegisterPage.js
│   │   ├── data/
│   │   │   └── properties.js
│   │   └── styles.css
│   ├── public/
│   │   └── index.html
│   └── package.json
├── backend/              # FastAPI backend
│   ├── api.py           # Main API endpoints
│   ├── preprocessing.py # Data preprocessing utilities
│   ├── auto_detect.py   # Auto-detection functionality
│   ├── detect_functions.py
│   └── geo/
│       └── postcoderequests.py
└── datacleaning/        # Data cleaning notebooks
    ├── datacleaning.ipynb
    ├── test.csv
    └── output.csv
```

## Technology Stack

### Frontend
- **React** 18.2.0 - UI framework
- **React Router DOM** 7.9.6 - Routing
- **Leaflet** 1.9.4 & **React-Leaflet** 4.2.1 - Interactive maps
- **Recharts** 3.5.1 - Data visualization and charts
- **PapaParse** 5.5.3 - CSV parsing
- **XLSX** 0.18.5 - Excel file handling

### Backend
- **FastAPI** - Python web framework
- **Pandas** - Data processing and manipulation
- **Python 3.12** - Runtime environment

## Features

### Current Features
- 🏠 **Landing Page** - Welcome page with project introduction
- 🔐 **Authentication** - Login and registration functionality
- 📊 **Data Ingestion** - Upload and process CSV/Excel files
- 🗺️ **Interactive Maps** - Visualize property locations using Leaflet
- 📈 **Analytics Dashboard** - Charts and data visualization with Recharts
- 🔍 **Portfolio Explorer** - Filter and search properties by:
  - City
  - Risk level
  - Tenure type
  - Custom search queries
- 📋 **Document Management** - Stock listing (Doc A) and High value (Doc B) views

### Application Tabs
1. **Ingestion & Overview** - Upload and view uploaded data
2. **Portfolio Explorer** - Browse and filter property portfolio
3. **Analytics** - Data visualization and insights
4. **Stock Listing (Doc A)** - Document A view
5. **High Value (Doc B)** - Document B view

## Getting Started

### Prerequisites
- Node.js (v14 or higher)
- Python 3.12+
- npm or yarn

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm start
```

The frontend will run on `http://localhost:3000` (or the next available port).

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Install Python dependencies (create a virtual environment first):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install fastapi uvicorn pandas python-multipart
```

3. Start the FastAPI server:
```bash
uvicorn api:app --reload --port 8000
```

The backend API will run on `http://localhost:8000`.

**Note**: The backend is configured to accept CORS requests from `http://localhost:3002`. Update the CORS configuration in `backend/api.py` if using a different port.

## Development Workflow

### Branch Strategy

- **Main Branch**: Production-ready code
- **Feature Branches**: Individual developer branches (Igor, Kanishka) for parallel development
- **Integration**: Merge feature branches into main after review

### Recent Development Activity

Recent commits include:
- CSV upload and display functionality
- Chart integration and data visualization
- Login functionality with authentication
- Landing page creation and styling
- Property data management

## API Endpoints

### Backend API (FastAPI)

- `POST /upload-csv` - Upload and process CSV files
  - Accepts CSV file uploads
  - Standardizes column names
  - Returns processed data in JSON format
  - Response schema: [CSV Upload Response Schema](schemas/csv-upload-response-schema.json)

## Data Schemas

The project uses JSON schemas to define core data structures:

- **[Property Schema](schemas/property-schema.json)** - Complete property data structure with all fields including insurance, risk, and high-value property details
- **[Standardized Property Schema](schemas/standardized-property-schema.json)** - Property data after column standardization (based on preprocessing column mapping)
- **[CSV Upload Response Schema](schemas/csv-upload-response-schema.json)** - API response structure for CSV upload endpoint
- **[Auto-Detection Result Schema](schemas/auto-detection-result-schema.json)** - Structure of auto-detection results from the data type detection system

These schemas can be used for:
- API validation
- Data transformation pipelines
- Frontend type definitions
- Documentation and testing

## Data Processing

The backend includes utilities for:
- **Column Standardization** - Automatically standardize CSV column names
- **Data Preprocessing** - Clean and prepare data for analysis
- **Auto-Detection** - Automatically detect data patterns and types (see [Auto-Detection Documentation](docs/auto-detection.md))
- **Geographic Processing** - Handle postcode and location data
