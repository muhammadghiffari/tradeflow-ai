"""
Tests for AI node error handling
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai.nodes.extract import llm_extraction_node
from src.ai.state import ExtractionGraphState


@pytest.mark.asyncio
async def test_extraction_node_handles_missing_doc_fields():
    """Test that extraction node validates required document fields."""
    state = ExtractionGraphState(
        batch_id="test-batch",
        documents=[
            {
                "doc_id": "doc-1",
                # Missing 'pages' field
                "storage_path": "s3://bucket/doc.pdf"
            }
        ]
    )

    result = await llm_extraction_node(state)

    # Should mark document as error instead of crashing
    assert len(result["documents"]) == 1
    assert "error" in result["documents"][0]
    assert result["documents"][0].get("fallback_required") is True


@pytest.mark.asyncio
async def test_extraction_node_handles_empty_documents():
    """Test that extraction node handles empty document list."""
    state = ExtractionGraphState(
        batch_id="test-batch",
        documents=[]
    )

    result = await llm_extraction_node(state)

    # Should return gracefully with no documents
    assert result["documents"] == []
    assert result["combined_data"] == {}


@pytest.mark.asyncio
async def test_extraction_node_specific_exception_handling():
    """Test that extraction node catches only specific exceptions."""
    state = ExtractionGraphState(
        batch_id="test-batch",
        documents=[
            {
                "doc_id": "doc-1",
                "pages": ["base64-encoded-image"],
                "storage_path": "s3://bucket/doc.pdf"
            }
        ]
    )

    # Mock LLM to raise ValueError (expected)
    with patch("src.ai.nodes.extract.ChatGoogleGenerativeAI") as mock_llm:
        mock_instance = MagicMock()
        structured_llm = AsyncMock()
        structured_llm.ainvoke = AsyncMock(side_effect=ValueError("Malformed input"))
        mock_instance.with_structured_output.return_value = structured_llm
        mock_llm.return_value = mock_instance

        result = await llm_extraction_node(state)

        # Should handle ValueError gracefully
        assert len(result["documents"]) == 1
        assert "error" in result["documents"][0]


@pytest.mark.asyncio
async def test_extraction_node_reraises_unknown_exceptions():
    """Test that extraction node re-raises unexpected exceptions."""
    state = ExtractionGraphState(
        batch_id="test-batch",
        documents=[
            {
                "doc_id": "doc-1",
                "pages": ["base64-encoded-image"],
                "storage_path": "s3://bucket/doc.pdf"
            }
        ]
    )

    # Mock LLM to raise unexpected exception
    with patch("src.ai.nodes.extract.ChatGoogleGenerativeAI") as mock_llm:
        mock_instance = MagicMock()
        structured_llm = AsyncMock()
        structured_llm.ainvoke = AsyncMock(side_effect=RuntimeError("Unexpected API error"))
        mock_instance.with_structured_output.return_value = structured_llm
        mock_llm.return_value = mock_instance

        # Should re-raise the unexpected exception
        with pytest.raises(RuntimeError, match="Unexpected API error"):
            await llm_extraction_node(state)


@pytest.mark.asyncio
async def test_extraction_node_combines_data_correctly():
    """Test that extraction node correctly combines data from multiple docs."""
    state = ExtractionGraphState(
        batch_id="test-batch",
        documents=[
            {
                "doc_id": "doc-1",
                "pages": ["page1"],
                "storage_path": "s3://bucket/doc1.pdf"
            },
            {
                "doc_id": "doc-2",
                "pages": ["page2"],
                "storage_path": "s3://bucket/doc2.pdf"
            }
        ]
    )

    # Mock LLM responses
    with patch("src.ai.nodes.extract.ChatGoogleGenerativeAI") as mock_llm:
        mock_instance = MagicMock()
        structured_llm = AsyncMock()

        # Return different data for each document
        responses = [
            MagicMock(model_dump=MagicMock(return_value={"importer_name": "Company A", "cif_value": 1000})),
            MagicMock(model_dump=MagicMock(return_value={"importer_name": "Company B", "cif_value": 2000}))
        ]
        structured_llm.ainvoke = AsyncMock(side_effect=responses)

        mock_instance.with_structured_output.return_value = structured_llm
        mock_llm.return_value = mock_instance

        result = await llm_extraction_node(state)

        # Combined data should have the last writer's value
        assert result["combined_data"]["importer_name"] == "Company B"
        assert result["combined_data"]["cif_value"] == 2000
