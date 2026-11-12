"""
run_etl.py — Orchestrator for Data Cleaning and Feature Engineering

Runs the pipeline sequentially:
1. Data Cleaning
2. Feature Engineering
"""

import os
import sys
import time

# Ensure imports work if executed from anywhere
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clean_data import clean_data
from engineer_features import engineer_features

def main():
    print("==================================================")
    print("   E-COMMERCE ETL PIPELINE")
    print("==================================================")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    raw_dir = os.path.join(base_dir, "data", "raw")
    processed_dir = os.path.join(base_dir, "data", "processed")
    analytics_dir = os.path.join(base_dir, "data", "analytics")
    
    t0 = time.time()
    
    # Step 1
    print("\n[STEP 1/2] Data Cleaning & Validation...")
    clean_data(raw_dir, processed_dir)
    
    # Step 2
    print("\n[STEP 2/2] Feature Engineering & Master Table Creation...")
    engineer_features(processed_dir, analytics_dir)
    
    t1 = time.time()
    print("\n==================================================")
    print(f"   ETL PIPELINE COMPLETE in {t1-t0:.2f}s")
    print("==================================================")

if __name__ == "__main__":
    main()
