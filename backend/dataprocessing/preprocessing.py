import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re

def normalize_column_name(col_name):
    """Normalize column names to snake_case."""
    # Strip leading/trailing whitespace
    col_name = col_name.strip()
    # Lowercase the column name
    col_name = col_name.lower()
    # Spaces and hyphens to underscores
    col_name = re.sub(r'[\s\-]+', '_', col_name)
    # Remove special characters
    col_name = re.sub(r'[^\w_]', '', col_name)
    return col_name


COLUMN_MAPPING = {
    'id': ['id', 'property_id', 'prop_id', 'reference', 'ref_number'],
    'uprn': ['uprn', 'unique_property_reference', 'property_reference'],
    'address': ['address', 'full_address', 'property_address', 'street_address'],
    'city': ['city', 'town', 'locality'],
    'postcode': ['postcode', 'post_code', 'zip_code', 'postal_code'],
    'buildYear': ['buildyear', 'build_year', 'year_built', 'construction_year', 'built'],
    'type': ['type', 'property_type', 'dwelling_type', 'house_type'],
    'tenure': ['tenure', 'ownership', 'tenancy_type'],
    'landlord': ['landlord', 'owner', 'landlord_name', 'housing_provider'],
    'epcRating': ['epcrating', 'epc_rating', 'epc', 'energy_rating', 'energy_performance'],
    'lastClaimDate': ['lastclaimdate', 'last_claim_date', 'lastclaim', 'previous_claim',
                      'last_claim', 'claim_date', 'most_recent_claim'],
    'claimFrequency': ['claimfrequency', 'claim_frequency', 'number_of_claims', 'claims_count'],
    'riskBand': ['riskband', 'risk_band', 'risk_level', 'risk_category', 'risk_rating']
}


def standardize_columns(df, mapping=COLUMN_MAPPING):
    normalized_cols = {col: normalize_column_name(col) for col in df.columns}

    # Create reverse mapping from variants to standard names
    reverse_mapping = {}
    for standard_name, variants in mapping.items():
        for variant in variants:
            reverse_mapping[normalize_column_name(variant)] = standard_name

    # Create rename dictionary
    rename_dict = {}
    for original_col, normalized_col in normalized_cols.items():
        if normalized_col in reverse_mapping:
            rename_dict[original_col] = reverse_mapping[normalized_col]

    df_standardized = df.rename(columns=rename_dict)


    return df_standardized