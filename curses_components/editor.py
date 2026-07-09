"""Vi-like curses editor component.

Provides a modal text editor popup suitable for editing small files such as
SQL scripts.  Returns the edited text on save or None on quit-without-save.

Supported normal-mode commands:
    h j k l / arrow keys    move cursor
    w b                     move word forward / backward
    0 $                     start / end of line
    gg G                    first / last line
    i                       insert before cursor
    a                       insert after cursor
    o                       open new line below and insert
    O                       open new line above and insert
    x                       delete character under cursor
    dd                      delete current line
    yy                      yank (copy) current line
    p                       paste yanked line below current line
    u                       undo
    /                       enter search; n / N for next / previous match
    :                       enter command mode
    ESC                     cancel / return to normal

Supported command-mode entries:
    w [file]                write (save); optional filename overrides original
    q                       quit (prompts if unsaved changes)
    q!                      quit discarding changes
    wq [file]               write then quit
    s/pattern/replacement   substitute first match on current line
    s/pattern/replacement/g substitute all matches on current line
    %s/pattern/replacement  substitute first match on every line
    %s/pattern/replacement/g substitute all matches on every line
    <number>                jump to line number
"""

import curses
import re

from curses_components.popup import EditorHelpPopup
from curses_components.theme import resolve_color


_WORD_RE = re.compile(r'\w+|\W+')


class EditorPopup:
    """Vi-like modal text editor displayed as a curses popup.

    Args:
        stdscr: The parent curses window (full screen).
        title: Optional title shown in the top border.
    """

    def __init__(self, stdscr, title="Editor", width=None, height=None,
                 fg_color='green', bg_color='black', border_color='cyan',
                 bold=False, bold_background=False):
        """Initialise the editor.

        Args:
            stdscr: The parent curses window (full screen).
            title: Title shown in the top border.
            width: Window width in columns.  Clamped to terminal width.
                Defaults to the full terminal width when None.
            height: Window height in rows.  Clamped to terminal height.
                Defaults to the full terminal height when None.
            fg_color: Foreground text color name (default 'green').
            bg_color: Background color name (default 'black').
            border_color: Border and title color name (default 'cyan').
            bold: Apply bold to text characters; most terminals render bold
                green as bright green (default False).
            bold_background: Apply bold to background fill (empty cells).
                Defaults to False.
        """
        self.stdscr = stdscr
        self.title = title
        self.width = width
        self.height = height
        self.fg_color = fg_color
        self.bg_color = bg_color
        self.border_color = border_color
        self.bold = bold
        self.bold_background = bold_background

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def edit(self, text="", filename=None):
        """Open the editor with initial text.

        Args:
            text: Initial content as a single string (newlines preserved).
            filename: Optional file path shown in the status bar.

        Returns:
            The edited text as a string if the user saved, or None if they
            quit without saving.
        """
        self._lines = text.split('\n')
        self._filename = filename
        self._cursor_row = 0
        self._cursor_col = 0
        self._top_row = 0
        self._left_col = 0
        self._mode = 'normal'       # 'normal' | 'insert' | 'command' | 'search'
        self._cmd_buf = ''
        self._search_buf = ''
        self._last_search = ''
        self._search_forward = True
        self._yank_buf = None
        self._undo_stack = []
        self._modified = False
        self._status_msg = ''
        self._pending_normal = ''   # accumulates multi-char normal commands (dd, yy, gg)
        self._result = None         # set to text when user saves

        term_height, term_width = self.stdscr.getmaxyx()
        win_height = max(5, min(term_height, self.height or term_height))
        win_width = max(20, min(term_width, self.width or term_width))
        pos_y = max(0, (term_height - win_height) // 2)
        pos_x = max(0, (term_width - win_width) // 2)

        self._win = curses.newwin(win_height, win_width, pos_y, pos_x)
        self._win.keypad(True)
        self._win_height = win_height
        self._win_width = win_width
        # Usable text area inside border
        self._text_rows = win_height - 3   # top border + header + bottom status
        self._text_cols = win_width - 2    # left + right borders

        self._init_colors()
        curses.curs_set(1)
        try:
            return self._run()
        finally:
            curses.curs_set(0)

    # ------------------------------------------------------------------
    # Colour initialisation
    # ------------------------------------------------------------------

    def _init_colors(self):
        curses.start_color()
        curses.use_default_colors()
        bg = resolve_color(self.bg_color, curses.COLOR_BLACK)
        fg = resolve_color(self.fg_color, curses.COLOR_GREEN)
        mc = resolve_color(self.border_color, curses.COLOR_CYAN)
        curses.init_pair(10, fg, bg)
        curses.init_pair(11, mc, bg)
        curses.init_pair(12, curses.COLOR_BLACK, curses.COLOR_YELLOW)  # search highlight
        curses.init_pair(13, mc, bg)
        self._text_attr = curses.color_pair(10) | (curses.A_BOLD if self.bold else 0)
        self._bg_attr = curses.color_pair(10) | (curses.A_BOLD if self.bold_background else 0)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _run(self):
        while True:
            self._draw()
            key = self._win.getch()
            if self._mode == 'normal':
                action = self._handle_normal(key)
                if action == 'quit':
                    return None
                if action == 'save_quit':
                    return '\n'.join(self._lines)
            elif self._mode == 'insert':
                self._handle_insert(key)
            elif self._mode == 'command':
                result = self._handle_command_key(key)
                if result == 'quit':
                    return None
                if result == 'save_quit':
                    return '\n'.join(self._lines)
            elif self._mode == 'search':
                self._handle_search_key(key)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw(self):
        win = self._win
        text_attr = self._text_attr
        border_attr = curses.color_pair(11)
        status_attr = curses.color_pair(13)

        win.erase()
        win.bkgd(' ', self._bg_attr)
        win.border()

        # Repaint border in border color
        h, w = self._win_height, self._win_width
        try:
            win.attron(border_attr)
            win.border()
            win.attroff(border_attr)
        except curses.error:
            pass

        # Title in top border
        title_str = f' {self.title} '
        if self._filename:
            title_str = f' {self.title}: {self._filename} '
        title_str = title_str[:w - 2]
        win.addstr(0, max(1, (w - len(title_str)) // 2),
                   title_str, border_attr | curses.A_REVERSE)

        # Text lines
        for row_offset in range(self._text_rows):
            line_idx = self._top_row + row_offset
            screen_y = row_offset + 1
            if line_idx >= len(self._lines):
                try:
                    win.addstr(screen_y, 1, '~', text_attr)
                except curses.error:
                    pass
                continue
            line = self._lines[line_idx]
            visible = line[self._left_col:self._left_col + self._text_cols]
            # Highlight search matches
            if self._last_search:
                self._draw_line_with_highlight(screen_y, visible, line_idx, text_attr)
            else:
                try:
                    win.addstr(screen_y, 1, visible, text_attr)
                except curses.error:
                    pass

        # Status / command bar (second-to-last row inside border)
        status_y = self._win_height - 2
        try:
            win.addstr(status_y, 1, ' ' * (self._win_width - 2), status_attr)
        except curses.error:
            pass

        if self._mode == 'command':
            status_left = ':' + self._cmd_buf
        elif self._mode == 'search':
            status_left = ('/' if self._search_forward else '?') + self._search_buf
        elif self._status_msg:
            status_left = self._status_msg
        else:
            mode_label = '-- INSERT --' if self._mode == 'insert' else ''
            status_left = mode_label

        modified_flag = ' [+]' if self._modified else ''
        pos_info = f'{self._cursor_row + 1},{self._cursor_col + 1}{modified_flag}'
        try:
            win.addstr(status_y, 1, status_left[:self._win_width - len(pos_info) - 3],
                       status_attr)
            win.addstr(status_y, self._win_width - len(pos_info) - 1, pos_info,
                       status_attr)
        except curses.error:
            pass

        # Position the cursor
        if self._mode in ('command', 'search'):
            prefix_len = 1 + (len(self._cmd_buf) if self._mode == 'command'
                              else len(self._search_buf))
            try:
                win.move(status_y, min(1 + prefix_len, self._win_width - 2))
            except curses.error:
                pass
        else:
            screen_row = self._cursor_row - self._top_row + 1
            screen_col = self._cursor_col - self._left_col + 1
            try:
                win.move(screen_row, screen_col)
            except curses.error:
                pass

        win.noutrefresh()
        curses.doupdate()

    def _draw_line_with_highlight(self, screen_y, visible_text, line_idx, text_attr):
        win = self._win
        hl_attr = curses.color_pair(12)
        line = self._lines[line_idx]
        try:
            m = re.search(self._last_search, line)
        except re.error:
            m = None
        if not m:
            try:
                win.addstr(screen_y, 1, visible_text, text_attr)
            except curses.error:
                pass
            return
        # Map match positions into the visible slice
        vis_start = self._left_col
        vis_end = vis_start + self._text_cols
        ms, me = m.start(), m.end()
        x = 1
        try:
            # Before match
            pre = line[vis_start:min(ms, vis_end)]
            if pre:
                win.addstr(screen_y, x, pre, text_attr)
                x += len(pre)
            # Match portion
            hl = line[max(ms, vis_start):min(me, vis_end)]
            if hl:
                win.addstr(screen_y, x, hl, hl_attr)
                x += len(hl)
            # After match
            post = line[max(me, vis_start):vis_end]
            if post:
                win.addstr(screen_y, x, post, text_attr)
        except curses.error:
            pass

    # ------------------------------------------------------------------
    # Normal mode
    # ------------------------------------------------------------------

    def _handle_normal(self, key):
        ch = chr(key) if 0 <= key < 256 else ''
        self._status_msg = ''

        # Multi-char command accumulation (dd, yy, gg, dw)
        if self._pending_normal:
            combo = self._pending_normal + ch
            self._pending_normal = ''
            if combo == 'dd':
                self._push_undo()
                if len(self._lines) > 1:
                    self._lines.pop(self._cursor_row)
                    self._cursor_row = min(self._cursor_row, len(self._lines) - 1)
                else:
                    self._lines[0] = ''
                self._clamp_col()
                self._modified = True
            elif combo == 'yy':
                self._yank_buf = self._lines[self._cursor_row]
            elif combo == 'gg':
                self._cursor_row = 0
                self._cursor_col = 0
                self._scroll_to_cursor()
            elif combo == 'dw':
                self._delete_word()
            return None

        # Single-char commands
        if key in (curses.KEY_UP, ord('k')):
            self._cursor_row = max(0, self._cursor_row - 1)
            self._clamp_col()
            self._scroll_to_cursor()
        elif key in (curses.KEY_DOWN, ord('j')):
            self._cursor_row = min(len(self._lines) - 1, self._cursor_row + 1)
            self._clamp_col()
            self._scroll_to_cursor()
        elif key in (curses.KEY_LEFT, ord('h')):
            self._cursor_col = max(0, self._cursor_col - 1)
            self._scroll_to_cursor()
        elif key in (curses.KEY_RIGHT, ord('l')):
            line_len = len(self._lines[self._cursor_row])
            self._cursor_col = min(max(0, line_len - 1), self._cursor_col + 1)
            self._scroll_to_cursor()
        elif ch == 'w':
            self._move_word_forward()
        elif ch == 'b':
            self._move_word_backward()
        elif ch == '0' or key == curses.KEY_HOME:
            self._cursor_col = 0
            self._scroll_to_cursor()
        elif ch == '$' or key == curses.KEY_END:
            self._cursor_col = max(0, len(self._lines[self._cursor_row]) - 1)
            self._scroll_to_cursor()
        elif key == curses.KEY_PPAGE:
            self._cursor_row = max(0, self._cursor_row - self._text_rows)
            self._clamp_col()
            self._scroll_to_cursor()
        elif key == curses.KEY_NPAGE:
            self._cursor_row = min(len(self._lines) - 1,
                                   self._cursor_row + self._text_rows)
            self._clamp_col()
            self._scroll_to_cursor()
        elif ch == 'G':
            self._cursor_row = len(self._lines) - 1
            self._clamp_col()
            self._scroll_to_cursor()
        elif ch in ('i',):
            self._enter_insert()
        elif ch == 'a':
            line = self._lines[self._cursor_row]
            self._cursor_col = min(len(line), self._cursor_col + 1)
            self._enter_insert()
        elif ch == 'o':
            self._push_undo()
            self._lines.insert(self._cursor_row + 1, '')
            self._cursor_row += 1
            self._cursor_col = 0
            self._modified = True
            self._enter_insert()
        elif ch == 'O':
            self._push_undo()
            self._lines.insert(self._cursor_row, '')
            self._cursor_col = 0
            self._modified = True
            self._enter_insert()
        elif ch == 'x':
            line = self._lines[self._cursor_row]
            if line and self._cursor_col < len(line):
                self._push_undo()
                self._lines[self._cursor_row] = (line[:self._cursor_col] +
                                                  line[self._cursor_col + 1:])
                self._clamp_col()
                self._modified = True
        elif ch == 'p':
            if self._yank_buf is not None:
                self._push_undo()
                self._lines.insert(self._cursor_row + 1, self._yank_buf)
                self._cursor_row += 1
                self._cursor_col = 0
                self._modified = True
                self._scroll_to_cursor()
        elif ch == 'u':
            if self._undo_stack:
                self._lines, self._cursor_row, self._cursor_col = self._undo_stack.pop()
                self._clamp_col()
                self._scroll_to_cursor()
                self._modified = True
                self._status_msg = 'undo'
            else:
                self._status_msg = 'nothing to undo'
        elif ch in ('d', 'y', 'g'):
            self._pending_normal = ch
        elif ch == 'n':
            self._find_next(forward=self._search_forward)
        elif ch == 'N':
            self._find_next(forward=not self._search_forward)
        elif ch == '/':
            self._mode = 'search'
            self._search_buf = ''
            self._search_forward = True
        elif ch == ':':
            self._mode = 'command'
            self._cmd_buf = ''
        elif key == 27:  # ESC — clear pending
            self._pending_normal = ''
            self._status_msg = ''

        return None

    # ------------------------------------------------------------------
    # Insert mode
    # ------------------------------------------------------------------

    def _handle_insert(self, key):
        if key == 27:  # ESC → back to normal
            self._cursor_col = max(0, self._cursor_col - 1)
            self._mode = 'normal'
            return
        if key in (curses.KEY_BACKSPACE, 127):
            self._push_undo()
            line = self._lines[self._cursor_row]
            if self._cursor_col > 0:
                self._lines[self._cursor_row] = (line[:self._cursor_col - 1] +
                                                  line[self._cursor_col:])
                self._cursor_col -= 1
            elif self._cursor_row > 0:
                # Merge with line above
                prev = self._lines[self._cursor_row - 1]
                self._cursor_col = len(prev)
                self._lines[self._cursor_row - 1] = prev + line
                self._lines.pop(self._cursor_row)
                self._cursor_row -= 1
            self._modified = True
            self._scroll_to_cursor()
            return
        if key in (curses.KEY_ENTER, 10, 13):
            self._push_undo()
            line = self._lines[self._cursor_row]
            self._lines[self._cursor_row] = line[:self._cursor_col]
            self._lines.insert(self._cursor_row + 1, line[self._cursor_col:])
            self._cursor_row += 1
            self._cursor_col = 0
            self._modified = True
            self._scroll_to_cursor()
            return
        if key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT):
            self._handle_normal(key)
            return
        if key == ord('\t') or (0 <= key < 256 and chr(key).isprintable()):
            self._push_undo()
            insert = '    ' if key == ord('\t') else chr(key)
            line = self._lines[self._cursor_row]
            self._lines[self._cursor_row] = (line[:self._cursor_col] +
                                              insert +
                                              line[self._cursor_col:])
            self._cursor_col += len(insert)
            self._modified = True
            self._scroll_to_cursor()

    # ------------------------------------------------------------------
    # Command mode
    # ------------------------------------------------------------------

    def _handle_command_key(self, key):
        if key == 27:
            self._mode = 'normal'
            self._cmd_buf = ''
            return None
        if key in (curses.KEY_BACKSPACE, 127):
            self._cmd_buf = self._cmd_buf[:-1]
            return None
        if key in (curses.KEY_ENTER, 10, 13):
            self._mode = 'normal'
            result = self._execute_command(self._cmd_buf.strip())
            self._cmd_buf = ''
            return result
        if 0 <= key < 256 and chr(key).isprintable():
            self._cmd_buf += chr(key)
        return None

    def _execute_command(self, cmd):
        if not cmd:
            return None

        # :s and :%s — substitute
        sub_match = re.match(
            r'^(%?)s/([^/]*)/([^/]*?)(/g)?$', cmd
        )
        if sub_match:
            self._push_undo()
            whole_file = bool(sub_match.group(1))
            pattern = sub_match.group(2)
            replacement = sub_match.group(3)
            global_flag = bool(sub_match.group(4))
            count = 1 if not global_flag else 0  # re.sub count: 0 = all
            try:
                if whole_file:
                    changed = 0
                    for i, line in enumerate(self._lines):
                        new_line = re.sub(pattern, replacement, line,
                                          count=count)
                        if new_line != line:
                            self._lines[i] = new_line
                            changed += 1
                    self._status_msg = f'{changed} line(s) substituted'
                else:
                    row = self._cursor_row
                    new_line = re.sub(pattern, replacement,
                                      self._lines[row], count=count)
                    if new_line != self._lines[row]:
                        self._lines[row] = new_line
                        self._status_msg = 'substituted'
                    else:
                        self._status_msg = 'no match'
                self._modified = True
            except re.error as e:
                self._status_msg = f'bad pattern: {e}'
            return None

        # :sort, :sort!, :sort u, :sort! u
        sort_match = re.match(r'^sort(!)?(\s+u)?$', cmd.strip(), re.IGNORECASE)
        if sort_match:
            self._push_undo()
            reverse = bool(sort_match.group(1))
            unique = bool(sort_match.group(2))
            lines = sorted(self._lines, key=str.casefold, reverse=reverse)
            if unique:
                seen = set()
                deduped = []
                for line in lines:
                    key = line.casefold()
                    if key not in seen:
                        seen.add(key)
                        deduped.append(line)
                lines = deduped
            self._lines = lines
            self._cursor_row = min(self._cursor_row, len(self._lines) - 1)
            self._clamp_col()
            self._modified = True
            self._status_msg = f'sorted {len(self._lines)} lines'
            return None

        # :w, :q, :wq
        parts = cmd.split()
        verb = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else None

        if verb in ('w', 'wq', 'x'):
            if arg:
                self._filename = arg
            self._modified = False
            self._status_msg = f'written: {self._filename or "(no file)"}'
            if verb in ('wq', 'x'):
                return 'save_quit'
            return None

        if verb == 'q':
            if self._modified:
                self._status_msg = 'unsaved changes — use q! to force'
                return None
            return 'quit'

        if verb == 'q!':
            return 'quit'

        # Jump to line number
        if re.match(r'^\d+$', verb):
            line_no = int(verb)
            self._cursor_row = max(0, min(len(self._lines) - 1, line_no - 1))
            self._cursor_col = 0
            self._scroll_to_cursor()
            return None

        if verb == 'help':
            EditorHelpPopup(self.stdscr).display()
            return None

        self._status_msg = f'unknown command: {verb}'
        return None

    # ------------------------------------------------------------------
    # Search mode
    # ------------------------------------------------------------------

    def _handle_search_key(self, key):
        if key == 27:
            self._mode = 'normal'
            self._search_buf = ''
            return
        if key in (curses.KEY_BACKSPACE, 127):
            self._search_buf = self._search_buf[:-1]
            return
        if key in (curses.KEY_ENTER, 10, 13):
            self._mode = 'normal'
            if self._search_buf:
                try:
                    re.compile(self._search_buf)
                    self._last_search = self._search_buf
                    self._find_next(forward=self._search_forward)
                except re.error as e:
                    self._status_msg = f'bad pattern: {e}'
            self._search_buf = ''
            return
        if 0 <= key < 256 and chr(key).isprintable():
            self._search_buf += chr(key)

    def _find_next(self, forward=True):
        if not self._last_search:
            return
        total = len(self._lines)
        rows = (range(self._cursor_row, total) if forward
                else range(self._cursor_row, -1, -1))
        for i, row in enumerate(rows):
            line = self._lines[row]
            try:
                m = re.search(self._last_search, line)
            except re.error:
                return
            # Skip current row on first iteration (already there)
            if i == 0 and m and m.start() == self._cursor_col:
                continue
            if m:
                self._cursor_row = row
                self._cursor_col = m.start()
                self._scroll_to_cursor()
                return
        # Wrap around
        wrap_rows = (range(0, self._cursor_row + 1) if forward
                     else range(total - 1, self._cursor_row - 1, -1))
        for row in wrap_rows:
            try:
                m = re.search(self._last_search, self._lines[row])
            except re.error:
                return
            if m:
                self._cursor_row = row
                self._cursor_col = m.start()
                self._scroll_to_cursor()
                self._status_msg = 'search wrapped'
                return
        self._status_msg = 'pattern not found'

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _enter_insert(self):
        self._push_undo()
        self._mode = 'insert'
        self._scroll_to_cursor()

    def _push_undo(self):
        import copy
        self._undo_stack.append(
            (copy.copy(self._lines), self._cursor_row, self._cursor_col)
        )
        if len(self._undo_stack) > 100:
            self._undo_stack.pop(0)

    def _clamp_col(self):
        line_len = len(self._lines[self._cursor_row])
        max_col = max(0, line_len - 1) if self._mode == 'normal' else line_len
        self._cursor_col = min(self._cursor_col, max_col)

    def _scroll_to_cursor(self):
        # Vertical
        if self._cursor_row < self._top_row:
            self._top_row = self._cursor_row
        elif self._cursor_row >= self._top_row + self._text_rows:
            self._top_row = self._cursor_row - self._text_rows + 1
        # Horizontal
        if self._cursor_col < self._left_col:
            self._left_col = self._cursor_col
        elif self._cursor_col >= self._left_col + self._text_cols:
            self._left_col = self._cursor_col - self._text_cols + 1

    def _delete_word(self):
        """Delete from the cursor to the start of the next word (vi dw).

        Matches vi behaviour:
        - If the cursor is on a word character, deletes to the start of the
          next word (including trailing whitespace between words).
        - If the cursor is on whitespace, deletes the whitespace up to the
          next word.
        - At end of line, joins with the next line (if one exists).
        """
        self._push_undo()
        line = self._lines[self._cursor_row]
        col = self._cursor_col

        if col >= len(line):
            # At or past end of line — join with next line
            if self._cursor_row < len(self._lines) - 1:
                self._lines[self._cursor_row] = (
                    line + self._lines[self._cursor_row + 1]
                )
                self._lines.pop(self._cursor_row + 1)
            self._modified = True
            return

        # Find the end of the deletion range using vi dw rules:
        # 1. If on whitespace, consume all whitespace.
        # 2. If on a word char (\w), consume word chars then trailing spaces.
        # 3. If on a non-word/non-space char, consume those chars then spaces.
        pos = col
        if line[pos] == ' ':
            while pos < len(line) and line[pos] == ' ':
                pos += 1
        elif re.match(r'\w', line[pos]):
            while pos < len(line) and re.match(r'\w', line[pos]):
                pos += 1
            while pos < len(line) and line[pos] == ' ':
                pos += 1
        else:
            while pos < len(line) and not re.match(r'\w| ', line[pos]):
                pos += 1
            while pos < len(line) and line[pos] == ' ':
                pos += 1

        self._lines[self._cursor_row] = line[:col] + line[pos:]
        self._clamp_col()
        self._modified = True

    def _move_word_forward(self):
        line = self._lines[self._cursor_row]
        tokens = list(_WORD_RE.finditer(line))
        for m in tokens:
            if m.start() > self._cursor_col:
                self._cursor_col = m.start()
                self._scroll_to_cursor()
                return
        # Move to next line
        if self._cursor_row < len(self._lines) - 1:
            self._cursor_row += 1
            self._cursor_col = 0
            self._scroll_to_cursor()

    def _move_word_backward(self):
        line = self._lines[self._cursor_row]
        tokens = list(_WORD_RE.finditer(line))
        for m in reversed(tokens):
            if m.start() < self._cursor_col:
                self._cursor_col = m.start()
                self._scroll_to_cursor()
                return
        if self._cursor_row > 0:
            self._cursor_row -= 1
            line = self._lines[self._cursor_row]
            self._cursor_col = max(0, len(line) - 1)
            self._scroll_to_cursor()
