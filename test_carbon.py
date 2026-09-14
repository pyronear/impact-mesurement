"""Self-check: CO2 output equals hectares saved × the per-vegetation factor."""
import math
from wildfire_impact_calculator import TCO2_PER_HA, WildfireImpactCalculator

calc = WildfireImpactCalculator()
for veg in list(TCO2_PER_HA) + ['unknown_type']:
    impact = calc.calculate_impact(x_minutes_saved=15, dept='06', vegetation_type=veg)
    expected = impact['risk_adjusted_ha_saved'] * TCO2_PER_HA.get(veg, TCO2_PER_HA['mixed_forest'])
    assert math.isclose(impact['tco2_emissions_prevented'], expected, rel_tol=1e-3), (veg, impact['tco2_emissions_prevented'], expected)
print("OK: tCO2 = ha × TCO2_PER_HA for", ', '.join(TCO2_PER_HA), "and fallback")
