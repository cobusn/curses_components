import pytest

from curses_components.grid import GridComponent


def make_grid():
    grid = GridComponent()
    grid.data = [
        {"amount": 1000000, "ratio": 0.125, "code": "1000"},
        {"amount": 2500, "ratio": 0.5, "code": "2500"},
    ]
    grid.columns = ["amount", "ratio", "code"]
    grid.max_rows = 100
    grid._prepare_data()
    return grid


def test_default_formatter_uses_thousands_separators():
    grid = make_grid()

    assert grid._format_cell_value("amount", 1000000) == "1,000,000"
    assert grid._format_cell_value("ratio", 0.125) == "0.12"
    assert grid._format_cell_value("code", "1000") == "1000"


def test_default_formatter_handles_excel_style_integer():
    numpy = pytest.importorskip("numpy")
    grid = GridComponent()

    assert grid._format_cell_value("amount", numpy.int64(1000)) == "1,000"


def test_global_and_column_formatters_can_be_changed():
    grid = make_grid()
    grid.register_formatter("percent", lambda value: f"{value:.0%}")

    grid.set_default_formatter("off")
    grid.set_column_formatter("ratio", "percent")

    assert grid._format_cell_value("amount", 1000000) == "1000000"
    assert grid._format_cell_value("ratio", 0.125) == "12%"
    assert grid.col_widths["amount"] == len("1000000")

    grid.set_column_formatter("ratio", "inherit")
    assert grid._format_cell_value("ratio", 0.125) == "0.125"

    grid.set_default_formatter("commas")
    assert grid.col_widths["amount"] == len("1,000,000")


def test_format_command_changes_global_and_current_column():
    grid = make_grid()
    grid.col_idx = 1
    grid._cmd_format(["off"])

    assert grid._format_cell_value("ratio", 0.125) == "0.125"

    grid._cmd_format(["inherit"])
    grid._cmd_format(["all", "commas"])
    assert grid._format_cell_value("amount", 1000000) == "1,000,000"
    assert grid._format_cell_value("ratio", 0.125) == "0.12"


def test_custom_formatter_receives_raw_value():
    grid = make_grid()
    received = []

    def formatter(value):
        received.append(value)
        return "formatted"

    grid.register_formatter("custom", formatter)
    grid.set_column_formatter("amount", "custom")

    assert grid._format_cell_value("amount", 1000000) == "formatted"
    assert received[-1] == 1000000
