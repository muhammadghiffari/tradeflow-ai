import time
import requests
import sys

def main():
    print("\n1. Uploading Document to Multi-Agent API (Auth Disabled)...")
    api_url = "http://127.0.0.1:8888/api/v1/batches"
    
    pdf_path = "eval/fixtures/Hapag Filled 1.pdf"
    try:
        files = {
            "files": ("Hapag Filled 1.pdf", open(pdf_path, "rb"), "application/pdf")
        }
    except FileNotFoundError:
        print(f"File not found: {pdf_path}")
        sys.exit(1)
        
    data_form = {
        "doc_types": ["bill_of_lading"]
    }
    
    resp = requests.post(api_url, files=files, data=data_form)
    if not resp.ok:
        print(f"Upload failed: {resp.text}")
        sys.exit(1)
        
    batch_id = resp.json()["batch_id"]
    print(f"Upload successful! Batch ID: {batch_id}")

    print("\n2. Polling extraction status (Agents are working in the background)...")
    while True:
        resp = requests.get(f"http://127.0.0.1:8888/api/v1/batches/{batch_id}")
        if not resp.ok:
            print(f"Poll failed: {resp.text}")
            sys.exit(1)
            
        data = resp.json()
        status = data["batch"]["status"]
        print(f"Current Status: {status}")
        
        if status in ["review_required", "review_complete", "rejected", "failed", "error", "accepted"]:
            print("\nExtraction Complete!")
            print("--- Extracted Fields ---")
            fields = data.get("extracted_fields", [])
            if not fields:
                print("No fields extracted or extraction failed.")
            for field in fields:
                print(f"- {field.get('field_name')}: {field.get('extracted_value')} (Confidence: {field.get('confidence_score')})")
            break
            
        time.sleep(5)

if __name__ == "__main__":
    main()
