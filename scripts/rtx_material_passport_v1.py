"""RTX NonVisualMaterial passport v1.0 — room/target material conditions.

Maps thesis absorption conditions to Isaac Sim NonVisualMaterial presets.
PyRoom uses numeric absorption coefficients; RTX uses base/coating/attribute IDs.
Cross-model comparison is trend-level only — see experiment notes in summary JSON.

Canonical path:
  /home/lab109/song/isaacsim6.0/scripts/rtx_material_passport_v1.py
"""

from __future__ import annotations

from typing import Any

PASSPORT_VERSION = "v1.0"

# Condition IDs: A=low, B=medium (default), C=high absorption (PyRoom-aligned labels).
MATERIAL_CONDITIONS: dict[str, dict[str, Any]] = {
    "A": {
        "label": "low_absorption",
        "pra_absorption_value": 0.10,
        "room": {"bases": "concrete", "coatings": "paint", "attributes": "none"},
        "target": {"bases": "aluminum", "coatings": "clearcoat", "attributes": "retroreflective"},
        "method_note": "Hard/reflective room proxy; PRA reference absorption=0.10.",
    },
    "B": {
        "label": "medium_absorption",
        "pra_absorption_value": 0.35,
        "room": {"bases": "concrete", "coatings": "clearcoat", "attributes": "none"},
        "target": {"bases": "aluminum", "coatings": "paint", "attributes": "retroreflective"},
        "method_note": "Default formal room; PRA reference absorption=0.35.",
    },
    "C": {
        "label": "high_absorption",
        "pra_absorption_value": 0.70,
        "room": {"bases": "fabric", "coatings": "none", "attributes": "none"},
        "target": {"bases": "plastic", "coatings": "paint", "attributes": "none"},
        "method_note": "Soft/absorptive room proxy; PRA reference absorption=0.70.",
    },
}


def normalize_condition_id(condition_id: str | None) -> str | None:
    if condition_id is None or str(condition_id).lower() in ("none", ""):
        return None
    key = str(condition_id).upper()
    if key not in MATERIAL_CONDITIONS:
        raise ValueError(f"Unknown material condition '{condition_id}'; expected one of {sorted(MATERIAL_CONDITIONS)} or 'none'.")
    return key


def condition_summary(condition_id: str) -> dict[str, Any]:
    key = normalize_condition_id(condition_id)
    if key is None:
        return {"enabled": False}
    spec = MATERIAL_CONDITIONS[key]
    return {
        "enabled": True,
        "condition_id": key,
        "label": spec["label"],
        "pra_absorption_value": spec["pra_absorption_value"],
        "room_nv_material": spec["room"],
        "target_nv_material": spec["target"],
        "method_note": spec["method_note"],
        "passport_version": PASSPORT_VERSION,
    }


def apply_nonvisual_material(
    prim_path: str,
    spec: dict[str, str],
    *,
    Cube: Any,
    NonVisualMaterial: Any,
) -> int:
    """Bind a NonVisualMaterial to an existing Cube prim and return encoded material ID."""
    material_path = f"{prim_path}/rtx_nv_material"
    material = NonVisualMaterial(
        material_path,
        bases=spec["bases"],
        coatings=spec.get("coatings", "none"),
        attributes=spec.get("attributes", "none"),
    )
    cube = Cube(prim_path)
    cube.apply_visual_materials(material)
    return int(NonVisualMaterial.encode_material_ids(material).numpy().item())


def _material_spec_tuple(spec: dict[str, str]) -> tuple[str, str, str]:
    return (
        str(spec["bases"]),
        str(spec.get("coatings", "none")),
        str(spec.get("attributes", "none")),
    )


def verify_material_bindings(material_summary: dict[str, Any], *, NonVisualMaterial: Any) -> dict[str, Any]:
    """Verify encoded NonVisualMaterial IDs match the requested passport condition.

    Mirrors the official debug workflow:
      RTX Real-Time 2.0 > Debug View > Non-Visual Material ID
    """
    if not material_summary.get("enabled"):
        return {
            "enabled": False,
            "valid": True,
            "skipped": True,
            "debug_view_note": "RTX Real-Time 2.0 > Debug View > Non-Visual Material ID",
        }

    condition_id = str(material_summary.get("condition_id", "")).upper()
    if condition_id not in MATERIAL_CONDITIONS:
        return {
            "enabled": True,
            "valid": False,
            "issues": [f"unknown_condition_id:{condition_id}"],
            "debug_view_note": "RTX Real-Time 2.0 > Debug View > Non-Visual Material ID",
        }

    spec = MATERIAL_CONDITIONS[condition_id]
    expected_room = _material_spec_tuple(spec["room"])
    expected_target = _material_spec_tuple(spec["target"])
    room_ids: dict[str, int] = {
        str(path): int(value) for path, value in (material_summary.get("room_material_ids") or {}).items()
    }
    target_id = material_summary.get("target_material_id")
    issues: list[str] = []

    if not room_ids:
        issues.append("missing_room_material_ids")
    if target_id is None:
        issues.append("missing_target_material_id")

    room_id_values = list(room_ids.values())
    if room_id_values and len(set(room_id_values)) != 1:
        issues.append("room_material_ids_not_homogeneous")

    decoded_room = None
    if room_id_values:
        decoded_room = NonVisualMaterial.decode_material_ids(int(room_id_values[0]))[0]
        if decoded_room != expected_room:
            issues.append("room_material_decode_mismatch")

    decoded_target = None
    if target_id is not None:
        decoded_target = NonVisualMaterial.decode_material_ids(int(target_id))[0]
        if decoded_target != expected_target:
            issues.append("target_material_decode_mismatch")

    if (
        room_id_values
        and target_id is not None
        and int(target_id) == int(room_id_values[0])
        and expected_room != expected_target
    ):
        issues.append("target_room_material_id_identical_unexpected")

    return {
        "enabled": True,
        "valid": len(issues) == 0,
        "issues": issues,
        "condition_id": condition_id,
        "expected_room_material": list(expected_room),
        "expected_target_material": list(expected_target),
        "decoded_room_material": list(decoded_room) if decoded_room is not None else None,
        "decoded_target_material": list(decoded_target) if decoded_target is not None else None,
        "unique_room_material_id": int(room_id_values[0]) if room_id_values else None,
        "target_material_id": int(target_id) if target_id is not None else None,
        "debug_view_note": "RTX Real-Time 2.0 > Debug View > Non-Visual Material ID",
    }


def apply_room_and_target_materials(
    room_prim_paths: list[str],
    target_prim_path: str,
    condition_id: str,
    *,
    Cube: Any,
    NonVisualMaterial: Any,
    table_prim_path: str | None = None,
) -> dict[str, Any]:
    key = normalize_condition_id(condition_id)
    if key is None:
        return {"enabled": False}
    spec = MATERIAL_CONDITIONS[key]
    room_ids: dict[str, int] = {}
    for path in room_prim_paths:
        room_ids[path] = apply_nonvisual_material(path, spec["room"], Cube=Cube, NonVisualMaterial=NonVisualMaterial)
    table_id = None
    if table_prim_path:
        table_id = apply_nonvisual_material(
            table_prim_path, spec["room"], Cube=Cube, NonVisualMaterial=NonVisualMaterial
        )
    target_id = apply_nonvisual_material(target_prim_path, spec["target"], Cube=Cube, NonVisualMaterial=NonVisualMaterial)
    summary = condition_summary(key)
    summary["room_material_ids"] = room_ids
    summary["table_material_id"] = table_id
    summary["target_material_id"] = target_id
    summary["nv_material_verification"] = verify_material_bindings(summary, NonVisualMaterial=NonVisualMaterial)
    return summary