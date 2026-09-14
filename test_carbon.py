"""Self-check: CO2 output equals hectares saved × the per-vegetation factor."""
import math
from wildfire_impact_calculator import TCO2_PER_HA, WildfireImpactCalculator

calc = WildfireImpactCalculator()
for veg in list(TCO2_PER_HA) + ['unknown_type']:
    impact = calc.calculate_impact(x_minutes_saved=15, dept='06', vegetation_type=veg)
    expected = impact['risk_adjusted_ha_saved'] * TCO2_PER_HA.get(veg, TCO2_PER_HA['mixed_forest'])
    # abs_tol accounts for double-rounding: `expected` is derived from the
    # already-rounded (3 dp) `risk_adjusted_ha_saved`, while
    # `tco2_emissions_prevented` is rounded (2 dp) from the full-precision
    # hectare value, so small absolute differences are expected, especially
    # for near-zero hectare scenarios.
    assert math.isclose(impact['tco2_emissions_prevented'], expected, rel_tol=1e-3, abs_tol=0.05), (veg, impact['tco2_emissions_prevented'], expected)
print("OK: tCO2 = ha × TCO2_PER_HA for", ', '.join(TCO2_PER_HA), "and fallback")
