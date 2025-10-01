import curses
from curses_components.curses_component import COLORS


def main(stdscr):
    """
    Displays all the curses colors defined in the COLORS dictionary.
    """
    curses.curs_set(0)  # Hide the cursor

    if not curses.has_colors():
        stdscr.addstr(0, 0, "Your terminal does not support colors.")
        stdscr.getch()
        return

    curses.start_color()
    curses.use_default_colors()

    stdscr.addstr(0, 0, "Curses Color Palette", curses.A_BOLD | curses.A_UNDERLINE)
    stdscr.addstr(2, 0, "{:<10} | {:<10} | {}".format("Name", "ID", "Example"))
    stdscr.addstr(3, 0, "-" * 40)

    y = 4
    # Start pair number from 1, as 0 is reserved for black/white.
    for i, (name, color_id) in enumerate(COLORS.items(), 1):
        # init_pair(pair_number, fg, bg)
        # Using -1 for the background uses the terminal's default background.
        curses.init_pair(i, color_id, -1)

        # Prepare the text to display
        name_str = "{:<10}".format(name)
        id_str = "| {:<10}".format(color_id)
        example_str = "| Sample Text"

        # Display the text parts
        stdscr.addstr(y, 0, name_str)
        stdscr.addstr(y, 11, id_str)

        # Display the example text in the corresponding color
        stdscr.addstr(y, 24, example_str, curses.color_pair(i))

        y += 1

    stdscr.addstr(y + 2, 0, "Press any key to exit.")
    stdscr.getch()


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except curses.error as e:
        print(f"Curses error: {e}")
        print("This might be because the terminal is not large enough.")
