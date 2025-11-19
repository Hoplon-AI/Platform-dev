from detect_functions import *

def auto_detect_column_types(df):
    """
    Automatically detect column types using heuristics.
    Returns dictionary with column names and detected types with confidence.
    """
    results = {}

    for col in df.columns:
        series = df[col]
        detections = {}

        # Run all detectors
        detections['postcode'] = detect_postcode_column(series)
        detections['uprn'] = detect_uprn_column(series)
        detections['date'], date_fmt = detect_date_column(series)
        detections['address'] = detect_address_column(series)
        detections['numeric_id'], is_seq = detect_numeric_id_column(series)
        detections['categorical'], unique_count = detect_categorical_column(series)
        detections['boolean'] = detect_boolean_column(series)
        detections['year'] = detect_year_column(series)
        detections['latitude'] = detect_coordinate_column(series, 'lat')
        detections['longitude'] = detect_coordinate_column(series, 'lon')
        detections['city'] = detect_cities(series)
        detections['region'] = detect_regions(series)
        detections['house_type'] = detect_house_type(series)
        detections['epc_rating'] = detect_epc_rating_column(series)

        if detections['latitude'] > 0.8:
            best_type = 'latitude'
            best_confidence = detections['latitude']
        elif detections['longitude'] > 0.8:
            best_type = 'longitude'
            best_confidence = detections['longitude']
        else:
            best_type = max(detections, key=detections.get)
            best_confidence = detections[best_type]

        if best_confidence > 0:
            results[col] = {
                'detected_type': best_type,
                'confidence': best_confidence,
                'all_scores': detections
            }

            # Add metadata
            if best_type == 'date' and date_fmt:
                results[col]['format'] = date_fmt
            elif best_type == 'numeric_id':
                results[col]['is_sequential'] = is_seq
            elif best_type == 'categorical':
                results[col]['unique_count'] = unique_count
        else:
            results[col] = {
                'detected_type': 'unknown',
                'confidence': 0.0,
                'all_scores': detections
            }

    return results