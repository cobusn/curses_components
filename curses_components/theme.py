"""Shared color definitions for curses_components.

COLORS maps human-readable color names to curses color constants.
Import this module anywhere a color name needs to be resolved to a
curses integer — safe to import outside a curses session because the
curses color constants are plain integers defined at import time.
"""

import curses


COLORS = {
    'black':   curses.COLOR_BLACK,
    'blue':    curses.COLOR_BLUE,
    'cyan':    curses.COLOR_CYAN,
    'green':   curses.COLOR_GREEN,
    'magenta': curses.COLOR_MAGENTA,
    'red':     curses.COLOR_RED,
    'white':   curses.COLOR_WHITE,
    'yellow':  curses.COLOR_YELLOW,
}


def resolve_color(name, default):
    """Return the curses color constant for a color name.

    Args:
        name: A color name string (e.g. 'green').
        default: Curses color constant returned when name is not found.

    Returns:
        The matching curses color constant, or default if not found.
    """
    return COLORS.get(name, default)
