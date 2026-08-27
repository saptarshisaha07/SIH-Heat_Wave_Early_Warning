"""Thermal index calculations for SIH Heat Wave Early Warning System.

This module provides pure mathematical functions to compute:
1. Heat Index (HI) using the NOAA / National Weather Service (NWS) Rothfusz regression
   with low/high humidity corrections and Steadman mild-temperature threshold.
2. Simplified outdoor Wet Bulb Globe Temperature (WBGT) using the Australian
   Bureau of Meteorology (BOM) approximation with optional solar radiation adjustments.
"""

import math
from typing import Any, Dict, Optional


def heat_index(temp_c: float, humidity_pct: float) -> float:
    """Compute the NOAA / NWS Heat Index in degrees Celsius.

    Args:
        temp_c: Ambient dry-bulb temperature in degrees Celsius.
        humidity_pct: Relative humidity percentage (0.0 to 100.0).

    Returns:
        Computed Heat Index in degrees Celsius, rounded to 1 decimal place.

    Raises:
        ValueError: If inputs are non-numeric, booleans, or out of valid physical bounds.
    """
    if isinstance(temp_c, bool) or isinstance(humidity_pct, bool):
        raise ValueError("Temperature and humidity must be numeric, not booleans.")

    try:
        t_c = float(temp_c)
        rh = float(humidity_pct)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid non-numeric inputs: temp_c={temp_c!r}, humidity_pct={humidity_pct!r}") from exc

    if not (-50.0 <= t_c <= 70.0):
        raise ValueError(f"Temperature out of realistic bounds (-50 to 70 C): {t_c}")
    if not (0.0 <= rh <= 100.0):
        raise ValueError(f"Relative humidity must be between 0.0 and 100.0%: {rh}")

    # Convert Celsius to Fahrenheit
    t_f = t_c * 9.0 / 5.0 + 32.0

    # Step 1: Steadman simple approximation for mild conditions
    hi_simple = 0.5 * (t_f + 61.0 + ((t_f - 68.0) * 1.2) + (rh * 0.094))

    # If Steadman average with ambient temp is below 80 F (26.7 C), Rothfusz is not needed
    if (hi_simple + t_f) / 2.0 < 80.0:
        hi_f = hi_simple
    else:
        # Step 2: Full 9-term NWS Rothfusz polynomial regression
        t2 = t_f * t_f
        rh2 = rh * rh
        t_rh = t_f * rh

        hi_f = (
            -42.379
            + 2.04901523 * t_f
            + 10.14333127 * rh
            - 0.22475541 * t_rh
            - 0.00683783 * t2
            - 0.05481717 * rh2
            + 0.00122874 * t2 * rh
            + 0.00085282 * t_f * rh2
            - 0.00000199788 * t2 * rh2
        )

        # Step 3: NWS Adjustments
        # Low humidity correction (RH < 13% and 80 <= T_F <= 112)
        if rh < 13.0 and 80.0 <= t_f <= 112.0:
            diff = abs(t_f - 95.0)
            if diff < 17.0:
                adj = -((13.0 - rh) / 4.0) * math.sqrt((17.0 - diff) / 17.0)
                hi_f += adj

        # High humidity correction (RH > 85% and 80 <= T_F <= 87)
        elif rh > 85.0 and 80.0 <= t_f <= 87.0:
            adj = ((rh - 85.0) / 10.0) * ((87.0 - t_f) / 5.0)
            hi_f += adj

    # Convert back to Celsius
    hi_c = (hi_f - 32.0) * 5.0 / 9.0
    return round(hi_c, 1)


def wbgt(
    temp_c: float,
    humidity_pct: float,
    solar_radiation: Optional[float] = None,
) -> float:
    """Compute simplified outdoor Wet Bulb Globe Temperature (WBGT) in degrees Celsius.

    Uses the Australian Bureau of Meteorology (BOM) approximation:
    e = (RH / 100) * 6.105 * exp(17.27 * T / (237.7 + T))  [vapor pressure in hPa]
    WBGT = 0.567 * T + 0.393 * e + 3.94

    If shortwave solar radiation (W/m^2) is provided and exceeds 600 W/m^2,
    a slight thermal load adjustment is added for outdoor worker assessment.

    Args:
        temp_c: Ambient temperature in degrees Celsius.
        humidity_pct: Relative humidity percentage (0.0 to 100.0).
        solar_radiation: Optional shortwave solar radiation in W/m^2.

    Returns:
        WBGT in degrees Celsius, rounded to 1 decimal place.

    Raises:
        ValueError: If inputs are invalid or out of bounds.
    """
    if isinstance(temp_c, bool) or isinstance(humidity_pct, bool):
        raise ValueError("Temperature and humidity must be numeric, not booleans.")

    try:
        t_c = float(temp_c)
        rh = float(humidity_pct)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid non-numeric inputs: temp_c={temp_c!r}, humidity_pct={humidity_pct!r}") from exc

    if not (-50.0 <= t_c <= 70.0):
        raise ValueError(f"Temperature out of realistic bounds (-50 to 70 C): {t_c}")
    if not (0.0 <= rh <= 100.0):
        raise ValueError(f"Relative humidity must be between 0.0 and 100.0%: {rh}")

    # Vapor pressure (e) in hPa using Magnus-Tetens formula
    e = (rh / 100.0) * 6.105 * math.exp((17.27 * t_c) / (237.7 + t_c))

    # Base BOM approximation
    wbgt_val = 0.567 * t_c + 0.393 * e + 3.94

    # Optional solar radiation thermal load adjustment
    if solar_radiation is not None:
        if isinstance(solar_radiation, bool):
            raise ValueError("Solar radiation must be numeric, not boolean.")
        try:
            sol = float(solar_radiation)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid solar radiation value: {solar_radiation!r}") from exc

        if sol < 0.0:
            raise ValueError(f"Solar radiation cannot be negative: {sol}")

        # Add up to +1.5 C on high radiation hours (> 600 W/m^2)
        if sol > 600.0:
            solar_nudge = min(1.5, ((sol - 600.0) / 400.0) * 1.5)
            wbgt_val += solar_nudge

    return round(wbgt_val, 1)


def compute_thermal_metrics(
    temp_c: float,
    humidity_pct: float,
    solar_radiation: Optional[float] = None,
) -> Dict[str, float]:
    """Compute both Heat Index and WBGT for given atmospheric parameters.

    Args:
        temp_c: Ambient temperature in degrees Celsius.
        humidity_pct: Relative humidity percentage.
        solar_radiation: Optional solar radiation in W/m^2.

    Returns:
        Dictionary with keys 'heat_index_c' and 'wbgt_c'.
    """
    return {
        "heat_index_c": heat_index(temp_c, humidity_pct),
        "wbgt_c": wbgt(temp_c, humidity_pct, solar_radiation),
    }
