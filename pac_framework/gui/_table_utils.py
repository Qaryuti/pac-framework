"""Shared Qt table helpers used across GUI tab modules."""
from __future__ import annotations

from PyQt6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem


def _cell(table: QTableWidget, row: int, col: int, default: str = "") -> str:
    """Return the stripped text of a table cell, or *default* if empty."""
    item = table.item(row, col)
    return item.text().strip() if item else default


def _make_table(
    headers: list[str],
    min_height: int = 120,
    col_widths: dict[int, int] | None = None,
) -> QTableWidget:
    """Build a QTableWidget with standard row-selection and header behaviour.

    All columns except the last use Interactive resize mode; the last
    column stretches to fill.
    """
    t = QTableWidget()
    t.setColumnCount(len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.verticalHeader().setVisible(False)
    t.setMinimumHeight(min_height)
    hdr = t.horizontalHeader()
    for i in range(len(headers) - 1):
        hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
    hdr.setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeMode.Stretch)
    if col_widths:
        for col, width in col_widths.items():
            t.setColumnWidth(col, width)
    return t
