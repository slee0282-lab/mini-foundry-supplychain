#!/usr/bin/env python3
"""Debug cold chain data from Neo4j vs CSV."""

import sys
import pandas as pd
sys.path.insert(0, 'src')

from data_loader import Neo4jConnection
from simulator import SupplyChainSimulator

# Initialize
neo4j = Neo4jConnection()
simulator = SupplyChainSimulator(neo4j)

print("=== Cold Chain DataFrame Info ===")
print(f"Total rows: {len(simulator.cold_chain_df)}")
print(f"\nColumns: {list(simulator.cold_chain_df.columns)}")
print(f"\nData types:\n{simulator.cold_chain_df.dtypes}")

if not simulator.cold_chain_df.empty:
    print("\n=== Excursion Flag Values ===")
    print(simulator.cold_chain_df['excursion_flag'].value_counts())

    print("\n=== Sample Data ===")
    print(simulator.cold_chain_df[['reading_id', 'shipment_id', 'temperature_c', 'excursion_flag', 'threshold_min_c', 'threshold_max_c']].head(15))

    print("\n=== Testing Excursion Detection ===")
    def is_excursion(row):
        flag = str(row.get('excursion_flag', '')).upper()
        print(f"Row {row.get('reading_id')}: flag='{flag}' (type: {type(row.get('excursion_flag'))})")
        if flag == 'YES':
            return True
        temp = row.get('temperature_c')
        min_t = row.get('threshold_min_c')
        max_t = row.get('threshold_max_c')
        if pd.notna(temp) and (pd.notna(min_t) and temp < min_t or pd.notna(max_t) and temp > max_t):
            return True
        return False

    # Test first 5 rows
    print("\nTesting first 5 rows:")
    for idx, row in simulator.cold_chain_df.head(5).iterrows():
        result = is_excursion(row)
        print(f"  -> Result: {result}")

    # Apply to all
    simulator.cold_chain_df['is_excursion'] = simulator.cold_chain_df.apply(is_excursion, axis=1)
    excursions = simulator.cold_chain_df[simulator.cold_chain_df['is_excursion'] == True]
    print(f"\n=== Total Excursions Detected: {len(excursions)} ===")

    if not excursions.empty:
        print(excursions[['reading_id', 'shipment_id', 'excursion_flag']].head(10))
else:
    print("⚠️  cold_chain_df is EMPTY!")

neo4j.close()
