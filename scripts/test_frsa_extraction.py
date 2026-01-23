#!/usr/bin/env python3
"""Test FRA feature extraction on sample PDF files."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from backend.core.pdf_extraction.pdf_pipeline import extract_fra_features, _extract_text_sample

# Test with sample FRA files (data/frsa directory contains FRA files)
fra_dir = Path(__file__).parent.parent / "data" / "frsa"
fra_files = list(fra_dir.glob("*.pdf"))

if not fra_files:
    print("No FRA files found")
    sys.exit(1)

# Test with the first file
test_file = fra_files[0]
print(f"Testing FRA feature extraction on: {test_file.name}")

with open(test_file, "rb") as f:
    file_bytes = f.read()

# Extract text sample
text_sample = _extract_text_sample(file_bytes, max_pages=15)
print(f"\nExtracted {len(text_sample)} characters of text")

# Extract FRA features
features = extract_fra_features(text_sample)

print("\nExtracted FRA Features:")
print("=" * 60)
for key, value in features.items():
    if value:
        print(f"{key}: {value}")

print("\n" + "=" * 60)
