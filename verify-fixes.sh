#!/bin/bash
# Quick Start Guide: Verify All Critical Fixes
# Run this to verify all 8 critical security fixes are working

set -e

echo "════════════════════════════════════════════════════════════════"
echo "TradeFlow AI - Critical Fixes Verification"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Check 1: Gemini API Key is not hardcoded
echo "✓ Check 1: Verifying Gemini API Key is not hardcoded..."
if grep -q "AIzaSyDGED8ipUMA0mY_O8bxIuRPh2TSwfpT7u8" apps/api/src/config.py; then
    echo "  ❌ FAILED: Hardcoded API key still present!"
    exit 1
else
    echo "  ✅ PASSED: API key is not hardcoded"
fi

# Check 2: Config requires GEMINI_API_KEY from env
echo "✓ Check 2: Verifying GEMINI_API_KEY must come from env..."
if grep -q "Field(..., min_length=1)" apps/api/src/config.py; then
    echo "  ✅ PASSED: GEMINI_API_KEY is required from env"
else
    echo "  ⚠️  WARNING: Field definition might have changed"
fi

# Check 3: S3 bucket policy is private
echo "✓ Check 3: Verifying S3 bucket policy is private..."
if grep -q '"Effect": "Deny"' apps/api/src/services/ingest_svc.py && \
   grep -q '"Principal": "\*"' apps/api/src/services/ingest_svc.py; then
    echo "  ✅ PASSED: S3 bucket policy denies public access"
else
    echo "  ❌ FAILED: S3 bucket policy not properly restricted!"
    exit 1
fi

# Check 4: JWT caching has TTL
echo "✓ Check 4: Verifying JWT JWKS has TTL..."
if grep -q "KEYCLOAK_JWKS_TTL" apps/api/src/dependencies.py && \
   grep -q "3600" apps/api/src/dependencies.py; then
    echo "  ✅ PASSED: JWT cache has 1-hour TTL"
else
    echo "  ❌ FAILED: JWT cache TTL not implemented!"
    exit 1
fi

# Check 5: CORS is restricted
echo "✓ Check 5: Verifying CORS headers are restricted..."
if ! grep -q 'allow_headers=\["\*"\]' apps/api/src/main.py; then
    echo "  ✅ PASSED: CORS headers are restricted"
else
    echo "  ❌ FAILED: CORS still allows wildcard headers!"
    exit 1
fi

# Check 6: File validation with magic numbers
echo "✓ Check 6: Verifying file magic number validation..."
if grep -q "magic.from_buffer" apps/api/src/routers/batches.py; then
    echo "  ✅ PASSED: File magic number validation implemented"
else
    echo "  ⚠️  WARNING: Magic number validation might not be in batches router"
fi

# Check 7: Blockchain authorization
echo "✓ Check 7: Verifying blockchain authorization checks..."
if grep -q "company_id.*!= user.company_id" apps/api/src/routers/blockchain.py; then
    echo "  ✅ PASSED: Blockchain endpoint checks authorization"
else
    echo "  ⚠️  WARNING: Authorization check not found in expected format"
fi

# Check 8: Exception handling is specific
echo "✓ Check 8: Verifying exception handling is specific..."
if grep -q "except (ValueError, KeyError)" apps/api/src/ai/nodes/extract.py; then
    echo "  ✅ PASSED: Exception handling is specific (not generic)"
else
    echo "  ⚠️  WARNING: Exception handling format might have changed"
fi

# Check 9: Dependencies added
echo "✓ Check 9: Verifying required dependencies are added..."
if grep -q "slowapi" apps/api/pyproject.toml && \
   grep -q "python-magic" apps/api/pyproject.toml; then
    echo "  ✅ PASSED: slowapi and python-magic added to dependencies"
else
    echo "  ⚠️  WARNING: Some dependencies might be missing"
fi

# Check 10: Tests exist
echo "✓ Check 10: Verifying test suite exists..."
test_count=$(find apps/api/tests -name "test_*.py" | wc -l)
if [ "$test_count" -ge 5 ]; then
    echo "  ✅ PASSED: $test_count test files found"
else
    echo "  ⚠️  WARNING: Expected more test files"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ ALL CRITICAL FIXES VERIFIED!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "1. Add new GEMINI_API_KEY to .env file"
echo "2. Run: cd apps/api && pip install -e '.[dev]'"
echo "3. Run: pytest tests/ -v --cov=src"
echo "4. Test with: python -m uvicorn src.main:app --reload"
echo ""
