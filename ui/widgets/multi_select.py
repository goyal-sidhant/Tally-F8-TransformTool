"""
Multi-Select Widgets
Popup and ComboBox widgets for multi-selection functionality.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QBrush

from typing import List, Set


class MultiSelectPopup(QDialog):
    """Popup dialog for multi-select with checkboxes"""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setMinimumWidth(250)
        self.setMaximumHeight(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Type to search...")
        self.search_box.textChanged.connect(self._filter_items)
        layout.addWidget(self.search_box)

        # List widget with checkboxes
        self.list_widget = QListWidget()
        self.list_widget.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.list_widget)

        # Done button
        self.btn_done = QPushButton("Done")
        self.btn_done.clicked.connect(self.accept)
        layout.addWidget(self.btn_done)

        self._all_items = []
        self._disabled_items = set()
        self._callback = None

    def showEvent(self, event):
        """Auto-focus on search box when popup opens"""
        super().showEvent(event)
        self.search_box.setFocus()
        self.search_box.selectAll()

    def set_items(self, items: List[str], selected: List[str], disabled: Set[str]):
        """Set items with selection and disabled state"""
        self._all_items = items
        self._disabled_items = disabled
        self._selected = set(selected)
        self._rebuild_list()

    def _rebuild_list(self):
        """Rebuild list based on search filter, with smart sorting"""
        search_text = self.search_box.text().lower()

        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        # Sort items: currently selected first, then unselected available, then disabled at bottom
        available_items = []
        for item_text in self._all_items:
            # Filter by search
            if search_text and search_text not in item_text.lower():
                continue

            is_selected = item_text in self._selected
            is_disabled = item_text in self._disabled_items

            # Sort order: selected (0), available (1), disabled (2)
            sort_key = 0 if is_selected else (2 if is_disabled else 1)
            available_items.append((sort_key, item_text, is_selected, is_disabled))

        # Sort by sort_key, then alphabetically
        available_items.sort(key=lambda x: (x[0], x[1].lower()))

        for _, item_text, is_selected, is_disabled in available_items:
            item = QListWidgetItem(item_text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)

            if is_disabled:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                item.setCheckState(Qt.Unchecked)
                item.setForeground(QBrush(QColor('#999999')))
            else:
                if is_selected:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)

            self.list_widget.addItem(item)

        self.list_widget.blockSignals(False)

    def _filter_items(self):
        """Filter items based on search text"""
        self._rebuild_list()

    def _on_item_changed(self, item):
        """Handle item check state change"""
        if item.checkState() == Qt.Checked:
            self._selected.add(item.text())
        else:
            self._selected.discard(item.text())

        if self._callback:
            self._callback()

    def get_selected(self) -> List[str]:
        """Get selected items"""
        return [item for item in self._all_items if item in self._selected]

    def set_callback(self, callback):
        """Set callback for selection changes"""
        self._callback = callback


class MultiSelectComboBox(QWidget):
    """Custom widget that shows selected items and opens a popup for selection"""

    selection_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Display field
        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setPlaceholderText("Click to select columns...")
        self.display.mousePressEvent = self._on_click
        layout.addWidget(self.display)

        # Dropdown button
        self.btn_dropdown = QPushButton("▼")
        self.btn_dropdown.setFixedWidth(25)
        self.btn_dropdown.clicked.connect(self._show_popup)
        layout.addWidget(self.btn_dropdown)

        # Data
        self._all_items = []
        self._selected = []
        self._disabled_items = set()
        self._popup = None

    def _on_click(self, event):
        """Handle click on display field"""
        self._show_popup()

    def _show_popup(self):
        """Show the selection popup"""
        if not self._all_items:
            QMessageBox.information(self, "No Items",
                "No tax columns available.\nMark columns as Tax in Column List first.")
            return

        popup = MultiSelectPopup(self)
        popup.set_items(self._all_items, self._selected, self._disabled_items)
        popup.set_callback(self._on_selection_changed_in_popup)

        # Position popup below this widget
        pos = self.mapToGlobal(self.rect().bottomLeft())
        popup.move(pos)
        popup.setMinimumWidth(self.width())

        self._popup = popup
        popup.exec_()

        # Update selection from popup
        self._selected = popup.get_selected()
        self._update_display()
        self.selection_changed.emit()

    def _on_selection_changed_in_popup(self):
        """Handle real-time selection changes in popup"""
        if self._popup:
            self._selected = self._popup.get_selected()
            self._update_display()

    def _update_display(self):
        """Update display text"""
        if self._selected:
            self.display.setText(", ".join(self._selected))
        else:
            self.display.setText("")

    def set_items(self, items: List[str], disabled: Set[str] = None):
        """Set available items"""
        self._all_items = list(items) if items else []
        self._disabled_items = disabled or set()

        # Remove any selected items that are now disabled or don't exist
        self._selected = [s for s in self._selected
                         if s in self._all_items and s not in self._disabled_items]
        self._update_display()

    def get_selected(self) -> List[str]:
        """Get selected items"""
        return self._selected.copy()

    def set_selected(self, items: List[str]):
        """Set selected items"""
        self._selected = [s for s in items
                         if s in self._all_items and s not in self._disabled_items]
        self._update_display()

    def setEnabled(self, enabled: bool):
        """Enable/disable the widget"""
        super().setEnabled(enabled)
        self.display.setEnabled(enabled)
        self.btn_dropdown.setEnabled(enabled)
        if not enabled:
            self.display.setPlaceholderText("All tax columns assigned")
        else:
            self.display.setPlaceholderText("Click to select columns...")

    def lineEdit(self):
        """Return display field for compatibility"""
        return self.display
