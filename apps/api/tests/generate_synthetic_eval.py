"""
TradeFlow AI — Synthetic Evaluation Dataset Generator (Phase 7)
"""

import json
import uuid
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "eval_data"

def generate_dataset():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    scenarios = []

    # Generate 15 synthetic datasets
    for i in range(1, 16):
        is_happy = i <= 8
        is_warning = 8 < i <= 12
        is_critical = i > 12

        scenario = {
            "dataset_id": f"eval-{i:03d}",
            "expected_hs_code": "8517.62.21" if is_happy else "8471.30.20",
            "expected_risk": "LOW" if is_happy else "MEDIUM" if is_warning else "CRITICAL",
            "documents": {
                "bill_of_lading": {
                    "doc_id": str(uuid.uuid4()),
                    "extracted_text_mock": f"B/L {i:04d} - PT MAJU BERSAMA - 50 Cartons - 1200 KG",
                    "package_count": 50 if not is_critical else 48, # Mismatch for critical
                },
                "packing_list": {
                    "doc_id": str(uuid.uuid4()),
                    "extracted_text_mock": f"PL {i:04d} - 50 Cartons - 1200 KG - Electronics",
                    "package_count": 50,
                },
                "invoice": {
                    "doc_id": str(uuid.uuid4()),
                    "extracted_text_mock": f"INV {i:04d} - 25000 USD - FOB",
                    "total_value": 25000,
                    "currency": "USD" if not is_warning else "IDR", # Warning for IDR mismatch context
                }
            }
        }
        scenarios.append(scenario)

    output_path = DATA_DIR / "synthetic_eval_set.json"
    with open(output_path, "w") as f:
        json.dump(scenarios, f, indent=2)

    print(f"Generated {len(scenarios)} synthetic evaluation scenarios at {output_path}")

if __name__ == "__main__":
    generate_dataset()
