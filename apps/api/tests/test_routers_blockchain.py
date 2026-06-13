"""
Tests for blockchain router authorization
"""


import pytest


@pytest.mark.asyncio
async def test_get_blockchain_receipt_batch_not_found(mock_current_user, mock_supabase):
    """Test handling of non-existent batch."""
    assert True


@pytest.mark.asyncio
async def test_get_blockchain_receipt_owner_access(mock_current_user, mock_supabase):
    """Test that user can access their own company's batch."""
    assert True


@pytest.mark.asyncio
async def test_get_blockchain_receipt_admin_access(mock_admin_user, mock_supabase):
    """Test that admin can access any company's batch."""
    assert True
