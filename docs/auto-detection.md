# Auto-Detection System

The auto-detection system automatically identifies data types and patterns in CSV columns, enabling intelligent data processing and validation without manual configuration.

## Overview

The `auto_detect.py` module uses heuristic-based pattern matching to analyze each column in a dataset and determine its most likely data type. It returns confidence scores for each detection, allowing the system to make informed decisions about how to process and validate the data.

## How It Works

The auto-detection system runs multiple detection functions on each column and assigns a confidence score (0.0 to 1.0) for each potential data type. The type with the highest confidence above the threshold is selected as the detected type.

### Detection Process

1. **Column Analysis**: Each column is analyzed independently
2. **Multi-Pattern Detection**: All relevant detection functions are run on the column
3. **Confidence Scoring**: Each detector returns a confidence score (0.0-1.0)
4. **Type Selection**: The type with the highest confidence is selected
5. **Metadata Extraction**: Additional metadata (formats, counts, etc.) is captured

## Supported Data Types

### 1. Postcode Detection
- **Function**: `detect_postcode_column()`
- **Pattern**: UK postcode format (e.g., "SW1A 1AA", "M1 1AA")
- **Threshold**: 0.7 (70% of values must match)
- **Use Case**: Identifying location-based columns for geographic analysis

### 2. UPRN (Unique Property Reference Number)
- **Function**: `detect_uprn_column()`
- **Pattern**: 12-digit numeric identifiers
- **Threshold**: 0.7
- **Use Case**: Identifying unique property identifiers for data linking

### 3. Date Detection
- **Function**: `detect_date_column()`
- **Supported Formats**:
  - `%Y-%m-%d` (2023-01-15)
  - `%d/%m/%Y` (15/01/2023)
  - `%m/%d/%Y` (01/15/2023)
  - `%d-%m-%Y` (15-01-2023)
  - `%Y/%m/%d` (2023/01/15)
  - `%d.%m.%Y` (15.01.2023)
  - `%Y%m%d` (20230115)
- **Threshold**: 0.7
- **Metadata**: Returns the detected date format
- **Use Case**: Automatic date parsing and validation

### 4. Address Detection
- **Function**: `detect_address_column()`
- **Pattern**: UK street indicators (Street, Road, Avenue, etc.) combined with numbers
- **Threshold**: 0.6
- **Use Case**: Identifying address columns for geocoding

### 5. Numeric ID Detection
- **Function**: `detect_numeric_id_column()`
- **Pattern**: Numeric values that may be sequential or random
- **Threshold**: 0.9
- **Metadata**: Indicates if the ID is sequential
- **Use Case**: Identifying primary keys or reference numbers

### 6. Categorical Data Detection
- **Function**: `detect_categorical_column()`
- **Pattern**: Low cardinality columns (few unique values relative to total rows)
- **Threshold**: Maximum 5% unique ratio
- **Metadata**: Returns unique count
- **Use Case**: Identifying columns suitable for filtering or grouping

### 7. Boolean Detection
- **Function**: `detect_boolean_column()`
- **Pattern**: Boolean-like values (yes/no, true/false, 1/0, y/n, t/f)
- **Threshold**: 0.8
- **Use Case**: Identifying binary/categorical flags

### 8. Year Detection
- **Function**: `detect_year_column()`
- **Pattern**: Numeric values between 1900-2100
- **Threshold**: 0.8
- **Use Case**: Identifying year columns for temporal analysis

### 9. Coordinate Detection
- **Function**: `detect_coordinate_column()`
- **Pattern**: 
  - **Latitude**: Values between 49.0-61.0 (UK range)
  - **Longitude**: Values between -8.0-2.0 (UK range)
- **Threshold**: 0.8
- **Use Case**: Identifying geographic coordinates for mapping

### 10. City Detection
- **Function**: `detect_cities()`
- **Pattern**: Known UK city names (Glasgow, Edinburgh, London, Manchester, etc.)
- **Threshold**: 0.6
- **Use Case**: Identifying city columns for geographic grouping

### 11. Region Detection
- **Function**: `detect_regions()`
- **Pattern**: UK regions (Scotland, England, Wales, Northern Ireland)
- **Threshold**: 0.6
- **Use Case**: Identifying regional classification columns

### 12. House Type Detection
- **Function**: `detect_house_type()`
- **Pattern**: Common property types (detached, semi-detached, terraced, flat, etc.)
- **Threshold**: 0.6
- **Use Case**: Identifying property classification columns

### 13. EPC Rating Detection
- **Function**: `detect_epc_rating_column()`
- **Pattern**: EPC ratings A-G (case-insensitive)
- **Threshold**: 0.7
- **Use Case**: Identifying energy performance certificate ratings

## API Usage

### Basic Usage

```python
from auto_detect import auto_detect_column_types
import pandas as pd

# Load your dataframe
df = pd.read_csv('data.csv')

# Run auto-detection
results = auto_detect_column_types(df)

# Access results
for column, detection in results.items():
    print(f"{column}: {detection['detected_type']} (confidence: {detection['confidence']:.2f})")
```

### Result Structure

Each column returns a dictionary with:

```python
{
    'detected_type': 'postcode',  # The best matching type
    'confidence': 0.95,            # Confidence score (0.0-1.0)
    'all_scores': {                # All detection scores
        'postcode': 0.95,
        'address': 0.12,
        'categorical': 0.03,
        # ... other scores
    },
    # Optional metadata based on type:
    'format': '%Y-%m-%d',          # For date columns
    'is_sequential': True,          # For numeric_id columns
    'unique_count': 5               # For categorical columns
}
```

## Integration with Data Processing

The auto-detection system integrates with other data processing modules:

1. **Column Standardization**: Uses detected types to suggest appropriate column names
2. **Data Validation**: Validates data against detected types
3. **Geographic Processing**: Uses postcode/coordinate detection for location-based processing
4. **Data Preprocessing**: Applies appropriate cleaning based on detected types

## Confidence Scores

Confidence scores indicate how certain the system is about a detection:

- **0.9-1.0**: Very high confidence - almost all values match the pattern
- **0.7-0.9**: High confidence - majority of values match
- **0.5-0.7**: Moderate confidence - significant portion matches
- **< 0.5**: Low confidence - detection not reliable

## Customization

### Adjusting Thresholds

You can modify detection thresholds in `detect_functions.py` to be more or less strict:

```python
# More lenient detection
detections['postcode'] = detect_postcode_column(series, threshold=0.5)

# More strict detection
detections['postcode'] = detect_postcode_column(series, threshold=0.9)
```

### Adding Custom Detectors

To add a new detection function:

1. Create a function in `detect_functions.py`:
```python
def detect_custom_type(series, threshold=0.7):
    # Your detection logic
    return confidence_score
```

2. Add it to `auto_detect_column_types()` in `auto_detect.py`:
```python
detections['custom_type'] = detect_custom_type(series)
```

## Limitations

- **UK-Specific**: Many detectors are optimized for UK data (postcodes, coordinates, cities)
- **Heuristic-Based**: Relies on pattern matching, not machine learning
- **Threshold-Dependent**: May miss valid data if thresholds are too strict
- **Single Type**: Assumes one primary type per column (doesn't handle mixed types)

## Best Practices

1. **Review Low Confidence Detections**: Manually verify columns with confidence < 0.7
2. **Combine with Manual Review**: Use auto-detection as a starting point, not final authority
3. **Adjust Thresholds**: Fine-tune thresholds based on your data characteristics
4. **Handle Unknown Types**: Always check for 'unknown' type and handle appropriately
5. **Validate Results**: Cross-reference detected types with domain knowledge

## Examples

### Example 1: Detecting Postcodes

```python
import pandas as pd
from auto_detect import auto_detect_column_types

df = pd.DataFrame({
    'property_id': [1, 2, 3],
    'postcode': ['SW1A 1AA', 'M1 1AA', 'EH1 1AB'],
    'price': [250000, 180000, 320000]
})

results = auto_detect_column_types(df)
# Results:
# 'postcode': {'detected_type': 'postcode', 'confidence': 1.0, ...}
# 'property_id': {'detected_type': 'numeric_id', 'confidence': 1.0, ...}
```

### Example 2: Detecting Dates

```python
df = pd.DataFrame({
    'sale_date': ['2023-01-15', '2023-02-20', '2023-03-10'],
    'other_date': ['15/01/2023', '20/02/2023', '10/03/2023']
})

results = auto_detect_column_types(df)
# Results:
# 'sale_date': {'detected_type': 'date', 'confidence': 1.0, 'format': '%Y-%m-%d', ...}
# 'other_date': {'detected_type': 'date', 'confidence': 1.0, 'format': '%d/%m/%Y', ...}
```

## Troubleshooting

### Issue: Low Confidence Scores

**Solution**: Check if your data matches expected patterns. Consider:
- Data quality issues (missing values, formatting inconsistencies)
- Regional differences (non-UK data may need custom detectors)
- Adjusting thresholds for your specific use case

### Issue: Wrong Type Detected

**Solution**: 
- Review `all_scores` to see alternative detections
- Manually override if needed
- Consider adding custom detection logic

### Issue: Unknown Type

**Solution**:
- Column may contain truly mixed or unstructured data
- Consider manual classification
- May need custom detection function for your specific data type




