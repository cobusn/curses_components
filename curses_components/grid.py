"""A curses-based component for displaying tabular data."""

import curses
import itertools
import logging
import re
import time
import pyperclip


logging.basicConfig(filename='help_debug.log', level=logging.DEBUG)


class QuitApplication(Exception):
    """Custom exception to signal application exit."""


class Help:
    """Displays a help screen with navigation and command information."""
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.scroll_pos = 0

    def display(self):
        """Renders and manages the help screen."""
        height, width = self.stdscr.getmaxyx()
        win_height = 25
        win_width = 80
        pos_y = (height - win_height) // 2
        pos_x = (width - win_width) // 2
        win = curses.newwin(win_height, win_width, pos_y, pos_x)
        win.keypad(True)

        help_text = [
            ("Navigation", ""),
            ("j, k, h, l", "Move down, up, left, right"),
            ("Arrow keys", "Move down, up, left, right"),
            ("Home/End", "Go to the first/last row"),
            ("Page Up/Down", "Move up/down one page"),
            ("^/$", "Go to the first/last column"),
            ("", ""),
            ("Searching", ""),
            ("/", "Enter search mode"),
            ("n", "Find next match"),
            ("ESC", "Exit search mode"),
            ("", ""),
            ("Input Mode", ""),
            (":", "Enter input mode"),
            ("q or quit", "Quit the application"),
            ("row number", "Go to specific row"),
            ("$", "Go to last row"),
            ("sort", "Sort by current column"),
            ("copy", "Copy current cell value"),
            ("ESC", "Exit input mode"),
            ("", ""),
            ("Column Width", ""),
            ("Ctrl + Left/Right", "Decrease/increase width of current column"),
            ("", ""),
            ("Other", ""),
            ("?", "Show this help screen"),
        ]

        max_scroll = max(0, len(help_text) - (win_height - 4))

        while True:
            win.border()
            title = "Help"
            win.addstr(0, (win_width - len(title)) // 2, title, curses.A_REVERSE)

            for i_idx in range(1, win_height - 1):
                win.addstr(i_idx, 1, " " * (win_width - 2))

            text_y = 2
            for i_idx, (key, desc) in enumerate(help_text[self.scroll_pos:]):
                if text_y >= win_height - 2:
                    break
                win.addstr(text_y, 2, key, curses.A_BOLD)
                win.addstr(text_y, 20, desc)
                text_y += 1

            win.addstr(win_height - 2, 2, "Press 'q' to close...")
            win.noutrefresh()
            curses.doupdate()

            key = win.getch()
            if key in (ord('q'), ord('?')):
                break
            if key == curses.KEY_UP or key == ord('k'):
                self.scroll_pos = max(0, self.scroll_pos - 1)
            elif key == curses.KEY_DOWN or key == ord('j'):
                self.scroll_pos = min(max_scroll, self.scroll_pos + 1)


COLORS = {
    'green': curses.COLOR_GREEN,
    'black': curses.COLOR_BLACK,
    'white': curses.COLOR_WHITE,
    'red': curses.COLOR_RED,
    'blue': curses.COLOR_BLUE,
    'yellow': curses.COLOR_YELLOW,
    'magenta': curses.COLOR_MAGENTA,
    'cyan': curses.COLOR_CYAN
}


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
        self.error_message = None
        self.error_message_expiry = 0
        self.stdscr = None  # Initialized in _display
        self.data = []  # Initialized in _display
        self.columns = []  # Initialized in _display
        self.max_rows = 0  # Initialized in _display
        self.col_widths = {}  # Initialized in _prepare_data
        self.cmap = dict(COLORS)  # Initialized here
        self.commands = {  # Initialized in _handle_input_mode
            "$": self._cmd_dollar,
            "copy": self._cmd_copy,
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

        bg = self.cmap.get(self.bg_color, curses.COLOR_BLACK)
        fg = self.cmap.get(self.fg_color, curses.COLOR_GREEN)
        curses.init_pair(1, fg, bg)   # Main display color

        # Search highlight
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_YELLOW)

        # Margins
        mc = self.cmap.get(self.border_color, curses.COLOR_CYAN)
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
        self.col_widths = self._get_col_widths()

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

    def _draw_selected_cell_info_bar(self, max_width):
        """Draws information about the selected cell at the top."""
        self.stdscr.addstr(0, 0, " " * (max_width - 1))
        if self.data and self.row_idx < len(self.data) and self.col_idx < len(self.columns):
            value = self.data[self.row_idx].get(self.columns[self.col_idx], '')
            display_text = f"> {str(value)}"
            self.stdscr.addstr(0, 0, display_text[:max_width - 1])

    def _draw(self):
        """Draws the entire grid, including header, data, and status bar."""
        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()
        row_num_width = len(str(len(self.data))) + 2
        self._draw_selected_cell_info_bar(width)
        self._draw_header(row_num_width, width)
        self._draw_data(height, row_num_width, width)
        self._draw_status_bar(width, height)
        self.stdscr.noutrefresh()
        curses.doupdate()

    def _draw_header(self, row_num_width, max_width):
        """Draws the column headers."""
        self.stdscr.addstr(1, 0, " ".center(row_num_width), curses.color_pair(3) | curses.A_REVERSE)
        current_x = row_num_width
        for col_idx, col_name in enumerate(self.columns[self.left_col:]):
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
            row_num_str = str(self.top_row + row_offset + 1).rjust(row_num_width - 1) + " "
            self.stdscr.addstr(current_y, 0, row_num_str, curses.color_pair(3) | curses.A_REVERSE)
            current_x = row_num_width
            for col_offset, col_name in enumerate(self.columns[self.left_col:]):
                if current_x + self.col_widths[col_name] + 1 > max_width:
                    break
                self._draw_cell(current_y, current_x, row_offset, col_offset, row_data, col_name)
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
                sb_r = f" {self.row_idx + 1}/{len(self.data)} "
                if max_width > len(sb_r) + 1:
                    self.stdscr.addstr(
                        max_height - 1,
                        max_width - len(sb_r) - 1,
                        sb_r
                    )
        except curses.error:
            pass

    def _draw_cell(self, pos_y, pos_x, row_offset, col_offset, row_data, col_name):
        """Draws a single cell with appropriate formatting and highlighting."""
        value = row_data.get(col_name, '')
        if isinstance(value, float):
            value = format(value, self.float_fmt)
        align_func = str.rjust if self.is_number(value) else str.ljust
        display_value = align_func(str(value), self.col_widths[col_name])
        is_current_cell = (self.row_idx == self.top_row + row_offset and
                           self.col_idx == self.left_col + col_offset)
        try:
            if self.last_search and self.last_search in str(value):
                self._draw_highlighted_cell(pos_y, pos_x, display_value, is_current_cell)
            else:
                attr = curses.color_pair(1)
                if is_current_cell:
                    attr |= curses.A_REVERSE
                else:
                    attr |= curses.A_BOLD
                self.stdscr.addstr(pos_y, pos_x, display_value, attr)
            if pos_x + self.col_widths[col_name] < self.stdscr.getmaxyx()[1]:
                self.stdscr.addstr(pos_y, pos_x + self.col_widths[col_name], " ")
        except curses.error:
            pass

    def _draw_highlighted_cell(self, pos_y, pos_x, display_value, is_current_cell):
        """Draws a cell with search term highlighted."""
        start_idx = str(display_value).find(self.last_search)
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

    def _cmd_help(self, _cmds):
        """Handles the 'help' command, displaying the help screen."""
        help_screen = Help(self.stdscr)
        help_screen.display()

    def _cmd_dollar(self, _cmds):
        """Handles the '$' command, moving to the last row."""
        _height, _width = self.stdscr.getmaxyx()
        self.row_idx = len(self.data) - 1
        if self.row_idx >= self.top_row + _height - 3:
            self.top_row = self.row_idx - (_height - 4)

    def _cmd_sort(self, _cmds):
        """Handles the 'sort' command, sorting data by the current column."""
        reverse = 'desc' in _cmds
        if not self.data or self.col_idx >= len(self.columns):
            return
        sort_column_key = self.columns[self.col_idx]

        def sort_key(row):
            value = row.get(sort_column_key, '')
            try:
                return (0, float(value))
            except (ValueError, TypeError):
                if value == '':
                    return (2, '')
                return (1, str(value))
        self.data.sort(key=sort_key, reverse=reverse)

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
                    _height, _width = self.stdscr.getmaxyx()
                    row = int(cmd)
                    self.row_idx = min(len(self.data) - 1, max(0, row - 1))
                    if self.row_idx < self.top_row or self.row_idx >= self.top_row + _height - 3:
                        self.top_row = self.row_idx
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
            self.last_search = self.search_buffer
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
                self.row_idx = max(0, self.row_idx - 1)
                if self.row_idx < self.top_row:
                    self.top_row = self.row_idx
            elif key == curses.KEY_DOWN or key == ord('j'):
                self.row_idx = min(len(self.data) - 1, self.row_idx + 1)
                if self.row_idx >= self.top_row + height - 3:
                    self.top_row += 1
            elif key == curses.KEY_LEFT or key == ord('h'):
                self.col_idx = max(0, self.col_idx - 1)
                if self.col_idx < self.left_col:
                    self.left_col = self.col_idx
            elif key == curses.KEY_RIGHT or key == ord('l'):
                self.col_idx = min(len(self.columns) - 1, self.col_idx + 1)
                self._adjust_scroll_position()
            elif key == ord('$'):
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
                self.row_idx = len(self.data) - 1
                if self.row_idx >= self.top_row + height - 3:
                    self.top_row = self.row_idx - (height - 4)
            elif key == curses.KEY_PPAGE:
                self.row_idx = max(0, self.row_idx - (height - 3))
                self.top_row = self.row_idx
            elif key == curses.KEY_NPAGE:
                self.row_idx = min(len(self.data) - 1, self.row_idx + (height - 3))
                if self.row_idx >= self.top_row + height - 3:
                    self.top_row = self.row_idx - (height - 4)
            elif key == ord(':'):
                self.input_mode = True
                self.input_buffer = ""
            elif key == ord('/'):
                self.search_mode = True
                self.search_buffer = ""
            elif key == ord('n'):
                self._find_next_match()
            elif key == ord('?'):
                help_screen = Help(self.stdscr)
                help_screen.display()

    def _get_visible_cols(self):
        """Returns a list of column names currently visible on screen."""
        max_width = self.stdscr.getmaxyx()[1]
        row_num_width = len(str(len(self.data))) + 2
        visible_cols = []
        current_x = row_num_width
        if not self.columns[self.left_col:]:
            return []
        for col_name in self.columns[self.left_col:]:
            if current_x + self.col_widths[col_name] + 1 > max_width:
                break
            visible_cols.append(col_name)
            current_x += self.col_widths[col_name] + 1
        return visible_cols

    def _find_next_match(self):
        """Finds the next occurrence of the search term."""
        if not self.last_search:
            return

        def cell_generator():
            start_row = self.row_idx
            start_col = self.col_idx
            # Search from current position to end
            for row_num in range(start_row, len(self.data)):
                for col_num in range(start_col + 1 if row_num == start_row else 0, len(self.columns)):   # noqa
                    yield row_num, col_num, str(self.data[row_num].get(self.columns[col_num], ''))
                if row_num == start_row:
                    start_col = -1  # Reset start_col for subsequent rows

            # Search from beginning to current position if no match found above
            for row_num in range(len(self.data)):
                for col_num in range(len(self.columns)):
                    if row_num == self.row_idx and col_num == self.col_idx:
                        return  # Stop if we've wrapped around to the starting cell
                    yield row_num, col_num, str(self.data[row_num].get(self.columns[col_num], ''))

        for row_num, col_num, value in cell_generator():
            if self.last_search in value:
                self.row_idx = row_num
                self.col_idx = col_num
                self._adjust_scroll_position()
                return

    def _adjust_scroll_position(self):
        """Adjusts top_row and left_col to keep the current cell in view."""
        height, _width = self.stdscr.getmaxyx()  # _width is unused
        # Adjust vertical scroll
        if self.row_idx < self.top_row:
            self.top_row = self.row_idx
        elif self.row_idx >= self.top_row + height - 3:  # -3 for header and status bar
            self.top_row = self.row_idx - (height - 4)  # -4 to keep one row visible below

        # Adjust horizontal scroll
        if self.col_idx < self.left_col:
            self.left_col = self.col_idx
        else:
            visible_cols = self._get_visible_cols()
            while self.col_idx >= self.left_col + len(visible_cols):
                if self.left_col + len(visible_cols) >= len(self.columns):
                    break
                self.left_col += 1
                visible_cols = self._get_visible_cols()
