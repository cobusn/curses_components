Todo list
=========

# Grid Component
- [ ] Consistent alignment per column

# Editor Component
- [ ] Autocomplete dropdown — show completions when typing in insert mode.
      Pass a list at construction: `EditorPopup(stdscr, completions=[...])`.
      Trigger on word boundary; filter as user types; Tab/Down/Up to navigate;
      Enter or Tab to accept; Esc to dismiss.  Dropdown window positioned below
      cursor, clamped to terminal bounds.  See conversation notes for
      implementation detail.
