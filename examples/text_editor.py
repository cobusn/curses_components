#!/usr/bin/env python
"""Test driver for EditorPopup.

Usage:
    python test_editor.py                   # fullscreen with built-in SQL sample
    python test_editor.py <file>            # fullscreen with existing file
    python test_editor.py --new <file>      # fullscreen with blank buffer
    python test_editor.py --size WxH [file] # explicit size, e.g. 100x30
"""

import curses
import os
import sys

from curses_components.editor import EditorPopup

SAMPLE_SQL = """\
-- Sample SQL script
SELECT
    c.customer_id,
    c.name,
    c.email,
    SUM(o.amount) AS total_spent
FROM customers c
JOIN orders o
    ON o.customer_id = c.customer_id
WHERE c.active = 1
  AND o.created_at >= '2025-01-01'
GROUP BY
    c.customer_id,
    c.name,
    c.email
HAVING total_spent > 100
ORDER BY total_spent DESC
LIMIT 50;
"""


def main(stdscr):
    curses.curs_set(0)

    filename = None
    initial_text = SAMPLE_SQL
    win_width = None
    win_height = None

    args = sys.argv[1:]
    while args and args[0].startswith('--'):
        flag = args.pop(0)
        if flag == '--new' and args:
            filename = args.pop(0)
            initial_text = ''
        elif flag == '--size' and args:
            size_str = args.pop(0)
            try:
                win_width, win_height = (int(v) for v in size_str.lower().split('x'))
            except ValueError:
                pass

    if args:
        filename = args[0]
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                initial_text = f.read()
        else:
            initial_text = ''

    editor = EditorPopup(stdscr, title='Vi Editor', width=win_width,
                         height=win_height, bold=True, bold_background=False)
    result = editor.edit(text=initial_text, filename=filename)

    # After the popup closes, show outcome on the main screen
    stdscr.clear()
    stdscr.refresh()
    height, width = stdscr.getmaxyx()

    if result is None:
        msg = 'Quit without saving.'
        stdscr.addstr(height // 2, max(0, (width - len(msg)) // 2), msg)
    else:
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(result)
                msg = f'Saved to {filename}  ({len(result.splitlines())} lines)'
            except OSError as e:
                msg = f'Write failed: {e}'
        else:
            msg = f'Saved (no file)  ({len(result.splitlines())} lines)'

        lines = result.splitlines()
        preview_rows = min(height - 4, len(lines))
        for i, line in enumerate(lines[:preview_rows]):
            try:
                stdscr.addstr(i, 0, line[:width - 1])
            except curses.error:
                pass
        try:
            stdscr.addstr(height - 2, 0, msg[:width - 1], curses.A_REVERSE)
            stdscr.addstr(height - 1, 0, 'Press any key to exit...'[:width - 1])
        except curses.error:
            pass

    stdscr.getch()


if __name__ == '__main__':
    curses.wrapper(main)
