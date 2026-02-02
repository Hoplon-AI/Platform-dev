import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re


def detect_postcode_column(series, threshold=0.7):
    """
    Detect if column contains UK postcodes.
    Returns confidence score (0-1).
    """
    uk_postcode_pattern = re.compile(
        r'^[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}$',
        re.IGNORECASE
    )

    non_null = series.dropna().astype(str).str.strip()
    if len(non_null) == 0:
        return 0.0

    matches = non_null.str.match(uk_postcode_pattern).sum()
    confidence = matches / len(non_null)


def detect_uprn_column(series, threshold=0.7):
    """
    Detect if column contains UPRN (Unique Property Reference Number).
    UPRNs are typically 12-digit numbers.
    Returns confidence score (0-1).
    """
    non_null = series.dropna().astype(str).str.strip()
    if len(non_null) == 0:
        return 0.0

    # Remove non-digits and check length
    digits_only = non_null.str.replace(r'\D', '', regex=True)
    matches = (digits_only.str.len() == 12).sum()
    confidence = matches / len(non_null)

    return confidence if confidence >= threshold else 0.0


def detect_date_column(series, threshold=0.7):
    """
    Detect if column contains dates.
    Returns confidence score (0-1) and inferred format if detected.
    """
    non_null = series.dropna().astype(str)
    if len(non_null) == 0:
        return 0.0, None

    formats = [
        '%Y-%m-%d',  # 2023-01-15
        '%d/%m/%Y',  # 15/01/2023
        '%m/%d/%Y',  # 01/15/2023
        '%d-%m-%Y',  # 15-01-2023
        '%Y/%m/%d',  # 2023/01/15
        '%d.%m.%Y',  # 15.01.2023
        '%Y%m%d',  # 20230115
    ]
    best_confidence = 0.0
    best_format = None

    for fmt in formats:
        try:
            parsed = pd.to_datetime(non_null, format=fmt, errors='coerce')
            valid = parsed.notna().sum()
            confidence = valid / len(non_null)

            if confidence > best_confidence:
                best_confidence = confidence
                best_format = fmt
        except:
            continue

    return (best_confidence if best_confidence >= threshold else 0.0), best_format


def detect_address_column(series, threshold=0.6):
    """
    Detect if column contains street addresses.
    Looks for common UK street indicators.
    Returns confidence score (0-1).
    """
    street_indicators = [
        r'\bstreet\b', r'\bst\b', r'\broad\b', r'\brd\b',
        r'\blive\b', r'\bave\b', r'\bavenue\b', r'\bclose\b',
        r'\bcourt\b', r'\bterrace\b', r'\bplace\b', r'\bsquare\b',
        r'\bway\b', r'\bcrescent\b', r'\bdrive\b', r'\bgardens\b'
    ]

    non_null = series.dropna().astype(str).str.lower()
    if len(non_null) == 0:
        return 0.0

    # Check for street indicators + numbers
    pattern = '|'.join(street_indicators)
    has_indicator = non_null.str.contains(pattern, regex=True, na=False)
    has_number = non_null.str.contains(r'\d', regex=True, na=False)

    matches = (has_indicator & has_number).sum()
    confidence = matches / len(non_null)

    return confidence if confidence >= threshold else 0.0


def detect_numeric_id_column(series, threshold=0.9):
    """
    Detect if column is a numeric ID (sequential or random integers).
    Returns confidence score (0-1) and whether it's sequential.
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return 0.0, False

    # Check if numeric
    numeric = pd.to_numeric(non_null, errors='coerce')
    numeric_ratio = numeric.notna().sum() / len(non_null)

    if numeric_ratio < threshold:
        return 0.0, False

    # Check if sequential
    numeric_clean = numeric.dropna().astype(int)
    if len(numeric_clean) > 1:
        diffs = numeric_clean.diff().dropna()
        is_sequential = (diffs == 1).mean() > 0.9
    else:
        is_sequential = False

    return numeric_ratio, is_sequential


def detect_categorical_column(series, max_unique_ratio=0.05):
    """
    Detect if column is categorical (low cardinality).
    Returns confidence score and unique count.
    """
    non_null_count = series.notna().sum()
    if non_null_count == 0:
        return 0.0, 0

    unique_count = series.nunique(dropna=True)
    unique_ratio = unique_count / non_null_count

    # High confidence if very few unique values
    if unique_ratio <= max_unique_ratio:
        confidence = 1.0 - unique_ratio
    else:
        confidence = 0.0

    return confidence, unique_count


def detect_boolean_column(series, threshold=0.8):
    """
    Detect if column contains boolean-like values.
    Returns confidence score (0-1).
    """
    non_null = series.dropna().astype(str).str.strip().str.lower()
    if len(non_null) == 0:
        return 0.0

    boolean_values = {
        'yes', 'no', 'true', 'false', '1', '0',
        'y', 'n', 't', 'f'
    }

    matches = non_null.isin(boolean_values).sum()
    confidence = matches / len(non_null)

    return confidence if confidence >= threshold else 0.0


def detect_year_column(series, threshold=0.8):
    """
    Detect if column contains year values (1900-2100).
    Returns confidence score (0-1).
    """
    non_null = pd.to_numeric(series, errors='coerce').dropna()
    if len(non_null) == 0:
        return 0.0

    in_year_range = ((non_null >= 1900) & (non_null <= 2100)).sum()
    confidence = in_year_range / len(non_null)

    return confidence if confidence >= threshold else 0.0


def detect_coordinate_column(series, lat_or_lon='lat', threshold=0.8):
    """
    Detect if column contains geographic coordinates.
    lat_or_lon: 'lat' for latitude or 'lon' for longitude
    Returns confidence score (0-1).
    """
    non_null = pd.to_numeric(series, errors='coerce').dropna()
    if len(non_null) == 0:
        return 0.0

    if lat_or_lon == 'lat':
        # UK latitude range: approximately 49-61
        in_range = ((non_null >= 49.0) & (non_null <= 61.0)).sum()
    else:  # lon
        # UK longitude range: approximately -8 to 2
        in_range = ((non_null >= -8.0) & (non_null <= 2.0)).sum()

    confidence = in_range / len(non_null)
    return confidence if confidence >= threshold else 0.0


def detect_cities(series, known_cities=None, threshold=0.6):
    """
    Detect if column contains city names.
    known_cities: set of known city names for matching.
    Returns confidence score (0-1).
    """
    if known_cities is None:
        known_cities = {
            "glasgow", "edinburgh", "aberdeen", "dundee", "inverness",
            "london", "manchester", "birmingham", "cardiff", "belfast"
        }

    non_null = series.dropna().astype(str).str.strip().str.lower()
    if len(non_null) == 0:
        return 0.0

    matches = non_null.isin(known_cities).sum()
    confidence = matches / len(non_null)

    return confidence if confidence >= threshold else 0.0


def detect_regions(series, known_regions=None, threshold=0.6):
    """
    Detect if column contains region names.
    known_regions: set of known region names for matching.
    Returns confidence score (0-1).
    """
    if known_regions is None:
        known_regions = {
            "scotland", "england", "wales", "northern ireland"
        }

    non_null = series.dropna().astype(str).str.strip().str.lower()
    if len(non_null) == 0:
        return 0.0

    matches = non_null.isin(known_regions).sum()
    confidence = matches / len(non_null)

    return confidence if confidence >= threshold else 0.0


def detect_house_type(series, confidence=0.6):
    """
    Detect house type column based on common house type keywords.
    Returns column name if detected, else None.
    """
    house_type_keywords = {
        "high-rise flat", "detached house", "semi-detached",
        "terraced", "bungalow", "apartment", "cottage", "maisonette",
        "duplex", "studio", "villa", "townhouse"
    }

    non_null = series.dropna().astype(str).str.strip().str.lower()

    if len(non_null) == 0:
        return 0.0

    matches = non_null.isin(house_type_keywords).sum()
    confidence = matches / len(non_null)

    return confidence if confidence >= confidence else 0.0


def detect_epc_rating_column(series, threshold=0.7):
    """
    Detect if column contains EPC ratings (A-G).
    Returns confidence score (0-1).
    """
    valid_ratings = {'a', 'b', 'c', 'd', 'e', 'f', 'g'}

    non_null = series.dropna().astype(str).str.strip().str.lower()
    if len(non_null) == 0:
        return 0.0

    matches = non_null.isin(valid_ratings).sum()
    confidence = matches / len(non_null)

    return confidence if confidence >= threshold else 0.0