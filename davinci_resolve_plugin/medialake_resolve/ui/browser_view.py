"""Browser view for displaying Media Lake assets."""

from typing import Optional, List, Set
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QGridLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QPushButton,
    QCheckBox,
    QFrame,
    QSizePolicy,
    QStackedWidget,
    QAbstractItemView,
    QMenu,
    QComboBox,
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QPixmap, QImage, QIcon, QCursor

from medialake_resolve.core.config import Config
from medialake_resolve.core.models import Asset, MediaType


class ThumbnailWidget(QFrame):
    """Widget for displaying a single asset thumbnail with selection."""
    
    clicked = Signal(Asset, object)  # asset, event (for modifier key detection)
    double_clicked = Signal(Asset)
    selection_changed = Signal(Asset, bool)
    
    def __init__(self, asset: Asset, thumbnail_size: int, parent: Optional[QWidget] = None):
        """Initialize thumbnail widget.
        
        Args:
            asset: The asset to display.
            thumbnail_size: Size for the thumbnail.
            parent: Parent widget.
        """
        super().__init__(parent)
        
        self.asset = asset
        self._thumbnail_size = thumbnail_size
        self._selected = False
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(1)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Selection checkbox
        self._checkbox = QCheckBox()
        self._checkbox.stateChanged.connect(self._on_checkbox_changed)
        
        # Thumbnail container
        thumb_container = QHBoxLayout()
        thumb_container.addWidget(self._checkbox)
        thumb_container.addStretch()
        
        # Thumbnail image
        self._thumbnail_label = QLabel()
        self._thumbnail_label.setFixedSize(self._thumbnail_size, self._thumbnail_size)
        self._thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail_label.setScaledContents(False)
        self._thumbnail_label.setStyleSheet(
            "background-color: #2a2a2a; border-radius: 4px;"
        )
        
        # Set placeholder
        self._set_placeholder()
        
        layout.addLayout(thumb_container)
        layout.addWidget(self._thumbnail_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Name label
        self._name_label = QLabel(self.asset.name)
        self._name_label.setWordWrap(True)
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setMaximumWidth(self._thumbnail_size + 8)
        font = self._name_label.font()
        font.setPointSize(10)
        self._name_label.setFont(font)
        layout.addWidget(self._name_label)
        
        # Info label (duration/type)
        info_text = self._get_info_text()
        self._info_label = QLabel(info_text)
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_label.setStyleSheet("color: gray; font-size: 9px;")
        layout.addWidget(self._info_label)
        
        self.setFixedWidth(self._thumbnail_size + 16)
        self._update_style()
    
    def _set_placeholder(self) -> None:
        """Set a placeholder icon based on media type."""
        icon_map = {
            MediaType.VIDEO: "🎬",
            MediaType.AUDIO: "🎵",
            MediaType.IMAGE: "🖼️",
            MediaType.DOCUMENT: "📄",
            MediaType.OTHER: "📁",
        }
        icon = icon_map.get(self.asset.media_type, "📁")
        self._thumbnail_label.setText(icon)
        self._thumbnail_label.setStyleSheet(
            "background-color: #2a2a2a; border-radius: 4px; font-size: 48px;"
        )
    
    def set_thumbnail(self, image_data: bytes) -> None:
        """Set the thumbnail image.
        
        Args:
            image_data: Raw image bytes.
        """
        image = QImage()
        if image.loadFromData(image_data):
            pixmap = QPixmap.fromImage(image)
            scaled = pixmap.scaled(
                self._thumbnail_size,
                self._thumbnail_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._thumbnail_label.setPixmap(scaled)
            self._thumbnail_label.setStyleSheet(
                "background-color: #2a2a2a; border-radius: 4px;"
            )
    
    def _get_info_text(self) -> str:
        """Get info text for the asset."""
        parts = []
        
        if self.asset.display_duration:
            parts.append(self.asset.display_duration)
        
        if self.asset.resolution:
            parts.append(self.asset.resolution)
        
        parts.append(self.asset.display_size)
        
        return " • ".join(parts)
    
    @property
    def is_selected(self) -> bool:
        """Check if this item is selected."""
        return self._selected
    
    @is_selected.setter
    def is_selected(self, selected: bool) -> None:
        """Set selection state."""
        self._selected = selected
        self._checkbox.setChecked(selected)
        self._update_style()
    
    def _update_style(self) -> None:
        """Update widget style based on selection state."""
        if self._selected:
            self.setStyleSheet(
                "ThumbnailWidget { background-color: #3d5a80; border: 2px solid #5c8ab8; border-radius: 4px; }"
            )
        else:
            self.setStyleSheet(
                "ThumbnailWidget { background-color: #1a1a1a; border: 1px solid #333; border-radius: 4px; }"
                "ThumbnailWidget:hover { background-color: #252525; border: 1px solid #444; }"
            )
    
    def _on_checkbox_changed(self, state: int) -> None:
        """Handle checkbox state change."""
        is_checked = state == Qt.CheckState.Checked.value
        self._selected = is_checked
        self._update_style()
        self.selection_changed.emit(self.asset, is_checked)
    
    def mousePressEvent(self, event) -> None:
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.asset, event)
        super().mousePressEvent(event)
    
    def mouseDoubleClickEvent(self, event) -> None:
        """Handle double click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.asset)
        super().mouseDoubleClickEvent(event)


class BrowserView(QWidget):
    """Browser view for displaying Media Lake assets in grid or list mode.
    
    Signals:
        asset_selected: Emitted when an asset is clicked. (asset)
        asset_double_clicked: Emitted on double-click. (asset)
        selection_changed: Emitted when selection changes. (selected_assets)
        load_more_requested: Emitted when more assets should be loaded.
    """
    
    asset_selected = Signal(Asset)
    asset_double_clicked = Signal(Asset)
    selection_changed = Signal(list)
    load_more_requested = Signal()
    page_changed = Signal(int)  # Emitted when user requests a specific page
    page_size_changed = Signal(int)  # Emitted when user changes page size
    
    def __init__(self, config: Config, parent: Optional[QWidget] = None):
        """Initialize browser view.
        
        Args:
            config: Application configuration.
            parent: Parent widget.
        """
        super().__init__(parent)
        
        self._config = config
        self._assets: List[Asset] = []
        self._selected_assets: Set[str] = set()  # asset IDs
        self._thumbnail_widgets: dict = {}  # asset_id -> ThumbnailWidget
        self._list_items: dict = {}  # asset_id -> QListWidgetItem (for list view thumbnails)
        self._thumbnail_cache: dict = {}  # asset_id -> bytes (thumbnail image data)
        self._current_view = "grid"
        self._last_clicked_asset_id: Optional[str] = None  # For shift-select range
        
        # Size for list view thumbnails
        self._list_thumbnail_size = 32
        
        # Pagination state
        self._current_page = 1
        self._total_pages = 1
        self._total_items = 0
        self._page_size = 10  # Default page size
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the browser UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        
        # Style for view mode toggle buttons
        view_button_style = """
            QPushButton {
                padding: 4px 12px;
                border: 1px solid #555;
                background-color: #3a3a3a;
                color: #aaa;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                color: #ddd;
            }
            QPushButton:checked {
                background-color: #0a5a9e;
                color: white;
                border: 1px solid #0a7acc;
            }
        """
        
        # View mode buttons
        self._grid_button = QPushButton("Grid")
        self._grid_button.setCheckable(True)
        self._grid_button.setChecked(True)
        self._grid_button.setStyleSheet(view_button_style)
        self._grid_button.clicked.connect(lambda: self.set_view_mode("grid"))
        toolbar.addWidget(self._grid_button)
        
        self._list_button = QPushButton("List")
        self._list_button.setCheckable(True)
        self._list_button.setStyleSheet(view_button_style)
        self._list_button.clicked.connect(lambda: self.set_view_mode("list"))
        toolbar.addWidget(self._list_button)
        
        toolbar.addStretch()
        
        # Selection info
        self._selection_label = QLabel("0 selected")
        toolbar.addWidget(self._selection_label)
        
        # Add spacing between label and buttons
        toolbar.addSpacing(16)
        
        # Select all / clear
        self._select_all_button = QPushButton("Select All")
        self._select_all_button.clicked.connect(self.select_all)
        toolbar.addWidget(self._select_all_button)
        
        self._clear_selection_button = QPushButton("Clear Selection")
        self._clear_selection_button.clicked.connect(self.clear_selection)
        toolbar.addWidget(self._clear_selection_button)
        
        layout.addLayout(toolbar)
        
        # Stacked widget for grid/list views
        self._stack = QStackedWidget()
        
        # Grid view (scroll area with grid layout)
        self._grid_scroll = QScrollArea()
        self._grid_scroll.setWidgetResizable(True)
        self._grid_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self._grid_container = QWidget()
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(12)
        self._grid_layout.setContentsMargins(12, 12, 12, 12)
        # Align items to top-left so they don't stretch when few items
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._grid_scroll.setWidget(self._grid_container)
        
        self._stack.addWidget(self._grid_scroll)
        
        # List view
        self._list_widget = QListWidget()
        self._list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list_widget.setAlternatingRowColors(True)
        self._list_widget.setSpacing(0)
        self._list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #3a3a3a;
                background-color: #2d2d2d;
                color: #e0e0e0;
            }
            QListWidget::item {
                padding: 4px 8px;
                border-bottom: 1px solid #3a3a3a;
            }
            QListWidget::item:alternate {
                background-color: #333333;
            }
            QListWidget::item:selected {
                background-color: #0a5a9e;
                color: white;
            }
            QListWidget::item:hover:!selected {
                background-color: #404040;
            }
        """)
        self._list_widget.itemClicked.connect(self._on_list_item_clicked)
        self._list_widget.itemDoubleClicked.connect(self._on_list_item_double_clicked)
        self._list_widget.itemSelectionChanged.connect(self._on_list_selection_changed)
        self._stack.addWidget(self._list_widget)
        
        layout.addWidget(self._stack)
        
        # Pagination bar
        pagination_bar = QHBoxLayout()
        pagination_bar.setContentsMargins(8, 4, 8, 4)
        pagination_bar.setSpacing(8)
        
        # Status label (left side)
        self._status_label = QLabel("No assets loaded")
        self._status_label.setStyleSheet("color: gray;")
        pagination_bar.addWidget(self._status_label)
        
        pagination_bar.addStretch()
        
        # Page size selector
        page_size_label = QLabel("Show:")
        pagination_bar.addWidget(page_size_label)
        
        self._page_size_combo = QComboBox()
        self._page_size_combo.addItems(["10", "20", "30", "50"])
        self._page_size_combo.setCurrentText("10")  # Default
        self._page_size_combo.setFixedWidth(60)
        self._page_size_combo.currentTextChanged.connect(self._on_page_size_changed)
        pagination_bar.addWidget(self._page_size_combo)
        
        pagination_bar.addSpacing(16)
        
        # Previous button
        self._prev_button = QPushButton("◀ Prev")
        self._prev_button.setFixedWidth(70)
        self._prev_button.clicked.connect(self._on_prev_page)
        self._prev_button.setEnabled(False)
        pagination_bar.addWidget(self._prev_button)
        
        # Page indicator
        self._page_label = QLabel("Page 1 of 1")
        self._page_label.setStyleSheet("padding: 0 8px;")
        pagination_bar.addWidget(self._page_label)
        
        # Next button
        self._next_button = QPushButton("Next ▶")
        self._next_button.setFixedWidth(70)
        self._next_button.clicked.connect(self._on_next_page)
        self._next_button.setEnabled(False)
        pagination_bar.addWidget(self._next_button)
        
        layout.addLayout(pagination_bar)
        
        # Connect scroll for infinite loading (disabled - using pagination instead)
        # self._grid_scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)
    
    def set_assets(self, assets: List[Asset], append: bool = False) -> None:
        """Set or append assets to display.
        
        Args:
            assets: List of assets to display.
            append: If True, append to existing assets.
        """
        print(f"\n=== SET_ASSETS ===")
        print(f"  Received {len(assets)} assets, append={append}")
        print(f"  Current assets before: {len(self._assets)}")
        
        if not append:
            self._clear_view()
            self._assets = []
            self._selected_assets.clear()
            print(f"  Cleared view, assets now: {len(self._assets)}")
        
        self._assets.extend(assets)
        print(f"  After extend, assets now: {len(self._assets)}")
        self._update_view()
        self._update_status()
    
    def get_selected_assets(self) -> List[Asset]:
        """Get list of selected assets.
        
        Returns:
            List of selected Asset objects.
        """
        return [a for a in self._assets if a.asset_id in self._selected_assets]
    
    def set_view_mode(self, mode: str) -> None:
        """Set the view mode.
        
        Args:
            mode: "grid" or "list".
        """
        # Clear selection when switching views
        if self._current_view != mode:
            self.clear_selection()
        
        self._current_view = mode
        self._grid_button.setChecked(mode == "grid")
        self._list_button.setChecked(mode == "list")
        
        if mode == "grid":
            self._stack.setCurrentWidget(self._grid_scroll)
        else:
            self._stack.setCurrentWidget(self._list_widget)
        
        self._update_view()
        
        # Save preference
        self._config.view_mode = mode
        self._config.save()
    
    def set_thumbnail(self, asset_id: str, image_data: bytes) -> None:
        """Set thumbnail for an asset.
        
        Args:
            asset_id: The asset ID.
            image_data: Raw image bytes.
        """
        # Cache the thumbnail data
        self._thumbnail_cache[asset_id] = image_data
        
        # Update grid view thumbnail
        if asset_id in self._thumbnail_widgets:
            self._thumbnail_widgets[asset_id].set_thumbnail(image_data)
        
        # Update list view thumbnail
        if asset_id in self._list_items:
            image = QImage()
            if image.loadFromData(image_data):
                pixmap = QPixmap.fromImage(image)
                scaled = pixmap.scaled(
                    self._list_thumbnail_size,
                    self._list_thumbnail_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._list_items[asset_id].setIcon(QIcon(scaled))
    
    def select_all(self) -> None:
        """Select all visible assets."""
        for asset in self._assets:
            self._selected_assets.add(asset.asset_id)
            # Update grid view widgets
            if asset.asset_id in self._thumbnail_widgets:
                widget = self._thumbnail_widgets[asset.asset_id]
                widget._checkbox.blockSignals(True)
                widget.is_selected = True
                widget._checkbox.blockSignals(False)
        
        # Update list view selection
        self._list_widget.blockSignals(True)
        self._list_widget.selectAll()
        self._list_widget.blockSignals(False)
        
        self._update_selection_info()
        self.selection_changed.emit(self.get_selected_assets())
    
    def clear_selection(self) -> None:
        """Clear all selections."""
        # Make a copy since we're modifying during iteration
        selected_ids = list(self._selected_assets)
        
        # Update grid view widgets
        for asset_id in selected_ids:
            if asset_id in self._thumbnail_widgets:
                widget = self._thumbnail_widgets[asset_id]
                # Block signals to prevent cascading updates
                widget._checkbox.blockSignals(True)
                widget.is_selected = False
                widget._checkbox.blockSignals(False)
        
        # Update list view selection
        self._list_widget.blockSignals(True)
        self._list_widget.clearSelection()
        self._list_widget.blockSignals(False)
        
        self._selected_assets.clear()
        self._last_clicked_asset_id = None
        self._update_selection_info()
        self.selection_changed.emit([])
    
    def _clear_view(self) -> None:
        """Clear all widgets from the view."""
        # Clear grid
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Clear list
        self._list_widget.clear()
        
        self._thumbnail_widgets.clear()
        self._list_items.clear()
        self._thumbnail_cache.clear()
    
    def _update_view(self) -> None:
        """Update the view with current assets."""
        if self._current_view == "grid":
            self._update_grid_view()
        else:
            self._update_list_view()
    
    def _update_grid_view(self) -> None:
        """Update the grid view."""
        # Calculate columns based on width
        thumbnail_size = self._config.thumbnail_size
        available_width = self._grid_scroll.viewport().width() - 24
        cols = max(1, available_width // (thumbnail_size + 24))
        
        # Add widgets for assets not already in view
        for i, asset in enumerate(self._assets):
            if asset.asset_id not in self._thumbnail_widgets:
                widget = ThumbnailWidget(asset, thumbnail_size)
                widget.clicked.connect(self._on_thumbnail_clicked)
                widget.double_clicked.connect(self._on_thumbnail_double_clicked)
                widget.selection_changed.connect(self._on_thumbnail_selection_changed)
                
                if asset.asset_id in self._selected_assets:
                    widget.is_selected = True
                
                self._thumbnail_widgets[asset.asset_id] = widget
                
                row = i // cols
                col = i % cols
                self._grid_layout.addWidget(widget, row, col)
    
    def _update_list_view(self) -> None:
        """Update the list view."""
        self._list_widget.clear()
        self._list_items.clear()
        
        # Set icon size for thumbnails
        self._list_widget.setIconSize(QSize(self._list_thumbnail_size, self._list_thumbnail_size))
        
        for asset in self._assets:
            item = QListWidgetItem()
            
            # Build a more detailed display string
            details = [asset.name]
            if asset.media_type:
                details.append(f"[{asset.media_type.value.upper()}]")
            details.append(asset.display_size)
            if asset.display_duration and asset.display_duration != "N/A":
                details.append(asset.display_duration)
            if asset.width and asset.height:
                details.append(f"{asset.width}×{asset.height}")
            
            item.setText("  •  ".join(details))
            item.setData(Qt.ItemDataRole.UserRole, asset)
            
            # Check if we have a cached thumbnail for this asset
            if asset.asset_id in self._thumbnail_cache:
                # Use the cached thumbnail
                image = QImage()
                if image.loadFromData(self._thumbnail_cache[asset.asset_id]):
                    pixmap = QPixmap.fromImage(image)
                    scaled = pixmap.scaled(
                        self._list_thumbnail_size,
                        self._list_thumbnail_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    item.setIcon(QIcon(scaled))
                else:
                    # Fallback to placeholder if image load fails
                    placeholder_pixmap = self._create_placeholder_icon("", asset.media_type)
                    item.setIcon(QIcon(placeholder_pixmap))
            else:
                # No cached thumbnail, use placeholder
                placeholder_pixmap = self._create_placeholder_icon("", asset.media_type)
                item.setIcon(QIcon(placeholder_pixmap))
            
            if asset.asset_id in self._selected_assets:
                item.setSelected(True)
            
            self._list_widget.addItem(item)
            self._list_items[asset.asset_id] = item
    
    def _create_placeholder_icon(self, emoji: str, media_type: MediaType) -> QPixmap:
        """Create a placeholder icon pixmap.
        
        Args:
            emoji: The emoji to display (not used, we use colored squares).
            media_type: The media type for color coding.
            
        Returns:
            A QPixmap placeholder.
        """
        from PySide6.QtGui import QPainter, QColor, QFont
        
        # Color by media type
        color_map = {
            MediaType.VIDEO: QColor("#4a90d9"),  # Blue
            MediaType.AUDIO: QColor("#9b59b6"),  # Purple
            MediaType.IMAGE: QColor("#27ae60"),  # Green
            MediaType.DOCUMENT: QColor("#f39c12"),  # Orange
            MediaType.OTHER: QColor("#7f8c8d"),  # Gray
        }
        
        pixmap = QPixmap(self._list_thumbnail_size, self._list_thumbnail_size)
        pixmap.fill(color_map.get(media_type, QColor("#7f8c8d")))
        
        # Draw a simple icon letter
        painter = QPainter(pixmap)
        painter.setPen(QColor("white"))
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        painter.setFont(font)
        
        # First letter of media type
        letter = media_type.value[0].upper() if media_type else "?"
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, letter)
        painter.end()
        
        return pixmap
    
    def _update_status(self) -> None:
        """Update the status label and pagination controls."""
        count = len(self._assets)
        if self._total_items > 0:
            self._status_label.setText(f"Showing {count} of {self._total_items} asset{'s' if self._total_items != 1 else ''}")
        else:
            self._status_label.setText(f"{count} asset{'s' if count != 1 else ''}")
        
        # Update pagination controls
        self._update_pagination_controls()
    
    def _update_pagination_controls(self) -> None:
        """Update pagination button states and page label."""
        self._page_label.setText(f"Page {self._current_page} of {self._total_pages}")
        self._prev_button.setEnabled(self._current_page > 1)
        self._next_button.setEnabled(self._current_page < self._total_pages)
    
    def set_pagination_info(self, current_page: int, total_pages: int, total_items: int) -> None:
        """Set pagination information from search results.
        
        Args:
            current_page: Current page number (1-based).
            total_pages: Total number of pages.
            total_items: Total number of items across all pages.
        """
        self._current_page = current_page
        self._total_pages = total_pages
        self._total_items = total_items
        self._update_status()
    
    def get_page_size(self) -> int:
        """Get the current page size setting.
        
        Returns:
            Current page size.
        """
        return self._page_size
    
    def _on_page_size_changed(self, text: str) -> None:
        """Handle page size combo box change."""
        try:
            new_size = int(text)
            if new_size != self._page_size:
                self._page_size = new_size
                self._current_page = 1  # Reset to first page
                self.page_size_changed.emit(new_size)
        except ValueError:
            pass
    
    def _on_prev_page(self) -> None:
        """Handle previous page button click."""
        if self._current_page > 1:
            self._current_page -= 1
            self.page_changed.emit(self._current_page)
    
    def _on_next_page(self) -> None:
        """Handle next page button click."""
        if self._current_page < self._total_pages:
            self._current_page += 1
            self.page_changed.emit(self._current_page)
    
    def _update_selection_info(self) -> None:
        """Update the selection label."""
        count = len(self._selected_assets)
        self._selection_label.setText(f"{count} selected")
    
    def _on_thumbnail_clicked(self, asset: Asset, event) -> None:
        """Handle thumbnail click with multi-select support.
        
        - Normal click: Select only this asset (clear others)
        - Ctrl/Cmd + click: Toggle this asset's selection
        - Shift + click: Select range from last clicked to this asset
        """
        modifiers = event.modifiers() if event else Qt.KeyboardModifier.NoModifier
        
        ctrl_pressed = modifiers & Qt.KeyboardModifier.ControlModifier
        # On macOS, Cmd key is MetaModifier
        cmd_pressed = modifiers & Qt.KeyboardModifier.MetaModifier
        shift_pressed = modifiers & Qt.KeyboardModifier.ShiftModifier
        
        if shift_pressed and self._last_clicked_asset_id:
            # Range select
            self._select_range(self._last_clicked_asset_id, asset.asset_id)
        elif ctrl_pressed or cmd_pressed:
            # Toggle selection
            self._toggle_selection(asset)
        else:
            # Normal click - select only this asset
            self._select_single(asset)
        
        self._last_clicked_asset_id = asset.asset_id
        self._update_selection_info()
        self.selection_changed.emit(self.get_selected_assets())
        self.asset_selected.emit(asset)
    
    def _select_single(self, asset: Asset) -> None:
        """Select only one asset, deselecting others."""
        # Deselect all
        for asset_id in list(self._selected_assets):
            if asset_id in self._thumbnail_widgets:
                self._thumbnail_widgets[asset_id].is_selected = False
        self._selected_assets.clear()
        
        # Select this asset
        self._selected_assets.add(asset.asset_id)
        if asset.asset_id in self._thumbnail_widgets:
            self._thumbnail_widgets[asset.asset_id].is_selected = True
    
    def _toggle_selection(self, asset: Asset) -> None:
        """Toggle selection of an asset."""
        if asset.asset_id in self._selected_assets:
            self._selected_assets.discard(asset.asset_id)
            if asset.asset_id in self._thumbnail_widgets:
                self._thumbnail_widgets[asset.asset_id].is_selected = False
        else:
            self._selected_assets.add(asset.asset_id)
            if asset.asset_id in self._thumbnail_widgets:
                self._thumbnail_widgets[asset.asset_id].is_selected = True
    
    def _select_range(self, from_asset_id: str, to_asset_id: str) -> None:
        """Select a range of assets."""
        # Find indices
        from_idx = None
        to_idx = None
        
        for i, asset in enumerate(self._assets):
            if asset.asset_id == from_asset_id:
                from_idx = i
            if asset.asset_id == to_asset_id:
                to_idx = i
        
        if from_idx is None or to_idx is None:
            return
        
        # Ensure from_idx < to_idx
        start_idx = min(from_idx, to_idx)
        end_idx = max(from_idx, to_idx)
        
        # Select all assets in range
        for i in range(start_idx, end_idx + 1):
            asset = self._assets[i]
            self._selected_assets.add(asset.asset_id)
            if asset.asset_id in self._thumbnail_widgets:
                self._thumbnail_widgets[asset.asset_id].is_selected = True
    
    def _on_thumbnail_double_clicked(self, asset: Asset) -> None:
        """Handle thumbnail double-click."""
        self.asset_double_clicked.emit(asset)
    
    def _on_thumbnail_selection_changed(self, asset: Asset, selected: bool) -> None:
        """Handle thumbnail selection change."""
        if selected:
            self._selected_assets.add(asset.asset_id)
        else:
            self._selected_assets.discard(asset.asset_id)
        
        self._update_selection_info()
        self.selection_changed.emit(self.get_selected_assets())
    
    def _on_list_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle list item click."""
        asset = item.data(Qt.ItemDataRole.UserRole)
        if asset:
            self.asset_selected.emit(asset)
    
    def _on_list_selection_changed(self) -> None:
        """Handle list selection changed - sync with shared selection state."""
        # Update _selected_assets based on list selection
        self._selected_assets.clear()
        for item in self._list_widget.selectedItems():
            asset = item.data(Qt.ItemDataRole.UserRole)
            if asset:
                self._selected_assets.add(asset.asset_id)
        
        # Also update grid view widgets to stay in sync
        for asset_id, widget in self._thumbnail_widgets.items():
            widget._checkbox.blockSignals(True)
            widget.is_selected = asset_id in self._selected_assets
            widget._checkbox.blockSignals(False)
        
        self._update_selection_info()
        self.selection_changed.emit(self.get_selected_assets())
    
    def _on_list_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle list item double-click."""
        asset = item.data(Qt.ItemDataRole.UserRole)
        if asset:
            self.asset_double_clicked.emit(asset)
    
    def _on_scroll(self, value: int) -> None:
        """Handle scroll for infinite loading."""
        scrollbar = self._grid_scroll.verticalScrollBar()
        if scrollbar.maximum() - value < 100:
            self.load_more_requested.emit()
    
    def resizeEvent(self, event) -> None:
        """Handle resize to reflow grid."""
        super().resizeEvent(event)
        if self._current_view == "grid" and self._assets:
            # Reflow grid on resize
            QTimer.singleShot(100, self._reflow_grid)
    
    def _reflow_grid(self) -> None:
        """Reflow the grid layout based on current width."""
        thumbnail_size = self._config.thumbnail_size
        available_width = self._grid_scroll.viewport().width() - 24
        cols = max(1, available_width // (thumbnail_size + 24))
        
        # Reposition all widgets
        widgets = list(self._thumbnail_widgets.values())
        for i, widget in enumerate(widgets):
            row = i // cols
            col = i % cols
            self._grid_layout.addWidget(widget, row, col)
