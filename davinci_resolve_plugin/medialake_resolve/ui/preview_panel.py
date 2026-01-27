"""Preview panel for video playback and asset details."""

from typing import Optional, Any
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QFrame,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
)
from PySide6.QtCore import Qt, Signal, QUrl, QTimer
from PySide6.QtGui import QPixmap, QImage

from medialake_resolve.core.models import Asset, MediaType

# QtMultimedia is optional - video preview will be disabled if not available
MULTIMEDIA_AVAILABLE = False

try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PySide6.QtMultimediaWidgets import QVideoWidget
    MULTIMEDIA_AVAILABLE = True
except ImportError:
    QMediaPlayer = None
    QAudioOutput = None
    QVideoWidget = None


class VideoPreviewPlaceholder(QWidget):
    """Placeholder widget shown when QtMultimedia is not available."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize placeholder widget."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        label = QLabel("Video preview not available.\n\nPySide6-Multimedia is not installed.\nThumbnails will be shown instead.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: gray; font-size: 12px;")
        label.setWordWrap(True)
        layout.addWidget(label)
    
    def load_url(self, url: str) -> None:
        """No-op for compatibility."""
        pass
    
    def load_file(self, file_path: str) -> None:
        """No-op for compatibility."""
        pass
    
    def play(self) -> None:
        """No-op for compatibility."""
        pass
    
    def pause(self) -> None:
        """No-op for compatibility."""
        pass
    
    def stop(self) -> None:
        """No-op for compatibility."""
        pass


if MULTIMEDIA_AVAILABLE:
    class VideoPreviewWidget(QWidget):
        """Widget for video preview with playback controls."""
        
        def __init__(self, parent: Optional[QWidget] = None):
            """Initialize video preview widget.
            
            Args:
                parent: Parent widget.
            """
            super().__init__(parent)
            
            self._player: Optional[Any] = None
            self._audio_output: Optional[Any] = None
            self._duration_ms = 0
            
            self._setup_ui()
            self._setup_player()
        
        def _setup_ui(self) -> None:
            """Set up the widget UI."""
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            
            # Video display
            self._video_widget = QVideoWidget()
            self._video_widget.setMinimumSize(320, 180)
            self._video_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            layout.addWidget(self._video_widget, 1)
            
            # Controls
            controls_layout = QHBoxLayout()
            controls_layout.setContentsMargins(8, 4, 8, 4)
            
            # Play/pause button
            self._play_button = QPushButton("▶")
            self._play_button.setFixedWidth(40)
            self._play_button.clicked.connect(self._toggle_playback)
            controls_layout.addWidget(self._play_button)
            
            # Time label
            self._time_label = QLabel("0:00 / 0:00")
            self._time_label.setMinimumWidth(100)
            controls_layout.addWidget(self._time_label)
            
            # Seek slider
            self._seek_slider = QSlider(Qt.Orientation.Horizontal)
            self._seek_slider.setRange(0, 1000)
            self._seek_slider.sliderMoved.connect(self._on_seek)
            self._seek_slider.sliderPressed.connect(self._on_seek_start)
            self._seek_slider.sliderReleased.connect(self._on_seek_end)
            controls_layout.addWidget(self._seek_slider, 1)
            
            # Volume slider
            self._volume_slider = QSlider(Qt.Orientation.Horizontal)
            self._volume_slider.setRange(0, 100)
            self._volume_slider.setValue(80)
            self._volume_slider.setFixedWidth(80)
            self._volume_slider.valueChanged.connect(self._on_volume_changed)
            controls_layout.addWidget(QLabel("🔊"))
            controls_layout.addWidget(self._volume_slider)
            
            layout.addLayout(controls_layout)
            
            self._seeking = False
        
        def _setup_player(self) -> None:
            """Set up the media player."""
            self._player = QMediaPlayer()
            self._audio_output = QAudioOutput()
            self._player.setAudioOutput(self._audio_output)
            self._player.setVideoOutput(self._video_widget)
            
            # Set initial volume
            self._audio_output.setVolume(0.8)
            
            # Connect signals
            self._player.playbackStateChanged.connect(self._on_playback_state_changed)
            self._player.positionChanged.connect(self._on_position_changed)
            self._player.durationChanged.connect(self._on_duration_changed)
            self._player.errorOccurred.connect(self._on_error)
        
        def load_url(self, url: str) -> None:
            """Load video from URL.
            
            Args:
                url: URL to the video file.
            """
            if self._player:
                self._player.setSource(QUrl(url))
        
        def load_file(self, file_path: str) -> None:
            """Load video from file.
            
            Args:
                file_path: Path to the video file.
            """
            if self._player:
                self._player.setSource(QUrl.fromLocalFile(file_path))
        
        def play(self) -> None:
            """Start playback."""
            if self._player:
                self._player.play()
        
        def pause(self) -> None:
            """Pause playback."""
            if self._player:
                self._player.pause()
        
        def stop(self) -> None:
            """Stop playback."""
            if self._player:
                self._player.stop()
        
        def _toggle_playback(self) -> None:
            """Toggle play/pause."""
            if not self._player:
                return
            
            if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._player.pause()
            else:
                self._player.play()
        
        def _on_playback_state_changed(self, state) -> None:
            """Handle playback state change."""
            if state == QMediaPlayer.PlaybackState.PlayingState:
                self._play_button.setText("⏸")
            else:
                self._play_button.setText("▶")
        
        def _on_position_changed(self, position: int) -> None:
            """Handle position change."""
            if not self._seeking and self._duration_ms > 0:
                slider_pos = int((position / self._duration_ms) * 1000)
                self._seek_slider.setValue(slider_pos)
            
            self._update_time_label(position, self._duration_ms)
        
        def _on_duration_changed(self, duration: int) -> None:
            """Handle duration change."""
            self._duration_ms = duration
            self._update_time_label(0, duration)
        
        def _update_time_label(self, position_ms: int, duration_ms: int) -> None:
            """Update the time label."""
            pos_str = self._format_time(position_ms)
            dur_str = self._format_time(duration_ms)
            self._time_label.setText(f"{pos_str} / {dur_str}")
        
        @staticmethod
        def _format_time(ms: int) -> str:
            """Format milliseconds as mm:ss."""
            seconds = ms // 1000
            minutes = seconds // 60
            seconds = seconds % 60
            return f"{minutes}:{seconds:02d}"
        
        def _on_seek_start(self) -> None:
            """Handle seek start."""
            self._seeking = True
        
        def _on_seek_end(self) -> None:
            """Handle seek end."""
            self._seeking = False
        
        def _on_seek(self, value: int) -> None:
            """Handle seek slider change."""
            if self._player and self._duration_ms > 0:
                position = int((value / 1000) * self._duration_ms)
                self._player.setPosition(position)
        
        def _on_volume_changed(self, value: int) -> None:
            """Handle volume change."""
            if self._audio_output:
                self._audio_output.setVolume(value / 100)
        
        def _on_error(self, error, message: str) -> None:
            """Handle player error."""
            print(f"Player error: {error} - {message}")
else:
    # Use placeholder when QtMultimedia is not available
    VideoPreviewWidget = VideoPreviewPlaceholder


class PreviewPanel(QWidget):
    """Panel for showing asset preview and details.
    
    Signals:
        download_requested: Emitted when download is requested. (asset, variant)
    """
    
    download_requested = Signal(Asset, str)
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize preview panel.
        
        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        
        self._current_asset: Optional[Asset] = None
        self._video_preview_available = MULTIMEDIA_AVAILABLE
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Preview area (stacked for video/image/placeholder)
        self._preview_stack = QStackedWidget()
        
        # Placeholder
        placeholder = QLabel("Select an asset to preview")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: gray; font-size: 14px;")
        self._preview_stack.addWidget(placeholder)
        
        # Video preview (or placeholder if not available)
        self._video_preview = VideoPreviewWidget()
        self._preview_stack.addWidget(self._video_preview)
        
        # Image preview
        self._image_preview = QLabel()
        self._image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_preview.setScaledContents(False)
        self._preview_stack.addWidget(self._image_preview)
        
        # Limit preview area height to leave more room for details
        self._preview_stack.setMaximumHeight(250)
        layout.addWidget(self._preview_stack)
        
        # Details section
        details_frame = QFrame()
        details_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(8, 8, 8, 8)
        details_layout.setSpacing(4)
        
        # Asset name
        self._name_label = QLabel("")
        font = self._name_label.font()
        font.setPointSize(14)
        font.setBold(True)
        self._name_label.setFont(font)
        self._name_label.setWordWrap(True)
        details_layout.addWidget(self._name_label)
        
        # Details scroll area
        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        
        self._details_content = QLabel("")
        self._details_content.setWordWrap(True)
        self._details_content.setAlignment(Qt.AlignmentFlag.AlignTop)
        details_scroll.setWidget(self._details_content)
        details_layout.addWidget(details_scroll, 1)  # Give it stretch to expand
        
        # Add spacing between info and buttons
        details_layout.addSpacing(16)
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        
        self._download_button = QPushButton("Download Original")
        self._download_button.clicked.connect(self._on_download_original)
        self._download_button.setEnabled(False)
        buttons_layout.addWidget(self._download_button)
        
        self._download_proxy_button = QPushButton("Download Proxy")
        self._download_proxy_button.clicked.connect(self._on_download_proxy)
        self._download_proxy_button.setEnabled(False)
        buttons_layout.addWidget(self._download_proxy_button)
        
        details_layout.addLayout(buttons_layout)
        
        layout.addWidget(details_frame)
    
    def set_asset(self, asset: Asset) -> None:
        """Set the asset to preview.
        
        Args:
            asset: The asset to display.
        """
        self._current_asset = asset
        
        # Stop any playing video
        self._video_preview.stop()
        
        # Update name
        self._name_label.setText(asset.name)
        
        # Update details
        details = self._format_details(asset)
        self._details_content.setText(details)
        
        # Enable download buttons
        self._download_button.setEnabled(True)
        self._download_proxy_button.setEnabled(asset.has_proxy)
        
        # Default to image preview (will show thumbnail)
        # Video will play if we have a preview URL and multimedia is available
        self._preview_stack.setCurrentWidget(self._image_preview)
        self._image_preview.setText("Loading preview...")
        
        # Set preview based on media type
        if asset.media_type == MediaType.VIDEO:
            if self._video_preview_available and (asset.preview_url or asset.proxy_url):
                self._preview_stack.setCurrentWidget(self._video_preview)
                url = asset.preview_url or asset.proxy_url
                if url:
                    self._video_preview.load_url(url)
            # Otherwise stay on image preview to show thumbnail
        elif asset.media_type == MediaType.IMAGE:
            self._preview_stack.setCurrentWidget(self._image_preview)
            # Image will be set via set_preview_image
        else:
            self._preview_stack.setCurrentIndex(0)  # Placeholder
    
    def set_preview_image(self, image_data: bytes) -> None:
        """Set the preview image.
        
        Args:
            image_data: Raw image bytes.
        """
        image = QImage()
        if image.loadFromData(image_data):
            pixmap = QPixmap.fromImage(image)
            # Scale to fit while maintaining aspect ratio
            scaled = pixmap.scaled(
                self._image_preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._image_preview.setPixmap(scaled)
    
    def clear(self) -> None:
        """Clear the preview."""
        self._current_asset = None
        self._video_preview.stop()
        self._name_label.setText("")
        self._details_content.setText("")
        self._download_button.setEnabled(False)
        self._download_proxy_button.setEnabled(False)
        self._preview_stack.setCurrentIndex(0)
    
    def _format_details(self, asset: Asset) -> str:
        """Format asset details as text.
        
        Args:
            asset: The asset.
            
        Returns:
            Formatted details string.
        """
        lines = []
        
        lines.append(f"<b>Type:</b> {asset.media_type.value.title()}")
        lines.append(f"<b>Size:</b> {asset.display_size}")
        
        if asset.resolution:
            lines.append(f"<b>Resolution:</b> {asset.resolution}")
        
        if asset.duration:
            lines.append(f"<b>Duration:</b> {asset.display_duration}")
        
        if asset.frame_rate:
            lines.append(f"<b>Frame Rate:</b> {asset.frame_rate} fps")
        
        if asset.codec:
            lines.append(f"<b>Codec:</b> {asset.codec}")
        
        lines.append(f"<b>Format:</b> {asset.file_extension.upper()}")
        
        if asset.has_proxy:
            proxy_size = asset.proxy_file_size or 0
            for unit in ["B", "KB", "MB", "GB"]:
                if proxy_size < 1024:
                    lines.append(f"<b>Proxy Size:</b> {proxy_size:.1f} {unit}")
                    break
                proxy_size /= 1024
        
        if asset.created_at:
            lines.append(f"<b>Created:</b> {asset.created_at.strftime('%Y-%m-%d %H:%M')}")
        
        if asset.tags:
            lines.append(f"<b>Tags:</b> {', '.join(asset.tags)}")
        
        return "<br>".join(lines)
    
    def _on_download_original(self) -> None:
        """Handle download original button."""
        if self._current_asset:
            self.download_requested.emit(self._current_asset, "original")
    
    def _on_download_proxy(self) -> None:
        """Handle download proxy button."""
        if self._current_asset:
            self.download_requested.emit(self._current_asset, "proxy")
