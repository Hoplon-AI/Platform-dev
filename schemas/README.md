# Data Schemas

This directory contains JSON Schema definitions for the core data structures used in the Platform-dev application.

## Available Schemas

### 1. Property Schema (`property-schema.json`)

Complete schema for property portfolio data, including:
- Basic property information (address, location, identifiers)
- Insurance details (policy references, deductibles, sum insured)
- Risk metrics (flood score, crime index, deprivation index)
- Property characteristics (construction, age, type)
- High-value property details (Doc B fields: cladding, EWS status, fire risk management)

**Use Cases:**
- Validating property data before storage
- Generating TypeScript types for frontend
- API request/response validation
- Data migration and transformation

### 2. Standardized Property Schema (`standardized-property-schema.json`)

Schema for property data after column standardization. This reflects the output from the `preprocessing.standardize_columns()` function, which normalizes various column name variants to standard names.

**Key Standardizations:**
- `id` ← id, property_id, prop_id, reference, ref_number
- `uprn` ← uprn, unique_property_reference, property_reference
- `address` ← address, full_address, property_address, street_address
- `postcode` ← postcode, post_code, zip_code, postal_code
- `epcRating` ← epcrating, epc_rating, epc, energy_rating
- And more...

**Use Cases:**
- Validating CSV upload results
- Understanding column mapping transformations
- Frontend data handling after API processing

### 3. CSV Upload Response Schema (`csv-upload-response-schema.json`)

Schema for the response from the `/upload-csv` API endpoint.

**Response Structure:**
```json
{
  "success": true,
  "message": "Successfully processed 100 rows",
  "columns": ["id", "address", "postcode", ...],
  "data": [...],
  "column_mapping": {"original_name": "standardized_name"},
  "row_count": 100,
  "original_filename": "properties.csv"
}
```

**Use Cases:**
- API response validation
- Frontend type definitions
- Testing and mocking

### 4. Auto-Detection Result Schema (`auto-detection-result-schema.json`)

Schema for results from the auto-detection system that identifies data types in CSV columns.

**Structure:**
- Each column name maps to a detection result
- Contains detected type, confidence score, and all detection scores
- Includes metadata like date formats, sequential flags, unique counts

**Use Cases:**
- Validating auto-detection API responses
- Understanding detection confidence levels
- Debugging data type identification

## Using the Schemas

### Python (with jsonschema)

```python
import json
import jsonschema
from jsonschema import validate

# Load schema
with open('schemas/property-schema.json') as f:
    schema = json.load(f)

# Validate data
try:
    validate(instance=property_data, schema=schema)
    print("Valid property data")
except jsonschema.exceptions.ValidationError as e:
    print(f"Validation error: {e.message}")
```

### TypeScript Generation

You can generate TypeScript types from these schemas using tools like:
- `json-schema-to-typescript`
- `quicktype`

```bash
npm install -g json-schema-to-typescript
json2ts -i schemas/property-schema.json -o types/property.ts
```

### FastAPI Integration

```python
from fastapi import FastAPI
from pydantic import BaseModel
import json

# Load schema for validation
with open('schemas/property-schema.json') as f:
    property_schema = json.load(f)

# Use with Pydantic models or jsonschema validation
```

## Schema Versioning

All schemas include a `version` field using semantic versioning (e.g., "1.0.0"). These schemas follow JSON Schema Draft 7 specification.

**Version Format:** `MAJOR.MINOR.PATCH`
- **MAJOR**: Breaking changes (incompatible API changes)
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

**When updating schemas:**
1. Maintain backward compatibility when possible
2. Increment version numbers according to semantic versioning:
   - Breaking changes → increment MAJOR
   - New fields/features → increment MINOR
   - Bug fixes → increment PATCH
3. Document changes in commit messages
4. Update the `version` field in the schema file
5. The `$id` field should remain stable for schema identification

## Contributing

When adding new schemas:
1. Follow JSON Schema Draft 7 format
2. Include comprehensive descriptions for all properties
3. Use appropriate validation constraints (min/max, patterns, enums)
4. Add examples where helpful
5. Update this README with schema documentation

