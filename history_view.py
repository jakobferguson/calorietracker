"""
History view — shows a list of past logged days with daily calorie summary.
Tapping a row calls on_select_date(date_str) so the home screen can navigate to it.
"""

import ui
from datetime import date, timedelta

import storage
from models import sum_nutrients


class HistoryView(ui.View):
    """Scrollable list of past days with calorie summaries."""

    def __init__(self, on_select_date=None, **kwargs):
        super().__init__(**kwargs)
        self.on_select_date = on_select_date
        self.background_color = (0.07, 0.07, 0.07)
        self._dates = []
        self._summaries = {}  # date_str -> totals dict
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        W = self.width or 375

        self._table = ui.TableView(frame=(0, 0, W, self.height))
        self._table.background_color = (0.07, 0.07, 0.07)
        self._table.separator_color = (0.18, 0.18, 0.18)
        self._table.data_source = self
        self._table.delegate = self
        self.add_subview(self._table)

    def _load_data(self):
        self._dates = storage.get_logged_dates()
        goals = storage.load_goals()
        self._cal_goal = goals['calories']

        for d in self._dates:
            log = storage.load_log(d)
            self._summaries[d] = sum_nutrients(log['entries'])

        self._table.reload()

    # ── TableView data source ─────────────────────────────────────────────────

    def tableview_number_of_rows(self, tableview, section):
        return len(self._dates)

    def tableview_cell_for_row(self, tableview, section, row):
        cell = ui.TableViewCell('subtitle')
        date_str = self._dates[row]
        totals = self._summaries.get(date_str, {})
        cell.background_color = (0.10, 0.10, 0.10)

        # Date label
        d = date.fromisoformat(date_str)
        today = date.today()
        if d == today:
            label = 'Today'
        elif d == today - timedelta(days=1):
            label = 'Yesterday'
        else:
            label = d.strftime('%A, %b %-d %Y')

        cell.text_label.text = label
        cell.text_label.text_color = (1, 1, 1)
        cell.text_label.font = ('<system-bold>', 15)

        cal = int(totals.get('calories', 0))
        fat = totals.get('fat', 0)
        protein = totals.get('protein', 0)
        carbs = totals.get('carbs', 0)

        cell.detail_text_label.text = (
            f'{cal} kcal  ·  '
            f'F {fat:.0f}g  P {protein:.0f}g  C {carbs:.0f}g'
        )
        cell.detail_text_label.text_color = (0.55, 0.55, 0.55)
        cell.detail_text_label.font = ('<system>', 12)

        # Progress bar as accessory
        goal = self._cal_goal or 2000
        progress = min(cal / goal, 1.0)
        bar = _MiniBarView(progress=progress, frame=(0, 0, 60, 20))
        cell.accessory_view = bar

        return cell

    def tableview_did_select(self, tableview, section, row):
        tableview.selected_row = -1
        date_str = self._dates[row]
        if self.on_select_date:
            self.on_select_date(date_str)


class _MiniBarView(ui.View):
    """Tiny horizontal progress bar."""

    def __init__(self, progress=0.0, **kwargs):
        super().__init__(**kwargs)
        self.progress = progress
        self.background_color = (0, 0, 0, 0)

    def draw(self):
        w, h = self.width, self.height
        # Background
        bg = ui.Path.rounded_rect(0, h / 2 - 3, w, 6, 3)
        ui.set_color((0.2, 0.2, 0.2))
        bg.fill()
        # Fill
        if self.progress > 0:
            fill_w = max(6, w * self.progress)
            color = (0.95, 0.30, 0.30) if self.progress >= 1.0 else (0.29, 0.85, 0.60)
            fg = ui.Path.rounded_rect(0, h / 2 - 3, fill_w, 6, 3)
            ui.set_color(color)
            fg.fill()
