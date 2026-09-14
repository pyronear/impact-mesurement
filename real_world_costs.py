"""
Real-world cost data fetcher for wildfire impact calculations.
Integrates with multiple data sources to get accurate suppression costs and asset values.

Note: This module is designed to work with external APIs (Eurostat, data.gouv.fr, World Bank).
For now, it provides a framework and ASSUMPTION-based placeholder data. API integration can
be enabled by:
  1. Installing requests: pip install requests
  2. Calling with use_api=True

IMPORTANT - sourcing status of FALLBACK_COSTS (issue #7): BDIFF
(Incendies.csv, the "historical" data referenced elsewhere in this project)
records fire location, cause, area burned, and casualty/building-damage
counts. It does **not** contain any suppression-cost or asset-value field, so
these figures cannot be described as "BDIFF historical" data - that label was
incorrect and has been removed. The values below are unsourced planning-level
assumptions (a plausible €/ha order of magnitude for French wildfire
suppression operations and rural/peri-urban asset density), not a cited
dataset. Until a real source is integrated (e.g. SDIS/DGSCGC budget reports,
Cour des comptes wildfire cost reviews, ONF/DDT asset valuations, or FFA
insurance-claims statistics, each with a year and method), treat every value
here as ``ASSUMPTION``.
"""

import json
from typing import Dict, Optional
from functools import lru_cache
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================================
# FALLBACK VALUES (used if APIs unavailable)
#
# ASSUMPTION - see module docstring: not derived from BDIFF or any other
# cited dataset. Kept as a single table (the duplicate ECONOMIC_FACTORS table
# that used to live in wildfire_impact_calculator.py has been removed; this
# is now the only place these numbers are defined).
# ============================================================================

FALLBACK_COSTS = {
    # Department: {suppression_cost_€/ha, asset_value_€/ha, source}
    '06': {'suppression': 2500, 'asset_value': 8000, 'source': 'ASSUMPTION (unsourced placeholder, Alpes-Maritimes)'},
    '13': {'suppression': 2200, 'asset_value': 6500, 'source': 'ASSUMPTION (unsourced placeholder, Bouches-du-Rhône)'},
    '11': {'suppression': 2000, 'asset_value': 5500, 'source': 'ASSUMPTION (unsourced placeholder, Aude)'},
    '83': {'suppression': 2300, 'asset_value': 7000, 'source': 'ASSUMPTION (unsourced placeholder, Var)'},
    '2A': {'suppression': 2400, 'asset_value': 7500, 'source': 'ASSUMPTION (unsourced placeholder, Corse-du-Sud)'},
    '2B': {'suppression': 2400, 'asset_value': 7500, 'source': 'ASSUMPTION (unsourced placeholder, Haute-Corse)'},
    'default': {'suppression': 1800, 'asset_value': 4500, 'source': 'ASSUMPTION (conservative unsourced default)'},
}

# ============================================================================
# REAL-WORLD DATA FETCHERS
# ============================================================================

class RealWorldCostFetcher:
    """Fetch real-world cost data from multiple sources."""
    
    def __init__(self, timeout: int = 10):
        """Initialize fetcher with API timeout."""
        self.timeout = timeout
        self.cache = {}
    
    @lru_cache(maxsize=32)
    def get_eurostat_land_values(self, country_code: str = 'FR') -> Optional[Dict]:
        """
        Framework for fetching land value data from Eurostat (EU Statistics).
        
        Uses the SDMX REST API endpoint for agricultural land prices.
        Requires: pip install requests
        
        Returns: Dict with region-level land values or None if unavailable
        """
        try:
            import requests
            
            # Eurostat SDMX API for land values
            # Dataset: apri_pt16 (Agricultural prices - land prices)
            url = (
                'https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/'
                f'apri_pt16?format=JSON&time=2023&geo={country_code}'
            )
            
            logger.info(f"Fetching Eurostat data for {country_code}...")
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            if 'data' in data and data['data']['dataSets']:
                dataset = data['data']['dataSets'][0]
                obs = dataset.get('observations', {})
                
                # Parse observations
                values = {}
                for key, val in obs.items():
                    if val:
                        values[key] = val[0]  # Get the first observation value
                
                logger.info(f"✓ Retrieved Eurostat data: {len(values)} observations")
                return {'source': 'Eurostat', 'values': values, 'year': 2023}
            
        except ImportError:
            logger.warning("Requests module not installed. Install with: pip install requests")
            logger.info("Using fallback cost values (unsourced assumption, see FALLBACK_COSTS docstring)")
        except Exception as e:
            logger.warning(f"Eurostat API error: {e}")
        
        return None
    
    @lru_cache(maxsize=32)
    def get_french_open_data(self) -> Optional[Dict]:
        """
        Framework for fetching French government open data from data.gouv.fr.
        
        Provides: Property values, insurance costs by commune
        Requires: pip install requests
        
        Returns: Dict with regional data or metadata about available datasets
        """
        try:
            import requests
            
            # Query data.gouv.fr CKAN API for fire-related datasets
            url = 'https://www.data.gouv.fr/api/1/datasets/?search=incendie&page_size=20'
            
            logger.info("Fetching French open data...")
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            datasets = data.get('data', [])
            
            logger.info(f"✓ Found {len(datasets)} French fire-related datasets")
            
            # Extract relevant datasets
            relevant = []
            for ds in datasets:
                if 'incendie' in ds.get('title', '').lower() or \
                   'fire' in ds.get('title', '').lower():
                    relevant.append({
                        'title': ds.get('title'),
                        'url': ds.get('page'),
                        'resources': len(ds.get('resources', []))
                    })
            
            return {'source': 'data.gouv.fr', 'datasets': relevant}
            
        except ImportError:
            logger.warning("Requests module not installed")
            logger.info("French open data datasets: BDIFF (already integrated), data.gouv.fr (needs requests)")
        except Exception as e:
            logger.warning(f"data.gouv.fr API error: {e}")
        
        return None
    
    @lru_cache(maxsize=32)
    def get_worldbank_land_values(self, country_code: str = 'FRA') -> Optional[Dict]:
        """
        Framework for fetching World Bank land and agricultural economic data.
        
        Requires: pip install requests
        Returns: Dict with regional economic indicators or None
        """
        try:
            import requests
            
            # World Bank Open Data API
            url = (
                f'https://api.worldbank.org/v2/country/{country_code}/'
                'indicators/NV.AGR.TOTL.ZS?format=json'
            )
            
            logger.info("Fetching World Bank economic data...")
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            if len(data) > 1 and data[1]:
                records = data[1]
                logger.info(f"✓ Retrieved World Bank data: {len(records)} years")
                return {
                    'source': 'World Bank',
                    'data': records,
                    'indicator': 'Agriculture % of GDP'
                }
            
        except ImportError:
            logger.warning("Requests module not installed")
        except Exception as e:
            logger.warning(f"World Bank API error: {e}")
        
        return None
    
    def get_combined_costs(self, dept: str, use_api: bool = True) -> Dict:
        """
        Get costs for a department.

        Parameters:
        -----------
        dept : str
            French department code
        use_api : bool
            Reserved for future use once a real API-based adjustment is
            wired up (see note below). Currently has no effect: no API
            source is applied to these numbers.

        Returns:
        --------
        Dict with {suppression, asset_value, source}

        NOTE (issue #11): this function previously called
        ``get_eurostat_land_values()`` and a (now removed) unsourced
        ``get_insurance_data()`` helper containing two sets of hardcoded
        multipliers - 1.8/1.4/1.0 by risk class, and 1.5/1.3/1.4 by
        department - and only appended text like " + insurance adjustment
        (factor: 1.5)" to the ``source`` string without ever multiplying
        ``suppression`` or ``asset_value`` by that factor. That was
        misleading: it made the output look risk-adjusted when the numbers
        were untouched. Both multiplier tables have been deleted rather than
        silently kept unused. If department-specific cost adjustments are
        wanted, they need a real, cited source and must actually be applied
        to the returned values, not just described in ``source``.
        """
        # FALLBACK_COSTS is currently the only implemented data source; see
        # its docstring/comments for sourcing status (all ASSUMPTION).
        return FALLBACK_COSTS.get(dept, FALLBACK_COSTS['default']).copy()
    
    def get_cost_metadata(self) -> Dict:
        """
        Return metadata about cost sources and methodologies.
        
        Useful for transparency and audit trails.
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'primary_source': 'ASSUMPTION (unsourced placeholder values, see module docstring)',
            'secondary_sources': [
                'Eurostat (EU land values) - fetch framework only, not yet applied to costs',
                'data.gouv.fr (French open data) - fetch framework only, not yet applied to costs',
                'World Bank (economic indicators) - fetch framework only, not yet applied to costs',
            ],
            'methodology': 'Static per-department placeholder table (FALLBACK_COSTS); no API-derived adjustment is currently applied',
            'update_frequency': 'Manual (no automated update pipeline exists)',
            'confidence': {
                'suppression_costs': 'Low (unsourced assumption)',
                'asset_values': 'Low (unsourced assumption)',
                'total': 'Low (unsourced placeholder values; do not use for financial decisions without replacing with a cited source)'
            },
            'api_integration': 'Available when requests module is installed'
        }


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_cost_fetcher = None

def get_cost_fetcher() -> RealWorldCostFetcher:
    """Get or create the singleton cost fetcher."""
    global _cost_fetcher
    if _cost_fetcher is None:
        _cost_fetcher = RealWorldCostFetcher()
    return _cost_fetcher


def get_department_costs(dept: str, use_api: bool = True) -> Dict:
    """
    Convenience function to get costs for a department.
    
    Parameters:
    -----------
    dept : str
        French department code
    use_api : bool
        Whether to use API enhancements
    
    Returns:
    --------
    Dict with {suppression, asset_value, source}
    """
    fetcher = get_cost_fetcher()
    return fetcher.get_combined_costs(dept, use_api=use_api)


if __name__ == '__main__':
    # Test the fetcher
    logging.basicConfig(level=logging.INFO)
    
    fetcher = RealWorldCostFetcher()
    
    print("\n" + "="*70)
    print("REAL-WORLD COST DATA FETCHER - TEST")
    print("="*70)
    
    # Test individual sources
    print("\n1. Testing Eurostat API...")
    eurostat_data = fetcher.get_eurostat_land_values()
    if eurostat_data:
        print(f"   ✓ Success: {eurostat_data['source']}")
    else:
        print("   ✗ Failed (expected - may need auth)")
    
    print("\n2. Testing French Open Data...")
    french_data = fetcher.get_french_open_data()
    if french_data:
        print(f"   ✓ Success: Found {len(french_data.get('datasets', []))} datasets")
    else:
        print("   ✗ Failed")
    
    print("\n3. Testing World Bank API...")
    wb_data = fetcher.get_worldbank_land_values()
    if wb_data:
        print(f"   ✓ Success: {wb_data['source']}")
    else:
        print("   ✗ Failed")
    
    print("\n4. Testing Combined Costs for Department 06...")
    costs_06 = fetcher.get_combined_costs('06', use_api=False)
    print(f"   Suppression: €{costs_06['suppression']}/ha")
    print(f"   Asset Value: €{costs_06['asset_value']}/ha")
    print(f"   Total Value: €{costs_06['suppression'] + costs_06['asset_value']}/ha")
    print(f"   Source: {costs_06['source']}")
    
    print("\n5. Cost Metadata...")
    metadata = fetcher.get_cost_metadata()
    print(f"   Primary: {metadata['primary_source']}")
    print(f"   Secondary sources: {len(metadata['secondary_sources'])}")
    print(f"   Confidence: {metadata['confidence']['total']}")
    
    print("\n" + "="*70 + "\n")
