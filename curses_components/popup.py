"""Reusable curses popup components."""

import curses


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

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.scroll_pos = 0

    @property
    def rows(self):
        """Return a list of (left, right) string tuples to display."""
        return []

    def display(self):
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
            win.border()
            title = self.title
            win.addstr(0, max(0, (win_width - len(title)) // 2), title, curses.A_REVERSE)

            for i in range(1, win_height - 1):
                win.addstr(i, 1, " " * (win_width - 2))

            text_y = 2
            for left, right in content[self.scroll_pos:]:
                if text_y >= win_height - 2:
                    break
                win.addstr(text_y, 2, left, curses.A_BOLD)
                if right:
                    win.addstr(text_y, self.key_col_width, right)
                text_y += 1

            win.addstr(win_height - 2, 2, "Press 'q' to close...")
            win.noutrefresh()
            curses.doupdate()

            key = win.getch()
            if key in (ord('q'), ord('?')):
                break
            if key in (curses.KEY_UP, ord('k')):
                self.scroll_pos = max(0, self.scroll_pos - 1)
            elif key in (curses.KEY_DOWN, ord('j')):
                self.scroll_pos = min(max_scroll, self.scroll_pos + 1)


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
