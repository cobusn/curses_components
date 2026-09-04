Todo list
=========

# Grid Component
- [ ] Consistent alignment per column
- [ ] :hide command to hide column
- [ ] :count command to count distinct values in column
- [ ] :write (:w) command to write to csv or jsonl
- [ ] :hist comand to do a simple histogram

# Editor Component
- [ ] Autocomplete dropdown — show completions when typing in insert mode.
      Pass a list at construction: `EditorPopup(stdscr, completions=[...])`.
      Trigger on word boundary; filter as user types; Tab/Down/Up to navigate;
      Enter or Tab to accept; Esc to dismiss.  Dropdown window positioned below
      cursor, clamped to terminal bounds.  See conversation notes for
      implementation detail.
