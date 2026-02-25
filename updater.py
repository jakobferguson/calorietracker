"""
CalorieTracker auto-updater for Pythonista.

Downloads the latest versions of all app files from GitHub and replaces
local copies when they differ. Run this script independently from main.py.

Configuration:
  Set GITHUB_RAW_BASE to the raw content URL for your repo branch.
  Format: https://raw.githubusercontent.com/<user>/<repo>/<branch>
"""

import ui
import requests
import os
import hashlib
import threading

try:
    from objc_util import on_main_thread as _on_main_thread
    def _main(fn, *args): _on_main_thread(fn)(*args)
except ImportError:
    def _main(fn, *args): fn(*args)

# ── Configuration ─────────────────────────────────────────────────────────────

GITHUB_RAW_BASE = 'https://raw.githubusercontent.com/jakobferguson/calorietracker/claude/calorie-tracker-app-g20kn'

APP_FILES = [
    'main.py',
    'models.py',
    'storage.py',
    'api.py',
    'home_view.py',
    'meal_view.py',
    'search_view.py',
    'history_view.py',
    'settings_view.py',
    'updater.py',
]

# The directory where this updater lives (same as the app)
APP_DIR = os.path.dirname(os.path.abspath(__file__))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _md5(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def _fetch(filename):
    """Download a file from GitHub. Returns text content or raises."""
    url = f'{GITHUB_RAW_BASE}/{filename}'
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text


def _local_content(filename):
    path = os.path.join(APP_DIR, filename)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return None


def _write(filename, content):
    path = os.path.join(APP_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


# ── Updater UI ────────────────────────────────────────────────────────────────

class UpdaterView(ui.View):
    """Simple progress view shown during update."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0.07, 0.07, 0.07)
        self._build_ui()

    def _build_ui(self):
        W = self.width or 375
        PAD = 24

        title = ui.Label(frame=(PAD, 40, W - PAD * 2, 30))
        title.text = 'CalorieTracker Updater'
        title.font = ('<system-bold>', 20)
        title.text_color = (1, 1, 1)
        title.alignment = ui.ALIGN_CENTER
        self.add_subview(title)

        self._status = ui.Label(frame=(PAD, 82, W - PAD * 2, 22))
        self._status.text = 'Checking for updates…'
        self._status.font = ('<system>', 14)
        self._status.text_color = (0.6, 0.6, 0.6)
        self._status.alignment = ui.ALIGN_CENTER
        self.add_subview(self._status)

        self._spinner = ui.ActivityIndicator(frame=(W / 2 - 16, 116, 32, 32))
        self._spinner.style = ui.ACTIVITY_INDICATOR_STYLE_WHITE
        self._spinner.start()
        self.add_subview(self._spinner)

        self._log = ui.TextView(frame=(PAD, 164, W - PAD * 2, 260))
        self._log.editable = False
        self._log.background_color = (0.12, 0.12, 0.12)
        self._log.text_color = (0.75, 0.75, 0.75)
        self._log.font = ('<system>', 12)
        self._log.corner_radius = 8
        self.add_subview(self._log)

        self._btn = ui.Button(frame=(PAD, 440, W - PAD * 2, 44))
        self._btn.title = 'Close'
        self._btn.font = ('<system-bold>', 16)
        self._btn.background_color = (0.20, 0.20, 0.20)
        self._btn.tint_color = (0.29, 0.85, 0.60)
        self._btn.corner_radius = 10
        self._btn.action = self._close
        self._btn.enabled = False
        self.add_subview(self._btn)

    def _close(self, sender):
        self.close()

    def _append_log(self, line):
        current = self._log.text or ''
        self._log.text = current + line + '\n'

    def run_update(self):
        threading.Thread(target=self._do_update, daemon=True).start()

    def _do_update(self):
        updated = []
        skipped = []
        errors = []

        for filename in APP_FILES:
            _main(self._set_status, f'Checking {filename}…')
            try:
                remote = _fetch(filename)
            except Exception as e:
                errors.append(filename)
                _main(self._append_log, f'  ✗ {filename}: {e}')
                continue

            local = _local_content(filename)
            if local is not None and _md5(local) == _md5(remote):
                skipped.append(filename)
                _main(self._append_log, f'  – {filename}: up to date')
            else:
                _write(filename, remote)
                updated.append(filename)
                status = 'new' if local is None else 'updated'
                _main(self._append_log, f'  ✓ {filename}: {status}')

        summary = (
            f'\nDone. '
            f'{len(updated)} updated, '
            f'{len(skipped)} unchanged'
            + (f', {len(errors)} errors' if errors else '')
            + '.'
        )
        if updated:
            summary += '\n\nRestart the app to apply changes.'

        _main(self._finish, summary)

    def _set_status(self, text):
        self._status.text = text

    def _finish(self, summary):
        self._spinner.stop()
        self._status.text = 'Update complete.'
        self._append_log(summary)
        self._btn.enabled = True
        self._btn.background_color = (0.29, 0.85, 0.60)
        self._btn.tint_color = (1, 1, 1)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    screen_w, screen_h = ui.get_screen_size()
    view = UpdaterView(frame=(0, 0, screen_w, screen_h))
    view.present('sheet')
    view.run_update()


if __name__ == '__main__':
    main()
