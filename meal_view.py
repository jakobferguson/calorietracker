"""
Meal detail view — shows all food entries for a given meal type on a given day.
Allows deleting individual entries and logging more food for this meal.
"""

import ui
import storage
from models import entries_for_meal, sum_nutrients, MEAL_COLORS


class MealView(ui.View):
    """
    Displayed when the user taps a meal tile on the home screen.
    Shows logged foods in a TableView with swipe-to-delete.
    """

    def __init__(self, meal_type, date_str, on_change=None, **kwargs):
        super().__init__(**kwargs)
        self.meal_type = meal_type
        self.date_str = date_str
        self.on_change = on_change  # called when entries change so home refreshes
        self.background_color = (0.07, 0.07, 0.07)
        self._entries = []
        self._build_ui()
        self.refresh()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        W = self.width or 375
        PAD = 16

        # Summary bar at top
        self._summary = ui.Label(frame=(PAD, 8, W - PAD * 2, 36))
        self._summary.text_color = (1, 1, 1)
        self._summary.font = ('<system-bold>', 15)
        self._summary.alignment = ui.ALIGN_CENTER
        self.add_subview(self._summary)

        # Macro bar (fat / protein / carbs text)
        self._macro_bar = ui.Label(frame=(PAD, 44, W - PAD * 2, 20))
        self._macro_bar.text_color = (0.6, 0.6, 0.6)
        self._macro_bar.font = ('<system>', 12)
        self._macro_bar.alignment = ui.ALIGN_CENTER
        self.add_subview(self._macro_bar)

        # Table of food entries
        self._table = ui.TableView(frame=(0, 72, W, self.height - 72 - 56))
        self._table.background_color = (0.07, 0.07, 0.07)
        self._table.separator_color = (0.18, 0.18, 0.18)
        self._table.allows_selection = True
        self._table.data_source = self
        self._table.delegate = self
        self.add_subview(self._table)

        # Add food button
        btn = ui.Button(frame=(PAD, self.height - 52, W - PAD * 2, 44))
        btn.title = f'+ Add to {self.meal_type}'
        btn.font = ('<system-bold>', 15)
        btn.background_color = MEAL_COLORS.get(self.meal_type, (0.3, 0.3, 0.3))
        btn.tint_color = (1, 1, 1)
        btn.corner_radius = 10
        btn.action = self._add_food
        self.add_subview(btn)

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self):
        log = storage.load_log(self.date_str)
        self._entries = entries_for_meal(log, self.meal_type)
        totals = sum_nutrients(self._entries)

        cal = int(totals['calories'])
        fat = totals['fat']
        protein = totals['protein']
        carbs = totals['carbs']

        self._summary.text = f'{cal} kcal'
        self._macro_bar.text = (
            f'Fat {fat:.1f}g  ·  Protein {protein:.1f}g  ·  Carbs {carbs:.1f}g'
        )
        self._table.reload()

    # ── TableView data source ─────────────────────────────────────────────────

    def tableview_number_of_rows(self, tableview, section):
        return len(self._entries)

    def tableview_cell_for_row(self, tableview, section, row):
        cell = ui.TableViewCell('subtitle')
        entry = self._entries[row]
        cell.background_color = (0.10, 0.10, 0.10)
        cell.text_label.text = entry['food_name']
        cell.text_label.text_color = (1, 1, 1)
        cell.text_label.font = ('<system>', 15)

        qty_str = f"{entry['quantity']:.0f}{entry['unit']}"
        cal_str = f"{int(entry['calories'])} kcal"
        cell.detail_text_label.text = f'{qty_str}  ·  {cal_str}'
        cell.detail_text_label.text_color = (0.6, 0.6, 0.6)
        cell.detail_text_label.font = ('<system>', 12)

        # Right accessory: macros mini text
        macro_lbl = ui.Label()
        macro_lbl.text = (
            f"F {entry['fat']:.0f}  "
            f"P {entry['protein']:.0f}  "
            f"C {entry['carbs']:.0f}"
        )
        macro_lbl.font = ('<system>', 10)
        macro_lbl.text_color = (0.5, 0.5, 0.5)
        macro_lbl.size_to_fit()
        cell.accessory_view = macro_lbl

        return cell

    def tableview_can_delete(self, tableview, section, row):
        return True

    def tableview_delete(self, tableview, section, row):
        entry = self._entries[row]
        storage.delete_entry(entry['id'], self.date_str)
        self.refresh()
        if self.on_change:
            self.on_change()

    def tableview_did_select(self, tableview, section, row):
        tableview.selected_row = -1

    # ── Navigation ───────────────────────────────────────────────────────────

    def _add_food(self, sender):
        nav = self._find_nav()
        if not nav:
            return
        from search_view import SearchView
        sv = SearchView(
            date_str=self.date_str,
            default_meal=self.meal_type,
            on_logged=self._on_food_logged,
            frame=self.frame,
        )
        sv.name = 'Search Food'
        nav.push_view(sv)

    def _on_food_logged(self):
        self.refresh()
        if self.on_change:
            self.on_change()

    def _find_nav(self):
        """Walk up the view hierarchy to find the NavigationView."""
        v = self.superview
        while v:
            if isinstance(v, ui.NavigationView):
                return v
            v = v.superview
        return None
