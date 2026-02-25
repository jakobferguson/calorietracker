"""
JSON-based persistence layer for CalorieTracker.
Stores data in ~/Documents/CalorieTracker/data/ (Pythonista documents directory).
"""

import json
import os

from models import make_daily_log, make_goals, DEFAULT_GOALS, today_str

# Resolve data directory relative to this file so it works both in Pythonista
# (~/Documents/CalorieTracker/) and during testing from any working directory.
_BASE_DIR = os.path.expanduser('~/Documents/CalorieTracker')
DATA_DIR = os.path.join(_BASE_DIR, 'data')

LOGS_FILE = os.path.join(DATA_DIR, 'logs.json')
FOODS_FILE = os.path.join(DATA_DIR, 'foods.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')


def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)


def _read_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_json(path, data):
    _ensure_dirs()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Settings / Goals ────────────────────────────────────────────────────────

def load_goals():
    """Return goals dict, falling back to defaults."""
    data = _read_json(SETTINGS_FILE, {})
    goals = make_goals(**DEFAULT_GOALS)
    goals.update(data.get('goals', {}))
    return goals


def save_goals(goals):
    data = _read_json(SETTINGS_FILE, {})
    data['goals'] = goals
    _write_json(SETTINGS_FILE, data)


# ── Food Cache ───────────────────────────────────────────────────────────────

def load_foods():
    """Return dict of food_id -> food dict."""
    return _read_json(FOODS_FILE, {})


def save_food(food):
    """Add or overwrite a food in the local cache."""
    foods = load_foods()
    foods[food['id']] = food
    _write_json(FOODS_FILE, foods)


def get_food(food_id):
    foods = load_foods()
    return foods.get(food_id)


def search_local_foods(query):
    """Return list of locally cached foods whose name matches query (case-insensitive)."""
    query_lower = query.lower()
    foods = load_foods()
    return [f for f in foods.values()
            if query_lower in f['name'].lower() or query_lower in f.get('brand', '').lower()]


def delete_food(food_id):
    foods = load_foods()
    foods.pop(food_id, None)
    _write_json(FOODS_FILE, foods)


# ── Daily Logs ───────────────────────────────────────────────────────────────

def load_all_logs():
    """Return dict of date_str -> daily_log dict."""
    return _read_json(LOGS_FILE, {})


def load_log(date_str=None):
    """Return the daily log for a given date (defaults to today). Creates if missing."""
    if date_str is None:
        date_str = today_str()
    logs = load_all_logs()
    if date_str not in logs:
        logs[date_str] = make_daily_log(date_str)
    return logs[date_str]


def save_log(daily_log):
    logs = load_all_logs()
    logs[daily_log['date']] = daily_log
    _write_json(LOGS_FILE, logs)


def add_entry(entry, date_str=None):
    """Append a log entry to a day's log."""
    if date_str is None:
        date_str = today_str()
    log = load_log(date_str)
    log['entries'].append(entry)
    save_log(log)


def delete_entry(entry_id, date_str=None):
    """Remove a log entry by its id."""
    if date_str is None:
        date_str = today_str()
    log = load_log(date_str)
    log['entries'] = [e for e in log['entries'] if e['id'] != entry_id]
    save_log(log)


def get_logged_dates():
    """Return sorted list of date strings that have at least one entry."""
    logs = load_all_logs()
    return sorted(
        [d for d, log in logs.items() if log.get('entries')],
        reverse=True
    )
