# Requirements
Please assist with writing a Python class that will be used as a reusable
component.  The class will be used to display table data in a Text User
interface format using the Curses Library.  The display will follow
a similar interface as a text spreadsheet such as Lotus 123.

## Interface
* The class will have a .display(data, columns=None) method that will activate
  the display.
* The class will have a __init__ constructor with the following variables:
  - `fg=green` is the foreground colour
  - `bg=black` is the background colour
  - `max_width=20` is the maximum column width
  - `float_fmt=.2f' is the format for floating point numbers
* Data provided will be in a list of `dict` or iterator of `dict` format. The
  keys will be the column headers;

## Display
* the screen should not flicker on updating
* the control must be able to handle tables that are wider than the visible
  screen space and be able to scroll left ad right.
* If the columns variable of the .display method is not provided then the
  column names of the first row will be used
* Column widths will be determined as the maximum string width of the column or
  variable `max_col_width`, a variable that is defaulted to (as provided in the
  __init__ function)
* The top row will display the column names and will be in reverse text 

### Row index and Status bar
The leftmost column will display the row number right aligned and will be in
reverse text colors.

The bottom row is the status bar, it is not in reverse text
and display the followng information:
  - row numnber on the right hand side
  - when "search mode" or "command mode" is enabled the commands or search text is
    echoed on the left hand of the status bar
* text alignments as follow:
  - text is left aligned
  - numbers are right aligned

## User Interface and Navigation
The control should have a vim like interface. 

### Normal mode
In normal mode, provide the usual Navigational keys such as

  - `arrow up` or `k` move one up
  - `arrow down` or `j` move one down
  - `arrow left` or `h` move one column to the left
  - `arrow right` or `l` move one column to the right
  - `$` move to the last column on the right
  - `^` move to the first column`
  - home, end, PgUp, PgDn
  - home and end should move to the first and last row respectively however the
    column should still be the same.
  - When `Ctl left arror` or `Ctl right arrow` is pressed the width of the
    current column is respectively either reduced or increased;

### Command Mode
Entering the  `:` character enable a command mode with the following commands:
  - when `:` and a number is typed the cursor must move to the row identified
    by the number. 
  - ':$' take you to the last row
  - when `:q` and Enter is typed then exit the application

### Search mode
`/` enable search mode.  When search mode is enabled, any text after the /
and before Enter is a search text. The control will search through the rows
and stop at a cell that contain the search text.

When the application is in the Normal state and if a search have been activated
then pressing the `n` button will move to the next position where the search
match.

# Test driver application
Also provide a `test_control.py`  example that will read the CSV file provided
as a parameter to the script.  `Customers.csv` can be used to test
