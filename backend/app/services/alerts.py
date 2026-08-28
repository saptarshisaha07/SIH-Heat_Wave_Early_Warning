"""Alerts simulation service for SIH Heat Wave Early Warning System.

Builds automated SMS and WhatsApp early warning broadcast messages
formatted with localized thermal indicators, risk severity, and real public health advisories.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.services.advisory import get_advisory
from app.services.risk_engine import evaluate_ward_risk


def format_sms_message(
    ward_name: str, risk_category: str, heat_index_c: float, headline: str
) -> str:
    """Generate concise SMS warning text (suitable for telecom gateway broadcast)."""
    return (
        f"HEAT ALERT: {ward_name} is under {risk_category.upper()} risk "
        f"(Heat Index: {heat_index_c:.1f}°C). {headline}. "
        f"Dial 108/112 for emergencies. - BMC Heat Cell"
    )


def format_whatsapp_message(
    ward_name: str,
    risk_category: str,
    heat_index_c: float,
    headline: str,
    precautions: List[str],
) -> str:
    """Generate rich formatted WhatsApp alert message with action bullet points."""
    bullet_items = "\n".join([f"• {p}" for p in precautions[:3]]) if precautions else "• Follow standard heat safety precautions."
    return (
        f"⚠️ *HEATWAVE EARLY WARNING NOTICE*\n\n"
        f"*Location:* {ward_name}\n"
        f"*Risk Level:* {risk_category}\n"
        f"*Thermal Heat Index:* {heat_index_c:.1f}°C\n\n"
        f"*Advisory:* {headline}\n\n"
        f"*Key Protective Measures:*\n"
        f"{bullet_items}\n\n"
        f"🚑 *Emergency Helpline:* Dial 108 / 112\n"
        f"_Issued by Bhubaneswar Municipal Heat Action Cell_"
    )


def build_simulated_alert(
    ward_id: Any,
    heat_index_c: float,
    channel: str = "sms",
    custom_vuln_index: Optional[float] = None,
    ward_name: Optional[str] = None,
    risk_category: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a simulated alert broadcast payload for a specific ward.

    Args:
        ward_id: Database ID (int) or code (str) of the ward.
        heat_index_c: Current Heat Index in degrees Celsius.
        channel: Delivery medium ('sms' or 'whatsapp').
        custom_vuln_index: Optional override for vulnerability index.
        ward_name: Optional explicit name of the ward.
        risk_category: Optional explicit risk category tier.

    Returns:
        Structured response dict matching the required Blueprint schema.
    """
    channel_norm = str(channel).lower().strip()
    if channel_norm not in ["sms", "whatsapp"]:
        channel_norm = "sms"

    if not ward_name or not risk_category:
        ward_str = (
            f"BBSR-{int(ward_id):02d}"
            if isinstance(ward_id, int) or (isinstance(ward_id, str) and ward_id.isdigit())
            else str(ward_id)
        )
        risk_profile = evaluate_ward_risk(ward_str, heat_index_c, custom_vuln_index)
        resolved_name = ward_name or risk_profile["ward_name"]
        resolved_cat = risk_category or risk_profile["risk_category"]
    else:
        resolved_name = ward_name
        resolved_cat = risk_category

    advisory = get_advisory(resolved_cat)
    headline = advisory.get("headline", "Take precautions during high heat.")
    precautions = advisory.get("general_public", []) + advisory.get("outdoor_workers", [])

    if channel_norm == "whatsapp":
        message_text = format_whatsapp_message(
            ward_name=resolved_name,
            risk_category=resolved_cat,
            heat_index_c=heat_index_c,
            headline=headline,
            precautions=precautions,
        )
    else:
        message_text = format_sms_message(
            ward_name=resolved_name,
            risk_category=resolved_cat,
            heat_index_c=heat_index_c,
            headline=headline,
        )

    return {
        "ward_id": ward_id,
        "ward_name": resolved_name,
        "channel": channel_norm,
        "status": "simulated",
        "message": message_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
