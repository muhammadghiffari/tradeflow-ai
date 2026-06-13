# TradeFlow AI Test Suite

## Overview

Comprehensive test suite covering critical security and reliability fixes implemented in the audit remediation.

## Test Files

### `conftest.py`
Shared fixtures for all tests:
- `test_client`: FastAPI test client
- `mock_current_user`: Authenticated operator user
- `mock_admin_user`: Authenticated admin user  
- `mock_supabase`: Mocked Supabase AsyncClient
- Sample file bytes (PDF, PNG, malicious)

### `test_config.py`
Configuration and environment variable tests:
- ✅ `GEMINI_API_KEY` is required (not hardcoded)
- ✅ `GEMINI_API_KEY` must come from environment variable
- ✅ CORS origins are controlled (not wildcard)

### `test_routers_batches.py`
File upload validation tests:
- File magic number validation (detects spoofed files)
- File size limits (50MB max)
- MIME type validation
- Filename path traversal protection
- Batch creation with invalid files (rollback)
- Maximum 3 files per batch
- doc_types validation

### `test_routers_blockchain.py`
Authorization and access control tests:
- ✅ Authentication required for blockchain endpoints
- ✅ Users can only access their company's batches
- ✅ Admins can access any batch
- ✅ Non-existent batch handling
- ✅ Batch ownership verification

### `test_ai_nodes_extract.py`
AI node error handling tests:
- ✅ Validates required document fields (doc_id, pages)
- ✅ Handles empty document lists
- ✅ Catches only specific exceptions (ValueError, KeyError)
- ✅ Re-raises unexpected exceptions
- ✅ Correctly combines data from multiple documents

### `test_dependencies.py`
JWT and authentication tests:
- ✅ Keycloak JWKS cached with TTL (1 hour)
- ✅ JWKS refreshes after TTL expires
- ✅ HTTP errors in JWKS fetch are handled
- ✅ CurrentUser stores all required fields

### `test_storage_service.py`
Storage security tests:
- ✅ MinIO bucket created with private policy
- ✅ Bucket policy denies public access
- ✅ Existing buckets are handled correctly
- ✅ File upload paths are sanitized

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_config.py -v

# Run specific test
pytest tests/test_config.py::test_gemini_api_key_required -v
```

## Coverage Goals

Target: **70% code coverage** (as per pyproject.toml)

Current coverage baseline: 0% → Target: 70%+ after implementation

## Critical Security Tests (Must Pass)

1. **Config Tests** - Ensure API keys are not hardcoded
   ```bash
   pytest tests/test_config.py -v
   ```

2. **Authorization Tests** - Ensure cross-company access is blocked
   ```bash
   pytest tests/test_routers_blockchain.py::test_get_blockchain_receipt_requires_ownership -v
   ```

3. **File Validation Tests** - Ensure spoofed files are rejected
   ```bash
   pytest tests/test_routers_batches.py::test_file_magic_number_validation -v
   ```

4. **Error Handling Tests** - Ensure exceptions are properly caught
   ```bash
   pytest tests/test_ai_nodes_extract.py::test_extraction_node_reraises_unknown_exceptions -v
   ```

5. **Storage Security Tests** - Ensure bucket policy is private
   ```bash
   pytest tests/test_storage_service.py::test_minio_bucket_policy_denies_public_access -v
   ```

## Next Steps

1. **Implement missing test bodies** - The test structure is in place, implementation code needs to be added
2. **Add integration tests** - Test full pipeline (upload → extract → validate → blockchain)
3. **Add performance tests** - Ensure large file uploads are handled efficiently
4. **Add stress tests** - Test behavior under load (rate limiting, timeouts)
5. **CI/CD integration** - Add to GitHub Actions for automatic testing on PRs

## Integration Testing

- Integration tests are marked with `@pytest.mark.integration` and should run against real service instances.
- Use `docker-compose.integration.yml` to start the required local services: Redis, MinIO, and ChromaDB.
- Run integration tests with:

```bash
cd apps/api
.venv/bin/python -m pytest -m integration tests/integration -q
```

## Deterministic E2E Testing

When you want reliable end-to-end pipeline validation without external LLM variability, enable deterministic mode:

```bash
set DETERMINISTIC_E2E=1&&set RUN_KEYCLOAK=1&&set RUN_FULL_E2E=1&&python -m pytest tests/integration -q
```

The deterministic mode uses a stable LLM stub for `apps/api/src/ai/nodes/extract.py`, so the extraction and review flow can be validated without Gemini or other external model dependencies.

## Keycloak E2E Provisioning

The repo includes `scripts/keycloak/provision_e2e.py` to provision a Keycloak E2E client/user and emit a `.env.e2e` file with an `E2E_BEARER_TOKEN`.

```bash
set KEYCLOAK_SERVER_URL=http://localhost:8080
set KEYCLOAK_ADMIN=admin
set KEYCLOAK_ADMIN_PASSWORD=admin1234
python scripts\keycloak\provision_e2e.py
```

Then run the guarded auth/E2E tests:

```bash
set RUN_KEYCLOAK=1&&set RUN_FULL_E2E=1&&python -m pytest tests/integration -q
```

> The CI workflow `.github/workflows/e2e.yml` runs the full E2E flow with `DETERMINISTIC_E2E=1` so the test pipeline remains stable without requiring a live LLM.

## Notes

- All tests use `pytest` with `pytest-asyncio` for async support
- Tests use mocks to avoid external dependencies (Supabase, Gemini API)
- Tests follow AAA pattern: Arrange, Act, Assert
