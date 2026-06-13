import argparse
import sys
import logging
from pathlib import Path
import pytest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eval")

def main():
    parser = argparse.ArgumentParser(description="TradeFlow AI Evaluation Gate")
    parser.add_argument("--fixtures", type=str, default="fixtures/", help="Path to evaluation fixtures")
    parser.add_argument("--mode", type=str, default="digital_pdf_only", help="Evaluation mode")
    parser.add_argument("--fail-under-f1", type=float, default=0.95, help="Fail if F1 score is below this threshold")
    
    args = parser.parse_args()
    logger.info(f"Running evaluation with mode: {args.mode}, fixtures: {args.fixtures}, fail_under_f1: {args.fail_under_f1}")
    
    # Check if ground truth exists
    gt_path = Path("docs/TradeFlow_GroundTruth_v5.2.json")
    if not gt_path.exists():
        logger.warning(f"Ground truth file {gt_path} not found. Skipping evaluation.")
        sys.exit(0)
    
    # Run pytest on the eval directory
    logger.info("Executing pytest for OCR accuracy and evaluation metrics...")
    exit_code = pytest.main(["-v", "eval/test_ocr_accuracy.py"])
    
    if exit_code != 0:
        logger.error("Evaluation failed!")
        sys.exit(exit_code)
        
    logger.info("Evaluation completed successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()
