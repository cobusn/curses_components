import curses


class QuitApplication(Exception):
    pass


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


class CursesComponent:

    def __init__(self, fg_color='green', bg_color='black', max_col_width=20, float_fmt='.2f'):
        self.fg_color = fg_color
        self.bg_color = bg_color
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

    def display(self, data, columns=None):
        try:
            curses.wrapper(self._display, data, columns)
        except QuitApplication:
            pass

    def _display(self, stdscr, data, columns):
        self.stdscr = stdscr
        self.data = data
        self.columns = columns
        self._init_curses()
        self._prepare_data()
        self._event_loop()

    def _init_curses(self):
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
        self.fg_color_map = dict(COLORS)
        self.bg_color_map = dict(COLORS)
        curses.init_pair(1, self.fg_color_map.get(
            self.fg_color, curses.COLOR_GREEN),
            self.bg_color_map.get(self.bg_color, curses.COLOR_BLACK)
        )
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_YELLOW)

    def _prepare_data(self):
        if not self.columns:
            if isinstance(self.data, list) and self.data:
                self.columns = list(self.data[0].keys())
            elif not isinstance(self.data, list):
                # For iterators
                self.data = list(self.data)
                if self.data:
                    self.columns = list(self.data[0].keys())

        if not self.columns:
            self.columns = []

        self.col_widths = self._get_col_widths()

    def _get_col_widths(self):
        col_widths = {col: len(col) for col in self.columns}
        for row in self.data:
            for col in self.columns:
                col_widths[col] = min(
                    self.max_col_width,
                    max(col_widths[col], len(str(row.get(col, ''))))
                )
        return col_widths

    def _update_col_width(self, delta):
        col = self.columns[self.col_idx]
        self.col_widths[col] = max(1, self.col_widths[col] + delta)

    def is_number(self, s):
        try:
            float(s)
            return True
        except (ValueError, TypeError):
            return False

    def _draw(self):
        """main draw function"""
        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()
        row_num_width = len(str(len(self.data))) + 2

        # Draw header
        i, col = self.draw_header(row_num_width, width)

        # Draw data
        self._draw_data(height, i, row_num_width, width, col)

        # Draw status bar
        self._draw_status_bar(width, height)

        self.stdscr.noutrefresh()
        curses.doupdate()

    def draw_header(self, row_num_width, width):
        self.stdscr.addstr(0, 0, " ".center(row_num_width), curses.A_REVERSE)
        x = row_num_width
        for i, col in enumerate(self.columns[self.left_col:]):
            if x + self.col_widths[col] + 1 > width:
                break
            try:
                self.stdscr.addstr(0, x, col.center(self.col_widths[col] + 1), curses.A_REVERSE)
            except curses.error:
                pass
            x += self.col_widths[col] + 1
        return i, col

    def _draw_data(self, height, i, row_num_width, width, col):
        # Draw data
        for i, row in enumerate(self.data[self.top_row:]):
            if i + 2 >= height:
                break
            y = i + 1

            row_num_str = str(self.top_row + i + 1).rjust(row_num_width - 1) + " "
            self.stdscr.addstr(y, 0, row_num_str, curses.A_REVERSE)

            x = row_num_width
            for j, col in enumerate(self.columns[self.left_col:]):
                if x + self.col_widths[col] + 1 > width:
                    break

                self._draw_cell(y, x, i, j, row, col)

                x += self.col_widths[col] + 1

    def _draw_status_bar(self, width, height):
        # Draw status bar
        try:
            if width > 0:
                self.stdscr.addstr(height - 1, 0, " " * (width - 1))

            status_bar_left = ""
            if self.input_mode:
                status_bar_left = ":" + self.input_buffer
            elif self.search_mode:
                status_bar_left = "/" + self.search_buffer

            self.stdscr.addstr(height - 1, 0, status_bar_left)

            status_bar_right = f" {self.row_idx + 1}/{len(self.data)} "
            if width > len(status_bar_right) + 1:
                self.stdscr.addstr(height - 1, width - len(status_bar_right) - 1, status_bar_right)
        except curses.error:
            pass

    def _draw_cell(self, y, x, i, j, row, col):
        val = row.get(col, '')
        if isinstance(val, float):
            val = format(val, self.float_fmt)

        align = str.rjust if self.is_number(val) else str.ljust
        display_val = align(str(val), self.col_widths[col])

        is_current_cell = (i == self.row_idx - self.top_row and j == self.col_idx - self.left_col)

        try:
            if self.last_search and self.last_search in str(val):
                self._draw_highlighted_cell(y, x, display_val, is_current_cell)
            else:
                attr = curses.color_pair(1)
                if is_current_cell:
                    attr |= curses.A_REVERSE
                self.stdscr.addstr(y, x, display_val, attr)

            if x + self.col_widths[col] < self.stdscr.getmaxyx()[1]:
                self.stdscr.addstr(y, x + self.col_widths[col], " ")

        except curses.error:
            pass

    def _draw_highlighted_cell(self, y, x, display_val, is_current_cell):
        start_idx = str(display_val).find(self.last_search)
        end_idx = start_idx + len(self.last_search)

        attr = curses.color_pair(1)
        highlight_attr = curses.color_pair(2)
        if is_current_cell:
            attr |= curses.A_REVERSE
            highlight_attr |= curses.A_REVERSE

        self.stdscr.addstr(y, x, display_val[:start_idx], attr)
        self.stdscr.addstr(
            y, x + start_idx, display_val[start_idx:end_idx], highlight_attr
        )
        self.stdscr.addstr(y, x + end_idx, display_val[end_idx:], attr)

    def _handle_input_mode(self, key):  #noqa
        if not self.input_mode:
            return False

        height, width = self.stdscr.getmaxyx()
        if key in [curses.KEY_ENTER, 10, 13]:
            self.input_mode = False
            if self.input_buffer == "quit" or self.input_buffer == "q":
                raise QuitApplication
            elif self.input_buffer == "$":
                self.row_idx = len(self.data) - 1
                if self.row_idx >= self.top_row + height - 2:
                    self.top_row = self.row_idx - (height - 3)
            else:
                try:
                    row = int(self.input_buffer)
                    self.row_idx = min(len(self.data) - 1, max(0, row - 1))
                    if self.row_idx < self.top_row or self.row_idx >= self.top_row + height - 2:
                        self.top_row = self.row_idx
                except ValueError:
                    pass
            self.input_buffer = ""
        elif key == 27:  # Escape
            self.input_mode = False
            self.input_buffer = ""
        elif key == ord("$"):
            self.input_buffer += chr(key)
        elif key >= ord('a') and key <= ord('z'):
            self.input_buffer += chr(key)
        elif key >= ord('0') and key <= ord('9'):
            self.input_buffer += chr(key)
        elif key == curses.KEY_BACKSPACE or key == 127:
            self.input_buffer = self.input_buffer[:-1]

        return True

    def _handle_search_mode(self, key):
        if not self.search_mode:
            return False

        if key in [curses.KEY_ENTER, 10, 13]:
            self.search_mode = False
            self.last_search = self.search_buffer
            self._find_next_match()
            self.search_buffer = ""
        elif key == 27:  # Escape
            self.search_mode = False
            self.search_buffer = ""
        elif key >= 32 and key <= 126:  # Printable characters
            self.search_buffer += chr(key)
        elif key == curses.KEY_BACKSPACE or key == 127:
            self.search_buffer = self.search_buffer[:-1]

        return True

    def _event_loop(self): #noqa
        while True:
            self._draw()
            key = self.stdscr.getch()
            height, width = self.stdscr.getmaxyx()

            if self._handle_input_mode(key) or self._handle_search_mode(key):
                continue

            if key == curses.KEY_UP or key == ord('k'):
                self.row_idx = max(0, self.row_idx - 1)
                if self.row_idx < self.top_row:
                    self.top_row = self.row_idx
            elif key == curses.KEY_DOWN or key == ord('j'):
                self.row_idx = min(len(self.data) - 1, self.row_idx + 1)
                if self.row_idx >= self.top_row + height - 2:
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
            elif curses.keyname(key) == b'kLFT5':  # Ctrl + Left
                self._update_col_width(-1)
            elif curses.keyname(key) == b'kRIT5':  # Ctrl + Right
                self._update_col_width(1)
            elif key == curses.KEY_HOME:
                self.row_idx = 0
                self.top_row = 0
            elif key == curses.KEY_END:
                self.row_idx = len(self.data) - 1
                if self.row_idx >= self.top_row + height - 2:
                    self.top_row = self.row_idx - (height - 3)
            elif key == curses.KEY_PPAGE:
                self.row_idx = max(0, self.row_idx - (height - 2))
                self.top_row = self.row_idx
            elif key == curses.KEY_NPAGE:
                self.row_idx = min(len(self.data) - 1, self.row_idx + (height - 2))
                if self.row_idx >= self.top_row + height - 2:
                    self.top_row = self.row_idx - (height - 3)
            elif key == ord(':'):
                self.input_mode = True
                self.input_buffer = ""
            elif key == ord('/'):
                self.search_mode = True
                self.search_buffer = ""
            elif key == ord('n'):
                self._find_next_match()

    def _get_visible_cols(self):
        width = self.stdscr.getmaxyx()[1]
        row_num_width = len(str(len(self.data))) + 2
        visible_cols = []
        x = row_num_width
        if not self.columns[self.left_col:]:
            return []
        for col in self.columns[self.left_col:]:
            if x + self.col_widths[col] + 1 > width:
                break
            visible_cols.append(col)
            x += self.col_widths[col] + 1
        return visible_cols

    def _find_next_match(self):   #noqa
        if not self.last_search:
            return

        def cell_generator():
            start_row = self.row_idx
            start_col = self.col_idx

            # Yield cells from current position to the end
            for r in range(start_row, len(self.data)):
                for c in range(start_col + 1 if r == start_row else 0, len(self.columns)):
                    yield r, c, str(self.data[r].get(self.columns[c], ''))
                # Reset start_col for subsequent rows
                if r == start_row:
                    start_col = -1

            # Yield cells from the beginning to the current position
            for r in range(len(self.data)):
                for c in range(len(self.columns)):
                    if r == self.row_idx and c == self.col_idx:
                        return
                    yield r, c, str(self.data[r].get(self.columns[c], ''))

        for r, c, val in cell_generator():
            if self.last_search in val:
                self.row_idx = r
                self.col_idx = c
                self._adjust_scroll_position()
                return

    def _adjust_scroll_position(self):
        height, width = self.stdscr.getmaxyx()
        # Adjust top_row
        if self.row_idx < self.top_row:
            self.top_row = self.row_idx
        elif self.row_idx >= self.top_row + height - 2:
            self.top_row = self.row_idx - (height - 3)

        # Adjust left_col
        if self.col_idx < self.left_col:
            self.left_col = self.col_idx
        else:
            visible_cols = self._get_visible_cols()
            while self.col_idx >= self.left_col + len(visible_cols):
                if self.left_col + len(visible_cols) >= len(self.columns):
                    break
                self.left_col += 1
                visible_cols = self._get_visible_cols()
