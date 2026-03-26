"""Search panel with keyword and semantic search support."""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QCheckBox,
    QCompleter,
    QSlider,
    QProgressBar,
)
from PySide6.QtCore import Qt, Signal, QStringListModel, QTimer, QPropertyAnimation, Property
from PySide6.QtGui import QIcon, QPainter, QColor, QPen

from medialake_resolve.core.config import Config


class SearchPanel(QWidget):
    """Search panel for Media Lake assets.
    
    Features:
    - Search input with history/autocomplete
    - Toggle between keyword and semantic search
    
    Signals:
        search_requested: Emitted when search is triggered. (query, search_type)
    """
    
    search_requested = Signal(str, str)  # query, search_type
    
    def __init__(self, config: Config, parent: Optional[QWidget] = None):
        """Initialize search panel.
        
        Args:
            config: Application configuration.
            parent: Parent widget.
        """
        super().__init__(parent)
        
        self._config = config
        
        # Create a timer for debouncing slider changes
        self._confidence_timer = QTimer(self)
        self._confidence_timer.setSingleShot(True)
        self._confidence_timer.timeout.connect(self._trigger_search_after_slider)
        
        self._setup_ui()
        self._load_search_history()
    
    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Search row
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        
        # Search input
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search assets...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.returnPressed.connect(self._on_search)
        search_row.addWidget(self._search_input, 1)
        
        # Confidence threshold slider (only visible when semantic search is enabled)
        confidence_layout = QHBoxLayout()
        confidence_layout.setSpacing(4)
        
        self._confidence_label = QLabel("Confidence:")
        self._confidence_label.setToolTip("Minimum confidence score for semantic search results (0.0-1.0)")
        confidence_layout.addWidget(self._confidence_label)
        
        self._confidence_slider = QSlider(Qt.Orientation.Horizontal)
        self._confidence_slider.setMinimum(0)
        self._confidence_slider.setMaximum(100)
        self._confidence_slider.setValue(int(self._config.confidence_threshold * 100))
        self._confidence_slider.setFixedWidth(100)
        self._confidence_slider.setToolTip(f"Current threshold: {self._config.confidence_threshold:.2f}")
        self._confidence_slider.valueChanged.connect(self._on_confidence_changed)
        confidence_layout.addWidget(self._confidence_slider)
        
        self._confidence_value_label = QLabel(f"{self._config.confidence_threshold:.2f}")
        self._confidence_value_label.setFixedWidth(30)
        confidence_layout.addWidget(self._confidence_value_label)
        
        search_row.addLayout(confidence_layout)
        
        # Search type toggle
        self._semantic_checkbox = QCheckBox("Semantic")
        self._semantic_checkbox.setToolTip("Use AI-powered semantic search")
        self._semantic_checkbox.setChecked(True)  # Semantic search is default
        self._semantic_checkbox.toggled.connect(self._on_semantic_toggled)
        search_row.addWidget(self._semantic_checkbox)
        
        # Search button
        self._search_button = QPushButton("Search")
        self._search_button.clicked.connect(self._on_search)
        search_row.addWidget(self._search_button)
        
        layout.addLayout(search_row)
        
        # Setup search history completer
        self._history_model = QStringListModel(self)
        self._completer = QCompleter(self._history_model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._search_input.setCompleter(self._completer)
        
        # Initialize confidence threshold controls visibility based on semantic search state
        is_semantic = self._semantic_checkbox.isChecked()
        self._confidence_label.setVisible(is_semantic)
        self._confidence_slider.setVisible(is_semantic)
        self._confidence_value_label.setVisible(is_semantic)
    
    def _load_search_history(self) -> None:
        """Load search history from config."""
        self._history_model.setStringList(self._config.search_history)
    
    def get_current_query(self) -> str:
        """Get the current search query.
        
        Returns:
            The search query string.
        """
        return self._search_input.text().strip()
    
    def get_search_type(self) -> str:
        """Get the current search type.
        
        Returns:
            "keyword" or "semantic".
        """
        return "semantic" if self._semantic_checkbox.isChecked() else "keyword"
    
    def set_search_query(self, query: str) -> None:
        """Set the search query.
        
        Args:
            query: The search query to set.
        """
        self._search_input.setText(query)
    
    def _on_search(self) -> None:
        """Handle search triggered."""
        query = self.get_current_query()
        
        # Add to search history
        if query:
            self._config.add_to_search_history(query)
            self._load_search_history()
        
        # Show loading indicator
        self.set_loading(True)
        
        # Emit search signal
        self.search_requested.emit(
            query,
            self.get_search_type(),
        )
    
    def set_loading(self, loading: bool) -> None:
        """Update search button state during loading.
        
        Args:
            loading: True when search is in progress, False when complete.
        """
        self._search_button.setEnabled(not loading)
        if loading:
            self._search_button.setText("Searching...")
        else:
            self._search_button.setText("Search")
    
    def clear_search(self) -> None:
        """Clear the search input."""
        self._search_input.clear()
    
    def focus_search(self) -> None:
        """Focus the search input."""
        self._search_input.setFocus()
        self._search_input.selectAll()
    
    def _on_confidence_changed(self, value: int) -> None:
        """Handle confidence threshold slider change.
        
        Args:
            value: Slider value (0-100).
        """
        # Convert slider value (0-100) to confidence threshold (0.0-1.0)
        threshold = value / 100.0
        
        # Update the label
        self._confidence_value_label.setText(f"{threshold:.2f}")
        
        # Update tooltip
        self._confidence_slider.setToolTip(f"Current threshold: {threshold:.2f}")
        
        # Update config
        self._config.confidence_threshold = threshold
        self._config.save()
        
        # Only trigger a new search if we're using semantic search and have a query
        if self._semantic_checkbox.isChecked() and self.get_current_query():
            # Start/restart the timer to debounce rapid slider changes
            self._confidence_timer.start(300)  # 300ms delay
    
    def _trigger_search_after_slider(self) -> None:
        """Trigger a search after the slider movement has stopped."""
        if self._semantic_checkbox.isChecked() and self.get_current_query():
            self._on_search()
    
    def _on_semantic_toggled(self, checked: bool) -> None:
        """Handle semantic checkbox toggle.
        
        Args:
            checked: Whether semantic search is enabled.
        """
        # Show/hide confidence threshold controls based on semantic search state
        self._confidence_label.setVisible(checked)
        self._confidence_slider.setVisible(checked)
        self._confidence_value_label.setVisible(checked)
