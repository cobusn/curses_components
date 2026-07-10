curses_components
=================

A reusable Python terminal UI library built on curses.  Provides a grid viewer
for tabular data and a vi-like text editor popup.  Both components focus purely
on the user interface and accept data in a canonical format.

Components
----------

GridComponent
    Displays tabular data (e.g. CSV, database result sets) in a scrollable,
    interactive grid.  Supports filtering, sorting, searching, column
    navigation, and CSV export.

EditorPopup
    A vi-like modal text editor shown as a popup window.  Suitable for editing
    small text files such as SQL scripts.  Supports insert mode, normal mode
    commands, search, substitute, and sort.

ScrollablePopup
    Base class for bordered, scrollable popup windows.  Subclass to build
    custom help screens or information panels.

Installation
------------

Install as an editable local package (recommended for development):

    pip install -e /path/to/curses_component

Or add as a git submodule in another project:

    git submodule add <repo-url> libs/curses_component
    pip install -e libs/curses_component

Usage
-----

GridComponent:

    import curses
    from curses_components import GridComponent

    data = [
        {'name': 'Alice', 'age': 30},
        {'name': 'Bob',   'age': 25},
    ]

    def main(stdscr):
        grid = GridComponent(data, fg_color='green', bg_color='black')
        grid.display(stdscr)

    curses.wrapper(main)

EditorPopup:

    import curses
    from curses_components import EditorPopup

    def main(stdscr):
        editor = EditorPopup(stdscr, title='Edit', fg_color='green',
                             bg_color='black', bold=True)
        result = editor.edit(text='', filename='script.sql')
        if result is not None:
            print(result)

    curses.wrapper(main)

See examples/ for runnable demos:

    python examples/grid_editor.py
    python examples/text_editor.py
    python examples/text_editor.py <file>
    python examples/text_editor.py --size 120x40 <file>

GridComponent key bindings
--------------------------

Navigation:   j/k/h/l or arrow keys, Home/End, Page Up/Down, ^/$
Search:       / (substring), r/<pattern> (regex), n/N (next/previous)
Input mode:   : (enter), q (quit), sort, filter, col, freeze, copy,
              copyrow, export <file>
Sorting:      sort col1 col2!   (! suffix = descending)
Filtering:    filter <val>      (current column, wildcards supported)
              filter reset
Marks:        m (set), ' (jump)
Other:        # (toggle row numbers), ? (help), Ctrl+Left/Right (resize column)

EditorPopup key bindings
------------------------

Normal mode:  h/j/k/l or arrow keys, w/b (word), 0/$ (line), gg/G (file)
Editing:      i/a (insert), o/O (new line), x (delete char), dw (delete word),
              dd (delete line), yy (yank), p (paste), u (undo)
Search:       / (enter), n/N (next/previous)
Command mode: :w [file], :q, :q!, :wq, :x, :<number> (jump to line)
Substitute:   :s/pat/rep[/g], :%s/pat/rep[/g]
Sort:         :sort[!][ u]
Help:         :help

Color options (both components)
--------------------------------

Both GridComponent and EditorPopup accept fg_color, bg_color, and border_color
as constructor arguments.  Valid color names:

    black  blue  cyan  green  magenta  red  white  yellow

EditorPopup also accepts bold=True (bright text) and bold_background=True.

Dependencies
------------

- Python 3.13+
- pyperclip (for copy/copyrow commands in GridComponent)

License
-------

MIT
