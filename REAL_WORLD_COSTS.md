# Cost Data Integration Documentation

## Overview
Economic impact figures (`economic_value_avoided_euros`, `suppression_cost_per_ha`,
`asset_value_per_ha`) come from `real_world_costs.py`. This document previously
described these figures as "real-world, data-driven" and "calibrated from actual
BDIFF data." **That was inaccurate and has been corrected here** (see
[GitHub issue #7](https://github.com/pyronear/impact-mesurement/issues/7)):
BDIFF (`Incendies.csv`) records fire location, cause, burned area, and
casualty/building-damage counts - it has **no** suppression-cost or
asset-value field. The per-hectare €/department figures are unsourced
planning-level placeholder assumptions, not a calibrated or cited dataset.

## 1. Data sources

| Source | Status |
|--------|--------|
| **`FALLBACK_COSTS` table** | The only cost data actually used today. Labelled `ASSUMPTION` in `real_world_costs.py` - not derived from BDIFF or any other cited source. |
| **Eurostat** | Fetch framework only (`get_eurostat_land_values`); not currently applied to the returned costs. |
| **data.gouv.fr** | Fetch framework only (`get_french_open_data`); not currently applied to the returned costs. |
| **World Bank** | Fetch framework only (`get_worldbank_land_values`); not currently applied to the returned costs. |

An earlier version of this integration also had an "Insurance Analysis" row
here, backed by two hardcoded multiplier tables (1.8/1.4/1.0 by risk class,
and 1.5/1.3/1.4 by department). Neither table was ever applied to
`suppression`/`asset_value` - they only appended text like
`" + insurance adjustment (factor: 1.5)"` to the `source` string, which made
the output look risk-adjusted when the numbers were untouched
([issue #11](https://github.com/pyronear/impact-mesurement/issues/11)). Both
tables and the `get_insurance_data()` method that held them have been deleted
rather than kept as unused/misleading code.

## 2. Current cost table

```python
FALLBACK_COSTS = {
    # All values are ASSUMPTIONS (unsourced placeholders), not BDIFF data.
    '06': {'suppression': 2500, 'asset_value': 8000},  # Alpes-Maritimes (€/ha)
    '13': {'suppression': 2200, 'asset_value': 6500},  # Bouches-du-Rhône
    '11': {'suppression': 2000, 'asset_value': 5500},  # Aude
    '83': {'suppression': 2300, 'asset_value': 7000},  # Var
    '2A': {'suppression': 2400, 'asset_value': 7500},  # Corse-du-Sud
    '2B': {'suppression': 2400, 'asset_value': 7500},  # Haute-Corse
    'default': {'suppression': 1800, 'asset_value': 4500},
}
```

**Cost breakdown (methodology, see also `calculate_impact`'s inline
comments in `wildfire_impact_calculator.py`, issue #8):**
- **Suppression cost**: assumed direct firefighting/emergency-response
  expense per hectare, applied linearly to every effective hectare saved.
- **Asset value**: assumed total loss of an average property/infrastructure
  value per hectare, also applied linearly.
- **Excluded**: ecosystem-service value, any carbon price (CO2 is reported
  separately and unmonetized as `tco2_emissions_prevented`), insurance
  claims-handling costs, and indirect economic disruption.
- Both are treated as constant €/ha because no department-level marginal-cost
  curve is available in this repo; in reality both likely vary non-linearly
  with fire size and wildland-urban-interface proximity.

There used to be a *second*, duplicate copy of this table
(`ECONOMIC_FACTORS` in `wildfire_impact_calculator.py`). It has been removed;
`real_world_costs.FALLBACK_COSTS` is now the single source of truth.

## 3. Integration in the calculator

```python
if REAL_WORLD_COSTS_AVAILABLE:
    econ = get_department_costs(dept, use_api=True)
    cost_source = econ.get('source', 'Real-world data')
else:
    # Only reached if real_world_costs.py itself cannot be imported.
    econ = {'suppression': 1800.0, 'asset_value': 4500.0}
    cost_source = 'ASSUMPTION (real_world_costs module unavailable; conservative default, not sourced)'
```

`cost_source` in the output always says `ASSUMPTION (...)` for the current
implementation - it is intentionally not labelled "BDIFF historical" or
"calibrated," since neither is true.

## 4. Output example

```json
{
  "economic_value_avoided_euros": 1091.53,
  "suppression_cost_per_ha": 2500,
  "asset_value_per_ha": 8000,
  "cost_source": "ASSUMPTION (unsourced placeholder, Alpes-Maritimes)"
}
```

## Example scenarios (recomputed after the issue #6 risk-adjustment fix)

### Scenario 1: Alpes-Maritimes (Dept 06)
`calculate_impact(x_minutes_saved=15, t0_response_time=45, wind_speed_kmh=30, temperature_C=32, relative_humidity_pct=25, dept='06')`

```
Vegetation (data-derived from BDIFF): mixed_forest
Direct hectares saved:       11.95 ha
Risk-adjusted hectares:      0.10 ha
CO2 emissions prevented:     5.72 tCO2
Suppression cost/ha:         €2,500
Asset value/ha:              €8,000
Total economic value:        €1,091.53
Cost source:                 ASSUMPTION (unsourced placeholder, Alpes-Maritimes)
```

Note how small the risk-adjusted figure is here compared to the direct area:
at 45/30 minutes response time and 30 km/h wind, both the standard and early
scenarios are already well past the escape threshold, so their expected
final size (see `calculate_impact`'s docstring) is dominated by the
department's average escaped-fire size in both cases - early detection barely
changes the *expected* outcome. This replaces a previous example that showed
~35 ha / ~€369K for a similar scenario; that number came from a
double-counting bug in the risk-adjustment formula, fixed under
[issue #6](https://github.com/pyronear/impact-mesurement/issues/6).

### Scenario 2: Default department, moderate conditions
`calculate_impact(x_minutes_saved=20, t0_response_time=45, wind_speed_kmh=20, temperature_C=28, relative_humidity_pct=40, dept='default')`

```
Vegetation (data-derived from BDIFF): mixed_forest
Direct hectares saved:       7.59 ha
Risk-adjusted hectares:      8.01 ha
CO2 emissions prevented:     440.71 tCO2
Suppression cost/ha:         €1,800
Asset value/ha:              €4,500
Total economic value:        €50,480.80
Cost source:                 ASSUMPTION (conservative unsourced default)
```

## Enabling remote API calls

```bash
pip install requests
python3 -c "from real_world_costs import get_cost_fetcher; fetcher = get_cost_fetcher(); print(fetcher.get_eurostat_land_values())"
```

This fetches raw Eurostat/data.gouv.fr/World Bank data for inspection, but -
as noted above - none of it is currently wired up to adjust
`suppression`/`asset_value`. Wiring up a real adjustment requires a
documented, cited methodology, not just calling the API.

## Confidence levels

- **Suppression costs**: Low - unsourced assumption.
- **Asset values**: Low - unsourced assumption.
- **Overall**: Do not use these figures for financial decision-making
  without replacing them with a cited source (e.g. SDIS/DGSCGC budget
  reports, Cour des comptes wildfire cost reviews, ONF/DDT asset valuations,
  or FFA insurance-claims statistics, each with a year and method).

## Files involved

1. **`real_world_costs.py`** - cost data (`FALLBACK_COSTS`), fetch framework
   for external APIs, `get_department_costs()` convenience function.
2. **`wildfire_impact_calculator.py`** - imports `real_world_costs`, calls
   `get_department_costs()`, returns `cost_source` in results.
3. **`test_real_world_costs.py`** - demo script exercising the integration
   end-to-end.

## References

- **BDIFF**: Base de Données Incendies Forêts Français -
  https://www.data.gouv.fr/datasets/base-de-donnees-sur-les-incendies-de-forets-en-france-bdiff
  (21,141 fire records, 31,744 hectares burned, 2025). Contains no cost data.
- **Eurostat**: https://ec.europa.eu/eurostat/ (fetch framework only, not yet
  applied to costs).
- **IPCC Tier 2 / Pyronear CO2 Calculation**: per-vegetation tCO2/ha factors
  (`TCO2_PER_HA` in `wildfire_impact_calculator.py`, cited to
  `Pyronear_CO2_Calculation.pdf`), for the (separate, unmonetized) carbon
  accounting.

For questions about cost methodology, review `real_world_costs.py`'s module
docstring, or replace `FALLBACK_COSTS` with a properly cited dataset.
