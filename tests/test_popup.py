import curses

import pytest

from curses_components.grid import GridComponent
from curses_components.popup import HelpPopup, ScrollablePopup, TextPopup


class FakeWindow:
    def __init__(self, key=ord("q")):
        self.key = key
        self.writes = []

    def keypad(self, enabled):
        pass

    def attrset(self, attrs):
        pass

    def border(self):
        pass

    def addstr(self, y, x, text, attrs=0):
        self.writes.append((y, x, text))

    def noutrefresh(self):
        pass

    def getch(self):
        return self.key


class FakeScreen:
    def __init__(self, height=40, width=120):
        self.height = height
        self.width = width
        self.window = FakeWindow()
        self.created = None

    def getmaxyx(self):
        return self.height, self.width


def _new_window(screen, *args):
    screen.created = args
    return screen.window


@pytest.fixture
def fake_curses(monkeypatch):
    screen = FakeScreen()
    monkeypatch.setattr("curses_components.popup.curses.newwin",
                        lambda *args: _new_window(screen, *args))
    monkeypatch.setattr("curses_components.popup.curses.init_pair", lambda *args: None)
    monkeypatch.setattr("curses_components.popup.curses.color_pair", lambda value: value)
    monkeypatch.setattr("curses_components.popup.curses.doupdate", lambda: None)
    return screen


def test_popup_dimensions_are_clamped_and_centered(fake_curses):
    ScrollablePopup(fake_curses, rows=[], width=60, height=12).display()

    assert fake_curses.created == (12, 60, 14, 30)


def test_popup_uses_safe_minimum_and_terminal_bounds(fake_curses):
    ScrollablePopup(fake_curses, rows=[], width=2, height=2).display()
    assert fake_curses.created == (5, 8, 17, 56)

    fake_curses.height, fake_curses.width = 6, 10
    ScrollablePopup(fake_curses, rows=[], width=100, height=100).display()
    assert fake_curses.created == (4, 8, 1, 1)


@pytest.mark.parametrize("name", ["width", "height"])
def test_popup_rejects_non_positive_dimensions(name):
    with pytest.raises(ValueError):
        ScrollablePopup(object(), **{name: 0})
    with pytest.raises(ValueError):
        ScrollablePopup(object(), **{name: -1})


def test_text_popup_clips_lines_without_overwriting_border(fake_curses):
    TextPopup(fake_curses, ["x" * 100], width=12, height=8).display()

    assert fake_curses.created[:2] == (8, 12)
    for _, x, text in fake_curses.window.writes:
        assert x + len(text) <= 11


def test_grid_forwards_key_column_width_to_text_popup(monkeypatch):
    captured = {}

    class CapturePopup:
        def __init__(self, stdscr, lines, **kwargs):
            captured.update(lines=lines, kwargs=kwargs)

        def display(self):
            pass

    grid = GridComponent()
    grid.stdscr = object()
    monkeypatch.setattr("curses_components.grid.TextPopup", CapturePopup)

    grid.show_popup("Summary", lines=["long line"], key_col_width=60,
                    width=70, height=12)

    assert captured["kwargs"]["key_col_width"] == 60
    assert captured["kwargs"]["width"] == 70
    assert captured["kwargs"]["height"] == 12


def test_grid_rows_popup_still_receives_key_column_width(monkeypatch):
    captured = {}

    class CapturePopup:
        def __init__(self, stdscr, **kwargs):
            captured.update(kwargs)

        def display(self):
            pass

    grid = GridComponent()
    grid.stdscr = object()
    monkeypatch.setattr("curses_components.grid.ScrollablePopup", CapturePopup)

    grid.show_popup("Rows", rows=[("key", "value")], key_col_width=33)

    assert captured["key_col_width"] == 33


def test_count_popup_width_fits_value_and_count_columns(monkeypatch):
    captured = {}
    value = "long value " * 5
    grid = GridComponent()
    grid.columns = ["status"]
    grid.data = [{"status": value}] * 123
    monkeypatch.setattr(grid, "show_popup", lambda *args, **kwargs: captured.update(kwargs))

    grid._cmd_count([])

    assert captured["key_col_width"] == len(value) + 2
    assert captured["width"] == len(value) + 2 + len("Count") + 2
    assert captured["height"] == 7


def test_input_mode_normalizes_only_the_command_name():
    received = []
    grid = GridComponent()
    grid.register_command("echo", lambda _grid, args: received.extend(args))
    grid.input_mode = True
    grid.input_buffer = "EcHo MixedCase VALUE"

    assert grid._handle_input_mode(10) is True
    assert received == ["MixedCase", "VALUE"]


def test_extension_help_is_sorted_and_re_registration_updates_it():
    grid = GridComponent()
    handler = lambda args: None
    grid.register_command(" Zeta ", handler, help_text="zeta  Zeta help")
    grid.register_command("alpha", handler, help_text="alpha  Alpha help")

    rows = HelpPopup(object(), extension_help=grid._extension_help).rows
    extension_rows = rows[rows.index(("Extension Commands", "")) + 1:]
    assert extension_rows == [("alpha", "Alpha help"), ("zeta", "Zeta help")]

    grid.register_command("ALPHA", handler, help_text="alpha  Updated help")
    rows = HelpPopup(object(), extension_help=grid._extension_help).rows
    assert ("alpha", "Updated help") in rows
    assert ("alpha", "Alpha help") not in rows


def test_extension_help_without_column_separator_stays_in_left_column():
    rows = HelpPopup(object(), extension_help={"info": "info"}).rows

    assert ("info", "") in rows


def test_registering_without_help_removes_extension_help():
    grid = GridComponent()
    handler = lambda args: None
    grid.register_command("summary", handler, help_text="summary help")
    grid.register_command("SUMMARY", handler)

    rows = HelpPopup(object(), extension_help=grid._extension_help).rows
    assert ("Extension Commands", "") not in rows
    assert ("summary help", "") not in rows


def test_help_lists_format_commands_and_registered_formatters():
    grid = GridComponent()
    grid.register_formatter("percent", lambda value: f"{value:.0%}")

    rows = HelpPopup(object(), formatters=grid._formatters).rows

    assert ("format all <name>", "Set the global formatter") in rows
    assert ("commas", "Thousands separators") in rows
    assert ("fixed", "Thousands separators with float_fmt precision") in rows
    assert ("off", "Display raw values; default formatter") in rows
    assert ("percent", "Custom formatter") in rows


def test_active_column_header_is_inverted(monkeypatch):
    class Screen:
        def __init__(self):
            self.writes = []

        def addstr(self, y, x, text, attrs=0):
            self.writes.append((y, x, text, attrs))

    screen = Screen()
    monkeypatch.setattr("curses_components.grid.curses.color_pair", lambda value: value)
    grid = GridComponent()
    grid.stdscr = screen
    grid.columns = ["First", "Second"]
    grid.col_widths = {"First": 5, "Second": 6}
    grid.col_idx = 1

    grid._draw_header(row_num_width=0, max_width=40)

    assert screen.writes[0][3] == 3 | curses.A_REVERSE
    assert screen.writes[1][3] == 3


def test_active_row_header_is_inverted(monkeypatch):
    class Screen:
        def __init__(self):
            self.writes = []

        def addstr(self, y, x, text, attrs=0):
            self.writes.append((y, x, text, attrs))

    screen = Screen()
    monkeypatch.setattr("curses_components.grid.curses.color_pair", lambda value: value)
    grid = GridComponent()
    grid.stdscr = screen
    grid.columns = ["Value"]
    grid.col_widths = {"Value": 5}
    grid.data = [{"Value": "one"}, {"Value": "two"}]
    grid.col_is_numeric = {"Value": False}
    grid.row_idx = 1

    grid._draw_data(max_height=10, row_num_width=4, max_width=40)

    assert screen.writes[0][3] == 3 | curses.A_REVERSE
    assert screen.writes[3][3] == 3


def test_help_popup_has_no_extension_heading_by_default():
    rows = HelpPopup(object()).rows

    assert ("Extension Commands", "") not in rows
