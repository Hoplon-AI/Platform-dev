#!/usr/bin/env python3
"""
Check agentic extraction results for a given upload_id.

Shows both regex and agentic features, comparison metadata, and extraction method.
"""

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

# Add project root
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import asyncpg
from backend.core.database.db_pool import DatabasePool


async def check_results(upload_id_str: str):
    """Check extraction results for an upload."""
    try:
        upload_id = uuid.UUID(upload_id_str)
    except ValueError:
        print(f"Error: Invalid upload_id: {upload_id_str}")
        return 1

    # Connect to DB
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "postgres")
    database = os.getenv("DB_NAME", "platform_dev")

    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
    except Exception as e:
        print(f"DB connection failed: {e}")
        print("\nFor AWS RDS, set:")
        print("  export DB_HOST=<rds-endpoint>")
        print("  export DB_PASSWORD=$(aws secretsmanager get-secret-value --secret-id <secret-arn> --query SecretString --output text | jq -r .password)")
        return 1

    try:
        # Get upload info
        upload = await conn.fetchrow(
            """
            SELECT upload_id, ha_id, filename, file_type, status, metadata
            FROM upload_audit
            WHERE upload_id = $1
            """,
            upload_id,
        )

        if not upload:
            print(f"Upload {upload_id} not found")
            return 1

        print("=" * 70)
        print(f"Upload: {upload['filename']} ({upload['file_type']})")
        print(f"Status: {upload['status']}")
        print("=" * 70)

        # Get document_features
        doc_feat = await conn.fetchrow(
            """
            SELECT feature_id, document_type, extraction_method,
                   agentic_features_json, extraction_comparison_metadata,
                   features_json
            FROM document_features
            WHERE upload_id = $1
            """,
            upload_id,
        )

        if not doc_feat:
            print("\nNo document_features found. Extraction may not have completed yet.")
            return 0

        print(f"\nFeature ID: {doc_feat['feature_id']}")
        print(f"Extraction Method: {doc_feat['extraction_method'] or 'regex'}")

        # Show comparison metadata
        if doc_feat["extraction_comparison_metadata"]:
            comp = doc_feat["extraction_comparison_metadata"]
            if isinstance(comp, str):
                comp = json.loads(comp)
            print("\n" + "=" * 70)
            print("EXTRACTION COMPARISON")
            print("=" * 70)
            print(f"Agreement Score: {comp.get('agreement_score', 'N/A')}")
            discrepancies = comp.get("discrepancies", [])
            if discrepancies:
                print(f"\nDiscrepancies ({len(discrepancies)}):")
                for d in discrepancies:
                    print(f"  - {d.get('field')}:")
                    print(f"    Regex:   {d.get('regex_value')}")
                    print(f"    Agentic: {d.get('agentic_value')}")
                    print(f"    Score:   {d.get('score')}")
            else:
                print("No discrepancies found")

        # Show agentic features summary
        if doc_feat["agentic_features_json"]:
            agentic = doc_feat["agentic_features_json"]
            if isinstance(agentic, str):
                agentic = json.loads(agentic)

            print("\n" + "=" * 70)
            print("AGENTIC FEATURES (Category A + B)")
            print("=" * 70)

            # High-rise indicators
            hr = agentic.get("high_rise_indicators", {})
            if hr.get("high_rise_building_mentioned"):
                print("\nHigh-Rise Indicators:")
                print(f"  Building Height Category: {hr.get('building_height_category')}")
                print(f"  Number of Storeys: {hr.get('number_of_storeys')}")
                print(f"  BSA Applicable: {hr.get('building_safety_act_applicable')}")

            # Evacuation strategy
            evac = agentic.get("evacuation_strategy", {})
            if evac.get("evacuation_strategy_mentioned"):
                print("\nEvacuation Strategy:")
                print(f"  Type: {evac.get('evacuation_strategy_type')}")
                print(f"  Description: {evac.get('evacuation_strategy_description', '')[:100]}...")

            # Fire safety measures
            fire = agentic.get("fire_safety_measures", {})
            if fire.get("fire_safety_measures_mentioned"):
                print("\nFire Safety Measures:")
                print(f"  Fire Doors Mentioned: {fire.get('fire_doors_mentioned')}")
                print(f"  Fire Safety Officers: {fire.get('fire_safety_officers_mentioned')}")

            # Building Safety Act
            bsa = agentic.get("building_safety_act_2022", {})
            if bsa.get("building_safety_act_2022_mentioned"):
                print("\nBuilding Safety Act 2022:")
                print(f"  Compliance Status: {bsa.get('building_safety_act_compliance_status')}")
                print(f"  Part 4 Duties: {bsa.get('part_4_duties_mentioned')}")

            # MOR
            mor = agentic.get("mandatory_occurrence_reports", {})
            if mor.get("mandatory_occurrence_report_mentioned"):
                print("\nMandatory Occurrence Reports:")
                mors = mor.get("mandatory_occurrence_reports", [])
                print(f"  Count: {len(mors)}")

        # Show building_safety_features table
        bsf = await conn.fetchrow(
            """
            SELECT high_rise_building_mentioned, evacuation_strategy_type,
                   fire_safety_measures_mentioned, building_safety_act_2022_mentioned,
                   extraction_method, agentic_confidence_score
            FROM building_safety_features
            WHERE upload_id = $1
            """,
            upload_id,
        )

        if bsf:
            print("\n" + "=" * 70)
            print("BUILDING SAFETY FEATURES (Normalized Table)")
            print("=" * 70)
            print(f"High-Rise Mentioned: {bsf['high_rise_building_mentioned']}")
            print(f"Evacuation Strategy: {bsf['evacuation_strategy_type']}")
            print(f"Fire Safety Mentioned: {bsf['fire_safety_measures_mentioned']}")
            print(f"BSA 2022 Mentioned: {bsf['building_safety_act_2022_mentioned']}")
            print(f"Extraction Method: {bsf['extraction_method']}")
            if bsf["agentic_confidence_score"]:
                print(f"Agentic Confidence: {bsf['agentic_confidence_score']:.2f}")

        # Show regex features (from features_json)
        if doc_feat["features_json"]:
            features = doc_feat["features_json"]
            if isinstance(features, str):
                features = json.loads(features)

            regex_features = features.get("features", {})
            if regex_features:
                print("\n" + "=" * 70)
                print("REGEX FEATURES (from features_json)")
                print("=" * 70)

                # Document-specific
                if upload["file_type"] == "fra_document" and "fra_specific" in regex_features:
                    fra = regex_features["fra_specific"]
                    print(f"Overall Risk Rating: {fra.get('overall_risk_rating')}")
                    print(f"Evacuation Strategy: {fra.get('evacuation_strategy')}")
                    print(f"Building Name: {fra.get('building_name')}")

                if upload["file_type"] == "fraew_document" and "fraew_specific" in regex_features:
                    fraew = regex_features["fraew_specific"]
                    print(f"PAS 9980 Compliant: {fraew.get('pas_9980_compliant')}")
                    print(f"Building Risk Rating: {fraew.get('building_risk_rating')}")

        print("\n" + "=" * 70)
        print("Full JSON available in:")
        print(f"  - document_features.features_json (regex)")
        print(f"  - document_features.agentic_features_json (agentic)")
        print(f"  - building_safety_features.agentic_features_json (normalized)")
        print("=" * 70)

    finally:
        await conn.close()

    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_agentic_results.py <upload_id>")
        print("\nExample:")
        print("  python scripts/check_agentic_results.py 426e54ac-2a10-4407-9e06-e9b4544f1f92")
        sys.exit(1)

    sys.exit(asyncio.run(check_results(sys.argv[1])))
