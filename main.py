"""
CalorieTracker — main entry point for Pythonista on iOS.

Run this file from Pythonista. It sets up a NavigationView with the
HomeView as the root and presents it full-screen.

Requirements (all available in Pythonista):
  - ui       (built-in)
  - requests (built-in in Pythonista)
  - json     (stdlib)
  - threading (stdlib)
"""

import ui
import sys
import os

# Make sure the script's directory is on the path so sibling modules import correctly.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from home_view import HomeView


def main():
    # Create the home view sized to the full screen
    screen_w, screen_h = ui.get_screen_size()

    home = HomeView(frame=(0, 0, screen_w, screen_h))
    home.name = 'CalorieTracker'

    # Wrap in a NavigationView (provides the back button and nav bar)
    nav = ui.NavigationView(home)
    nav.bar_tint_color = (0.10, 0.10, 0.10)
    nav.title_color = (1, 1, 1)
    nav.tint_color = (0.29, 0.85, 0.60)

    # Give the home view a reference to the nav controller so it can push views
    home.nav_controller = nav

    # Present full-screen on iPhone; on iPad you could use 'sheet'
    nav.present('fullscreen', hide_title_bar=True, animated=False)


if __name__ == '__main__':
    main()
