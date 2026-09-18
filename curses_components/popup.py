# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cobus Nel
"""Reusable curses popup components."""

import curses
from collections import Counter

from curses_components.theme import resolve_color


class ScrollablePopup:
    """
    A bordered, scrollable popup window centered on the parent screen.

    Subclass this and implement `title` and `rows` to create a popup with
    arbitrary two-column content.  Each row is a (left, right) string tuple;
    an empty-string left value is rendered as a blank separator line.

    Key bindings inside the popup:
        j / Down   scroll down
        k / Up     scroll up
        q / ?      close
    """

    title = ""
    key_col_width = 20  # characters reserved for the left column

    def __init__(self, stdscr, title=None, rows=None, key_col_width=None,
                 fg_color=None, bg_color=None, border_color=None):
        self.stdscr = stdscr
        if title is not None:
            self.title = title
        self._rows = rows
        if key_col_width is not None:
            self.key_col_width = key_col_width
        self.fg_color = fg_color
        self.bg_color = bg_color
        self.border_color = border_color
        self.scroll_pos = 0

    def _init_colors(self):
        """Initialize color pairs used by the popup."""
        bg = resolve_color(self.bg_color, -1)
        fg = resolve_color(self.fg_color, -1)
        border = resolve_color(self.border_color, -1)
        curses.init_pair(5, fg, bg)
        curses.init_pair(6, border, bg)

    @property
    def rows(self):
        """Return a list of (left, right) string tuples to display."""
        return self._rows or []

    def display(self):
        self._init_colors()
        height, width = self.stdscr.getmaxyx()
        win_height = min(25, height - 2)
        win_width = min(80, width - 2)
        pos_y = max(0, (height - win_height) // 2)
        pos_x = max(0, (width - win_width) // 2)
        win = curses.newwin(win_height, win_width, pos_y, pos_x)
        win.keypad(True)

        content = self.rows
        max_scroll = max(0, len(content) - (win_height - 4))

        while True:
            win.attrset(curses.color_pair(6))
            win.border()
            title = self.title
            title_x = max(0, (win_width - len(title)) // 2)
            win.addstr(
                0,
                title_x,
                title[:max(0, win_width - title_x - 1)],
                curses.color_pair(6) | curses.A_REVERSE,
            )

            for i in range(1, win_height - 1):
                win.addstr(i, 1, " " * (win_width - 2), curses.color_pair(5))

            text_y = 2
            for left, right in content[self.scroll_pos:]:
                if text_y >= win_height - 2:
                    break
                left_width = max(0, self.key_col_width - 3)
                right_width = max(0, win_width - self.key_col_width - 2)
                win.addstr(
                    text_y,
                    2,
                    left[:left_width],
                    curses.color_pair(5) | curses.A_BOLD,
                )
                if right:
                    win.addstr(
                        text_y,
                        self.key_col_width,
                        right[:right_width],
                        curses.color_pair(5),
                    )
                text_y += 1

            footer = "Press 'q' to close..."
            win.addstr(
                win_height - 2,
                2,
                footer[:max(0, win_width - 4)],
                curses.color_pair(5),
            )
            win.noutrefresh()
            curses.doupdate()

            key = win.getch()
            if key in (ord('q'), ord('?')):
                break
            if key in (curses.KEY_UP, ord('k')):
                self.scroll_pos = max(0, self.scroll_pos - 1)
            elif key in (curses.KEY_DOWN, ord('j')):
                self.scroll_pos = min(max_scroll, self.scroll_pos + 1)


class TextPopup(ScrollablePopup):
    """Popup displaying one scrollable line of text per row."""

    def __init__(self, stdscr, lines, **kwargs):
        super().__init__(stdscr, **kwargs)
        self.lines = [str(line) for line in lines]

    @property
    def rows(self):
        return [(line, "") for line in self.lines]

    def display(self):
        original_key_col_width = self.key_col_width
        screen_width = self.stdscr.getmaxyx()[1]
        self.key_col_width = min(80, max(1, screen_width - 2))
        try:
            super().display()
        finally:
            self.key_col_width = original_key_col_width


class HelpPopup(ScrollablePopup):
    """Help popup for GridComponent."""

    title = "Help"

    @property
    def rows(self):
        return [
            ("Navigation", ""),
            ("j, k, h, l", "Move down, up, left, right"),
            ("Arrow keys", "Move down, up, left, right"),
            ("Home/End", "Go to the first/last row"),
            ("Page Up/Down", "Move up/down one page"),
            ("^/$", "Go to the first/last column"),
            ("", ""),
            ("Searching", ""),
            ("/", "Enter search mode (substring)"),
            ("r/<pattern>", "Regex search (e.g. r/^\\d+$)"),
            ("n / N", "Find next / previous match"),
            ("ESC", "Exit search mode"),
            ("", ""),
            ("Input Mode", ""),
            (":", "Enter input mode"),
            ("q or quit", "Quit the application"),
            ("row number", "Go to specific row"),
            ("$", "Go to last row"),
            ("col <name>", "Jump to column by name (prefix ok)"),
            ("freeze <n>", "Pin first n columns (freeze 0 to clear)"),
            ("sort", "Sort by current column ascending"),
            ("sort desc", "Sort by current column descending"),
            ("sort col1 col2!", "col1 asc, col2 desc (! = descending)"),
            ("copy", "Copy current cell value"),
            ("copyrow", "Copy current row as JSON"),
            ("count", "Count distinct values in current column"),
            ("export <file>", "Export current data to CSV file"),
            ("ESC", "Exit input mode"),
            ("", ""),
            ("Row Filtering", ""),
            ("filter <val>", "Exact match on current column"),
            ("filter <col> <val>", "Exact match on named column"),
            ("filter *val*", "Wildcard match (* and ? supported)"),
            ("filter reset", "Clear active filter"),
            ("", ""),
            ("Column Width", ""),
            ("Ctrl + Left/Right", "Decrease/increase width of current column"),
            ("", ""),
            ("Marks", ""),
            ("m", "Set mark at current row"),
            ("'", "Jump to marked row"),
            ("", ""),
            ("Other", ""),
            ("#", "Toggle row number gutter"),
            ("?", "Show this help screen"),
            ("", ""),
            ("Info Bar (top row)", ""),
            ("numeric column", "Shows min/max/avg/count for column"),
        ]


class ValueCountPopup(ScrollablePopup):
    """Popup displaying the frequency of each value in a grid column."""

    title = "Value Counts"

    def __init__(self, stdscr, column, values, **colors):
        super().__init__(stdscr, **colors)
        self.column = column
        self.counts = Counter(values)
        self.key_col_width = min(
            40,
            max(
                24,
                max((len(str(value)) for value in self.counts), default=0) + 3,
            ),
        )

    @property
    def rows(self):
        rows = [("Value", "Count"), ("", "")]
        rows.extend(
            (str(value), str(count))
            for value, count in sorted(
                self.counts.items(),
                key=lambda item: (-item[1], str(item[0])),
            )
        )
        return rows

    def display(self):
        self.title = f"{self.column} ({len(self.counts)} unique)"
        super().display()


class EditorHelpPopup(ScrollablePopup):
    """Help popup for EditorPopup."""

    title = "Editor Help"

    @property
    def rows(self):
        return [
            ("Normal Mode", ""),
            ("h j k l", "Move left / down / up / right"),
            ("Arrow keys", "Move left / down / up / right"),
            ("w / b", "Move word forward / backward"),
            ("0 / $", "Start / end of line"),
            ("gg / G", "First / last line"),
            ("PgUp / PgDn", "Scroll one page up / down"),
            ("", ""),
            ("Editing", ""),
            ("i", "Insert before cursor"),
            ("a", "Insert after cursor"),
            ("o / O", "New line below / above and insert"),
            ("x", "Delete character under cursor"),
            ("dw", "Delete word under cursor"),
            ("dd", "Delete current line"),
            ("yy", "Yank (copy) current line"),
            ("p", "Paste yanked line below"),
            ("u", "Undo"),
            ("", ""),
            ("Search", ""),
            ("/", "Enter search mode"),
            ("n / N", "Find next / previous match"),
            ("ESC", "Cancel search"),
            ("", ""),
            ("Command Mode  (:)", ""),
            (":w [file]", "Save; optional filename"),
            (":q", "Quit (warns if unsaved)"),
            (":q!", "Quit discarding changes"),
            (":wq [file]", "Save and quit"),
            (":x [file]", "Save and quit (alias for :wq)"),
            ("<number>", "Jump to line number"),
            ("", ""),
            ("Substitute", ""),
            (":s/pat/rep", "Replace first match on current line"),
            (":s/pat/rep/g", "Replace all matches on current line"),
            (":%s/pat/rep", "Replace first match on every line"),
            (":%s/pat/rep/g", "Replace all matches on every line"),
            ("", ""),
            ("Sort", ""),
            (":sort", "Sort all lines ascending"),
            (":sort!", "Sort all lines descending"),
            (":sort u", "Sort ascending, remove duplicates"),
            (":sort! u", "Sort descending, remove duplicates"),
            ("", ""),
            ("Other", ""),
            (":help", "Show this help screen"),
        ]
