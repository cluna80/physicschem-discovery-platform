# -*- coding: utf-8 -*-
import os
import json
import time

def check_progress():
    """Check screening progress"""
    if os.path.exists("hiv_screening_100.json"):
        with open("hiv_screening_100.json", 'r') as f:
            results = json.load(f)
        return len(results)
    return 0

print("="*60)
print("HIV SCREENING MONITOR")
print("="*60)

while True:
    completed = check_progress()
    print(f"\rProgress: {completed}/100 compounds screened", end="")
    
    if completed >= 100:
        print("\n\nScreening complete! Analyzing results...")
        break
    
    time.sleep(30)  # Check every 30 seconds
