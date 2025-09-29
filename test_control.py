#!/usr/bin/env python
"""
Display a CSV file in a curses component.
"""

from curses_component import CursesComponent
import csv
import argparse


def read_csv_data(filename):
    data = []
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('filename', nargs='?',
                        default='customers.csv', help='The CSV file to display.')
    args = parser.parse_args()

    data = read_csv_data(args.filename)
    component = CursesComponent()
    component.display(data)
