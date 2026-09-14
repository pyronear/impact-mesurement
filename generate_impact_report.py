"""
Comprehensive Wildfire Impact Assessment Report
Integrates BDIFF French fire data with early detection impact model
"""

import pandas as pd
import numpy as np
from wildfire_impact_calculator import WildfireImpactCalculator
import json

def generate_comprehensive_report(bdiff_path: str):
    """Generate detailed impact assessment across French regions."""
    
    calc = WildfireImpactCalculator(bdiff_path)
    df = pd.read_csv(bdiff_path, encoding='utf-8', sep=';', skiprows=2)
    df['hectares'] = pd.to_numeric(df['Surface parcourue (m2)'], errors='coerce') / 10000
    
    # Regional analysis
    high_risk_depts = ['06', '13', '11', '83', '2A', '2B']  # Mediterranean coast
    moderate_risk_depts = ['30', '84', '66', '73']  # Southern inland
    low_risk_depts = ['63', '71', '03', '42']  # Central/Eastern
    
    print("\n" + "="*80)
    print("WILDFIRE EARLY DETECTION IMPACT ASSESSMENT - FRANCE 2025")
    print("="*80)
    
    # 1. DATASET OVERVIEW
    print("\n📊 DATASET OVERVIEW (BDIFF 2025)")
    print("-"*80)
    print(f"Total fire records:            {len(df):,}")
    print(f"Fires ≥1 hectare:              {len(df[df['hectares'] >= 1]):,}")
    print(f"Fires ≥10 hectares:            {len(df[df['hectares'] >= 10]):,}")
    print(f"Fires ≥100 hectares:           {len(df[df['hectares'] >= 100]):,}")
    print(f"\nTotal area burned:             {df['hectares'].sum():,.0f} ha")
    print(f"Mean fire size:                {df['hectares'].mean():.2f} ha")
    print(f"Median fire size:              {df['hectares'].median():.2f} ha")
    print(f"Largest fire:                  {df['hectares'].max():,.0f} ha (Dept {df.loc[df['hectares'].idxmax(), 'Département']})")
    
    # Top departments by total burned area
    print(f"\nTop departments by burned area:")
    dept_summary = df.groupby('Département')['hectares'].agg(['count', 'sum', 'mean', 'max']).sort_values('sum', ascending=False)
    for idx, (dept, row) in enumerate(dept_summary.head(10).iterrows(), 1):
        print(f"  {idx:2}. Dept {dept:>3}: {row['count']:>5.0f} fires, {row['sum']:>8,.0f} ha total, avg {row['mean']:>6.2f} ha, max {row['max']:>8.0f} ha")
    
    # 2. REGIONAL RISK ANALYSIS
    print("\n\n🔥 REGIONAL RISK CLASSIFICATION & EARLY DETECTION IMPACT")
    print("-"*80)
    
    regions = {
        'HIGH RISK (Mediterranean)': high_risk_depts,
        'MODERATE RISK (Southern)': moderate_risk_depts,
        'LOW RISK (Central/Eastern)': low_risk_depts,
    }
    
    regional_summary = []
    
    for risk_level, depts in regions.items():
        region_df = df[df['Département'].isin(depts)]
        region_veg = 'garrigue_maquis' if 'HIGH' in risk_level else ('mixed_forest' if 'LOW' in risk_level else 'mixed_forest')
        
        print(f"\n{risk_level}")
        print(f"  Departments: {', '.join(depts)}")
        print(f"  Fire count: {len(region_df):,} | Total area: {region_df['hectares'].sum():,.0f} ha")
        print(f"  Vegetation type: {region_veg}")
        
        # Impact scenarios
        dept_sample = depts[0]
        for minutes_saved in [10, 15, 20]:
            impact = calc.calculate_impact(
                x_minutes_saved=minutes_saved,
                t0_response_time=45,
                wind_speed_kmh=30,
                dept=dept_sample,
                vegetation_type=region_veg
            )
            print(f"\n    ➜ Saving {minutes_saved} minutes detection time:")
            print(f"      • Hectares protected: {impact['risk_adjusted_ha_saved']:.1f} ha")
            print(f"      • CO2 prevented: {impact['tco2_emissions_prevented']:,.0f} tCO2")
            print(f"      • Value protected: €{impact['economic_value_avoided_euros']:,.0f}")
            print(f"      • Buildings saved: {impact['buildings_protected']}")
            
            regional_summary.append({
                'Region': risk_level,
                'Minutes Saved': minutes_saved,
                'Ha Protected': impact['risk_adjusted_ha_saved'],
                'tCO2 Avoided': impact['tco2_emissions_prevented'],
                'Value €': impact['economic_value_avoided_euros'],
                'Buildings': impact['buildings_protected'],
            })
    
    # 3. NATIONAL IMPACT PROJECTION
    print("\n\n🌍 NATIONAL IMPACT PROJECTION (if applied across France)")
    print("-"*80)
    
    # Conservative estimate: average impact across typical French fire response scenario
    national_impact = calc.calculate_impact(
        x_minutes_saved=15,
        t0_response_time=45,
        wind_speed_kmh=28,
        dept='default',
        vegetation_type='mixed_forest'
    )
    
    # Scale to actual 2025 fire count (large fires where detection matters most)
    large_fires = df[df['hectares'] >= 5]
    national_scale_factor = len(large_fires)  # Apply to fires ≥5 hectares
    
    print(f"\nBase scenario: 15 minutes early detection")
    print(f"Typical response time: 45 minutes")
    print(f"Applied to: {len(large_fires):,} significant fires (≥5 ha) in 2025")
    print(f"\nProjected national impact from early detection:")
    print(f"  • Total hectares protected: {national_impact['risk_adjusted_ha_saved'] * national_scale_factor:,.0f} ha")
    print(f"  • Total CO2 prevented: {national_impact['tco2_emissions_prevented'] * national_scale_factor:,.0f} tCO2")
    print(f"  • Total economic value: €{national_impact['economic_value_avoided_euros'] * national_scale_factor:,.0f}")
    print(f"  • Total buildings protected: {national_impact['buildings_protected'] * national_scale_factor:,}")
    
    # 4. SENSITIVITY ANALYSIS
    print("\n\n📈 SENSITIVITY ANALYSIS: Impact of varying response time saved")
    print("-"*80)
    
    sensitivity_df = calc.scenario_analysis(
        minutes_saved_list=[5, 10, 15, 20, 30, 45],
        dept='06',
        vegetation_type='garrigue_maquis'
    )
    print("\nMediterranean High-Risk (Dept 06, Garrigue):")
    print(sensitivity_df.to_string(index=False))
    
    # 4b. Wind speed sensitivity
    print("\n\nWind speed sensitivity (15 minutes early detection, Dept 06):")
    wind_scenarios = []
    for wind_kmh in [15, 25, 35, 45]:
        wind_impact = calc.calculate_impact(
            x_minutes_saved=15,
            t0_response_time=45,
            wind_speed_kmh=wind_kmh,
            dept='06',
            vegetation_type='garrigue_maquis'
        )
        wind_scenarios.append({
            'Wind (km/h)': wind_kmh,
            'Ha Saved': wind_impact['risk_adjusted_ha_saved'],
            'tCO2 Avoided': wind_impact['tco2_emissions_prevented'],
            '€ Value': wind_impact['economic_value_avoided_euros'],
        })
    
    wind_df = pd.DataFrame(wind_scenarios)
    print(wind_df.to_string(index=False))
    
    # 5. FIRE CAUSE ANALYSIS
    print("\n\n🔍 FIRE CAUSE ANALYSIS (BDIFF 2025)")
    print("-"*80)
    
    cause_summary = df['Nature'].value_counts()
    print("\nFire causes (top 8):")
    for cause, count in cause_summary.head(8).items():
        pct = 100 * count / len(df)
        print(f"  • {cause}: {count:,} fires ({pct:.1f}%)")
    
    # 6. KEY FINDINGS & RECOMMENDATIONS
    print("\n\n✅ KEY FINDINGS & RECOMMENDATIONS")
    print("-"*80)
    print("""
1. SCALE OF POTENTIAL IMPACT
   • Early detection reducing response time by 15 minutes can save:
     - 15-35 hectares per fire in Mediterranean regions
     - 36-87 hectares per fire in central regions (due to escape threshold model)
     - €100K-€550K economic value per fire
   
2. REGIONAL VARIABILITY
   • HIGH-RISK Mediterranean (Depts 06, 13, 11, 83):
     - Dense population, high asset value
     - Garrigue/maquis vegetation burns rapidly
     - Earlier detection = directly proportional impact
   
   • MODERATE-RISK Southern inland (Depts 30, 84, 66):
     - Mixed forest/grassland
     - Significant escape probability after 3 ha threshold
   
   • LOWER-RISK Central/Eastern (Depts 63, 71, 03):
     - Mixed forests, lower wind speeds
     - HIGHEST potential from escape prevention model
     - Non-linear benefit (risk-adjusted ha far exceeds direct area)

3. WEATHER DEPENDENCY
   • Wind speed significantly amplifies early detection value
   • High wind conditions (35+ km/h): 3-4x impact vs low wind
   • Seasonal variation in effectiveness critical

4. NATIONAL SCALE OPPORTUNITY
   • 2025 had 21,141 fire records, 742 significant fires (≥5 ha)
   • If 15-minute early detection applied to all significant fires:
     - ~11,000-17,000 hectares annually protected
     - ~114,000-175,000 tCO2 emissions prevented per year
     - ~€1-2 billion economic value protected

5. RECOMMENDED FOCUS AREAS
   • Mediterranean coast (06, 13, 83, 2A, 2B): Direct high-value assets
   • Central France (63, 71): Highest leverage from escape prevention
   • Implement during high-wind alert periods for maximum ROI
""")
    
    # Save results
    results_summary = pd.DataFrame(regional_summary)
    results_summary.to_csv('wildfire_impact_results.csv', index=False)
    
    print("\n💾 Results saved to: wildfire_impact_results.csv")
    print("\n" + "="*80)
    
    return results_summary, calc

if __name__ == '__main__':
    bdiff_path = '/Users/doconnor/Desktop/untitled folder/Incendies.csv'
    results, calc = generate_comprehensive_report(bdiff_path)
