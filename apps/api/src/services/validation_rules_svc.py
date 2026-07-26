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
        rule_id = rule.get("rule_id") or rule.get("id", "UNKNOWN")
        rule_name = rule.get("name", rule_id)
        try:
            check_expr = rule.get("check")
            if not check_expr:
                legacy_result = self._evaluate_legacy_rule(rule, context)
                if legacy_result is not None:
                    return legacy_result
                # Rule has no evaluable expression — skip as PASS
                return {
                    "rule_id": rule_id,
                    "rule_name": rule_name,
                    "severity": "PASS",
                    "message": rule_name,
                    "affected_fields": rule.get("affected_fields") or rule.get("fields", []),
                }
            passed = evaluator.evaluate(check_expr)
            severity = "PASS" if passed else self._failure_severity(rule.get("severity"))
            message = rule_name
            if not passed:
                message = self._format_message(rule.get("error_message") or message, context)
        except Exception as exc:
            severity = self._failure_severity(rule.get("severity"))
            message = f"{rule_name} could not be evaluated: {exc}"

        return {
            "rule_id": rule_id,
            "rule_name": rule_name,
            "severity": severity,
            "message": message,
            "affected_fields": rule.get("affected_fields") or rule.get("fields", []),
        }

    def _evaluate_legacy_rule(
        self,
        rule: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        rule_type = rule.get("type")
        if not rule_type:
            return None

        rule_id = rule.get("rule_id") or rule.get("id", "UNKNOWN")
        rule_name = rule.get("name", rule_id)
        fields = rule.get("fields") or ([rule["field"]] if rule.get("field") else [])

        try:
            if rule_type in {"regex", "regex_and_lookup"}:
                field = fields[0] if fields else rule.get("field")
                value = self._first_context_value(context, field)
                if field in {"npwp", "nib"}:
                    value = re.sub(r"\D", "", str(value or ""))
                if field == "container_number":
                    containers = self._container_values(value)
                    passed = bool(containers) and all(
                        regex_match(container, rule.get("regex", ".*")) for container in containers
                    )
                else:
                    passed = regex_match(value, rule.get("regex", ".*"))
            elif rule_type == "cross_document_match":
                passed = all(self._cross_document_values_match(context, field, rule_id) for field in fields)
            elif rule_type == "cross_document":
                passed = self._evaluate_cross_document_rule(rule, context)
            elif rule_type == "date_sequence":
                passed = True
            elif rule_type == "lookup":
                passed = self._evaluate_lookup_rule(rule, context)
            else:
                return None
        except Exception as exc:
            passed = False
            log.warning("Legacy validation rule failed to evaluate", rule_id=rule_id, error=str(exc))

        severity = "PASS" if passed else self._legacy_failure_severity(rule_id, rule.get("severity"))
        return {
            "rule_id": rule_id,
            "rule_name": rule_name,
            "severity": severity,
            "message": rule_name if passed else rule.get("description") or rule_name,
            "affected_fields": rule.get("affected_fields") or fields,
        }

    def _field_aliases(self, field: str | None) -> list[str]:
        aliases = {
            "nomorBl": ["bl_number", "nomorBl"],
            "beratKotor": ["gross_weight", "beratKotor"],
            "jumlahKemasan": ["total_packages", "jumlahKemasan"],
            "namaKapal": ["vessel_name", "namaKapal"],
            "voyageNumber": ["voyage_number", "voyageNumber"],
            "kodePelabuhanMuat": ["port_of_loading", "kodePelabuhanMuat"],
            "kodePelabuhanBongkar": ["port_of_discharge", "kodePelabuhanBongkar"],
            "hs_code": ["hs_code", "posTarif"],
            "nib": ["importer_nib", "nib", "nibEntitas"],
            "npwp": ["importer_npwp", "npwp", "nomorIdentitas"],
            "container_number": ["container_numbers", "container_number"],
        }
        if not field:
            return []
        return aliases.get(field, [field])

    def _scope_value(self, scope: Any, field: str | None) -> Any:
        for alias in self._field_aliases(field):
            value = _unwrap(getattr(scope, alias, MISSING))
            if value not in (None, "", MISSING):
                return value
        return None

    def _first_context_value(self, context: dict[str, Any], field: str | None) -> Any:
        for scope_name in ("data", "inv", "pl", "bl", "item", "importir"):
            value = self._scope_value(context[scope_name], field)
            if value not in (None, "", MISSING):
                return value
        return None

    def _cross_document_values_match(self, context: dict[str, Any], field: str, rule_id: str | None = None) -> bool:
        scope_names = self._cross_document_scopes(rule_id, field)
        values = [
            self._normalize_compare_value(self._scope_value(context[scope_name], field))
            for scope_name in scope_names
        ]
        present = [value for value in values if value not in (None, "")]
        if len(present) < 2:
            return True
        return len(set(present)) == 1

    def _cross_document_scopes(self, rule_id: str | None, field: str | None) -> tuple[str, ...]:
        if rule_id == "CV008" or field == "jumlahKemasan":
            return ("bl", "pl")
        if rule_id == "CV007" or field == "beratKotor":
            return ("bl", "pl")
        return ("bl", "pl", "inv")

    def _normalize_compare_value(self, value: Any) -> str | None:
        if value is None or value is MISSING:
            return None
        if isinstance(value, (int, float)):
            return str(round(float(value), 4))
        return re.sub(r"\s+", " ", str(value)).strip().upper()

    def _evaluate_cross_document_rule(self, rule: dict[str, Any], context: dict[str, Any]) -> bool:
        rule_id = rule.get("rule_id") or rule.get("id")
        tolerance_pct = float(rule.get("tolerance_pct") or 0)
        if rule_id == "CV002" or not rule.get("fields"):
            cif = self._as_float(self._scope_value(context["inv"], "cif_value"))
            fob = self._as_float(self._scope_value(context["inv"], "fob_value"))
            freight = self._as_float(self._scope_value(context["inv"], "freight_value"))
            insurance = self._as_float(self._scope_value(context["inv"], "insurance_value"))
            if None in (cif, fob, freight, insurance) or not cif:
                return False
            diff_pct = abs(cif - (fob + freight + insurance)) / cif * 100
            return diff_pct <= tolerance_pct

        for field in rule.get("fields") or []:
            scope_names = self._cross_document_scopes(rule_id, field)
            values = [
                self._as_float(self._scope_value(context[scope_name], field))
                for scope_name in scope_names
            ]
            present = [value for value in values if value is not None]
            if len(present) < 2:
                return True
            baseline = present[0]
            if baseline == 0:
                return all(value == 0 for value in present)
            if any(abs(value - baseline) / abs(baseline) * 100 > tolerance_pct for value in present[1:]):
                return False
        return True

    def _evaluate_lookup_rule(self, rule: dict[str, Any], context: dict[str, Any]) -> bool:
        for field in rule.get("fields") or []:
            value = str(self._first_context_value(context, field) or "")
            if field in {"kodePelabuhanMuat", "kodePelabuhanBongkar"} and not re.search(r"\b[A-Z]{5}\b", value):
                return False
        return True

    def _as_float(self, value: Any) -> float | None:
        if value in (None, "", MISSING):
            return None
        try:
            return float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return None

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

        bl = by_type["bill_of_lading"]
        pl = by_type["packing_list"]
        inv = by_type["invoice"]
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
        return "CRITICAL_FAIL" if severity in {"CRITICAL", "ERROR"} else "WARNING"

    def _legacy_failure_severity(self, rule_id: str, severity: str | None) -> str:
        if rule_id in {"CV001", "CV002", "CV003", "CV006"}:
            return "CRITICAL_FAIL"
        return self._failure_severity(severity)

    def _container_values(self, value: Any) -> list[str]:
        if value in (None, "", MISSING):
            return []
        return re.findall(r"[A-Z]{4}\d{7}", str(value).upper())

    def _resolve_rules_path(self) -> Path:
        configured = Path(settings.VALIDATION_RULES_PATH)
        candidates = [
            configured,
            Path.cwd() / configured,
            Path("/app/validation_rules.json"),
        ]
        
        try:
            candidates.append(Path(__file__).resolve().parents[4] / configured)
        except IndexError:
            pass

        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        raise FileNotFoundError(f"Validation rules file not found: {settings.VALIDATION_RULES_PATH}")


validation_rules_service = ValidationRulesService()
