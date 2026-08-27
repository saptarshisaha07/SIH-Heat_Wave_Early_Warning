"""Public health advisory service for SIH Heat Wave Early Warning System.

Generates targeted, plain-language advisories and actionable public health guidelines
tailored to 5 thermal risk categories, distinct demographic cohorts, and municipal response teams.
"""

from typing import Any, Dict, List

ADVISORIES: Dict[str, Dict[str, Any]] = {
    "Normal": {
        "risk_category": "Normal",
        "alert_level": "Green",
        "headline": "Normal Weather Conditions",
        "summary": "Thermal stress levels are within normal physiological tolerance. No immediate heat hazard.",
        "general_public": [
            "Maintain standard daily hydration (2-3 liters of water).",
            "Enjoy outdoor activities safely with standard sun protection.",
        ],
        "outdoor_workers": [
            "Follow standard working hours with routine water breaks.",
        ],
        "vulnerable_groups": [
            "No special restrictions required; maintain regular indoor comfort.",
        ],
        "municipal_actions": [
            "Routine public health and meteorological surveillance.",
        ],
    },
    "Caution": {
        "risk_category": "Caution",
        "alert_level": "Yellow",
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
        ],
        "vulnerable_groups": [
            "Ensure elderly family members and children remain well-hydrated.",
            "Never leave children, elderly, or pets inside parked vehicles.",
        ],
        "municipal_actions": [
            "Issue advisory notices across municipal social channels and public transit screens.",
            "Inspect and ensure public tap water kiosks and water fountains are fully functional.",
        ],
    },
    "Extreme Caution": {
        "risk_category": "Extreme Caution",
        "alert_level": "Orange",
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
        ],
        "municipal_actions": [
            "Activate municipal hydration kiosks (Jal Chhatras) at major bus terminals and markets.",
            "Alert urban primary health centers (UPHCs) to stock IV fluids, ORS, and ice packs.",
        ],
    },
    "Danger": {
        "risk_category": "Danger",
        "alert_level": "Red",
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
        ],
        "municipal_actions": [
            "Open designated air-conditioned public cooling centers in community halls and libraries.",
            "Deploy mobile water tankers to high-density informal settlements and labor hubs.",
            "Place emergency medical services and ambulance networks on high-readiness status.",
        ],
    },
    "Extreme Danger": {
        "risk_category": "Extreme Danger",
        "alert_level": "Maroon",
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
        ],
        "vulnerable_groups": [
            "Evacuate vulnerable elderly and unhoused individuals without indoor cooling to municipal relief shelters.",
            "Continuous medical surveillance in nursing homes and maternal health facilities.",
        ],
        "municipal_actions": [
            "Declare official Municipal Heat Emergency.",
            "Operate 24/7 emergency cooling centers with medical triage personnel.",
            "Coordinate inter-agency disaster response across traffic, health, and civil defense departments.",
        ],
    },
}


def get_advisory(risk_category: str) -> Dict[str, Any]:
    """Retrieve the public health advisory and action list for a specific risk category.

    Args:
        risk_category: One of 'Normal', 'Caution', 'Extreme Caution', 'Danger', 'Extreme Danger'.

    Returns:
        Dictionary with headline, summary, and segmented action lists.
    """
    if risk_category not in ADVISORIES:
        return ADVISORIES["Caution"]
    return ADVISORIES[risk_category]


def get_all_advisories() -> Dict[str, Dict[str, Any]]:
    """Retrieve all advisory templates indexed by risk category name."""
    return ADVISORIES
