"""
Settings / Goals view.
Lets the user configure daily calorie and macro targets.
Also shows micronutrient goals for optional tracking.
"""

import ui
import storage
from models import make_goals


GOAL_FIELDS = [
    # (storage_key, display_label, unit)
    ('calories', 'Calories', 'kcal'),
    ('fat',      'Fat',      'g'),
    ('protein',  'Protein',  'g'),
    ('carbs',    'Carbs',    'g'),
    ('fiber',    'Fiber',    'g'),
    ('sugar',    'Sugar',    'g'),
    ('sodium',   'Sodium',   'mg'),
]


class SettingsView(ui.View):
    """Form for editing daily nutrition goals."""

    def __init__(self, on_save=None, **kwargs):
        super().__init__(**kwargs)
        self.on_save = on_save
        self.background_color = (0.07, 0.07, 0.07)
        self._fields = {}
        self._build_ui()
        self._load_goals()

    def _build_ui(self):
        W = self.width or 375
        PAD = 16

        scroll = ui.ScrollView(frame=(0, 0, W, self.height - 60))
        scroll.background_color = (0.07, 0.07, 0.07)  # match app dark background
        scroll.content_size = (W, len(GOAL_FIELDS) * 56 + 60)

        _BG = (0.07, 0.07, 0.07)   # dark background shared by this view
        _FIELD_BG = (0.14, 0.14, 0.14)  # slightly lighter for input areas

        y = 16
        header = ui.Label(frame=(PAD, y, W - PAD * 2, 22))
        header.text = 'Daily Goals'
        header.font = ('<system-bold>', 17)
        header.text_color = (1, 1, 1)
        header.background_color = _BG   # opaque bg so text is never on white
        scroll.add_subview(header)
        y += 30

        sub = ui.Label(frame=(PAD, y, W - PAD * 2, 18))
        sub.text = 'All nutrients are per-day targets.'
        sub.font = ('<system>', 12)
        sub.text_color = (0.5, 0.5, 0.5)
        sub.background_color = _BG
        scroll.add_subview(sub)
        y += 28

        for key, label, unit in GOAL_FIELDS:
            lbl = ui.Label(frame=(PAD, y, W - PAD * 2, 16))
            lbl.text = f'{label} ({unit})'
            lbl.font = ('<system>', 12)
            lbl.text_color = (0.55, 0.55, 0.55)
            lbl.background_color = _BG   # opaque so text never renders on white
            scroll.add_subview(lbl)

            # Wrap TextField in an opaque container — the most reliable way to
            # guarantee a dark backing regardless of ScrollView internal white layer.
            tf_bg = ui.View(frame=(PAD, y + 16, W - PAD * 2, 32))
            tf_bg.background_color = _FIELD_BG
            tf_bg.corner_radius = 6
            scroll.add_subview(tf_bg)

            tf = ui.TextField(frame=(4, 0, W - PAD * 2 - 8, 32))
            tf.keyboard_type = ui.KEYBOARD_DECIMAL_PAD
            tf.border_style = 0          # remove iOS rounded-rect white fill
            tf.background_color = (0, 0, 0, 0)  # transparent; bg comes from tf_bg
            tf.text_color = (1, 1, 1)
            tf.tint_color = (0.29, 0.85, 0.60)
            tf_bg.add_subview(tf)
            self._fields[key] = tf
            y += 56

        self.add_subview(scroll)

        # Save button
        btn = ui.Button(frame=(PAD, self.height - 52, W - PAD * 2, 44))
        btn.title = 'Save Goals'
        btn.font = ('<system-bold>', 16)
        btn.background_color = (0.29, 0.85, 0.60)
        btn.tint_color = (1, 1, 1)
        btn.corner_radius = 10
        btn.action = self._save
        self.add_subview(btn)

    def _load_goals(self):
        goals = storage.load_goals()
        for key, tf in self._fields.items():
            val = goals.get(key, 0)
            tf.text = str(int(val)) if val == int(val) else str(val)

    def _save(self, sender):
        def fval(key, default=0):
            txt = self._fields[key].text.strip()
            try:
                return float(txt) if txt else default
            except ValueError:
                return default

        goals = make_goals(
            calories=fval('calories', 2000),
            fat=fval('fat', 50),
            protein=fval('protein', 100),
            carbs=fval('carbs', 150),
            fiber=fval('fiber', 25),
            sugar=fval('sugar', 50),
            sodium=fval('sodium', 2300),
        )
        storage.save_goals(goals)

        if self.on_save:
            self.on_save()

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
