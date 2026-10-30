"""Small, dependency-free JSON Schema (draft-07 subset) validator.

The port validator must run on a clean Windows/Linux CI image without pip
install. This module implements the keywords used by Docs/Contracts/schemas:
$ref (local), type, enum, const, required, properties, patternProperties,
additionalProperties, items, min/max items, uniqueItems, min/max length,
pattern, numeric bounds, allOf/anyOf/oneOf/not, and dependencies.

It is intentionally not a complete JSON Schema implementation. Unknown
keywords are ignored, which matches the "additive changes only" policy for the
v1 contracts.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable


class SchemaError(RuntimeError):
    """Raised when a schema file itself cannot be loaded or resolved."""


_TYPE_CHECKS = {
    "null": lambda v: v is None,
    "boolean": lambda v: isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "string": lambda v: isinstance(v, str),
}


def load_schema(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as fh:
            schema = json.load(fh)
    except FileNotFoundError as exc:
        raise SchemaError(f"schema not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SchemaError(f"invalid schema JSON {path}: {exc}") from exc
    if not isinstance(schema, dict):
        raise SchemaError(f"schema must be an object: {path}")
    return schema


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__


def _matches_type(value: Any, expected: str) -> bool:
    check = _TYPE_CHECKS.get(expected)
    if check is None:
        return True
    return bool(check(value))


def _join(path: str, key: str) -> str:
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
        return f"{path}.{key}"
    return f"{path}[{key!r}]"


def _resolve_pointer(root: Any, pointer: str) -> Any:
    if pointer in ("", "/"):
        return root
    if not pointer.startswith("/"):
        raise SchemaError(f"unsupported $ref pointer: {pointer}")
    node = root
    for raw in pointer.lstrip("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list):
            try:
                node = node[int(token)]
            except (ValueError, IndexError) as exc:
                raise SchemaError(f"bad $ref array index {token!r}") from exc
        elif isinstance(node, dict):
            if token not in node:
                raise SchemaError(f"bad $ref key {token!r}")
            node = node[token]
        else:
            raise SchemaError(f"cannot descend $ref at {token!r}")
    return node


def _resolve_ref(ref: str, root: Any) -> Any:
    if not isinstance(ref, str):
        raise SchemaError("$ref must be a string")
    if ref.startswith("#"):
        return _resolve_pointer(root, ref[1:])
    raise SchemaError(f"external $ref is not supported: {ref}")


def _json_equivalent(a: Any, b: Any) -> bool:
    try:
        return json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(
            b, sort_keys=True, ensure_ascii=False
        )
    except (TypeError, ValueError):
        return a == b


def _validate(
    value: Any,
    schema: Any,
    path: str,
    root: Any,
    errors: list[str],
    depth: int,
) -> None:
    if depth > 64:
        errors.append(f"{path}: schema recursion limit exceeded")
        return
    if schema is True or schema is None:
        return
    if schema is False:
        errors.append(f"{path}: not allowed")
        return
    if not isinstance(schema, dict):
        errors.append(f"{path}: invalid schema node ({type(schema).__name__})")
        return

    if "$ref" in schema:
        _validate(value, _resolve_ref(schema["$ref"], root), path, root, errors, depth + 1)
        return

    expected = schema.get("type")
    if expected is not None:
        allowed = expected if isinstance(expected, list) else [expected]
        if not any(_matches_type(value, t) for t in allowed):
            errors.append(
                f"{path}: expected {'/'.join(str(t) for t in allowed)}, got {_type_name(value)}"
            )
            return

    if "const" in schema and not _json_equivalent(value, schema["const"]):
        errors.append(f"{path}: must equal {schema['const']!r}")

    if "enum" in schema:
        enum = schema["enum"]
        if isinstance(enum, list) and not any(_json_equivalent(value, item) for item in enum):
            errors.append(f"{path}: value {value!r} is not one of {enum!r}")

    if isinstance(value, dict):
        _validate_object(value, schema, path, root, errors, depth)
    elif isinstance(value, list):
        _validate_array(value, schema, path, root, errors, depth)
    elif isinstance(value, str):
        _validate_string(value, schema, path, errors)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        _validate_number(value, schema, path, errors)

    for key in ("allOf", "anyOf", "oneOf"):
        if key not in schema:
            continue
        subschemas = schema[key]
        if not isinstance(subschemas, list):
            errors.append(f"{path}: {key} must be an array")
            continue
        if key == "allOf":
            for sub in subschemas:
                _validate(value, sub, path, root, errors, depth + 1)
            continue

        valid: list[tuple[Any, list[str]]] = []
        for sub in subschemas:
            sub_errors: list[str] = []
            _validate(value, sub, path, root, sub_errors, depth + 1)
            if not sub_errors:
                valid.append((sub, []))
        if key == "anyOf":
            if not valid:
                errors.append(f"{path}: does not match any allowed shape (anyOf)")
        elif len(valid) == 0:
            errors.append(f"{path}: does not match any allowed shape (oneOf)")
        elif len(valid) > 1:
            errors.append(f"{path}: matches more than one exclusive shape (oneOf)")

    if "not" in schema:
        sub_errors: list[str] = []
        _validate(value, schema["not"], path, root, sub_errors, depth + 1)
        if not sub_errors:
            errors.append(f"{path}: must not match the 'not' schema")

    if "if" in schema:
        condition_errors: list[str] = []
        _validate(value, schema["if"], path, root, condition_errors, depth + 1)
        if not condition_errors and "then" in schema:
            _validate(value, schema["then"], path, root, errors, depth + 1)
        if condition_errors and "else" in schema:
            _validate(value, schema["else"], path, root, errors, depth + 1)


def _validate_object(
    value: dict,
    schema: dict,
    path: str,
    root: Any,
    errors: list[str],
    depth: int,
) -> None:
    required = schema.get("required", [])
    if isinstance(required, list):
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required field {key!r}")

    if "minProperties" in schema and len(value) < schema["minProperties"]:
        errors.append(f"{path}: expected at least {schema['minProperties']} properties")
    if "maxProperties" in schema and len(value) > schema["maxProperties"]:
        errors.append(f"{path}: expected at most {schema['maxProperties']} properties")

    properties = schema.get("properties", {})
    pattern_properties = schema.get("patternProperties", {})
    additional = schema.get("additionalProperties", True)
    property_names = schema.get("propertyNames")

    for key, item in value.items():
        child = _join(path, str(key))
        matched = False
        if isinstance(properties, dict) and key in properties:
            matched = True
            _validate(item, properties[key], child, root, errors, depth + 1)
        if isinstance(pattern_properties, dict):
            for pattern, subschema in pattern_properties.items():
                try:
                    if re.search(pattern, str(key)):
                        matched = True
                        _validate(item, subschema, child, root, errors, depth + 1)
                except re.error as exc:
                    errors.append(f"{path}: bad patternProperties regex {pattern!r}: {exc}")
        if not matched:
            if additional is False:
                errors.append(f"{path}: unexpected property {key!r}")
            elif isinstance(additional, dict):
                _validate(item, additional, child, root, errors, depth + 1)
        if isinstance(property_names, dict):
            _validate(str(key), property_names, child, root, errors, depth + 1)

    dependencies = schema.get("dependencies", {})
    if isinstance(dependencies, dict):
        for key, dependency in dependencies.items():
            if key not in value:
                continue
            if isinstance(dependency, list):
                for other in dependency:
                    if other not in value:
                        errors.append(f"{path}: field {key!r} requires {other!r}")
            elif isinstance(dependency, dict):
                _validate(value, dependency, path, root, errors, depth + 1)


def _validate_array(
    value: list,
    schema: dict,
    path: str,
    root: Any,
    errors: list[str],
    depth: int,
) -> None:
    if "minItems" in schema and len(value) < schema["minItems"]:
        errors.append(f"{path}: expected at least {schema['minItems']} items, got {len(value)}")
    if "maxItems" in schema and len(value) > schema["maxItems"]:
        errors.append(f"{path}: expected at most {schema['maxItems']} items, got {len(value)}")

    if schema.get("uniqueItems") is True:
        seen: list[Any] = []
        for index, item in enumerate(value):
            if any(_json_equivalent(item, other) for other in seen):
                errors.append(f"{path}[{index}]: duplicate item")
            seen.append(item)

    items = schema.get("items")
    if isinstance(items, dict):
        for index, item in enumerate(value):
            _validate(item, items, f"{path}[{index}]", root, errors, depth + 1)
    elif isinstance(items, list):
        for index, item in enumerate(value):
            if index < len(items):
                _validate(item, items[index], f"{path}[{index}]", root, errors, depth + 1)
            elif schema.get("additionalItems") is False:
                errors.append(f"{path}[{index}]: additional item not allowed")

    contains = schema.get("contains")
    if isinstance(contains, dict):
        if not any(_is_valid(item, contains, root, depth + 1) for item in value):
            errors.append(f"{path}: no item matches 'contains'")


def _is_valid(value: Any, schema: Any, root: Any, depth: int) -> bool:
    errors: list[str] = []
    _validate(value, schema, "$", root, errors, depth)
    return not errors


def _validate_string(value: str, schema: dict, path: str, errors: list[str]) -> None:
    if "minLength" in schema and len(value) < schema["minLength"]:
        errors.append(f"{path}: string shorter than {schema['minLength']}")
    if "maxLength" in schema and len(value) > schema["maxLength"]:
        errors.append(f"{path}: string longer than {schema['maxLength']}")
    if "pattern" in schema:
        try:
            if re.search(schema["pattern"], value) is None:
                errors.append(f"{path}: does not match pattern {schema['pattern']!r}")
        except re.error as exc:
            errors.append(f"{path}: bad pattern {schema['pattern']!r}: {exc}")


def _validate_number(value: float, schema: dict, path: str, errors: list[str]) -> None:
    if "minimum" in schema and value < schema["minimum"]:
        errors.append(f"{path}: {value} is less than minimum {schema['minimum']}")
    if "maximum" in schema and value > schema["maximum"]:
        errors.append(f"{path}: {value} is greater than maximum {schema['maximum']}")
    if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
        errors.append(f"{path}: {value} must be > {schema['exclusiveMinimum']}")
    if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
        errors.append(f"{path}: {value} must be < {schema['exclusiveMaximum']}")
    if "multipleOf" in schema and schema["multipleOf"]:
        quotient = value / schema["multipleOf"]
        if not math.isclose(quotient, round(quotient), rel_tol=0.0, abs_tol=1e-9):
            errors.append(f"{path}: {value} is not a multiple of {schema['multipleOf']}")


def validate(instance: Any, schema: dict) -> list[str]:
    """Return a list of human-readable validation errors (empty = valid)."""

    if not isinstance(schema, dict):
        raise SchemaError("schema must be an object")
    root = schema
    errors: list[str] = []
    _validate(instance, schema, "$", root, errors, 0)
    return errors


def iter_errors(instance: Any, schema: dict) -> Iterable[str]:
    yield from validate(instance, schema)
