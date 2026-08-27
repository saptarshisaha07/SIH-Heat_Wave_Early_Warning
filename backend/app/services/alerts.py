"""Alerts simulation service for SIH Heat Wave Early Warning System.

Builds realistic, automated SMS and WhatsApp early warning broadcast payloads
formatted with localized thermal indicators, risk severity, and immediate health precautions.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from app.services.risk_engine import evaluate_ward_risk
from app.services.advisory import get_advisory


def format_sms_message(
    ward_name: str, zone_name: str, risk_category: str, alert_level: str, heat_index_c: float
) -> str:
    """Generate concise SMS warning text (suitable for telecom gateway)."""
    zone_label = f" ({zone_name})" if zone_name else ""
    return (
        f"HEAT ALERT [{alert_level.upper()}]: {ward_name}{zone_label} is under {risk_category.upper()} "
        f"risk (Heat Index: {heat_index_c:.1f}°C). Avoid outdoor exposure 11am-4pm. Drink ORS/water. "
        f"Dial 108 for emergencies. - BMC Heat Cell"
    )


def format_whatsapp_message(
    ward_name: str,
    zone_name: str,
    risk_category: str,
    alert_level: str,
    heat_index_c: float,
    precautions: list,
) -> str:
    """Generate rich formatted WhatsApp alert message with emoji badges and action bullet points."""
    level_emojis = {
        "Green": "🟢",
        "Yellow": "🟡",
        "Orange": "🟠",
        "Red": "🔴",
        "Maroon": "🟣",
    }
    emoji = level_emojis.get(alert_level, "⚠️")
    zone_label = f" ({zone_name})" if zone_name else ""

    top_precautions = "\n".join([f"• {p}" for p in precautions[:3]])

    return (
        f"{emoji} *HEATWAVE EARLY WARNING NOTICE* {emoji}\n\n"
        f"*Location:* {ward_name}{zone_label}\n"
        f"*Risk Level:* {risk_category} ({alert_level})\n"
        f"*Thermal Heat Index:* {heat_index_c:.1f}°C\n\n"
        f"*Immediate Protective Measures:*\n"
        f"{top_precautions}\n\n"
        f"🚰 *Cooling & Hydration Centers:* Open at community halls.\n"
        f"🚑 *Emergency Helpline:* Dial 108 / 112\n"
        f"_Issued by Municipal Heatwave Early Warning Authority_"
    )


def build_simulated_alert(
    ward_id: str,
    heat_index_c: float,
    channel: str = "sms",
    custom_vuln_index: Optional[float] = None,
) -> Dict[str, Any]:
    """Generate a simulated alert broadcast payload for a specific ward.

    Args:
        ward_id: Unique ward identifier (e.g. 'BBSR-01').
        heat_index_c: Current or forecasted Heat Index in degrees Celsius.
        channel: Delivery medium ('sms' or 'whatsapp').
        custom_vuln_index: Optional override for vulnerability index.

    Returns:
        Structured simulation response dict ready for frontend display and alerts_log insertion.
    """
    risk_profile = evaluate_ward_risk(ward_id, heat_index_c, custom_vuln_index)
    advisory = get_advisory(risk_profile["risk_category"])

    channel_norm = channel.lower().strip()
    if channel_norm not in ["sms", "whatsapp"]:
        channel_norm = "sms"

    ward_name = risk_profile["ward_name"]
    zone_name = risk_profile.get("zone_name", "")
    risk_category = risk_profile["risk_category"]
    alert_level = risk_profile["alert_level"]

    if channel_norm == "whatsapp":
        message_text = format_whatsapp_message(
            ward_name=ward_name,
            zone_name=zone_name,
            risk_category=risk_category,
            alert_level=alert_level,
            heat_index_c=heat_index_c,
            precautions=advisory["general_public"] + advisory["outdoor_workers"],
        )
    else:
        message_text = format_sms_message(
            ward_name=ward_name,
            zone_name=zone_name,
            risk_category=risk_category,
            alert_level=alert_level,
            heat_index_c=heat_index_c,
        )

    return {
        "ward_id": ward_id,
        "ward_name": ward_name,
        "zone_name": zone_name,
        "channel": channel_norm,
        "status": "simulated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "risk_category": risk_category,
        "alert_level": alert_level,
        "color_hex": risk_profile["color_hex"],
        "heat_index_c": round(float(heat_index_c), 2),
        "composite_score": risk_profile["composite_score"],
        "vulnerability_adjustment": risk_profile["vulnerability_adjustment"],
        "message": message_text,
        "advisory_headline": advisory["headline"],
        "key_actions": advisory["general_public"][:2] + advisory["outdoor_workers"][:1],
    }
