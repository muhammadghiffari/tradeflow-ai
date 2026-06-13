"""
Deterministic LLM stub for deterministic E2E and tests.
Returns predictable CEISAFields outputs so the LangGraph flow is repeatable.
"""
from __future__ import annotations

import asyncio
from typing import Any
from pydantic import BaseModel


class DeterministicStructuredLLM:
    def __init__(self, model_schema: type[BaseModel]):
        self._schema = model_schema

    async def ainvoke(self, messages: Any):
        # Return a deterministic instance matching the pydantic output schema
        # Use simple fixed safe defaults; tests relying on presence of fields
        # can assert these exact values for determinism.
        data = {}
        # Pydantic v2 uses `model_fields`; v1 uses `__fields__` with different metadata
        schema_fields = getattr(self._schema, 'model_fields', None) or getattr(self._schema, '__fields__', {})
        for k, meta in schema_fields.items():
            # Determine annotation/type across pydantic versions
            if isinstance(meta, dict):
                ftype = meta.get('annotation')
            elif hasattr(meta, 'annotation'):
                ftype = getattr(meta, 'annotation')
            elif hasattr(meta, 'outer_type_'):
                ftype = getattr(meta, 'outer_type_')
            else:
                ftype = None

            # Provide reasonable deterministic defaults by common types
            if ftype is str or getattr(ftype, '__name__', '') == 'str':
                data[k] = f"det-{k}"
            elif ftype is int or getattr(ftype, '__name__', '') == 'int':
                data[k] = 1
            elif ftype is float or getattr(ftype, '__name__', '') == 'float':
                data[k] = 1.0
            else:
                data[k] = None

        # Create a pydantic model instance if possible
        try:
            return self._schema.model_validate(data) if hasattr(self._schema, 'model_validate') else self._schema(**data)
        except Exception:
            # Last resort: return raw dict
            return data


class DeterministicLLM:
    def __init__(self, *_, **__):
        pass

    def with_structured_output(self, schema: type[BaseModel]):
        return DeterministicStructuredLLM(schema)


# synchronous convenience factory
def create_deterministic_llm(*args, **kwargs):
    return DeterministicLLM()
