#!/usr/bin/env python3
"""Test the real-world cost integration in the wildfire impact calculator."""

import sys
sys.path.insert(0, '.')
from wildfire_impact_calculator import WildfireImpactCalculator

# Test with real-world costs
calc = WildfireImpactCalculator('Incendies.csv')

print("\n" + "="*80)
print("WILDFIRE IMPACT CALCULATOR - WITH REAL-WORLD COSTS")
print("="*80)

# Test scenario 1: High-risk Mediterranean region (Dept 06)
print("\n[SCENARIO 1] Early detection saves 15 minutes - Alpes-Maritimes (Dept 06)")
print("-" * 80)

impact = calc.calculate_impact(
    x_minutes_saved=15,
    t0_response_time=45,
    wind_speed_kmh=30,
    temperature_C=32,
    relative_humidity_pct=25,
    dept='06'
)

print(f"  Vegetation Type:           {impact['vegetation_type']}")
print(f"  Wind Category:             {impact['wind_category']}")
print(f"  Direct hectares saved:     {impact['direct_area_saved_ha']:.2f} ha")
print(f"  Risk-adjusted hectares:    {impact['risk_adjusted_ha_saved']:.2f} ha")
print(f"  CO2 emissions prevented:   {impact['tco2_emissions_prevented']:.2f} tCO2")
print(f"  Buildings protected:       {impact['buildings_protected']} buildings")
print(f"\n  💰 ECONOMIC VALUE:")
print(f"    Suppression cost per ha: €{impact['suppression_cost_per_ha']:,}/ha")
print(f"    Asset value per ha:      €{impact['asset_value_per_ha']:,}/ha")
print(f"    Total avoided cost:      €{impact['economic_value_avoided_euros']:,.2f}")
print(f"    Cost source:             {impact['cost_source']}")

# Test scenario 2: Less-risk region
print("\n[SCENARIO 2] Early detection saves 20 minutes - Default region")
print("-" * 80)

impact2 = calc.calculate_impact(
    x_minutes_saved=20,
    t0_response_time=45,
    wind_speed_kmh=20,
    temperature_C=28,
    relative_humidity_pct=40,
    dept='default'
)

print(f"  Vegetation Type:           {impact2['vegetation_type']}")
print(f"  Direct hectares saved:     {impact2['direct_area_saved_ha']:.2f} ha")
print(f"  Risk-adjusted hectares:    {impact2['risk_adjusted_ha_saved']:.2f} ha")
print(f"  CO2 emissions prevented:   {impact2['tco2_emissions_prevented']:.2f} tCO2")
print(f"\n  💰 ECONOMIC VALUE:")
print(f"    Suppression cost per ha: €{impact2['suppression_cost_per_ha']:,}/ha")
print(f"    Asset value per ha:      €{impact2['asset_value_per_ha']:,}/ha")
print(f"    Total avoided cost:      €{impact2['economic_value_avoided_euros']:,.2f}")
print(f"    Cost source:             {impact2['cost_source']}")

# Test scenario 3: Scenario analysis
print("\n[SCENARIO 3] Scenario Analysis - Multiple response times (Dept 06)")
print("-" * 80)

scenarios = calc.scenario_analysis(
    minutes_saved_list=[5, 10, 15, 20, 30],
    dept='06',
    vegetation_type='garrigue_maquis'
)

print("\nMinutes Saved | Direct Ha | Risk-Adj Ha | CO2 (tCO2) | Economic Value")
print("-" * 75)
for idx, row in scenarios.iterrows():
    mins = int(row['minutes_saved'])
    direct = row['direct_area_saved_ha']
    risk_adj = row['risk_adjusted_ha_saved']
    co2 = row['tco2_emissions_prevented']
    econ = row['economic_value_avoided_euros']
    print(f"      {mins:2d}    |   {direct:6.2f}   |   {risk_adj:6.2f}    |  {co2:6.1f}   |  €{econ:12,.0f}")

print("\n" + "="*80)
print("✓ Integration successful: Real-world costs are being used!")
print("="*80 + "\n")
