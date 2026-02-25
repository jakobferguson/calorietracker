"""
Food search and logging view.

Flow:
  1. User types in search box → results from local cache + Open Food Facts
  2. User taps a result → quantity sheet appears
  3. User confirms → entry is logged and on_logged callback fires
  4. Optional: "Create custom food" button for manual entry
"""

import threading
import ui

import api
import storage
from models import (
    MEAL_TYPES, make_log_entry, scale_food_nutrients, today_str
)


# ── Quantity / meal selector sheet ───────────────────────────────────────────

class LogFoodSheet(ui.View):
    """
    Modal-style view for selecting quantity and meal type before logging.
    Shown as a pushed view in the nav controller.
    """

    def __init__(self, food, date_str, default_meal='Breakfast',
                 on_logged=None, **kwargs):
        super().__init__(**kwargs)
        self.food = food
        self.date_str = date_str
        self.default_meal = default_meal
        self.on_logged = on_logged
        self.background_color = (0.07, 0.07, 0.07)
        self._build_ui()

    def _build_ui(self):
        W = self.width or 375
        PAD = 16
        y = 20

        # Food name header
        name_lbl = ui.Label(frame=(PAD, y, W - PAD * 2, 28))
        name_lbl.text = self.food['name']
        name_lbl.font = ('<system-bold>', 18)
        name_lbl.text_color = (1, 1, 1)
        name_lbl.number_of_lines = 2
        self.add_subview(name_lbl)
        y += 36

        # Brand (if any)
        if self.food.get('brand'):
            brand_lbl = ui.Label(frame=(PAD, y, W - PAD * 2, 18))
            brand_lbl.text = self.food['brand']
            brand_lbl.font = ('<system>', 13)
            brand_lbl.text_color = (0.6, 0.6, 0.6)
            self.add_subview(brand_lbl)
            y += 24

        y += 8

        # Per-serving nutrition preview (based on food's serving_size)
        info = (
            f"{int(self.food['calories'])} kcal  ·  "
            f"F {self.food['fat']:.1f}g  ·  "
            f"P {self.food['protein']:.1f}g  ·  "
            f"C {self.food['carbs']:.1f}g  "
            f"(per {self.food['serving_size']:.0f}{self.food['serving_unit']})"
        )
        info_lbl = ui.Label(frame=(PAD, y, W - PAD * 2, 36))
        info_lbl.text = info
        info_lbl.font = ('<system>', 12)
        info_lbl.text_color = (0.55, 0.55, 0.55)
        info_lbl.number_of_lines = 2
        self.add_subview(info_lbl)
        y += 44

        # Separator
        sep = ui.View(frame=(PAD, y, W - PAD * 2, 1))
        sep.background_color = (0.2, 0.2, 0.2)
        self.add_subview(sep)
        y += 12

        # Quantity field
        qty_lbl = ui.Label(frame=(PAD, y, 100, 24))
        qty_lbl.text = 'Quantity'
        qty_lbl.font = ('<system>', 14)
        qty_lbl.text_color = (0.8, 0.8, 0.8)
        self.add_subview(qty_lbl)

        self._qty_field = ui.TextField(frame=(PAD + 100, y - 4, W - PAD * 2 - 100 - 60, 32))
        self._qty_field.text = str(int(self.food['serving_size']))
        self._qty_field.keyboard_type = ui.KEYBOARD_DECIMAL_PAD
        self._qty_field.background_color = (0.15, 0.15, 0.15)
        self._qty_field.text_color = (1, 1, 1)
        self._qty_field.tint_color = (0.29, 0.85, 0.60)
        self._qty_field.corner_radius = 6
        self._qty_field.delegate = self
        self.add_subview(self._qty_field)

        unit_lbl = ui.Label(frame=(W - PAD - 52, y, 52, 24))
        unit_lbl.text = self.food['serving_unit']
        unit_lbl.font = ('<system>', 14)
        unit_lbl.text_color = (0.6, 0.6, 0.6)
        unit_lbl.alignment = ui.ALIGN_RIGHT
        self.add_subview(unit_lbl)
        y += 44

        # Meal type picker
        meal_lbl = ui.Label(frame=(PAD, y, 100, 24))
        meal_lbl.text = 'Meal'
        meal_lbl.font = ('<system>', 14)
        meal_lbl.text_color = (0.8, 0.8, 0.8)
        self.add_subview(meal_lbl)

        self._meal_seg = ui.SegmentedControl(
            frame=(PAD + 100, y - 4, W - PAD * 2 - 100, 32)
        )
        self._meal_seg.segments = MEAL_TYPES
        idx = MEAL_TYPES.index(self.default_meal) if self.default_meal in MEAL_TYPES else 0
        self._meal_seg.selected_index = idx
        self._meal_seg.tint_color = (0.29, 0.85, 0.60)
        self.add_subview(self._meal_seg)
        y += 48

        # Scaled nutrition preview (updates as quantity changes)
        self._nutrition_lbl = ui.Label(frame=(PAD, y, W - PAD * 2, 80))
        self._nutrition_lbl.font = ('<system>', 13)
        self._nutrition_lbl.text_color = (0.65, 0.65, 0.65)
        self._nutrition_lbl.number_of_lines = 5
        self.add_subview(self._nutrition_lbl)
        y += 88

        self._update_nutrition_preview()

        # Log button
        btn = ui.Button(frame=(PAD, y, W - PAD * 2, 44))
        btn.title = 'Log Food'
        btn.font = ('<system-bold>', 16)
        btn.background_color = (0.29, 0.85, 0.60)
        btn.tint_color = (1, 1, 1)
        btn.corner_radius = 10
        btn.action = self._log
        self.add_subview(btn)

    def _update_nutrition_preview(self):
        try:
            qty = float(self._qty_field.text or '0')
        except ValueError:
            qty = 0
        scaled = scale_food_nutrients(self.food, qty)
        lines = [
            f"Calories: {int(scaled['calories'])} kcal",
            f"Fat: {scaled['fat']:.1f}g   Protein: {scaled['protein']:.1f}g   Carbs: {scaled['carbs']:.1f}g",
        ]
        optionals = [
            ('Fiber', scaled.get('fiber'), 'g'),
            ('Sugar', scaled.get('sugar'), 'g'),
            ('Sodium', scaled.get('sodium'), 'mg'),
        ]
        for label, val, unit in optionals:
            if val is not None:
                lines.append(f"{label}: {val:.1f}{unit}")
        self._nutrition_lbl.text = '\n'.join(lines)

    # TextField delegate
    def textfield_did_change(self, textfield):
        self._update_nutrition_preview()

    def _log(self, sender):
        try:
            qty = float(self._qty_field.text or '0')
        except ValueError:
            qty = 0
        if qty <= 0:
            return

        meal_type = MEAL_TYPES[self._meal_seg.selected_index]
        scaled = scale_food_nutrients(self.food, qty)

        entry = make_log_entry(
            food_id=self.food['id'],
            food_name=self.food['name'],
            meal_type=meal_type,
            quantity=qty,
            unit=self.food['serving_unit'],
            calories=scaled['calories'],
            fat=scaled['fat'],
            protein=scaled['protein'],
            carbs=scaled['carbs'],
            fiber=scaled.get('fiber'),
            sugar=scaled.get('sugar'),
            sodium=scaled.get('sodium'),
            vitamin_c=scaled.get('vitamin_c'),
            vitamin_a=scaled.get('vitamin_a'),
            calcium=scaled.get('calcium'),
            iron=scaled.get('iron'),
        )

        storage.add_entry(entry, self.date_str)

        if self.on_logged:
            self.on_logged()

        # Pop back twice (past this sheet and search)
        nav = self._find_nav()
        if nav:
            nav.pop_view()
            nav.pop_view()

    def _find_nav(self):
        v = self.superview
        while v:
            if isinstance(v, ui.NavigationView):
                return v
            v = v.superview
        return None


# ── Custom food creation ──────────────────────────────────────────────────────

class CreateFoodView(ui.View):
    """Simple form for creating a custom food."""

    def __init__(self, on_created=None, **kwargs):
        super().__init__(**kwargs)
        self.on_created = on_created
        self.background_color = (0.07, 0.07, 0.07)
        self._fields = {}
        self._build_ui()

    def _build_ui(self):
        W = self.width or 375
        PAD = 16
        y = 20

        field_defs = [
            ('name', 'Food Name *', ui.KEYBOARD_DEFAULT),
            ('brand', 'Brand (optional)', ui.KEYBOARD_DEFAULT),
            ('calories', 'Calories (kcal) *', ui.KEYBOARD_DECIMAL_PAD),
            ('fat', 'Fat (g) *', ui.KEYBOARD_DECIMAL_PAD),
            ('protein', 'Protein (g) *', ui.KEYBOARD_DECIMAL_PAD),
            ('carbs', 'Carbs (g) *', ui.KEYBOARD_DECIMAL_PAD),
            ('fiber', 'Fiber (g)', ui.KEYBOARD_DECIMAL_PAD),
            ('sugar', 'Sugar (g)', ui.KEYBOARD_DECIMAL_PAD),
            ('sodium', 'Sodium (mg)', ui.KEYBOARD_DECIMAL_PAD),
            ('serving_size', 'Serving size (g)', ui.KEYBOARD_DECIMAL_PAD),
        ]

        scroll = ui.ScrollView(frame=(0, 0, W, self.height - 60))
        scroll.content_size = (W, len(field_defs) * 56 + 40)

        inner_y = 12
        for key, placeholder, kb_type in field_defs:
            lbl = ui.Label(frame=(PAD, inner_y, W - PAD * 2, 18))
            lbl.text = placeholder.replace(' *', '').replace(' (optional)', '')
            lbl.font = ('<system>', 12)
            lbl.text_color = (0.55, 0.55, 0.55)
            scroll.add_subview(lbl)

            tf = ui.TextField(frame=(PAD, inner_y + 18, W - PAD * 2, 30))
            tf.placeholder = placeholder
            tf.keyboard_type = kb_type
            tf.background_color = (0.14, 0.14, 0.14)
            tf.text_color = (1, 1, 1)
            tf.tint_color = (0.29, 0.85, 0.60)
            tf.corner_radius = 6
            if key == 'serving_size':
                tf.text = '100'
            scroll.add_subview(tf)
            self._fields[key] = tf
            inner_y += 56

        self.add_subview(scroll)

        btn = ui.Button(frame=(PAD, self.height - 52, W - PAD * 2, 44))
        btn.title = 'Save Food'
        btn.font = ('<system-bold>', 16)
        btn.background_color = (0.29, 0.85, 0.60)
        btn.tint_color = (1, 1, 1)
        btn.corner_radius = 10
        btn.action = self._save
        self.add_subview(btn)

    def _save(self, sender):
        from models import make_food

        def fval(key, default=None):
            txt = self._fields[key].text.strip()
            try:
                return float(txt) if txt else default
            except ValueError:
                return default

        name = self._fields['name'].text.strip()
        if not name:
            return  # must have a name

        calories = fval('calories', 0)
        food = make_food(
            name=name,
            brand=self._fields['brand'].text.strip(),
            calories=calories,
            fat=fval('fat', 0),
            protein=fval('protein', 0),
            carbs=fval('carbs', 0),
            fiber=fval('fiber'),
            sugar=fval('sugar'),
            sodium=fval('sodium'),
            serving_size=fval('serving_size', 100),
            serving_unit='g',
            source='custom',
        )
        storage.save_food(food)

        if self.on_created:
            self.on_created(food)

        nav = self._find_nav()
        if nav:
            nav.pop_view()

    def _find_nav(self):
        v = self.superview
        while v:
            if isinstance(v, ui.NavigationView):
                return v
            v = v.superview
        return None


# ── Search View ───────────────────────────────────────────────────────────────

class SearchView(ui.View):
    """
    Search screen: text field + results table.
    Searching hits local cache immediately, then Open Food Facts async.
    """

    def __init__(self, date_str=None, default_meal='Breakfast',
                 on_logged=None, **kwargs):
        super().__init__(**kwargs)
        self.date_str = date_str or today_str()
        self.default_meal = default_meal
        self.on_logged = on_logged
        self.background_color = (0.07, 0.07, 0.07)
        self._results = []
        self._searching = False
        self._build_ui()

    def _build_ui(self):
        W = self.width or 375
        PAD = 16

        # Search bar
        search_bg = ui.View(frame=(PAD, 12, W - PAD * 2, 36))
        search_bg.background_color = (0.15, 0.15, 0.15)
        search_bg.corner_radius = 10
        self.add_subview(search_bg)

        self._search_field = ui.TextField(frame=(8, 4, W - PAD * 2 - 16, 28))
        self._search_field.placeholder = 'Search foods…'
        self._search_field.keyboard_type = ui.KEYBOARD_DEFAULT
        self._search_field.background_color = (0, 0, 0, 0)
        self._search_field.text_color = (1, 1, 1)
        self._search_field.tint_color = (0.29, 0.85, 0.60)
        self._search_field.delegate = self
        search_bg.add_subview(self._search_field)

        # Activity indicator
        self._spinner = ui.ActivityIndicator(frame=(W - PAD - 28, 16, 22, 22))
        self._spinner.style = ui.ACTIVITY_INDICATOR_STYLE_WHITE
        self._spinner.hides_when_stopped = True
        self.add_subview(self._spinner)

        # Results table
        self._table = ui.TableView(frame=(0, 58, W, self.height - 58 - 52))
        self._table.background_color = (0.07, 0.07, 0.07)
        self._table.separator_color = (0.18, 0.18, 0.18)
        self._table.data_source = self
        self._table.delegate = self
        self.add_subview(self._table)

        # Create custom food button
        btn = ui.Button(frame=(PAD, self.height - 52, W - PAD * 2, 44))
        btn.title = '+ Create Custom Food'
        btn.font = ('<system>', 14)
        btn.background_color = (0.15, 0.15, 0.15)
        btn.tint_color = (0.29, 0.85, 0.60)
        btn.corner_radius = 10
        btn.action = self._create_custom
        self.add_subview(btn)

    # ── Search logic ──────────────────────────────────────────────────────────

    def textfield_did_change(self, textfield):
        query = textfield.text.strip()
        if len(query) < 2:
            self._results = []
            self._table.reload()
            return
        self._do_search(query)

    def textfield_should_return(self, textfield):
        textfield.end_editing()
        return True

    def _do_search(self, query):
        self._spinner.start()
        self._searching = True

        def _search():
            results = api.search_foods(query, max_results=25)
            ui.in_main_thread(self._update_results, results)

        threading.Thread(target=_search, daemon=True).start()

    def _update_results(self, results):
        self._results = results
        self._spinner.stop()
        self._searching = False
        self._table.reload()

    # ── TableView data source ─────────────────────────────────────────────────

    def tableview_number_of_rows(self, tableview, section):
        return len(self._results)

    def tableview_cell_for_row(self, tableview, section, row):
        cell = ui.TableViewCell('subtitle')
        food = self._results[row]
        cell.background_color = (0.10, 0.10, 0.10)

        name = food['name']
        brand = food.get('brand', '')
        cell.text_label.text = name
        cell.text_label.text_color = (1, 1, 1)
        cell.text_label.font = ('<system>', 15)

        cal_str = f"{int(food['calories'])} kcal"
        sub = f"{brand}  ·  {cal_str}" if brand else cal_str
        cell.detail_text_label.text = sub
        cell.detail_text_label.text_color = (0.55, 0.55, 0.55)
        cell.detail_text_label.font = ('<system>', 12)

        # Source badge
        src = food.get('source', '')
        badge = ui.Label()
        badge.text = 'OFF' if src == 'openfoodfacts' else 'custom'
        badge.font = ('<system>', 9)
        badge.text_color = (0.4, 0.6, 0.9) if src == 'openfoodfacts' else (0.5, 0.9, 0.6)
        badge.size_to_fit()
        cell.accessory_view = badge

        return cell

    def tableview_did_select(self, tableview, section, row):
        tableview.selected_row = -1
        food = self._results[row]
        nav = self._find_nav()
        if not nav:
            return
        sheet = LogFoodSheet(
            food=food,
            date_str=self.date_str,
            default_meal=self.default_meal,
            on_logged=self.on_logged,
            frame=self.frame,
        )
        sheet.name = food['name']
        nav.push_view(sheet)

    # ── Custom food ───────────────────────────────────────────────────────────

    def _create_custom(self, sender):
        nav = self._find_nav()
        if not nav:
            return
        cfv = CreateFoodView(
            on_created=self._on_custom_created,
            frame=self.frame,
        )
        cfv.name = 'Create Food'
        nav.push_view(cfv)

    def _on_custom_created(self, food):
        # Open the log sheet for the newly created food
        nav = self._find_nav()
        if not nav:
            return
        sheet = LogFoodSheet(
            food=food,
            date_str=self.date_str,
            default_meal=self.default_meal,
            on_logged=self.on_logged,
            frame=self.frame,
        )
        sheet.name = food['name']
        nav.push_view(sheet)

    def _find_nav(self):
        v = self.superview
        while v:
            if isinstance(v, ui.NavigationView):
                return v
            v = v.superview
        return None
