"""
Wildfire Impact Calculator: Early Detection Value Assessment
Combines physics model (elliptical fire spread) with real BDIFF data from France
Calculates avoided impacts: hectares, CO2, economic value, building protection

Real-world cost integration: Uses actual fire suppression costs and asset values
from multiple sources (BDIFF historical data, Eurostat, data.gouv.fr)

ASSUMPTIONS & LIMITATIONS
--------------------------
This model mixes a small number of values that are genuinely derived from the
BDIFF dataset shipped in this repo (``Incendies.csv``) with several constants
that are *working assumptions*, not calibrated or sourced figures. BDIFF only
records the final burned area, department, commune, cause ("Nature") and
casualty/building-damage counts per fire - it has **no** rate-of-spread,
suppression-cost, asset-value, or initial-attack-size field. Anywhere a
constant cannot be derived from data actually present in this repository, it
is labelled ``ASSUMPTION`` in the comment/docstring next to it so that this is
never mistaken for a calibrated or peer-reviewed value. See the per-function
docstrings below for the specific caveats, and the project README for a
consolidated list. (The per-vegetation CO2 factors, ``TCO2_PER_HA``, are the
exception: they are cited to ``Pyronear_CO2_Calculation.pdf`` and are not
covered by this note.)
"""

import math
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Tuple, List

# Import real-world cost fetcher
try:
    from real_world_costs import get_department_costs, get_cost_fetcher
    REAL_WORLD_COSTS_AVAILABLE = True
except ImportError:
    REAL_WORLD_COSTS_AVAILABLE = False

# ============================================================================
# STEP 1: SPREAD RATE DATABASE
#
# ASSUMPTION - NOT calibrated against BDIFF: BDIFF has no rate-of-spread
# field, only final burned area, so these head/back/flank rates of spread
# (m/min) cannot be fitted to this dataset. The relative shape (head fastest,
# flank ~0.3x head, back ~0.15x head) loosely follows the length-to-breadth
# elongation ratios discussed for wind-driven fires by Alexander (1985) and
# Anderson (1983), and the vegetation ordering (grassland < mixed forest <
# pine < garrigue/maquis for a given wind class) follows the general ranking
# of fuel types in Rothermel (1972) fuel models, but the exact numeric values
# below are illustrative placeholders, not a validated fit. They MUST be
# replaced with locally calibrated values (e.g. from Prométhée or INRAE fire
# spread records) before being used for anything beyond a rough order-of-
# magnitude demonstration.
# ============================================================================

SPREAD_RATES = {
    # Vegetation type: {wind_speed_category: (R_head, R_back, R_flank) in m/min}
    # ASSUMPTION: values are illustrative, see module docstring above.
    'pine_forest_dry': {
        'low': (8.0, 1.2, 2.4),
        'moderate': (12.0, 2.0, 4.0),
        'high': (18.0, 2.7, 6.0),
    },
    'garrigue_maquis': {
        'low': (10.0, 1.5, 3.0),
        'moderate': (16.0, 2.4, 4.8),
        'high': (24.0, 3.6, 7.2),
    },
    'grassland': {
        'low': (5.0, 0.8, 1.5),
        'moderate': (8.0, 1.2, 2.4),
        'high': (12.0, 1.8, 3.6),
    },
    'mixed_forest': {
        'low': (6.0, 0.9, 1.8),
        'moderate': (10.0, 1.5, 3.0),
        'high': (14.0, 2.1, 4.2),
    }
}

# CO2 emitted per hectare burned, by vegetation type (tCO2/ha).
# Source: Pyronear_CO2_Calculation.pdf at the repo root (IPCC Tier 2 approach,
# Emissions = A × MB × Cf × EF_CO2, with CORINE Land Cover classes).
# Values are the midpoints of the ranges given in that document, except
# pine_forest_dry which uses its worked example (85 t/ha × 0.52 × 1.58).
# Gross emissions only: post-fire regrowth and soil carbon are not modelled.
TCO2_PER_HA = {
    'pine_forest_dry': 69.8,   # CORINE 3.1.2 coniferous forest, range 50-90
    'garrigue_maquis': 25.0,   # CORINE 3.2.3 sclerophyllous vegetation, range 15-35
    'grassland': 10.0,         # CORINE 3.2.1 natural grassland, range 5-15
    'mixed_forest': 55.0,      # CORINE 3.1.3 mixed forest, range 40-70
}

# NOTE: Suppression cost and asset value per hectare used to live here as a
# second, duplicate ``ECONOMIC_FACTORS`` table (see issue #7). That table has
# been removed - ``real_world_costs.FALLBACK_COSTS`` is now the single source
# of truth for these figures, and it is clearly labelled as an assumption
# rather than a "BDIFF historical" value (BDIFF contains no cost data).
#
# Historical/observed escape fire sizes per department also used to live here
# as a hardcoded ``HISTORICAL_ESCAPE_SIZES_HA`` dict that was never actually
# computed from the loaded ``Incendies.csv`` data (see issue #5). It has been
# replaced by ``WildfireImpactCalculator.get_avg_escaped_fire_size_ha()``,
# which computes the mean size of "escaped" fires (>= the containment
# threshold used by ``calculate_escape_probability``) per department directly
# from the BDIFF dataframe when one is loaded, with a documented, clearly
# labelled fallback when it is not.

# Fire size (ha) at which a fire is considered to have escaped initial
# attack/containment. Shared by ``calculate_escape_probability`` (as the base
# of its sigmoid) and ``get_avg_escaped_fire_size_ha`` (as the cutoff used to
# select "escaped" fires from BDIFF). ASSUMPTION: 3 ha is a commonly cited
# rule-of-thumb initial-attack containment size, not a value fitted to this
# dataset (BDIFF has no initial-attack-size field to fit against).
ESCAPE_THRESHOLD_HA = 3.0

# Minimum number of BDIFF fires at/above ESCAPE_THRESHOLD_HA required before a
# department-specific average escaped-fire size is used; below this the
# national average is used instead to avoid over-fitting to a handful of
# records.
MIN_ESCAPED_FIRES_FOR_DEPT_ESTIMATE = 5

# Fallback dominant vegetation type per department, used only when no BDIFF
# dataframe is loaded (see ``get_vegetation_type``). Derived from the same
# 2025 BDIFF snapshot shipped as ``Incendies.csv``: for each department we
# summed the "Surface forêt (m2)", "Surface maquis garrigues (m2)", and
# "Autres surfaces naturelles hors forêt (m2)" + "Surfaces agricoles (m2)"
# columns across all 2025 fire records and picked the largest bucket
# (forest -> mixed_forest, maquis/garrigue -> garrigue_maquis, other
# natural/agricultural -> grassland). This is a proxy for land cover based on
# *what burned* in one calendar year, not a land-cover survey such as CORINE;
# it is reproducible from data in this repo but should be treated as a
# starting point, not ground truth. 'pine_forest_dry' is never chosen
# automatically because BDIFF does not distinguish conifer from broadleaf/
# mixed forest - pass ``vegetation_type='pine_forest_dry'`` explicitly to
# ``calculate_impact`` if it is known to apply.
DEPARTMENT_VEGETATION_FALLBACK = {
    '06': 'mixed_forest', '13': 'mixed_forest', '11': 'mixed_forest',
    '83': 'mixed_forest', '2A': 'mixed_forest', '2B': 'garrigue_maquis',
    '30': 'garrigue_maquis', '34': 'garrigue_maquis', '66': 'grassland',
    '84': 'grassland',
    'default': 'mixed_forest',
}

# Columns in Incendies.csv used to estimate dominant vegetation per
# department, grouped into the vegetation buckets used by this model.
_VEGETATION_SURFACE_COLUMNS = {
    'mixed_forest': ['Surface forêt (m2)'],
    'garrigue_maquis': ['Surface maquis garrigues (m2)'],
    'grassland': ['Autres surfaces naturelles hors forêt (m2)', 'Surfaces agricoles (m2)'],
}

# ============================================================================
# STEP 2: CORE IMPACT CALCULATION ENGINE
# ============================================================================

class WildfireImpactCalculator:
    """Calculate avoided impacts from early wildfire detection."""
    
    def __init__(self, bdiff_csv_path: str = None):
        """Initialize with optional BDIFF dataset for calibration."""
        self.bdiff_df = None
        self._dept_vegetation_cache = None
        self._dept_escape_size_cache = None
        if bdiff_csv_path:
            self.load_bdiff_data(bdiff_csv_path)
    
    def load_bdiff_data(self, path: str):
        """Load and parse BDIFF fire dataset."""
        self.bdiff_df = pd.read_csv(path, encoding='utf-8', sep=';', skiprows=2)
        self.bdiff_df['hectares'] = pd.to_numeric(
            self.bdiff_df['Surface parcourue (m2)'], errors='coerce'
        ) / 10000
        # Invalidate caches derived from the previous dataset, if any.
        self._dept_vegetation_cache = None
        self._dept_escape_size_cache = None
        print(f"✓ Loaded {len(self.bdiff_df)} fire records from BDIFF")
        print(f"  Mean fire size: {self.bdiff_df['hectares'].mean():.2f} ha")
        print(f"  Max fire size: {self.bdiff_df['hectares'].max():.0f} ha")
    
    def get_wind_category(self, wind_speed_kmh: float) -> str:
        """
        Classify wind speed into a spread-rate category.

        ASSUMPTION: the 15 / 30 km/h cut points are working thresholds, not
        drawn from an official wind or fire-danger classification (they do
        not correspond exactly to Beaufort force boundaries, which fall at
        ~12/20/29/39/50 km/h). They are assumed to represent a 10 m open-
        terrain average wind speed. Replace with a documented scale (e.g.
        Météo France fire-danger wind classes) when one is adopted.
        """
        if wind_speed_kmh < 15:
            return 'low'
        elif wind_speed_kmh < 30:
            return 'moderate'
        else:
            return 'high'
    
    def _compute_department_vegetation_from_bdiff(self) -> Dict[str, str]:
        """
        Compute the dominant vegetation bucket per department from the
        loaded BDIFF dataframe's burned-surface composition columns.

        Method: for every department, sum the "Surface forêt (m2)",
        "Surface maquis garrigues (m2)", "Autres surfaces naturelles hors
        forêt (m2)" and "Surfaces agricoles (m2)" columns across all loaded
        fire records, and assign the vegetation bucket whose columns sum to
        the largest share. This is a data-derived proxy for land cover (what
        actually burned in the loaded dataset), not a land-cover survey; it
        depends on sample size and will be less reliable for departments with
        few recorded fires.
        """
        df = self.bdiff_df
        result = {}
        if df is None or 'Département' not in df.columns:
            return result

        bucket_cols = {}
        for bucket, cols in _VEGETATION_SURFACE_COLUMNS.items():
            present = [c for c in cols if c in df.columns]
            if present:
                bucket_cols[bucket] = present

        if not bucket_cols:
            return result

        numeric = {}
        for bucket, cols in bucket_cols.items():
            numeric[bucket] = sum(
                pd.to_numeric(df[c], errors='coerce').fillna(0.0) for c in cols
            )

        composition = pd.DataFrame(numeric)
        composition['Département'] = df['Département'].values
        totals = composition.groupby('Département').sum()
        totals = totals[totals.sum(axis=1) > 0]

        for dept, row in totals.iterrows():
            result[str(dept)] = row.idxmax()

        return result

    def get_vegetation_type(self, dept: str, fire_nature: str = None) -> str:
        """
        Map a French department to a dominant vegetation type.

        When a BDIFF dataframe is loaded, the dominant vegetation bucket is
        computed per department from the actual burned-surface composition
        columns in that dataset (see
        ``_compute_department_vegetation_from_bdiff``). When no BDIFF data is
        loaded, a small static fallback table derived from the same 2025
        snapshot is used instead (``DEPARTMENT_VEGETATION_FALLBACK``). Both
        paths are documented at the top of this module and are proxies for
        land cover, not a CORINE Land Cover classification.

        ``fire_nature`` corresponds to BDIFF's "Nature" column, which records
        the fire's *ignition cause* (e.g. "Accidentelle", "Malveillance",
        "Naturelle") - not a fuel/vegetation type. It is accepted here for API
        compatibility and potential future use, but it cannot currently
        inform vegetation classification because BDIFF does not link cause to
        fuel type, so it has no effect on the result. (BDIFF's "Type de
        peuplement" stand-type column, which might be a better fit, is empty
        for >95% of 2025 records and is therefore not usable either.)
        """
        if self.bdiff_df is not None:
            if self._dept_vegetation_cache is None:
                self._dept_vegetation_cache = self._compute_department_vegetation_from_bdiff()
            veg = self._dept_vegetation_cache.get(dept)
            if veg is not None:
                return veg

        return DEPARTMENT_VEGETATION_FALLBACK.get(dept, DEPARTMENT_VEGETATION_FALLBACK['default'])
    
    def calculate_fire_area(self, t_minutes: float, R_head: float, 
                            R_back: float, R_flank: float) -> float:
        """
        Calculate elliptical fire area at time t.
        
        Formula: Area(t) = (π/2) × R_flank × (R_head + R_back) × t²

        This is the classic constant-rate elliptical fire-growth model
        (Van Wagner 1969, "A simple fire-growth model"; formalized with
        length-to-breadth ratios by Anderson 1983 and Alexander 1985) - not
        Rothermel (1972), which describes the rate-of-spread itself rather
        than the resulting ellipse geometry over time. Earlier versions of
        this project's documentation incorrectly attributed the ellipse
        model to Rothermel; that has been corrected.

        LIMITATION: the model assumes steady-state spread at the given rates
        from t=0 (ignition), with no build-up/acceleration phase. Real fires
        typically accelerate from ignition towards their steady-state rate of
        spread over the first tens of minutes (see e.g. Cheney & Gould 1995
        acceleration curves), so this formula overstates area in the first
        few minutes after ignition and, transitively, overstates the escape
        probability computed from that early area. No acceleration phase is
        implemented; this is a known simplification, not a validated result.

        Returns: Area in hectares
        """
        if t_minutes <= 0:
            return 0.0
        area_m2 = (math.pi / 2) * R_flank * (R_head + R_back) * (t_minutes ** 2)
        return area_m2 / 10000  # Convert m² to hectares
    
    def calculate_escape_probability(self, area_ha: float, 
                                     wind_speed_kmh: float) -> float:
        """
        Sigmoid escape probability based on fire size.

        p = 1 / (1 + exp(-(area_ha - threshold_ha)))
        threshold_ha = ESCAPE_THRESHOLD_HA + 0.1 * max(0, wind_speed_kmh - 20)

        ASSUMPTION - not fitted to BDIFF: this project's dataset only records
        the *final* burned area of each fire, not the area at the time
        initial attack was made, so a logistic regression of
        P(final size > X | size at attack) - the fit this docstring
        previously and incorrectly claimed was "empirical, calibrated to
        containment thresholds" - cannot be performed with the data available
        here. All three constants below are working assumptions, not
        calibrated parameters:
          - ``ESCAPE_THRESHOLD_HA`` (3.0 ha): a commonly cited rule-of-thumb
            initial-attack containment size.
          - The unit sigmoid slope (probability rises from ~0.27 to ~0.73
            within +/-1 ha of the threshold): chosen only to make the curve
            change quickly near the threshold, not derived from data.
          - The wind adjustment (+0.1 ha of threshold per km/h of wind above
            20 km/h): chosen to make higher wind reduce the effective margin
            before escape, not derived from data.
        Until a real initial-attack outcome dataset is available (or a
        published initial-attack success model is adopted and cited), treat
        this function's output as illustrative, not predictive.
        """
        # Base threshold adjusted by wind speed
        threshold_ha = ESCAPE_THRESHOLD_HA + (0.1 * max(0, wind_speed_kmh - 20))
        
        # Sigmoid function: probability increases sharply after threshold
        try:
            p_escape = 1.0 / (1.0 + math.exp(-(area_ha - threshold_ha)))
        except OverflowError:
            p_escape = 1.0 if area_ha > threshold_ha else 0.0
        
        return p_escape

    def get_avg_escaped_fire_size_ha(self, dept: str) -> float:
        """
        Estimate the average size of an "escaped" fire (area >=
        ``ESCAPE_THRESHOLD_HA``) for a department, computed from the loaded
        BDIFF dataframe.

        Method: filter loaded fires to hectares >= ``ESCAPE_THRESHOLD_HA``,
        group by department, and take the mean. If a department has fewer
        than ``MIN_ESCAPED_FIRES_FOR_DEPT_ESTIMATE`` such fires (or no BDIFF
        data is loaded at all), falls back to the national mean across all
        departments' escaped fires in the loaded dataset, and finally to a
        hardcoded default only if no BDIFF data is available whatsoever.

        This replaces the previously hardcoded, unsourced
        ``HISTORICAL_ESCAPE_SIZES_HA`` dict (issue #5) with a value actually
        computed from ``Incendies.csv``. It is still only a proxy: it is the
        mean size of fires that *did* escape in the loaded year(s) of BDIFF
        data, used as an estimate of "how big a fire gets if it escapes
        containment" for the risk-adjustment in ``calculate_impact``.
        """
        fallback_default = 150.0  # ASSUMPTION, used only with zero BDIFF data.

        if self.bdiff_df is None or 'hectares' not in self.bdiff_df.columns:
            return fallback_default

        if self._dept_escape_size_cache is None:
            df = self.bdiff_df
            escaped = df[df['hectares'] >= ESCAPE_THRESHOLD_HA]
            cache = {
                '__national_mean__': (
                    float(escaped['hectares'].mean()) if len(escaped) > 0 else fallback_default
                )
            }
            if 'Département' in escaped.columns and len(escaped) > 0:
                counts = escaped.groupby('Département')['hectares'].count()
                means = escaped.groupby('Département')['hectares'].mean()
                for d in means.index:
                    if counts[d] >= MIN_ESCAPED_FIRES_FOR_DEPT_ESTIMATE:
                        cache[str(d)] = float(means[d])
            self._dept_escape_size_cache = cache

        cache = self._dept_escape_size_cache
        if dept in cache:
            return cache[dept]
        return cache.get('__national_mean__', fallback_default)

    def calculate_impact(self, 
                        x_minutes_saved: float,
                        t0_response_time: float = 45,
                        wind_speed_kmh: float = 25,
                        temperature_C: float = 28,
                        relative_humidity_pct: float = 35,
                        dept: str = 'default',
                        vegetation_type: str = None) -> Dict:
        """
        Main calculation: Impact of saving x minutes of response time.
        
        Parameters:
        -----------
        x_minutes_saved : float
            Minutes saved by early detection
        t0_response_time : float
            Standard firefighter response time (minutes from ignition)
        wind_speed_kmh : float
            Average wind speed during fire
        temperature_C : float
            Temperature (for validation)
        relative_humidity_pct : float
            Relative humidity (for validation)
        dept : str
            French department code
        vegetation_type : str
            Override vegetation classification

        Risk-adjusted hectares methodology (issue #6):
        -----------------------------------------------
        For each scenario (standard vs. early response) we compute an
        expected fire size that mixes the "contained" outcome (the
        deterministic ellipse area at that response time) and the "escaped"
        outcome (the department's average escaped-fire size), weighted by
        the escape probability at that scenario's area:

            E[size] = p_escape * avg_escaped_ha + (1 - p_escape) * area

        ``effective_ha_saved`` is then the difference between the standard
        and early-detection scenarios' expected sizes. This avoids the
        previous formula's double counting, which added the deterministic
        area difference *and* a separate escape-probability term on top,
        even though the deterministic area is already part of the escaped
        fire's eventual size.
        
        Returns:
        --------
        Dict with avoided impacts
        """
        
        # Step 1: Determine spread rates
        if vegetation_type is None:
            vegetation_type = self.get_vegetation_type(dept)
        
        wind_cat = self.get_wind_category(wind_speed_kmh)
        rates = SPREAD_RATES.get(vegetation_type, SPREAD_RATES['mixed_forest'])
        R_head, R_back, R_flank = rates[wind_cat]
        
        # Step 2: Calculate areas
        area_standard = self.calculate_fire_area(t0_response_time, R_head, R_back, R_flank)
        area_early = self.calculate_fire_area(
            max(0, t0_response_time - x_minutes_saved), R_head, R_back, R_flank
        )
        delta_area_initial = area_standard - area_early
        
        # Step 3: Apply escape threshold factor
        p_escape_std = self.calculate_escape_probability(area_standard, wind_speed_kmh)
        p_escape_early = self.calculate_escape_probability(area_early, wind_speed_kmh)
        delta_p_escape = max(0, p_escape_std - p_escape_early)
        
        # Average escaped fire size for this department, derived from BDIFF
        # when available (see get_avg_escaped_fire_size_ha docstring).
        avg_escaped_ha = self.get_avg_escaped_fire_size_ha(dept)
        
        # Risk-adjusted hectares saved: expected-value derivation (issue #6).
        # E[size] = p_escape * avg_escaped_ha + (1 - p_escape) * area, for
        # each scenario; effective_ha_saved is the difference between the
        # standard and early-detection scenarios' expected sizes. See the
        # "Risk-adjusted hectares methodology" note in this method's
        # docstring for why this replaces the previous
        # `delta_area_initial + delta_p_escape * avg_escaped_ha` formula,
        # which double-counted the deterministic area.
        expected_size_standard = (
            p_escape_std * avg_escaped_ha + (1 - p_escape_std) * area_standard
        )
        expected_size_early = (
            p_escape_early * avg_escaped_ha + (1 - p_escape_early) * area_early
        )
        effective_ha_saved = expected_size_standard - expected_size_early
        
        # Step 4: Convert to impacts
        tCO2_per_ha = TCO2_PER_HA.get(vegetation_type, TCO2_PER_HA['mixed_forest'])
        tCO2_saved = effective_ha_saved * tCO2_per_ha
        
        # Economics - use real_world_costs.py as the single source of truth
        # for suppression cost / asset value per hectare (see issue #7: the
        # second, duplicate ECONOMIC_FACTORS table that used to live in this
        # file has been removed).
        if REAL_WORLD_COSTS_AVAILABLE:
            econ = get_department_costs(dept, use_api=True)
            cost_source = econ.get('source', 'Real-world data')
        else:
            # Only reached if real_world_costs.py itself cannot be imported.
            # ASSUMPTION: a single conservative default, not sourced.
            econ = {'suppression': 1800.0, 'asset_value': 4500.0}
            cost_source = 'ASSUMPTION (real_world_costs module unavailable; conservative default, not sourced)'
        
        supp_cost = econ['suppression']
        asset_val = econ['asset_value']
        # Methodology note (issue #8): euros_saved = ha * (suppression_cost +
        # asset_value) per hectare.
        #   - Included: an assumed suppression cost per hectare, plus a full
        #     loss of an assumed average asset value per hectare, for every
        #     effective hectare saved.
        #   - Excluded: ecosystem-service value and any carbon price (CO2 is
        #     reported separately, unmonetized, as tco2_emissions_prevented),
        #     insurance claims-handling costs, and indirect economic
        #     disruption (business interruption, tourism, etc.).
        #   - Why linear: no department-level marginal-cost curve is
        #     available in this repo, so €/ha is treated as constant; in
        #     reality both suppression cost and asset density likely vary
        #     non-linearly with fire size and proximity to the
        #     wildland-urban interface.
        #   - The €/ha figures themselves are assumptions, not a cited
        #     dataset - see real_world_costs.FALLBACK_COSTS's docstring.
        euros_saved = effective_ha_saved * (supp_cost + asset_val)
        
        # Buildings protected: ASSUMPTION, not derived from BD TOPO or
        # wildland-urban-interface (WUI) statistics (issue #9). The 1.0 vs
        # 0.3 buildings/ha split is a rough planning-level guess meant to
        # differentiate historically higher-WUI-density Mediterranean
        # departments (06, 13, 83) from the rest, applied uniformly to every
        # effective hectare saved - including forest interior far from any
        # building - which likely overstates exposure for large fires.
        # Replace with real building-density data (e.g. BD TOPO buildings
        # intersected with historical fire perimeters) before relying on this
        # for anything beyond an illustrative order of magnitude.
        buildings_density = 1.0 if dept in ['06', '13', '83'] else 0.3
        buildings_saved = max(0, int(effective_ha_saved * buildings_density))
        
        return {
            'minutes_saved': x_minutes_saved,
            'vegetation_type': vegetation_type,
            'wind_category': wind_cat,
            'spread_rates_m_min': {'head': R_head, 'back': R_back, 'flank': R_flank},
            'direct_area_saved_ha': round(delta_area_initial, 3),
            'escape_probability_avoided': round(delta_p_escape, 4),
            'risk_adjusted_ha_saved': round(effective_ha_saved, 3),
            'tco2_emissions_prevented': round(tCO2_saved, 2),
            'economic_value_avoided_euros': round(euros_saved, 2),
            'buildings_protected': buildings_saved,
            'response_time_standard_min': t0_response_time,
            'response_time_early_min': max(0, t0_response_time - x_minutes_saved),
            'suppression_cost_per_ha': supp_cost,
            'asset_value_per_ha': asset_val,
            'cost_source': cost_source,
        }
    
    def scenario_analysis(self, minutes_saved_list: List[float] = None,
                         dept: str = 'default', 
                         vegetation_type: str = None) -> pd.DataFrame:
        """
        Run impact calculation across multiple early detection scenarios.
        
        Parameters:
        -----------
        minutes_saved_list : List[float]
            Scenarios to evaluate (e.g., [5, 10, 15, 20, 30])
        dept : str
            Department code
        vegetation_type : str
            Override vegetation type
        
        Returns:
        --------
        DataFrame with results for each scenario
        """
        if minutes_saved_list is None:
            minutes_saved_list = [5, 10, 15, 20, 30]
        
        results = []
        for x_min in minutes_saved_list:
            impact = self.calculate_impact(
                x_minutes_saved=x_min,
                t0_response_time=45,
                wind_speed_kmh=25,
                dept=dept,
                vegetation_type=vegetation_type
            )
            results.append({
                'Minutes Saved': x_min,
                'Ha Saved (Direct)': impact['direct_area_saved_ha'],
                'Ha Saved (Risk-Adjusted)': impact['risk_adjusted_ha_saved'],
                'tCO2 Avoided': impact['tco2_emissions_prevented'],
                '€ Value Avoided': impact['economic_value_avoided_euros'],
                'Buildings Protected': impact['buildings_protected'],
            })
        
        return pd.DataFrame(results)


# ============================================================================
# STEP 5: REAL FIRE ANALYSIS (using BDIFF data)
# ============================================================================

def analyze_real_fires(bdiff_csv_path: str):
    """Analyze BDIFF dataset and calculate what early detection could have saved."""
    
    df = pd.read_csv(bdiff_csv_path, encoding='utf-8', sep=';', skiprows=2)
    df['hectares'] = pd.to_numeric(df['Surface parcourue (m2)'], errors='coerce') / 10000
    
    # Filter to moderate/large fires where early detection matters
    large_fires = df[df['hectares'] >= 5].copy()
    
    print("\n" + "="*70)
    print("BDIFF DATASET ANALYSIS")
    print("="*70)
    print(f"\nTotal fires in 2025: {len(df):,}")
    print(f"Fires ≥5 hectares: {len(large_fires):,}")
    print(f"\nFires by Department (Top 10):")
    print(df['Département'].value_counts().head(10))
    
    # Calculate potential impact if detection saved 15 minutes on large fires
    calc = WildfireImpactCalculator(bdiff_csv_path)
    
    print("\n" + "="*70)
    print("EARLY DETECTION IMPACT SCENARIOS")
    print("="*70)
    
    # Mediterranean (high-risk) vs Continental regions
    test_depts = ['06', '13', '11', '63', '71']  # Mix of high and low-risk
    
    for dept in test_depts:
        veg_type = calc.get_vegetation_type(dept)
        print(f"\n--- Department {dept} ({veg_type}) ---")
        
        results_df = calc.scenario_analysis(
            minutes_saved_list=[10, 15, 20],
            dept=dept,
            vegetation_type=veg_type
        )
        print(results_df.to_string(index=False))
    
    return df, calc


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == '__main__':
    bdiff_path = '/Users/doconnor/Desktop/untitled folder/Incendies.csv'
    
    # Analyze real fires
    df_fires, calculator = analyze_real_fires(bdiff_path)
    
    print("\n" + "="*70)
    print("EXAMPLE: Single Fire Impact Calculation")
    print("="*70)
    
    # Example: Early detection scenario
    impact = calculator.calculate_impact(
        x_minutes_saved=15,
        t0_response_time=45,
        wind_speed_kmh=35,  # High wind (aggressive fire)
        dept='06',  # Alpes-Maritimes (Mediterranean, high-risk)
        vegetation_type='garrigue_maquis'
    )
    
    print("\n📍 Scenario: Mediterranean fire (Dept 06, Garrigue)")
    print(f"   Early detection saves: 15 minutes")
    print(f"   Standard response time: 45 minutes")
    print(f"   Wind speed: 35 km/h (HIGH)")
    print(f"\n✅ AVOIDED IMPACTS:")
    print(f"   • Direct area saved: {impact['direct_area_saved_ha']:.2f} ha")
    print(f"   • Risk-adjusted saved: {impact['risk_adjusted_ha_saved']:.2f} ha")
    print(f"   • CO2 prevented: {impact['tco2_emissions_prevented']:.0f} tCO2")
    print(f"   • Economic value: €{impact['economic_value_avoided_euros']:,.0f}")
    print(f"   • Buildings protected: {impact['buildings_protected']}")
