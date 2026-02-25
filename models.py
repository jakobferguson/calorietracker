"""
Data models for CalorieTracker.
All models use plain dicts for JSON serialization compatibility with Pythonista.
"""

from datetime import date as date_type


# Default daily goals
DEFAULT_GOALS = {
    'calories': 2000,
    'fat': 50,
    'protein': 100,
    'carbs': 150,
    'fiber': 25,
    'sugar': 50,
    'sodium': 2300,
}

MEAL_TYPES = ['Breakfast', 'Lunch', 'Dinner', 'Snacks']

MICRO_KEYS = ['fiber', 'sugar', 'sodium', 'vitamin_c', 'vitamin_a', 'calcium', 'iron']

MACRO_COLORS = {
    'fat':     (0.95, 0.85, 0.20),   # yellow
    'protein': (0.95, 0.30, 0.30),   # red
    'carbs':   (0.30, 0.85, 0.40),   # green
}

MEAL_COLORS = {
    'Breakfast': (0.97, 0.65, 0.24),
    'Lunch':     (0.38, 0.80, 0.55),
    'Dinner':    (0.29, 0.69, 0.96),
    'Snacks':    (0.75, 0.50, 0.90),
}


def make_food(name, brand='', calories=0, fat=0.0, protein=0.0, carbs=0.0,
              fiber=None, sugar=None, sodium=None,
              vitamin_c=None, vitamin_a=None, calcium=None, iron=None,
              serving_size=100.0, serving_unit='g', food_id=None, source='custom'):
    """
    Create a food dict.

    Macros are per-serving (at serving_size / serving_unit).
    Micros are optional (None means not tracked).
    """
    return {
        'id': food_id or _generate_id(name),
        'name': name,
        'brand': brand,
        'calories': float(calories),
        'fat': float(fat),
        'protein': float(protein),
        'carbs': float(carbs),
        'fiber': float(fiber) if fiber is not None else None,
        'sugar': float(sugar) if sugar is not None else None,
        'sodium': float(sodium) if sodium is not None else None,
        'vitamin_c': float(vitamin_c) if vitamin_c is not None else None,
        'vitamin_a': float(vitamin_a) if vitamin_a is not None else None,
        'calcium': float(calcium) if calcium is not None else None,
        'iron': float(iron) if iron is not None else None,
        'serving_size': float(serving_size),
        'serving_unit': serving_unit,
        'source': source,  # 'custom' or 'openfoodfacts'
    }


def make_log_entry(food_id, food_name, meal_type, quantity, unit,
                   calories, fat, protein, carbs,
                   fiber=None, sugar=None, sodium=None,
                   vitamin_c=None, vitamin_a=None, calcium=None, iron=None,
                   entry_id=None):
    """
    A single logged food entry (a food consumed in a meal).
    Nutrient values are already scaled to the logged quantity.
    """
    import time
    return {
        'id': entry_id or str(int(time.time() * 1000)),
        'food_id': food_id,
        'food_name': food_name,
        'meal_type': meal_type,
        'quantity': float(quantity),
        'unit': unit,
        'calories': float(calories),
        'fat': float(fat),
        'protein': float(protein),
        'carbs': float(carbs),
        'fiber': float(fiber) if fiber is not None else None,
        'sugar': float(sugar) if sugar is not None else None,
        'sodium': float(sodium) if sodium is not None else None,
        'vitamin_c': float(vitamin_c) if vitamin_c is not None else None,
        'vitamin_a': float(vitamin_a) if vitamin_a is not None else None,
        'calcium': float(calcium) if calcium is not None else None,
        'iron': float(iron) if iron is not None else None,
    }


def make_daily_log(date_str):
    """A day's worth of logged entries."""
    return {
        'date': date_str,
        'entries': [],
    }


def make_goals(calories=2000, fat=50, protein=100, carbs=150,
               fiber=25, sugar=50, sodium=2300):
    return {
        'calories': float(calories),
        'fat': float(fat),
        'protein': float(protein),
        'carbs': float(carbs),
        'fiber': float(fiber),
        'sugar': float(sugar),
        'sodium': float(sodium),
    }


# --- Aggregation helpers ---

def entries_for_meal(daily_log, meal_type):
    return [e for e in daily_log['entries'] if e['meal_type'] == meal_type]


def sum_nutrients(entries):
    """Return a dict summing all numeric nutrient fields across entries."""
    keys = ['calories', 'fat', 'protein', 'carbs', 'fiber', 'sugar', 'sodium',
            'vitamin_c', 'vitamin_a', 'calcium', 'iron']
    totals = {k: 0.0 for k in keys}
    for e in entries:
        for k in keys:
            v = e.get(k)
            if v is not None:
                totals[k] += v
    return totals


def scale_food_nutrients(food, quantity):
    """
    Return scaled nutrient values for a food given a quantity (in the food's serving_unit).
    quantity is in the same unit as food['serving_size'].
    """
    ratio = quantity / food['serving_size'] if food['serving_size'] else 1.0
    scaled = {}
    for key in ['calories', 'fat', 'protein', 'carbs',
                'fiber', 'sugar', 'sodium', 'vitamin_c', 'vitamin_a', 'calcium', 'iron']:
        v = food.get(key)
        scaled[key] = round(v * ratio, 2) if v is not None else None
    return scaled


def today_str():
    return date_type.today().isoformat()


def _generate_id(name):
    import hashlib, time
    raw = f"{name}{time.time()}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]
