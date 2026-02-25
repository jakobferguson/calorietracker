"""
Home screen for CalorieTracker.

Layout:
  ┌────────────────────────────────┐
  │  < Wed Feb 25        ⚙  📋  │  ← date nav + settings/history buttons
  │                                │
  │     [Large calorie ring]       │
  │       1,245 / 2,000            │
  │          kcal                  │
  │                                │
  │  [Fat ○] [Protein ○] [Carbs ○]│  ← mini macro rings
  │                                │
  │  ┌─Breakfast─┐ ┌─Lunch──────┐  │
  │  │  320 kcal │ │  490 kcal  │  │
  │  └───────────┘ └────────────┘  │
  │  ┌─Dinner────┐ ┌─Snacks─────┐  │
  │  │    0 kcal │ │    0 kcal  │  │
  │  └───────────┘ └────────────┘  │
  └────────────────────────────────┘
"""

import math
import ui
from datetime import date, timedelta

import storage
from models import (
    MEAL_TYPES, MEAL_COLORS, MACRO_COLORS,
    entries_for_meal, sum_nutrients, today_str
)


# ── Ring drawing helpers ──────────────────────────────────────────────────────

def _draw_ring(cx, cy, radius, thickness, progress, fg_color, bg_color=(0.15, 0.15, 0.15)):
    """Draw a progress arc ring centered at (cx, cy)."""
    # Background ring
    bg = ui.Path()
    bg.add_arc(cx, cy, radius, 0, 2 * math.pi)
    bg.line_width = thickness
    ui.set_color(bg_color)
    bg.stroke()

    # Foreground arc (clamped to [0,1])
    p = max(0.0, min(1.0, progress))
    if p > 0:
        fg = ui.Path()
        start = -math.pi / 2          # top
        end = start + p * 2 * math.pi
        fg.add_arc(cx, cy, radius, start, end)
        fg.line_width = thickness
        ui.set_color(fg_color)
        fg.stroke()


# ── Ring views ────────────────────────────────────────────────────────────────

class CalorieRingView(ui.View):
    """Large central calorie ring."""

    def __init__(self, consumed=0, goal=2000, **kwargs):
        super().__init__(**kwargs)
        self.consumed = consumed
        self.goal = goal
        self.background_color = (0, 0, 0, 0)

    def draw(self):
        w, h = self.width, self.height
        cx, cy = w / 2, h / 2
        radius = min(w, h) / 2 - 14
        thickness = 18
        progress = self.consumed / self.goal if self.goal else 0

        # Colour shifts red if over goal
        if progress > 1.0:
            fg = (0.95, 0.30, 0.30)
        else:
            fg = (0.29, 0.85, 0.60)

        _draw_ring(cx, cy, radius, thickness, progress, fg)

        # Centre text
        ui.set_color((1, 1, 1))
        consumed_str = f'{int(self.consumed):,}'
        goal_str = f'{int(self.goal):,}'
        font_large = ('<system-bold>', 28)
        font_small = ('<system>', 13)

        # Consumed calories (large)
        tw, th = ui.measure_string(consumed_str, font=font_large)
        ui.draw_string(consumed_str, rect=(cx - tw / 2, cy - th - 4, tw, th),
                       font=font_large, color=(1, 1, 1),
                       alignment=ui.ALIGN_CENTER)

        # "/ goal kcal" (small)
        sub = f'/ {goal_str} kcal'
        tw2, th2 = ui.measure_string(sub, font=font_small)
        ui.draw_string(sub, rect=(cx - tw2 / 2, cy + 2, tw2, th2),
                       font=font_small, color=(0.7, 0.7, 0.7),
                       alignment=ui.ALIGN_CENTER)

        # Remaining label
        remaining = max(0, self.goal - self.consumed)
        rem_str = f'{int(remaining):,} remaining'
        tw3, th3 = ui.measure_string(rem_str, font=font_small)
        ui.draw_string(rem_str, rect=(cx - tw3 / 2, cy + th2 + 8, tw3, th3),
                       font=font_small, color=(0.5, 0.5, 0.5),
                       alignment=ui.ALIGN_CENTER)


class MacroRingView(ui.View):
    """Small ring for a single macro nutrient."""

    def __init__(self, label, consumed, goal, color, unit='g', **kwargs):
        super().__init__(**kwargs)
        self.label = label
        self.consumed = consumed
        self.goal = goal
        self.color = color
        self.unit = unit
        self.background_color = (0, 0, 0, 0)

    def draw(self):
        w, h = self.width, self.height
        cx, cy = w / 2, h * 0.42
        radius = min(w, h) * 0.38 - 4
        thickness = 8
        progress = self.consumed / self.goal if self.goal else 0

        _draw_ring(cx, cy, radius, thickness, progress, self.color)

        # Consumed value inside ring
        val_str = f'{int(self.consumed)}'
        font = ('<system-bold>', 13)
        tw, th = ui.measure_string(val_str, font=font)
        ui.draw_string(val_str, rect=(cx - tw / 2, cy - th / 2 - 1, tw, th),
                       font=font, color=(1, 1, 1),
                       alignment=ui.ALIGN_CENTER)

        # Label below ring
        font_lbl = ('<system>', 11)
        tw2, th2 = ui.measure_string(self.label, font=font_lbl)
        ui.draw_string(self.label,
                       rect=(cx - tw2 / 2, cy + radius + 6, tw2, th2),
                       font=font_lbl, color=(0.7, 0.7, 0.7),
                       alignment=ui.ALIGN_CENTER)

        # Goal below label
        goal_str = f'/ {int(self.goal)}{self.unit}'
        tw3, th3 = ui.measure_string(goal_str, font=font_lbl)
        ui.draw_string(goal_str,
                       rect=(cx - tw3 / 2, cy + radius + th2 + 8, tw3, th3),
                       font=font_lbl, color=(0.45, 0.45, 0.45),
                       alignment=ui.ALIGN_CENTER)


# ── Meal tile button ──────────────────────────────────────────────────────────

class MealTileView(ui.View):
    """Tappable tile showing a meal name and its calorie total."""

    def __init__(self, meal_type, calories, on_tap, **kwargs):
        super().__init__(**kwargs)
        self.meal_type = meal_type
        self.calories = calories
        self._on_tap = on_tap
        self.background_color = (0.12, 0.12, 0.12)
        self.corner_radius = 12

    def touch_ended(self, touch):
        self._on_tap(self.meal_type)

    def draw(self):
        w, h = self.width, self.height
        color = MEAL_COLORS.get(self.meal_type, (0.5, 0.5, 0.5))

        # Colour dot
        dot_r = 5
        dot_x, dot_y = 14, h / 2
        dot_path = ui.Path.oval(dot_x - dot_r, dot_y - dot_r, dot_r * 2, dot_r * 2)
        ui.set_color(color)
        dot_path.fill()

        # Meal name
        font_name = ('<system>', 14)
        ui.draw_string(self.meal_type,
                       rect=(28, h / 2 - 18, w - 36, 20),
                       font=font_name, color=(0.9, 0.9, 0.9))

        # Calorie count
        cal_str = f'{int(self.calories)} kcal'
        font_cal = ('<system-bold>', 13)
        ui.draw_string(cal_str,
                       rect=(28, h / 2 - 2, w - 36, 18),
                       font=font_cal, color=(1, 1, 1))

        # Chevron
        ui.set_color((0.4, 0.4, 0.4))
        chev = ui.Path()
        chev.move_to(w - 16, h / 2 - 5)
        chev.line_to(w - 10, h / 2)
        chev.line_to(w - 16, h / 2 + 5)
        chev.line_width = 1.5
        chev.stroke()


# ── Home View ─────────────────────────────────────────────────────────────────

class HomeView(ui.View):
    """
    Root home screen view.
    nav_controller must be set after creation so we can push child views.
    """

    def __init__(self, nav_controller=None, **kwargs):
        super().__init__(**kwargs)
        self.nav_controller = nav_controller
        self.background_color = (0.07, 0.07, 0.07)
        self._current_date = date.today()
        self._build_ui()
        self.refresh()

    # ── Build static skeleton ────────────────────────────────────────────────

    def _build_ui(self):
        W = self.width or 375
        PAD = 16

        # ── Header row ──────────────────────────────────────────────────────
        HDR_H = 44
        hdr = ui.View(frame=(0, 0, W, HDR_H))
        hdr.name = 'header'
        hdr.background_color = (0, 0, 0, 0)

        btn_prev = ui.Button(frame=(PAD, 8, 32, 28))
        btn_prev.title = '‹'
        btn_prev.font = ('<system>', 24)
        btn_prev.tint_color = (0.29, 0.85, 0.60)
        btn_prev.action = self._prev_day
        btn_prev.name = 'btn_prev'

        self._date_label = ui.Label(frame=(50, 10, W - 100, 24))
        self._date_label.text_color = (1, 1, 1)
        self._date_label.font = ('<system-bold>', 16)
        self._date_label.alignment = ui.ALIGN_CENTER

        btn_next = ui.Button(frame=(W - PAD - 32, 8, 32, 28))
        btn_next.title = '›'
        btn_next.font = ('<system>', 24)
        btn_next.tint_color = (0.29, 0.85, 0.60)
        btn_next.action = self._next_day
        btn_next.name = 'btn_next'

        btn_history = ui.Button(frame=(W - PAD - 32 - 36, 8, 32, 28))
        btn_history.image = ui.Image.named('iow:calendar_32')
        btn_history.tint_color = (0.6, 0.6, 0.6)
        btn_history.action = self._open_history

        btn_settings = ui.Button(frame=(W - PAD - 32 - 72, 8, 32, 28))
        btn_settings.image = ui.Image.named('iow:ios7_gear_32')
        btn_settings.tint_color = (0.6, 0.6, 0.6)
        btn_settings.action = self._open_settings

        hdr.add_subview(btn_prev)
        hdr.add_subview(self._date_label)
        hdr.add_subview(btn_next)
        hdr.add_subview(btn_history)
        hdr.add_subview(btn_settings)
        self.add_subview(hdr)

        # ── Calorie ring ─────────────────────────────────────────────────────
        RING_SIZE = min(W - 60, 200)
        ring_y = HDR_H + 12
        self._calorie_ring = CalorieRingView(
            frame=((W - RING_SIZE) / 2, ring_y, RING_SIZE, RING_SIZE)
        )
        self.add_subview(self._calorie_ring)

        # ── Macro rings row ──────────────────────────────────────────────────
        MACRO_SIZE = (W - PAD * 2) / 3
        macro_y = ring_y + RING_SIZE + 8
        self._macro_views = {}
        macros = [('Fat', 'fat'), ('Protein', 'protein'), ('Carbs', 'carbs')]
        for i, (label, key) in enumerate(macros):
            mv = MacroRingView(
                label=label, consumed=0, goal=50,
                color=MACRO_COLORS[key],
                frame=(PAD + i * MACRO_SIZE, macro_y, MACRO_SIZE, MACRO_SIZE * 0.85),
            )
            mv.name = f'macro_{key}'
            self._macro_views[key] = mv
            self.add_subview(mv)

        # ── Meal tiles ───────────────────────────────────────────────────────
        tiles_y = macro_y + MACRO_SIZE * 0.85 + 12
        TILE_W = (W - PAD * 3) / 2
        TILE_H = 62
        self._meal_tiles = {}
        for i, meal in enumerate(MEAL_TYPES):
            row, col = divmod(i, 2)
            tx = PAD + col * (TILE_W + PAD)
            ty = tiles_y + row * (TILE_H + 10)
            tile = MealTileView(
                meal_type=meal,
                calories=0,
                on_tap=self._open_meal,
                frame=(tx, ty, TILE_W, TILE_H),
            )
            self._meal_tiles[meal] = tile
            self.add_subview(tile)

        # ── Add food button ──────────────────────────────────────────────────
        btn_y = tiles_y + 2 * (TILE_H + 10) + 10
        btn_add = ui.Button(frame=(PAD, btn_y, W - PAD * 2, 44))
        btn_add.title = '+ Log Food'
        btn_add.font = ('<system-bold>', 16)
        btn_add.background_color = (0.29, 0.85, 0.60)
        btn_add.tint_color = (1, 1, 1)
        btn_add.corner_radius = 10
        btn_add.action = self._open_search
        self.add_subview(btn_add)

    # ── Data refresh ─────────────────────────────────────────────────────────

    def refresh(self):
        """Reload data for _current_date and update all subviews."""
        date_str = self._current_date.isoformat()
        log = storage.load_log(date_str)
        goals = storage.load_goals()
        all_entries = log['entries']
        totals = sum_nutrients(all_entries)

        # Date label
        today = date.today()
        if self._current_date == today:
            label = 'Today'
        elif self._current_date == today - timedelta(days=1):
            label = 'Yesterday'
        else:
            label = self._current_date.strftime('%a, %b %-d')
        self._date_label.text = label

        # Calorie ring
        self._calorie_ring.consumed = totals['calories']
        self._calorie_ring.goal = goals['calories']
        self._calorie_ring.set_needs_display()

        # Macro rings
        for key, mv in self._macro_views.items():
            mv.consumed = totals[key]
            mv.goal = goals[key]
            mv.set_needs_display()

        # Meal tiles
        for meal, tile in self._meal_tiles.items():
            meal_entries = entries_for_meal(log, meal)
            meal_totals = sum_nutrients(meal_entries)
            tile.calories = meal_totals['calories']
            tile.set_needs_display()

    # ── Navigation ───────────────────────────────────────────────────────────

    def _prev_day(self, sender):
        self._current_date -= timedelta(days=1)
        self.refresh()

    def _next_day(self, sender):
        next_d = self._current_date + timedelta(days=1)
        if next_d <= date.today():
            self._current_date = next_d
            self.refresh()

    def _open_meal(self, meal_type):
        if not self.nav_controller:
            return
        from meal_view import MealView
        mv = MealView(
            meal_type=meal_type,
            date_str=self._current_date.isoformat(),
            on_change=self.refresh,
            frame=self.frame,
        )
        mv.name = meal_type
        self.nav_controller.push_view(mv)

    def _open_search(self, sender):
        if not self.nav_controller:
            return
        from search_view import SearchView
        sv = SearchView(
            date_str=self._current_date.isoformat(),
            on_logged=self.refresh,
            frame=self.frame,
        )
        sv.name = 'Log Food'
        self.nav_controller.push_view(sv)

    def _open_history(self, sender):
        if not self.nav_controller:
            return
        from history_view import HistoryView
        hv = HistoryView(
            on_select_date=self._go_to_date,
            frame=self.frame,
        )
        hv.name = 'History'
        self.nav_controller.push_view(hv)

    def _open_settings(self, sender):
        if not self.nav_controller:
            return
        from settings_view import SettingsView
        sv = SettingsView(
            on_save=self.refresh,
            frame=self.frame,
        )
        sv.name = 'Goals'
        self.nav_controller.push_view(sv)

    def _go_to_date(self, date_str):
        self._current_date = date.fromisoformat(date_str)
        self.refresh()
        if self.nav_controller:
            self.nav_controller.pop_view()
