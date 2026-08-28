"""Public health advisory service for SIH Heat Wave Early Warning System.

Generates targeted, plain-language advisories and actionable public health guidelines
tailored to 5 thermal risk categories, distinct demographic cohorts, healthcare facilities,
and municipal response teams according to NDMA and Bhubaneswar Heat Action Plan standards.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

VALID_PERSONAS = [
    "general_public",
    "outdoor_workers",
    "vulnerable_groups",
    "hospitals_facilities",
    "municipal_actions",
]

ADVISORIES: Dict[str, Dict[str, Any]] = {
    "Normal": {
        "risk_category": "Normal",
        "alert_level": "Green",
        "color_hex": "#28a745",
        "heat_index_range_c": "< 27.0°C",
        "headline": "Normal Weather Conditions",
        "summary": "Thermal stress levels are within normal physiological tolerance. No immediate heat hazard.",
        "general_public": [
            "Maintain standard daily hydration (2-3 liters of water).",
            "Enjoy outdoor activities safely with standard sun protection.",
        ],
        "outdoor_workers": [
            "Follow standard working hours with routine water breaks.",
            "Wear breathable work attire.",
        ],
        "vulnerable_groups": [
            "No special restrictions required; maintain regular indoor comfort.",
            "Ensure regular dietary hydration for infants and seniors.",
        ],
        "hospitals_facilities": [
            "Routine outpatient surveillance and heat illness monitoring.",
            "Standard inventory check for emergency oral rehydration supplies.",
        ],
        "municipal_actions": [
            "Routine public health and meteorological surveillance.",
            "Maintain public tap water kiosks in operational condition.",
        ],
    },
    "Caution": {
        "risk_category": "Caution",
        "alert_level": "Yellow",
        "color_hex": "#ffc107",
        "heat_index_range_c": "27.0°C - 32.0°C",
        "headline": "Heat Discomfort & Fatigue Watch",
        "summary": "Prolonged exposure or strenuous physical activity can lead to heat fatigue, dizziness, and mild dehydration.",
        "general_public": [
            "Increase fluid intake; drink water regularly even before feeling thirsty.",
            "Wear loose, lightweight, light-colored cotton clothing.",
            "Carry an umbrella, sunglasses, or a wide-brimmed hat when outdoors.",
        ],
        "outdoor_workers": [
            "Take 10-minute rest breaks in shaded areas every 2 hours.",
            "Keep potable drinking water readily available at job sites.",
            "Avoid direct head exposure to midday sun.",
        ],
        "vulnerable_groups": [
            "Ensure elderly family members and children remain well-hydrated.",
            "Never leave children, elderly, or pets inside parked vehicles.",
            "Limit intense midday outdoor play for school children.",
        ],
        "hospitals_facilities": [
            "Ensure dedicated dehydration observation beds in emergency wards.",
            "Stock adequate supplies of ORS packets and intravenous saline fluids.",
        ],
        "municipal_actions": [
            "Issue advisory notices across municipal social channels and public transit screens.",
            "Inspect and ensure public tap water kiosks and water fountains are fully functional.",
        ],
    },
    "Extreme Caution": {
        "risk_category": "Extreme Caution",
        "alert_level": "Orange",
        "color_hex": "#fd7e14",
        "heat_index_range_c": "32.0°C - 41.0°C",
        "headline": "High Heat Stress Warning for Outdoor Workers & Vulnerable Groups",
        "summary": "Elevated thermal stress; heat cramps and heat exhaustion are likely with prolonged outdoor activity.",
        "general_public": [
            "Limit non-essential strenuous outdoor activities between 12:00 PM and 3:30 PM.",
            "Drink plenty of water, ORS (Oral Rehydration Solution), coconut water, or buttermilk.",
            "Stay in shaded or well-ventilated indoor spaces during peak afternoon heat.",
        ],
        "outdoor_workers": [
            "Enforce mandatory 15-minute shaded rest breaks every hour during peak sun.",
            "Shift heavy manual tasks to cooler morning hours (before 11:00 AM).",
            "Provide cold drinking water and electrolyte sachets on-site.",
        ],
        "vulnerable_groups": [
            "Elderly citizens and persons with cardiovascular/respiratory conditions should stay indoors.",
            "Monitor infants and young children closely for signs of heat lethargy or flushed skin.",
            "Ensure regular intake of electrolyte liquids for chronically ill residents.",
        ],
        "hospitals_facilities": [
            "Alert urban primary health centers (UPHCs) to stock IV fluids, ORS, and ice packs.",
            "Establish dedicated, cooled heatstroke stabilization bays in emergency rooms.",
            "Prepare mobile medical triage units for rapid response.",
        ],
        "municipal_actions": [
            "Activate municipal hydration kiosks (Jal Chhatras) at major bus terminals and markets.",
            "Deploy misting fans and temporary shaded tarpaulins at congested traffic junctions.",
            "Coordinate with local construction contractors to enforce afternoon rest periods.",
        ],
    },
    "Danger": {
        "risk_category": "Danger",
        "alert_level": "Red",
        "color_hex": "#dc3545",
        "heat_index_range_c": "41.0°C - 54.0°C",
        "headline": "Severe Heat Wave Alert — High Risk of Heat Stroke",
        "summary": "Dangerous thermal conditions; high risk of heat exhaustion and heat stroke for anyone outdoors.",
        "general_public": [
            "Avoid all non-essential outdoor travel between 11:00 AM and 4:00 PM.",
            "Keep rooms cool using curtains, fans, coolers, or air conditioning.",
            "Recognize heat stroke warning signs (confusion, high body temp, nausea, rapid pulse); call 108 immediately.",
        ],
        "outdoor_workers": [
            "Mandatory cessation of heavy outdoor manual labor between 11:30 AM and 3:30 PM.",
            "Establish cool, shaded recovery tents equipped with mist fans and water.",
            "Enforce buddy-checks among laborers to detect early confusion or ataxia.",
        ],
        "vulnerable_groups": [
            "Elderly individuals living alone should receive regular check-ins from community volunteers.",
            "Keep bedridden and chronically ill patients in the coolest room of the house.",
            "Restrict outdoor exposure strictly for pregnant women and young children.",
        ],
        "hospitals_facilities": [
            "Mobilize rapid-cooling baths and evaporative cooling setups in emergency departments.",
            "Cancel non-urgent elective procedures to ensure adequate acute medical beds.",
            "Place paramedic ambulance fleets on high-readiness alert status with active cooling supplies.",
        ],
        "municipal_actions": [
            "Open designated air-conditioned public cooling centers in community halls and libraries.",
            "Deploy mobile water tankers to high-density informal settlements and labor hubs.",
            "Place emergency medical services and ambulance networks on high-readiness status.",
            "Adjust working hours for sanitation and municipal field workers.",
        ],
    },
    "Extreme Danger": {
        "risk_category": "Extreme Danger",
        "alert_level": "Maroon",
        "color_hex": "#6f42c1",
        "heat_index_range_c": "≥ 54.0°C",
        "headline": "Emergency Extreme Heat Wave — Life-Threatening Crisis",
        "summary": "Life-threatening thermal conditions; immediate danger of severe heat stroke, systemic collapse, and shock.",
        "general_public": [
            "STAY STRICTLY INDOORS in cooled spaces; treat as an acute disaster situation.",
            "Do NOT engage in any outdoor physical exertion.",
            "If someone collapses: move to shade, apply cold water/wet towels all over the body, and call 108 immediately.",
        ],
        "outdoor_workers": [
            "Complete shutdown of all outdoor commercial, construction, and delivery operations.",
            "Transfer all field personnel to designated indoor cooling relief shelters.",
            "Enforce zero-tolerance policy on mandatory work stoppages during peak heat.",
        ],
        "vulnerable_groups": [
            "Evacuate vulnerable elderly and unhoused individuals without indoor cooling to municipal relief shelters.",
            "Continuous medical surveillance in nursing homes and maternal health facilities.",
            "Deploy community health workers (ASHA/Anganwadi) for door-to-door vulnerability checks.",
        ],
        "hospitals_facilities": [
            "Operate 24/7 disaster heat triage centers with specialized critical care protocols.",
            "Maintain emergency backup power and water for hospital HVAC cooling systems.",
            "Establish secondary acute heat illness wards in district hospitals.",
        ],
        "municipal_actions": [
            "Declare official Municipal Heat Emergency.",
            "Operate 24/7 emergency cooling centers with medical triage personnel.",
            "Coordinate inter-agency disaster response across traffic, health, and civil defense departments.",
            "Activate emergency siren broadcasts and mass SMS/WhatsApp alerts.",
        ],
    },
}

# Alias mapping for flexible category normalization
_CATEGORY_ALIASES = {
    "normal": "Normal",
    "green": "Normal",
    "caution": "Caution",
    "yellow": "Caution",
    "extreme caution": "Extreme Caution",
    "extreme_caution": "Extreme Caution",
    "orange": "Extreme Caution",
    "danger": "Danger",
    "red": "Danger",
    "extreme danger": "Extreme Danger",
    "extreme_danger": "Extreme Danger",
    "maroon": "Extreme Danger",
    "purple": "Extreme Danger",
}


def normalize_category_name(name: str) -> str:
    """Normalize user/API category or alert level name to canonical key."""
    if not isinstance(name, str):
        logger.warning(
            "Unrecognized category input '%s' (type %s); falling back to 'Caution'",
            name,
            type(name).__name__,
        )
        return "Caution"
    clean = name.strip().lower()
    canonical = _CATEGORY_ALIASES.get(clean)
    if canonical is None:
        logger.warning(
            "Unrecognized category input '%s'; falling back to 'Caution'",
            name,
        )
        return "Caution"
    return canonical


def get_advisory(risk_category: str) -> Dict[str, Any]:
    """Retrieve the public health advisory and action list for a specific risk category.

    Args:
        risk_category: Name of the risk category (e.g. 'Normal', 'Caution', 'Danger', etc.).

    Returns:
        Dictionary with headline, summary, and segmented action lists.
    """
    canonical = normalize_category_name(risk_category)
    return ADVISORIES.get(canonical, ADVISORIES["Caution"])


def get_all_advisories() -> Dict[str, Dict[str, Any]]:
    """Retrieve all advisory templates indexed by risk category name."""
    return ADVISORIES


def filter_advisories(
    category: Optional[str] = None,
    level: Optional[str] = None,
    persona: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Filter advisory matrix by category, alert level color, or target persona.

    Args:
        category: Optional category name filter (e.g. 'Danger', 'Extreme Caution').
        level: Optional alert level color filter (e.g. 'Red', 'Yellow').
        persona: Optional persona filter ('general_public', 'outdoor_workers', etc.).

    Returns:
        List of matching advisory dictionaries, filtered to the requested persona if specified.
    """
    results: List[Dict[str, Any]] = []

    for cat_key, adv in ADVISORIES.items():
        if category and normalize_category_name(category) != cat_key:
            continue
        if level and level.strip().lower() != adv["alert_level"].lower():
            continue

        if persona:
            persona_clean = persona.strip().lower()
            if persona_clean in VALID_PERSONAS:
                results.append(
                    {
                        "risk_category": adv["risk_category"],
                        "alert_level": adv["alert_level"],
                        "color_hex": adv["color_hex"],
                        "heat_index_range_c": adv["heat_index_range_c"],
                        "headline": adv["headline"],
                        "summary": adv["summary"],
                        "persona": persona_clean,
                        "actions": adv.get(persona_clean, []),
                    }
                )
            else:
                # If unknown persona, return standard object
                results.append(adv)
        else:
            results.append(adv)

    return results


def get_persona_advisory(risk_category: str, persona: str) -> Dict[str, Any]:
    """Retrieve targeted action items for a single persona under a given risk tier.

    Args:
        risk_category: Risk category (e.g. 'Danger').
        persona: Persona key (e.g. 'outdoor_workers').

    Returns:
        Structured persona advisory payload.
    """
    adv = get_advisory(risk_category)
    if isinstance(persona, str) and persona.strip().lower() in VALID_PERSONAS:
        resolved_persona = persona.strip().lower()
    else:
        logger.warning(
            "Unrecognized persona '%s'; falling back to 'general_public'",
            persona,
        )
        resolved_persona = "general_public"

    actions = adv.get(resolved_persona, adv["general_public"])
    return {
        "risk_category": adv["risk_category"],
        "alert_level": adv["alert_level"],
        "color_hex": adv["color_hex"],
        "heat_index_range_c": adv["heat_index_range_c"],
        "headline": adv["headline"],
        "summary": adv["summary"],
        "persona": resolved_persona,
        "actions": actions,
    }
