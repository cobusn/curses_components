from curses_components.grid import GridComponent


def make_grid():
    grid = GridComponent()
    grid.columns = ["Status", "Owner"]
    grid.data = [
        {"Status": "Resolved", "Owner": "Alice"},
        {"Status": "Closed", "Owner": "Alice"},
        {"Status": "Resolved", "Owner": "Bob"},
        {"Status": "Open", "Owner": "Alice"},
    ]
    grid._all_data = grid.data
    return grid


def test_filters_or_values_within_column_and_and_between_columns():
    grid = make_grid()

    grid._cmd_filter(["Status", "Resolved"])
    grid._cmd_filter(["or", "Status", "Closed"])
    grid._cmd_filter(["Owner", "Alice"])

    assert grid.active_filters == {
        "Status": ["Resolved", "Closed"],
        "Owner": ["Alice"],
    }
    assert grid.data == [
        {"Status": "Resolved", "Owner": "Alice"},
        {"Status": "Closed", "Owner": "Alice"},
    ]


def test_current_column_filter_and_or_shorthand():
    grid = make_grid()

    grid._cmd_filter(["Resolved"])
    grid._cmd_filter(["or", "Closed"])

    assert grid.active_filters == {"Status": ["Resolved", "Closed"]}
    assert [row["Status"] for row in grid.data] == ["Resolved", "Closed", "Resolved"]


def test_regular_filter_replaces_existing_column_values():
    grid = make_grid()

    grid._cmd_filter(["Status", "Resolved"])
    grid._cmd_filter(["or", "Status", "Closed"])
    grid._cmd_filter(["Status", "Open"])

    assert grid.active_filters == {"Status": ["Open"]}
    assert grid.data == [{"Status": "Open", "Owner": "Alice"}]


def test_filter_remove_value_column_and_reset():
    grid = make_grid()
    grid._cmd_filter(["Status", "Resolved"])
    grid._cmd_filter(["or", "Status", "Closed"])
    grid._cmd_filter(["Owner", "Alice"])

    grid._cmd_filter(["remove", "Status", "Closed"])
    assert grid.active_filters == {"Status": ["Resolved"], "Owner": ["Alice"]}
    assert grid.data == [{"Status": "Resolved", "Owner": "Alice"}]

    grid._cmd_filter(["remove", "Owner"])
    assert grid.active_filters == {"Status": ["Resolved"]}
    assert grid.data == [
        {"Status": "Resolved", "Owner": "Alice"},
        {"Status": "Resolved", "Owner": "Bob"},
    ]

    grid._cmd_filter(["reset"])
    assert grid.active_filters == {}
    assert grid.data == grid._all_data


def test_filters_are_case_sensitive_and_support_wildcards():
    grid = make_grid()
    grid.data.append({"Status": "resolved", "Owner": "Alice"})

    grid._cmd_filter(["Status", "Resolved"])
    assert all(row["Status"] == "Resolved" for row in grid.data)

    grid._cmd_filter(["Status", "Res*"])
    assert all(row["Status"] == "Resolved" for row in grid.data)
