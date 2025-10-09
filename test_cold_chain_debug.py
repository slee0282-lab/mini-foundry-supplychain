#!/usr/bin/env python3
"""Debug cold chain excursion detection."""

import sys
import pandas as pd
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

# Load cold chain data
csv_path = Path('data/pilot_missing_supporting_files/cold_chain_readings.csv')
print(f"Loading from: {csv_path}")
print(f"File exists: {csv_path.exists()}")
print()

if csv_path.exists():
    df = pd.read_csv(csv_path)
    print(f"Total rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    print()

    # Check excursion_flag values
    print("=== Excursion Flag Distribution ===")
    print(df['excursion_flag'].value_counts())
    print()

    # Test the is_excursion logic
    def is_excursion(row):
        flag = str(row.get('excursion_flag', '')).upper()
        if flag == 'YES':
            return True
        temp = row.get('temperature_c')
        min_t = row.get('threshold_min_c')
        max_t = row.get('threshold_max_c')
        if pd.notna(temp) and (pd.notna(min_t) and temp < min_t or pd.notna(max_t) and temp > max_t):
            return True
        return False

    df['is_excursion'] = df.apply(is_excursion, axis=1)
    excursion_df = df[df['is_excursion'] == True]

    print(f"=== Excursion Detection Results ===")
    print(f"Excursions detected: {len(excursion_df)}")
    print()

    if not excursion_df.empty:
        print("=== Sample Excursions ===")
        print(excursion_df[['reading_id', 'shipment_id', 'temperature_c', 'threshold_min_c', 'threshold_max_c', 'excursion_flag']].head(10))
        print()

        print("=== Shipments with Excursions ===")
        impacted_shipments = excursion_df['shipment_id'].dropna().unique().tolist()
        print(f"Impacted shipments: {impacted_shipments}")
    else:
        print("⚠️  NO EXCURSIONS DETECTED!")
        print("\nShowing first few rows of raw data:")
        print(df[['reading_id', 'shipment_id', 'temperature_c', 'excursion_flag']].head(15))
else:
    print("❌ CSV file not found!")
