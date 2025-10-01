import csv
import sys
import logging
import os
from curses_components.grid import GridComponent

os.environ.setdefault('TERM', 'xterm')

logging.basicConfig(filename='debug.log', level=logging.DEBUG)


def main():
    logging.debug("Starting the application")
    if len(sys.argv) != 2:
        logging.error(f"Usage: python {sys.argv[0]} <csv_file>")
        print(f"Usage: python {sys.argv[0]} <csv_file>")
        sys.exit(1)

    csv_file = sys.argv[1]
    logging.debug(f"CSV file: {csv_file}")
    data = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    logging.debug(f"Data loaded: {len(data)} rows")

    component = GridComponent()
    component.display(data)
    logging.debug("Application finished")


if __name__ == "__main__":
    main()
