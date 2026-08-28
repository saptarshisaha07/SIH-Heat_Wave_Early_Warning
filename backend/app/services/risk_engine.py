"""Risk Engine service for SIH Heat Wave Early Warning System.

Computes explainable Base Heat Scores (NWS Heat Index continuous interpolation),
applies demographic vulnerability adjustments (up to 30% amplification),
determines 5-band thermal risk categories, and supports heat-only vs composite evaluation.
"""

from typing import Any, Dict, Optional
from app.services.vulnerability import get_ward_vulnerability

# 5-Band Risk Classification Metadata
RISK_CATEGORIES = {
    "Normal": {
        "min_score": 0.0,
        "max_score": 20.0,
        "alert_level": "Green",
        "color_hex": "#28a745",
        "description": "Safe conditions with normal thermal stress levels.",
    },
    "Caution": {
        "min_score": 20.0,
        "max_score": 40.0,
        "alert_level": "Yellow",
        "color_hex": "#ffc107",
        "description": "Mild heat stress; prolonged exposure or physical activity may lead to fatigue.",
    },
    "Extreme Caution": {
        "min_score": 40.0,
        "max_score": 60.0,
        "alert_level": "Orange",
        "color_hex": "#fd7e14",
        "description": "High thermal stress; heat cramps and heat exhaustion possible for vulnerable groups and outdoor workers.",
    },
    "Danger": {
        "min_score": 60.0,
        "max_score": 85.0,
        "alert_level": "Red",
        "color_hex": "#dc3545",
        "description": "Severe heat stress; heat exhaustion likely and heat stroke possible with continued exposure.",
    },
    "Extreme Danger": {
        "min_score": 85.0,
        "max_score": 100.0,
        "alert_level": "Maroon",
        "color_hex": "#800000",
        "description": "Critical emergency; extreme danger of imminent heat stroke, hospitalization, and systemic shock.",
    },
}


def compute_base_heat_score(heat_index_c: float) -> float:
    """Compute continuous Base Heat Score (0–100) from Heat Index in Celsius via piecewise linear interpolation.

    Thresholds per Engineering Blueprint:
        - HI < 27°C: Normal (0 to 20)
        - 27°C <= HI < 32°C: Caution (20 to 40)
        - 32°C <= HI < 39°C: Extreme Caution (40 to 60)
        - 39°C <= HI < 51°C: Danger (60 to 85)
        - HI >= 51°C: Extreme Danger (85 to 100)

    Args:
        heat_index_c: Heat Index value in degrees Celsius.

    Returns:
        A float value between 0.0 and 100.0 rounded to 2 decimal places.
    """
    hi = float(heat_index_c)

    if hi <= 0.0:
        return 0.0
    elif hi < 27.0:
        score = (hi / 27.0) * 20.0
    elif hi < 32.0:
        score = 20.0 + ((hi - 27.0) / (32.0 - 27.0)) * 20.0
    elif hi < 39.0:
        score = 40.0 + ((hi - 32.0) / (39.0 - 32.0)) * 20.0
    elif hi < 51.0:
        score = 60.0 + ((hi - 39.0) / (51.0 - 39.0)) * 25.0
    else:
        # 51°C to 66°C scales from 85 to 100, capped at 100.0
        score = 85.0 + ((hi - 51.0) / 15.0) * 15.0

    score = max(0.0, min(100.0, score))
    return round(score, 2)


def categorize_risk(score: float) -> Dict[str, Any]:
    """Map a numerical risk score (0–100) to its corresponding 5-band risk category metadata.

    Args:
        score: Numerical score between 0.0 and 100.0.

    Returns:
        Dict with keys: category, alert_level, color_hex, description.
    """
    s = max(0.0, min(100.0, float(score)))

    if s < 20.0:
        cat_name = "Normal"
    elif s < 40.0:
        cat_name = "Caution"
    elif s < 60.0:
        cat_name = "Extreme Caution"
    elif s < 85.0:
        cat_name = "Danger"
    else:
        cat_name = "Extreme Danger"

    info = RISK_CATEGORIES[cat_name]
    return {
        "category": cat_name,
        "alert_level": info["alert_level"],
        "color_hex": info["color_hex"],
        "description": info["description"],
    }


def compute_composite_risk(heat_index_c: float, vulnerability_index: float) -> Dict[str, Any]:
    """Compute the multi-factor composite risk score and explainable component breakdown.

    Blueprint formula:
        composite_score = min(100, base_score * (1 + 0.3 * vulnerability_index))

    Args:
        heat_index_c: Heat Index in degrees Celsius.
        vulnerability_index: Normalized demographic vulnerability index (0.0 to 1.0).

    Returns:
        A dictionary with explainability metrics:
        {
            "heat_index_c": float,
            "base_heat_score": float,
            "heat_only_score": float,
            "vulnerability_index": float,
            "vulnerability_adjustment": float,
            "composite_score": float,
            "risk_category": str,
            "alert_level": str,
            "color_hex": str,
            "heat_only_category": str,
            "heat_only_color": str,
            "is_amplified": bool
        }
    """
    v_norm = max(0.0, min(1.0, float(vulnerability_index)))
    base_score = compute_base_heat_score(heat_index_c)

    # Calculate amplified composite score (capped at 100.0)
    composite_raw = base_score * (1.0 + (0.3 * v_norm))
    composite_score = round(min(100.0, composite_raw), 2)
    vuln_adj = round(max(0.0, composite_score - base_score), 2)

    comp_cat = categorize_risk(composite_score)
    heat_only_cat = categorize_risk(base_score)

    return {
        "heat_index_c": round(float(heat_index_c), 2),
        "base_heat_score": base_score,
        "heat_only_score": base_score,
        "vulnerability_index": round(v_norm, 4),
        "vulnerability_adjustment": vuln_adj,
        "composite_score": composite_score,
        "risk_category": comp_cat["category"],
        "alert_level": comp_cat["alert_level"],
        "color_hex": comp_cat["color_hex"],
        "heat_only_category": heat_only_cat["category"],
        "heat_only_risk_category": heat_only_cat["category"],
        "heat_only_color": heat_only_cat["color_hex"],
        "is_amplified": comp_cat["category"] != heat_only_cat["category"],
    }


def evaluate_ward_risk(
    ward_id: str, heat_index_c: float, custom_vuln_index: Optional[float] = None
) -> Dict[str, Any]:
    """Evaluate full thermal risk profile for a named ward using its stored vulnerability demographics.

    Args:
        ward_id: Unique ward identifier (e.g. 'BBSR-01').
        heat_index_c: Heat Index in degrees Celsius.
        custom_vuln_index: Optional override for vulnerability index (for simulation/testing).

    Returns:
        Dictionary containing ward metadata, vulnerability stats, and complete risk score breakdown.
    """
    ward_vuln = get_ward_vulnerability(ward_id)
    if ward_vuln is None and custom_vuln_index is None:
        raise ValueError(f"Ward ID '{ward_id}' not found in vulnerability dataset.")

    vuln_index = (
        custom_vuln_index
        if custom_vuln_index is not None
        else (ward_vuln["vulnerability_index"] if ward_vuln else 0.0)
    )

    risk_result = compute_composite_risk(heat_index_c, vuln_index)

    return {
        "ward_id": ward_id,
        "ward_name": ward_vuln["ward_name"] if ward_vuln else ward_id,
        "zone_name": ward_vuln["zone_name"] if ward_vuln else "",
        "population": ward_vuln["population"] if ward_vuln else 0,
        "elderly_pct": ward_vuln["elderly_pct"] if ward_vuln else 0.0,
        "outdoor_worker_pct": ward_vuln["outdoor_worker_pct"] if ward_vuln else 0.0,
        "vulnerability_notes": ward_vuln["vulnerability_notes"] if ward_vuln else "",
        **risk_result,
    }
