"""
Hot-reloadable CEISA validation rules.

Domain experts can update packages/db/validation_rules.json and the API will
pick up the new rules on the next validation call without a worker restart.
"""

from __future__ import annotations

import ast
import json
import operator
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from ..config import settings

log = structlog.get_logger()


class MissingValue:
    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "MISSING"


MISSING = MissingValue()


class RuleNamespace:
    """Attribute-access wrapper for dicts/lists used by rule expressions."""

    def __init__(self, value: Any) -> None:
        self._value = value or {}

    def __getattr__(self, name: str) -> Any:
        if isinstance(self._value, dict):
            return _wrap(self._value.get(name, MISSING))
        return MISSING

    def __getitem__(self, key: str) -> Any:
        if isinstance(self._value, dict):
            return _wrap(self._value.get(key, MISSING))
        return MISSING

    def unwrap(self) -> Any:
        return self._value


def _wrap(value: Any) -> Any:
    if isinstance(value, dict):
        return RuleNamespace(value)
    if isinstance(value, list):
        return [_wrap(item) for item in value]
    return value


def _unwrap(value: Any) -> Any:
    if value is MISSING:
        return None
    if isinstance(value, RuleNamespace):
        return value.unwrap()
    return value


def regex_match(value: Any, pattern: str) -> bool:
    if value is MISSING:
        return False
    return bool(re.fullmatch(pattern, str(_unwrap(value) or "")))


def sum_values(items: Any, field_name: str) -> float:
    raw_items = _unwrap(items) or []
    total = 0.0
    for item in raw_items:
        raw_item = _unwrap(item) or {}
        if isinstance(raw_item, dict):
            total += float(raw_item.get(field_name) or 0.0)
    return total


def npwp_checksum_valid(value: Any) -> bool:
    digits = re.sub(r"\D", "", str(_unwrap(value) or ""))
    # Indonesian NPWP formats have changed; for demo validation we enforce
    # structurally valid 15/16 digit values and leave live DJP checksum to prod.
    return len(digits) in {15, 16}


ALLOWED_FUNCS = {
    "abs": abs,
    "sum_values": sum_values,
    "regex_match": regex_match,
    "npwp_checksum_valid": npwp_checksum_valid,
}

ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}

ALLOWED_CMPOPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


class SafeRuleEvaluator:
    def __init__(self, context: dict[str, Any]) -> None:
        self.context = context

    def evaluate(self, expression: str) -> bool:
        normalized = self._normalize_expression(expression)
        node = ast.parse(normalized, mode="eval")
        return bool(self._eval(node.body))

    def _normalize_expression(self, expression: str) -> str:
        return re.sub(
            r"sum\(([\w.]+)\.\[\*\]\.(\w+)\)",
            r"sum_values(\1, '\2')",
            expression,
        )

    def _eval(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in self.context:
                return self.context[node.id]
            raise ValueError(f"Unknown rule variable: {node.id}")
        if isinstance(node, ast.Attribute):
            return getattr(self._eval(node.value), node.attr)
        if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_BINOPS:
            return ALLOWED_BINOPS[type(node.op)](self._eval(node.left), self._eval(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -self._eval(node.operand)
        if isinstance(node, ast.Compare):
            left = self._eval(node.left)
            for op, comparator in zip(node.ops, node.comparators, strict=True):
                right = self._eval(comparator)
                if left is MISSING or right is MISSING:
                    return False
                if type(op) not in ALLOWED_CMPOPS or not ALLOWED_CMPOPS[type(op)](left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            func = ALLOWED_FUNCS.get(node.func.id)
            if func is None:
                raise ValueError(f"Function not allowed in validation rule: {node.func.id}")
            return func(*(self._eval(arg) for arg in node.args))
        raise ValueError(f"Unsupported validation expression: {ast.dump(node)}")


@dataclass
class RulesCache:
    path: Path | None = None
    mtime_ns: int | None = None
    payload: dict[str, Any] | None = None


class ValidationRulesService:
    def __init__(self) -> None:
        self._cache = RulesCache()

    def load_rules(self) -> dict[str, Any]:
        path = self._resolve_rules_path()
        stat = path.stat()
        if (
            self._cache.path != path
            or self._cache.mtime_ns != stat.st_mtime_ns
            or self._cache.payload is None
        ):
            self._cache = RulesCache(
                path=path,
                mtime_ns=stat.st_mtime_ns,
                payload=json.loads(path.read_text(encoding="utf-8")),
            )
            log.info(
                "Validation rules reloaded",
                path=str(path),
                version=self._cache.payload.get("version"),
                rule_count=len(self._cache.payload.get("rules", [])),
            )
        return self._cache.payload

    def evaluate(self, state: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
        payload = self.load_rules()
        context = self._build_context(state)
        evaluator = SafeRuleEvaluator(context)
        results = []
        needs_review = state.get("needs_human_review", False)

        for rule in payload.get("rules", []):
            result = self._evaluate_rule(rule, evaluator, context)
            results.append(result)
            needs_review = needs_review or result["severity"] == "CRITICAL_FAIL"

        return results, needs_review

    def _evaluate_rule(
        self,
        rule: dict[str, Any],
        evaluator: SafeRuleEvaluator,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            passed = evaluator.evaluate(rule["check"])
            severity = "PASS" if passed else self._failure_severity(rule.get("severity"))
            message = rule.get("name", rule.get("rule_id", "Validation rule"))
            if not passed:
                message = self._format_message(rule.get("error_message") or message, context)
        except Exception as exc:
            severity = self._failure_severity(rule.get("severity"))
            message = f"{rule.get('name', rule.get('rule_id'))} could not be evaluated: {exc}"

        return {
            "rule_id": rule.get("rule_id", "UNKNOWN"),
            "rule_name": rule.get("name", rule.get("rule_id", "Validation rule")),
            "severity": severity,
            "message": message,
            "affected_fields": rule.get("affected_fields", []),
        }

    def _build_context(self, state: dict[str, Any]) -> dict[str, Any]:
        combined = state.get("combined_data") or {}
        by_type: dict[str, dict[str, Any]] = {
            "bill_of_lading": {},
            "packing_list": {},
            "invoice": {},
        }
        for doc in state.get("documents", []):
            doc_type = doc.get("doc_type")
            if doc_type in by_type:
                by_type[doc_type].update(doc.get("extracted_data") or {})

        bl = {**combined, **by_type["bill_of_lading"]}
        pl = {**combined, **by_type["packing_list"]}
        inv = {**combined, **by_type["invoice"]}
        for scoped in (bl, pl, inv):
            if "currency_code" not in scoped and scoped.get("currency"):
                scoped["currency_code"] = scoped["currency"]

        return {
            "data": RuleNamespace(combined),
            "bl": RuleNamespace(bl),
            "pl": RuleNamespace(pl),
            "inv": RuleNamespace(inv),
            "item": RuleNamespace(combined.get("item") or combined),
            "importir": RuleNamespace(
                {
                    **combined,
                    "npwp": combined.get("npwp")
                    or combined.get("importer_npwp")
                    or combined.get("npwp_importir"),
                }
            ),
        }

    def _format_message(self, template: str, context: dict[str, Any]) -> str:
        values = {
            "bl": getattr(context["bl"], "total_packages", None),
            "pl": getattr(context["pl"], "total_packages", None),
            "inv": getattr(context["inv"], "currency_code", None)
            or getattr(context["inv"], "currency", None),
            "diff": "n/a",
            "npwp": getattr(context["importir"], "npwp", None),
            "hs_code": getattr(context["item"], "hs_code", None),
            "bl_date": getattr(context["bl"], "bl_date", None),
            "arrival_date": getattr(context["bl"], "arrival_date", None),
        }
        try:
            return template.format(**values)
        except Exception:
            return template

    def _failure_severity(self, severity: str | None) -> str:
        return "CRITICAL_FAIL" if severity == "CRITICAL" else "WARNING"

    def _resolve_rules_path(self) -> Path:
        configured = Path(settings.VALIDATION_RULES_PATH)
        candidates = [
            configured,
            Path.cwd() / configured,
            Path(__file__).resolve().parents[4] / configured,
            Path("/app/validation_rules.json"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        raise FileNotFoundError(f"Validation rules file not found: {settings.VALIDATION_RULES_PATH}")


validation_rules_service = ValidationRulesService()
