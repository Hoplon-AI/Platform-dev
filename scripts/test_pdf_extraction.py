#!/usr/bin/env python3
"""
Test PDF extraction for a single file to debug why features aren't being extracted.
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.core.pdf_extraction.pdf_pipeline import build_pdf_artifacts

# Test file
test_file = project_root / "data" / "fraew" / "Fire risk appraisal of external walls for Elizabeth Court.pdf"

if not test_file.exists():
    print(f"Test file not found: {test_file}")
    sys.exit(1)

print(f"Testing PDF extraction for: {test_file.name}")
print(f"File size: {test_file.stat().st_size / (1024*1024):.2f} MB")
print("=" * 60)

try:
    with open(test_file, "rb") as f:
        file_bytes = f.read()
    
    print("Building PDF artifacts...")
    artifacts = build_pdf_artifacts(
        file_bytes,
        file_type="fraew_document",
        filename=test_file.name,
    )
    
    print("\n✅ Extraction successful!")
    print(f"  Scanned: {artifacts.extraction.get('scanned', False)}")
    print(f"  Pages: {len(artifacts.extraction.get('pages', []))}")
    print(f"  Features extracted: {bool(artifacts.features.get('features'))}")
    
    if artifacts.features.get('features'):
        features = artifacts.features['features']
        print(f"\n  Extracted features:")
        if 'fraew_specific' in features:
            fraew = features['fraew_specific']
            print(f"    - Building name: {fraew.get('building_name', 'N/A')}")
            print(f"    - Risk rating: {fraew.get('building_risk_rating', 'N/A')}")
            print(f"    - PAS 9980 compliant: {fraew.get('pas_9980_compliant', 'N/A')}")
        
        if 'uprns' in features:
            print(f"    - UPRNs: {features['uprns']}")
        if 'postcodes' in features:
            print(f"    - Postcodes: {features['postcodes']}")
        if 'dates' in features:
            print(f"    - Dates: {features['dates']}")
    
    print("\n" + "=" * 60)
    print("Extraction test complete!")
    
except Exception as e:
    print(f"\n❌ Extraction failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
