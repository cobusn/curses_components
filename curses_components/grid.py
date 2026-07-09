"""A curses-based component for displaying tabular data."""

import csv
import curses
import fnmatch
import itertools
import json
import logging
import re
import time
import pyperclip

from curses_components.popup import HelpPopup
from curses_components.theme import resolve_color


logging.basicConfig(filename='help_debug.log', level=logging.DEBUG)


class QuitApplication(Exception):
    """Custom exception to signal application exit."""



class GridComponent:
    """
    A curses-based component for displaying and interacting with tabular data.
    Provides navigation, searching, sorting, and column resizing.
    """

    def __init__(self, fg_color='green', bg_color='black', border_color='cyan',
                 max_col_width=20, float_fmt='.2f'):
        self.fg_color = fg_color
        self.bg_color = bg_color
        self.border_color = border_color
        self.max_col_width = max_col_width
        self.float_fmt = float_fmt
        self.top_row = 0
        self.left_col = 0
        self.row_idx = 0
        self.col_idx = 0
        self.input_mode = False
        self.input_buffer = ""
        self.search_mode = False
        self.search_buffer = ""
        self.last_search = ""
        self.search_is_regex = False
        self.error_message = None
        self.error_message_expiry = 0
        self.stdscr = None  # Initialized in _display
        self.data = []  # Initialized in _display
        self.columns = []  # Initialized in _display
        self.max_rows = 0  # Initialized in _display
        self.col_widths = {}  # Initialized in _prepare_data
        self._all_data = []  # Initialized in _prepare_data
        self.active_filter = None  # (column, value) tuple or None
        self.frozen_cols = 0
        self.mark_row = None  # row index of the marked row
        self.show_row_numbers = True
        self.commands = {  # Initialized in _handle_input_mode
            "$": self._cmd_dollar,
            "col": self._cmd_col,
            "copy": self._cmd_copy,
            "copyrow": self._cmd_copyrow,
            "export": self._cmd_export,
            "filter": self._cmd_filter,
            "freeze": self._cmd_freeze,
            "help": self._cmd_help,
            "q": self._cmd_quit,
            "quit": self._cmd_quit,
            "sort": self._cmd_sort,
        }

    def display(self, data, columns=None, max_rows=10000):
        """
        Initializes the curses application and displays the grid.

        Args:
            data (list of dict): The tabular data to display.
            columns (list, optional): List of column headers to display.
                                      If None, uses keys from the first data row.
            max_rows (int, optional): Maximum number of rows to display. Defaults to 10000.
        """
        try:
            curses.wrapper(self._display, data, columns, max_rows)
        except QuitApplication:
            pass

    def _display(self, stdscr, data, columns, max_rows):
        """Internal method to set up and run the curses application."""
        self.stdscr = stdscr
        self.data = data
        self.columns = columns
        self.max_rows = max_rows
        self._init_curses()
        self._prepare_data()
        self._event_loop()

    def _init_curses(self):
        """Initializes curses settings and color pairs."""
        self.stdscr.timeout(100)
        curses.curs_set(0)  # Hide cursor
        curses.start_color()
        curses.use_default_colors()

        bg = resolve_color(self.bg_color, curses.COLOR_BLACK)
        fg = resolve_color(self.fg_color, curses.COLOR_GREEN)
        curses.init_pair(1, fg, bg)   # Main display color

        # Search highlight
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_YELLOW)

        # Margins
        mc = resolve_color(self.border_color, curses.COLOR_CYAN)
        curses.init_pair(3, mc, bg)

        # Border
        curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_RED)  # Error message

    def _prepare_data(self):
        """Prepares data and calculates initial column widths."""
        self.data = list(itertools.islice(self.data, self.max_rows))
        if not self.columns and self.data:
            self.columns = list(self.data[0].keys())
        if not self.columns:
            self.columns = []
        self._all_data = self.data
        self.col_widths = self._get_col_widths()
        self.col_is_numeric = {
            col: any(self.is_number(str(row.get(col, ''))) for row in self.data)
            for col in self.columns
        }

    def _get_col_widths(self):
        """Calculates optimal column widths based on content and max_col_width."""
        col_widths = {col: len(col) for col in self.columns}
        for row in self.data:
            for col in self.columns:
                col_widths[col] = min(
                    self.max_col_width,
                    max(col_widths[col], len(str(row.get(col, ''))))
                )
        return col_widths

    def _update_col_width(self, delta):
        """Adjusts the width of the current column."""
        if self.columns:
            col = self.columns[self.col_idx]
            self.col_widths[col] = max(1, self.col_widths[col] + delta)

    @staticmethod
    def is_number(value_str):
        """Checks if a string can be converted to a float."""
        try:
            float(value_str)
            return True
        except (ValueError, TypeError):
            return False

    def show_error(self, message, delay=0.8):
        """Displays an error message in the status bar."""
        self.error_message = message
        self.error_message_expiry = time.time() + delay

    def _get_col_stats(self, col):
        """Returns (min, max, avg, count) for a numeric column over current data, or None."""
        values = [float(str(row.get(col, ''))) for row in self.data
                  if self.is_number(str(row.get(col, '')))]
        if not values:
            return None
        return min(values), max(values), sum(values) / len(values), len(values)

    def _draw_selected_cell_info_bar(self, max_width):
        """Draws information about the selected cell at the top."""
        try:
            self.stdscr.addstr(0, 0, " " * (max_width - 1))
        except curses.error:
            pass
        if not (self.data and self.row_idx < len(self.data) and self.col_idx < len(self.columns)):
            return
        col = self.columns[self.col_idx]
        value = self.data[self.row_idx].get(col, '')
        display_text = f"> {str(value)}"
        try:
            self.stdscr.addstr(0, 0, display_text[:max_width - 1])
        except curses.error:
            pass
        if self.col_is_numeric.get(col, False):
            stats = self._get_col_stats(col)
            if stats:
                mn, mx, avg, count = stats
                fmt = lambda v: f"{v:.4g}"
                stats_text = f" min:{fmt(mn)} max:{fmt(mx)} avg:{fmt(avg)} n:{count} "
                stats_x = max_width - len(stats_text) - 1
                if stats_x > len(display_text) + 1:
                    try:
                        self.stdscr.addstr(0, stats_x, stats_text, curses.color_pair(3))
                    except curses.error:
                        pass

    def _draw(self):
        """Draws the entire grid, including header, data, and status bar."""
        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()
        row_num_width = (len(str(len(self.data))) + 2) if self.show_row_numbers else 0
        self._draw_selected_cell_info_bar(width)
        self._draw_header(row_num_width, width)
        self._draw_data(height, row_num_width, width)
        self._draw_status_bar(width, height)
        self.stdscr.noutrefresh()
        curses.doupdate()

    def _draw_header(self, row_num_width, max_width):
        """Draws the column headers."""
        if row_num_width:
            try:
                self.stdscr.addstr(1, 0, " ".center(row_num_width), curses.color_pair(3) | curses.A_REVERSE)
            except curses.error:
                pass
        current_x = row_num_width
        # Frozen columns first
        for col_name in self.columns[:self.frozen_cols]:
            if current_x + self.col_widths[col_name] + 1 > max_width:
                break
            try:
                self.stdscr.addstr(1, current_x, col_name.center(self.col_widths[col_name] + 1),
                                   curses.color_pair(3) | curses.A_REVERSE | curses.A_BOLD)
            except curses.error:
                pass
            current_x += self.col_widths[col_name] + 1
        # Scrollable columns
        for col_name in self.columns[self.left_col:]:
            if current_x + self.col_widths[col_name] + 1 > max_width:
                break
            try:
                self.stdscr.addstr(1, current_x, col_name.center(self.col_widths[col_name] + 1),
                                   curses.color_pair(3) | curses.A_REVERSE)
            except curses.error:
                pass
            current_x += self.col_widths[col_name] + 1

    def _draw_data(self, max_height, row_num_width, max_width):
        """Draws the main data rows."""
        for row_offset, row_data in enumerate(self.data[self.top_row:]):
            if row_offset + 3 >= max_height:
                break
            current_y = row_offset + 2
            abs_row = self.top_row + row_offset
            if row_num_width:
                marker = ">" if abs_row == self.mark_row else " "
                row_num_str = str(abs_row + 1).rjust(row_num_width - 2) + marker + " "
                try:
                    self.stdscr.addstr(current_y, 0, row_num_str, curses.color_pair(3) | curses.A_REVERSE)
                except curses.error:
                    pass
            current_x = row_num_width
            # Frozen columns first
            for abs_col_idx, col_name in enumerate(self.columns[:self.frozen_cols]):
                if current_x + self.col_widths[col_name] + 1 > max_width:
                    break
                self._draw_cell(current_y, current_x, row_offset, abs_col_idx, row_data, col_name, max_width)
                current_x += self.col_widths[col_name] + 1
            # Scrollable columns
            for abs_col_idx, col_name in enumerate(self.columns[self.left_col:], start=self.left_col):
                if current_x + self.col_widths[col_name] + 1 > max_width:
                    break
                self._draw_cell(current_y, current_x, row_offset, abs_col_idx, row_data, col_name, max_width)
                current_x += self.col_widths[col_name] + 1

    def _draw_status_bar(self, max_width, max_height):
        """Draws the status bar at the bottom of the screen."""
        try:
            if max_width > 0:
                self.stdscr.addstr(max_height - 1, 0, " " * (max_width - 1))
            if self.error_message and time.time() < self.error_message_expiry:
                error_text = self.error_message[:max_width - 1]
                self.stdscr.addstr(max_height - 1, 0, error_text, curses.color_pair(4))
            else:
                self.error_message = None
                status_bar_left = ""
                if self.input_mode:
                    status_bar_left = ":" + self.input_buffer
                elif self.search_mode:
                    status_bar_left = "/" + self.search_buffer
                self.stdscr.addstr(max_height - 1, 0, status_bar_left)
                if self.active_filter:
                    col, val = self.active_filter
                    filter_text = f" [{col}={val}] "
                    if max_width > len(filter_text) + 1:
                        self.stdscr.addstr(
                            max_height - 1,
                            max_width - len(filter_text) - 1,
                            filter_text,
                            curses.color_pair(2),
                        )
                else:
                    sb_r = f" {self.row_idx + 1}/{len(self.data)} "
                    if max_width > len(sb_r) + 1:
                        self.stdscr.addstr(
                            max_height - 1,
                            max_width - len(sb_r) - 1,
                            sb_r
                        )
        except curses.error:
            pass

    def _draw_cell(self, pos_y, pos_x, row_offset, abs_col_idx, row_data, col_name, max_width):
        """Draws a single cell with appropriate formatting and highlighting."""
        value = row_data.get(col_name, '')
        if isinstance(value, float):
            value = format(value, self.float_fmt)
        col_width = self.col_widths[col_name]
        text = str(value)[:col_width]
        align_func = str.rjust if self.col_is_numeric.get(col_name, False) else str.ljust
        display_value = align_func(text, col_width)
        is_current_cell = (self.row_idx == self.top_row + row_offset and
                           self.col_idx == abs_col_idx)
        value_str = str(value)
        has_match = (self.last_search and (
            re.search(self.last_search, value_str) if self.search_is_regex
            else self.last_search in value_str
        ))
        try:
            if has_match:
                self._draw_highlighted_cell(pos_y, pos_x, display_value, is_current_cell, value_str)
            else:
                attr = curses.color_pair(1)
                if is_current_cell:
                    attr |= curses.A_REVERSE
                else:
                    attr |= curses.A_BOLD
                self.stdscr.addstr(pos_y, pos_x, display_value, attr)
            if pos_x + col_width < max_width:
                self.stdscr.addstr(pos_y, pos_x + col_width, " ")
        except curses.error:
            pass

    def _draw_highlighted_cell(self, pos_y, pos_x, display_value, is_current_cell, raw_value=None):
        """Draws a cell with search term highlighted."""
        if self.search_is_regex:
            m = re.search(self.last_search, raw_value or display_value)
            start_idx = display_value.find((raw_value or display_value)[m.start():m.end()]) if m else -1
            end_idx = start_idx + (m.end() - m.start()) if m and start_idx != -1 else start_idx
        else:
            start_idx = display_value.find(self.last_search)
            end_idx = start_idx + len(self.last_search)
        attr = curses.color_pair(1)
        highlight_attr = curses.color_pair(2)
        if is_current_cell:
            attr |= curses.A_REVERSE
            highlight_attr |= curses.A_REVERSE
        self.stdscr.addstr(pos_y, pos_x, display_value[:start_idx], attr)
        self.stdscr.addstr(pos_y, pos_x + start_idx, display_value[start_idx:end_idx], highlight_attr)  # noqa
        self.stdscr.addstr(pos_y, pos_x + end_idx, display_value[end_idx:], attr)

    def _cmd_quit(self, _cmds):
        """Handles the 'quit' command."""
        raise QuitApplication

    def _cmd_copy(self, _cmds):
        """Handles the 'copy' command, copying the current cell's value to clipboard."""
        if self.data and self.row_idx < len(self.data) and self.col_idx < len(self.columns):
            value = self.data[self.row_idx].get(self.columns[self.col_idx], '')
            pyperclip.copy(str(value))

    def _cmd_copyrow(self, _cmds):
        """Handles the 'copyrow' command, copying the current row as JSON."""
        if self.data and self.row_idx < len(self.data):
            row = {col: self.data[self.row_idx].get(col, '') for col in self.columns}
            pyperclip.copy(json.dumps(row, ensure_ascii=False))
            self.show_error("Row copied as JSON", delay=0.8)

    def _cmd_export(self, _cmds):
        """Handles the 'export' command, writing current data to a CSV file."""
        if not _cmds:
            self.show_error("Usage: export <filename>")
            return
        filename = _cmds[0]
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.columns, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(self.data)
            self.show_error(f"Exported {len(self.data)} rows to {filename}", delay=1.5)
        except OSError as e:
            self.show_error(f"Export failed: {e}")

    def _cmd_help(self, _cmds):
        """Handles the 'help' command, displaying the help screen."""
        help_screen = HelpPopup(self.stdscr)
        help_screen.display()

    def _cmd_dollar(self, _cmds):
        """Handles the '$' command, moving to the last row."""
        if not self.data:
            return
        self.row_idx = len(self.data) - 1
        self._adjust_scroll_position()

    def _cmd_col(self, _cmds):
        """Handles the 'col' command, jumping to a column by name prefix."""
        if not _cmds:
            self.show_error("Usage: col <name>")
            return
        fragment = _cmds[0]
        matches = [i for i, c in enumerate(self.columns) if c.lower().startswith(fragment)]
        if not matches:
            self.show_error(f"No column matches: {fragment}")
            return
        self.col_idx = matches[0]
        self._adjust_scroll_position()

    def _cmd_freeze(self, _cmds):
        """Handles the 'freeze' command. freeze <n> pins the first n columns; freeze 0 clears."""
        if not _cmds:
            self.show_error("Usage: freeze <n>")
            return
        try:
            n = int(_cmds[0])
        except ValueError:
            self.show_error(f"Invalid number: {_cmds[0]}")
            return
        if n < 0 or n >= len(self.columns):
            self.show_error(f"freeze: must be between 0 and {len(self.columns) - 1}")
            return
        self.frozen_cols = n
        self.left_col = max(self.left_col, n)

    def _cmd_sort(self, _cmds):
        """Handles the 'sort' command.

        Usage:
            sort                   — sort by current column ascending
            sort desc              — sort by current column descending
            sort col1 col2!        — sort col1 asc, col2 desc
            sort col1! col2        — sort col1 desc, col2 asc
        """
        if not self.data or self.col_idx >= len(self.columns):
            return

        def make_sort_key(col):
            def sort_key(row):
                value = row.get(col, '')
                try:
                    return (0, float(value))
                except (ValueError, TypeError):
                    if value == '':
                        return (2, '')
                    return (1, str(value))
            return sort_key

        if not _cmds:
            # :sort — current column ascending
            self.data.sort(key=make_sort_key(self.columns[self.col_idx]))
            return

        if _cmds == ['desc']:
            # :sort desc — current column descending (single-column shorthand)
            self.data.sort(key=make_sort_key(self.columns[self.col_idx]), reverse=True)
            return

        # Multi-column: each token is col_name (asc) or col_name! (desc)
        sort_cols = []  # list of (column, reverse)
        for token in _cmds:
            reverse = token.endswith('!')
            fragment = token.rstrip('!').lower()
            matches = [c for c in self.columns if c.lower().startswith(fragment)]
            if not matches:
                self.show_error(f"No column matches: {fragment}")
                return
            sort_cols.append((matches[0], reverse))

        # Stable multi-key sort: apply in reverse order of priority
        for col, reverse in reversed(sort_cols):
            self.data.sort(key=make_sort_key(col), reverse=reverse)

    def _cmd_filter(self, _cmds):
        """Handles the 'filter' command.

        Usage:
            filter reset         — clear active filter
            filter <col> <val>   — show rows where col contains val (case-insensitive)
            filter <val>         — search across all columns
        """
        if not _cmds or _cmds[0] == 'reset':
            self.data = self._all_data
            self.active_filter = None
            self.row_idx = 0
            self.top_row = 0
            self.mark_row = None
            return

        if len(_cmds) >= 2:
            col_fragment, value = _cmds[0], ' '.join(_cmds[1:])
            # Match column name case-insensitively, partial prefix OK
            matches = [c for c in self.columns if c.lower().startswith(col_fragment)]
            if not matches:
                self.show_error(f"No column matches: {_cmds[0]}")
                return
            col = matches[0]
        else:
            if not self.columns:
                return
            col = self.columns[self.col_idx]
            value = _cmds[0]

        if any(c in value for c in ('*', '?', '[')):
            self.data = [r for r in self._all_data
                         if fnmatch.fnmatch(str(r.get(col, '')).lower(), value)]
        else:
            self.data = [r for r in self._all_data
                         if str(r.get(col, '')).lower() == value]
        self.active_filter = (col, value)
        self.row_idx = 0
        self.top_row = 0
        self.mark_row = None
        if not self.data:
            self.show_error(f"No rows match filter: {' '.join(_cmds)}")

    def _handle_input_mode(self, key):
        """Handles key presses when in input (command) mode."""
        if not self.input_mode:
            return False

        if key in (curses.KEY_ENTER, 10, 13):
            self.input_mode = False
            cmds = self.input_buffer.lower().split()
            if not cmds:
                self.input_buffer = ""
                return True
            cmd = cmds[0]
            if cmd in self.commands:
                self.commands[cmd](cmds[1:])
            elif re.match(r'^[0-9]+$', cmd):
                try:
                    row = int(cmd)
                    if self.data:
                        self.row_idx = min(len(self.data) - 1, max(0, row - 1))
                        self._adjust_scroll_position()
                except ValueError:
                    self.show_error(f"Invalid row number: {cmd}")
            else:
                self.show_error(f"Unknown command: {cmd}")
            self.input_buffer = ""
        elif key == 27:  # ESC
            self.input_mode = False
            self.input_buffer = ""
        elif key in (curses.KEY_BACKSPACE, 127):
            self.input_buffer = self.input_buffer[:-1]
        elif key < 256 and chr(key).isprintable():
            self.input_buffer += chr(key)
        return True

    def _handle_search_mode(self, key):
        """Handles key presses when in search mode."""
        if not self.search_mode:
            return False
        if key in (curses.KEY_ENTER, 10, 13):
            self.search_mode = False
            buf = self.search_buffer
            if buf.startswith('r/'):
                pattern = buf[2:]
                try:
                    re.compile(pattern)
                    self.last_search = pattern
                    self.search_is_regex = True
                except re.error as e:
                    self.show_error(f"Invalid regex: {e}")
                    self.search_buffer = ""
                    return True
            else:
                self.last_search = buf
                self.search_is_regex = False
            self._find_next_match()
            self.search_buffer = ""
        elif key == 27:  # ESC
            self.search_mode = False
            self.search_buffer = ""
        elif key in (curses.KEY_BACKSPACE, 127):
            self.search_buffer = self.search_buffer[:-1]
        elif key < 256 and chr(key).isprintable():
            self.search_buffer += chr(key)
        return True

    def _event_loop(self):
        """The main event loop for handling user input and updating the display."""
        while True:
            self._draw()
            key = self.stdscr.getch()
            if key == -1:  # No input
                continue
            height, width = self.stdscr.getmaxyx()
            if self._handle_input_mode(key) or self._handle_search_mode(key):
                continue

            if key == curses.KEY_UP or key == ord('k'):
                if self.data:
                    self.row_idx = max(0, self.row_idx - 1)
                    if self.row_idx < self.top_row:
                        self.top_row = self.row_idx
            elif key == curses.KEY_DOWN or key == ord('j'):
                if self.data:
                    self.row_idx = min(len(self.data) - 1, self.row_idx + 1)
                    if self.row_idx >= self.top_row + height - 3:
                        self.top_row += 1
            elif key == curses.KEY_LEFT or key == ord('h'):
                if self.columns:
                    self.col_idx = max(0, self.col_idx - 1)
                    if self.col_idx < self.left_col:
                        self.left_col = max(self.frozen_cols, self.col_idx)
            elif key == curses.KEY_RIGHT or key == ord('l'):
                if self.columns:
                    self.col_idx = min(len(self.columns) - 1, self.col_idx + 1)
                    self._adjust_scroll_position()
            elif key == ord('$'):
                if self.columns:
                    self.col_idx = len(self.columns) - 1
                    self._adjust_scroll_position()
            elif key == ord('^'):
                self.col_idx = 0
                self.left_col = 0
            elif curses.keyname(key) == b'kLFT5':  # Ctrl + Left Arrow
                self._update_col_width(-1)
            elif curses.keyname(key) == b'kRIT5':  # Ctrl + Right Arrow
                self._update_col_width(1)
            elif key == curses.KEY_HOME:
                self.row_idx = 0
                self.top_row = 0
            elif key == curses.KEY_END:
                if self.data:
                    self.row_idx = len(self.data) - 1
                    self._adjust_scroll_position()
            elif key == curses.KEY_PPAGE:
                if self.data:
                    self.row_idx = max(0, self.row_idx - (height - 3))
                    self.top_row = self.row_idx
            elif key == curses.KEY_NPAGE:
                if self.data:
                    self.row_idx = min(len(self.data) - 1, self.row_idx + (height - 3))
                    self._adjust_scroll_position()
            elif key == ord(':'):
                self.input_mode = True
                self.input_buffer = ""
            elif key == ord('/'):
                self.search_mode = True
                self.search_buffer = ""
            elif key == ord('n'):
                self._find_next_match()
            elif key == ord('N'):
                self._find_prev_match()
            elif key == ord('#'):
                self.show_row_numbers = not self.show_row_numbers
            elif key == ord('m'):
                self.mark_row = self.row_idx
                self.show_error(f"Mark set at row {self.row_idx + 1}", delay=0.6)
            elif key == ord("'"):
                if self.mark_row is not None and self.mark_row < len(self.data):
                    self.row_idx = self.mark_row
                    self._adjust_scroll_position()
                else:
                    self.show_error("No mark set")
            elif key == ord('?'):
                help_screen = HelpPopup(self.stdscr)
                help_screen.display()

    def _get_visible_cols(self):
        """Returns a list of scrollable column names currently visible on screen."""
        max_width = self.stdscr.getmaxyx()[1]
        row_num_width = (len(str(len(self.data))) + 2) if self.show_row_numbers else 0
        current_x = row_num_width
        # Account for space taken by frozen columns
        for col_name in self.columns[:self.frozen_cols]:
            current_x += self.col_widths[col_name] + 1
        visible_cols = []
        if self.left_col >= len(self.columns):
            return []
        for col_name in self.columns[self.left_col:]:
            if current_x + self.col_widths[col_name] + 1 > max_width:
                break
            visible_cols.append(col_name)
            current_x += self.col_widths[col_name] + 1
        return visible_cols

    def _find_match(self, reverse=False):
        """Finds the next or previous occurrence of the search term."""
        if not self.last_search:
            return

        def cell_generator_forward():
            start_row = self.row_idx
            start_col = self.col_idx
            for row_num in range(start_row, len(self.data)):
                for col_num in range(start_col + 1 if row_num == start_row else 0, len(self.columns)):
                    yield row_num, col_num, str(self.data[row_num].get(self.columns[col_num], ''))
                if row_num == start_row:
                    start_col = -1
            for row_num in range(len(self.data)):
                for col_num in range(len(self.columns)):
                    if row_num == self.row_idx and col_num == self.col_idx:
                        return
                    yield row_num, col_num, str(self.data[row_num].get(self.columns[col_num], ''))

        def cell_generator_backward():
            start_row = self.row_idx
            start_col = self.col_idx
            for row_num in range(start_row, -1, -1):
                end_col = start_col - 1 if row_num == start_row else len(self.columns) - 1
                for col_num in range(end_col, -1, -1):
                    yield row_num, col_num, str(self.data[row_num].get(self.columns[col_num], ''))
            for row_num in range(len(self.data) - 1, -1, -1):
                for col_num in range(len(self.columns) - 1, -1, -1):
                    if row_num == self.row_idx and col_num == self.col_idx:
                        return
                    yield row_num, col_num, str(self.data[row_num].get(self.columns[col_num], ''))

        if self.search_is_regex:
            def matches(value):
                return bool(re.search(self.last_search, value))
        else:
            def matches(value):
                return self.last_search in value

        gen = cell_generator_backward() if reverse else cell_generator_forward()
        for row_num, col_num, value in gen:
            if matches(value):
                self.row_idx = row_num
                self.col_idx = col_num
                self._adjust_scroll_position()
                return

    def _find_next_match(self):
        """Finds the next occurrence of the search term."""
        self._find_match(reverse=False)

    def _find_prev_match(self):
        """Finds the previous occurrence of the search term."""
        self._find_match(reverse=True)

    def _adjust_scroll_position(self):
        """Adjusts top_row and left_col to keep the current cell in view."""
        height, _width = self.stdscr.getmaxyx()  # _width is unused
        page_size = max(1, height - 3)  # rows visible between header and status bar
        # Adjust vertical scroll
        if self.row_idx < self.top_row:
            self.top_row = self.row_idx
        elif self.row_idx >= self.top_row + page_size:
            self.top_row = self.row_idx - (page_size - 1)

        # Adjust horizontal scroll
        if self.col_idx < self.frozen_cols:
            pass  # frozen columns are always visible; no left_col adjustment needed
        elif self.col_idx < self.left_col:
            self.left_col = max(self.frozen_cols, self.col_idx)
        else:
            while True:
                visible_cols = self._get_visible_cols()
                if self.col_idx < self.left_col + len(visible_cols):
                    break
                if self.left_col + len(visible_cols) >= len(self.columns):
                    break
                self.left_col += 1
