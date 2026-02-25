"""
Open Food Facts API integration.
Searches the OFF API and maps results to our internal food model.
Successfully fetched foods are cached locally via storage.save_food().
"""

import json

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

from models import make_food
import storage

OFF_SEARCH_URL = 'https://world.openfoodfacts.org/cgi/search.pl'
OFF_PRODUCT_URL = 'https://world.openfoodfacts.org/api/v0/product/{barcode}.json'

# Fields to request from OFF to keep response small
OFF_FIELDS = (
    'code,product_name,brands,nutriments,'
    'serving_size,serving_quantity'
)


def search_foods(query, max_results=20):
    """
    Search Open Food Facts for foods matching query.
    Returns list of food dicts (our model). Also caches each result locally.
    Falls back to local cache results on network failure.
    """
    # Always include local cache results first
    local = storage.search_local_foods(query)
    local_ids = {f['id'] for f in local}

    if not _HAS_REQUESTS:
        return local

    params = {
        'search_terms': query,
        'search_simple': 1,
        'action': 'process',
        'json': 1,
        'page_size': max_results,
        'fields': OFF_FIELDS,
        'lc': 'en',
    }

    try:
        resp = requests.get(OFF_SEARCH_URL, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return local

    foods = []
    for product in data.get('products', []):
        food = _parse_off_product(product)
        if food is None:
            continue
        storage.save_food(food)
        if food['id'] not in local_ids:
            foods.append(food)
            local_ids.add(food['id'])

    # Local results first (previously used foods), then API results
    return local + foods


def fetch_by_barcode(barcode):
    """
    Fetch a single product by barcode. Returns food dict or None.
    """
    if not _HAS_REQUESTS:
        return None
    try:
        resp = requests.get(OFF_PRODUCT_URL.format(barcode=barcode), timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    if data.get('status') != 1:
        return None

    food = _parse_off_product(data.get('product', {}))
    if food:
        storage.save_food(food)
    return food


def _parse_off_product(product):
    """
    Parse an Open Food Facts product dict into our food model.
    Returns None if essential data (name, calories) is missing.
    """
    name = product.get('product_name', '').strip()
    if not name:
        return None

    n = product.get('nutriments', {})

    # Prefer per-100g values for consistency; fall back to per-serving
    def _get(key_100, key_serving=None):
        v = n.get(key_100)
        if v is None and key_serving:
            v = n.get(key_serving)
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    calories = _get('energy-kcal_100g', 'energy-kcal_serving')
    if calories is None:
        # Try energy in kJ and convert
        kj = _get('energy_100g')
        if kj is not None:
            calories = round(kj / 4.184, 1)
    if calories is None:
        return None

    # Serving size: prefer serving_quantity (numeric grams), else parse serving_size string
    serving_size = None
    serving_unit = 'g'
    sq = product.get('serving_quantity')
    if sq:
        try:
            serving_size = float(sq)
        except (TypeError, ValueError):
            pass
    if serving_size is None:
        serving_size = 100.0  # Default: nutrients are per 100g

    barcode = product.get('code', '')
    food_id = f"off_{barcode}" if barcode else None

    return make_food(
        name=name,
        brand=product.get('brands', '').split(',')[0].strip(),
        calories=calories,
        fat=_get('fat_100g') or 0.0,
        protein=_get('proteins_100g') or 0.0,
        carbs=_get('carbohydrates_100g') or 0.0,
        fiber=_get('fiber_100g'),
        sugar=_get('sugars_100g'),
        sodium=(_get('sodium_100g') or 0) * 1000,  # OFF gives sodium in g, we store mg
        vitamin_c=_get('vitamin-c_100g'),
        vitamin_a=_get('vitamin-a_100g'),
        calcium=_get('calcium_100g'),
        iron=_get('iron_100g'),
        serving_size=serving_size,
        serving_unit=serving_unit,
        food_id=food_id,
        source='openfoodfacts',
    )
