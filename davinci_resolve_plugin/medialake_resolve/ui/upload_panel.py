"""Upload panel for Media Lake Resolve Plugin."""

import os
import sys
import subprocess
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QProgressBar,
    QFrame,
    QScrollArea,
    QListWidget,
    QListWidgetItem,
    QFileIconProvider,
)
from PySide6.QtCore import Qt, Signal, QMimeData, QSize, QFileInfo
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPainter, QColor, QPen, QDragMoveEvent, QIcon, QPixmap

from medialake_resolve.core.config import Config
from medialake_resolve.resolve.connection import ResolveConnection

class DropArea(QFrame):
    """Drag and drop area for files.
    
    Supports drag and drop from:
    - Standard file managers (URLs)
    - DaVinci Resolve Media Pool (various MIME types)
    - Text-based file paths
    """
    
    files_dropped = Signal(list)  # List of file paths
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize drop area."""
        super().__init__(parent)
        
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setMinimumSize(200, 150)
        self.setStyleSheet("""
            DropArea {
                background-color: #2b2b2b;
                border: 2px dashed #555555;
                border-radius: 5px;
            }
        """)
        
        # Layout
        layout = QVBoxLayout(self)
        
        # Label for empty state
        self._label = QLabel("Drag files here or use 'Add Selected from Media Pool' button")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 12px;
                padding: 20px;
            }
        """)
        layout.addWidget(self._label)
        
        # File list widget (hidden initially)
        self._file_list = QListWidget()
        self._file_list.setVisible(False)
        self._file_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                color: #cccccc;
                border: none;
                border-radius: 3px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3a3a3a;
                border-radius: 3px;
            }
            QListWidget::item:hover {
                background-color: #2d2d2d;
            }
            QListWidget::item:selected {
                background-color: #3a3a3a;
            }
        """)
        layout.addWidget(self._file_list)
        
        # Store dropped files for later use
        self._dropped_files: List[str] = []
    
    def _debug_mime_data(self, mime_data: QMimeData, event_type: str) -> None:
        """Debug helper to log all MIME data formats."""
        print(f"\n=== {event_type} MIME Data Debug ===")
        print(f"  Available formats: {mime_data.formats()}")
        print(f"  hasUrls: {mime_data.hasUrls()}")
        print(f"  hasText: {mime_data.hasText()}")
        print(f"  hasHtml: {mime_data.hasHtml()}")
        
        if mime_data.hasUrls():
            urls = mime_data.urls()
            print(f"  URLs ({len(urls)}):")
            for url in urls[:5]:  # Limit to first 5
                print(f"    - {url.toString()}")
                print(f"      Local file: {url.toLocalFile()}")
        
        if mime_data.hasText():
            text = mime_data.text()
            print(f"  Text (first 500 chars): {text[:500]}")
        
        # Check for common DaVinci Resolve MIME types
        resolve_formats = [
            "application/x-qt-windows-mime;value=\"DaVinci Resolve\"",
            "application/x-davinci-resolve",
            "application/x-bmd-mediapool",
            "text/uri-list",
            "text/plain",
            "application/x-qt-image",
        ]
        
        for fmt in mime_data.formats():
            if fmt not in ["text/plain", "text/uri-list"]:
                data = mime_data.data(fmt)
                if data and data.size() > 0:
                    try:
                        decoded = bytes(data.data()).decode('utf-8', errors='replace')
                        print(f"  Format '{fmt}': {decoded[:200]}")
                    except:
                        print(f"  Format '{fmt}': [binary data, {data.size()} bytes]")
        
        print("=== End MIME Debug ===\n")
    
    def _get_resolve_selected_clips(self) -> List[str]:
        """Get file paths from currently selected clips in Resolve Media Pool.
        
        Returns:
            List of file paths from selected media pool items.
        """
        file_paths = []
        
        try:
            resolve_conn = ResolveConnection()
            if not resolve_conn.is_connected:
                resolve_conn.connect()
            
            media_pool = resolve_conn.get_media_pool()
            if not media_pool:
                print("  Could not access Media Pool")
                return file_paths
            
            # Get currently selected clips in the media pool
            selected_clips = media_pool.GetSelectedClips()
            
            if not selected_clips:
                print("  No clips selected in Media Pool")
                return file_paths
            
            print(f"  Found {len(selected_clips)} selected clips in Media Pool")
            
            # Extract file paths from each clip
            for clip in selected_clips:
                try:
                    # Get the clip's file path
                    clip_property = clip.GetClipProperty()
                    if clip_property and "File Path" in clip_property:
                        file_path = clip_property["File Path"]
                        if file_path and os.path.isfile(file_path):
                            file_paths.append(file_path)
                            print(f"    Added: {file_path}")
                        else:
                            print(f"    Invalid path: {file_path}")
                except Exception as e:
                    print(f"    Error getting clip property: {e}")
                    
        except Exception as e:
            print(f"  Error accessing Resolve API: {e}")
        
        return file_paths
    
    def _extract_file_paths(self, mime_data: QMimeData) -> List[str]:
        """Extract file paths from MIME data.
        
        Handles multiple formats that DaVinci Resolve and other apps may use.
        """
        file_paths = []
        
        # Method 1: Standard URLs (most common - works for Finder/Explorer)
        if mime_data.hasUrls():
            for url in mime_data.urls():
                local_file = url.toLocalFile()
                if local_file:
                    file_paths.append(local_file)
        
        # Method 2: text/uri-list format
        if mime_data.hasFormat("text/uri-list"):
            uri_data = mime_data.data("text/uri-list")
            if uri_data and uri_data.size() > 0:
                try:
                    uri_text = bytes(uri_data.data()).decode('utf-8')
                    from urllib.parse import unquote, urlparse
                    for line in uri_text.strip().split('\n'):
                        line = line.strip()
                        if line and not line.startswith('#'):
                            if line.startswith('file://'):
                                # Parse file URL
                                parsed = urlparse(line)
                                path = unquote(parsed.path)
                                # Handle Windows paths (file:///C:/...)
                                if path.startswith('/') and len(path) > 2 and path[2] == ':':
                                    path = path[1:]  # Remove leading /
                                if path and path not in file_paths:
                                    file_paths.append(path)
                except Exception as e:
                    print(f"  Error parsing text/uri-list: {e}")
        
        # Method 3: Plain text (may contain file paths)
        if mime_data.hasText():
            text = mime_data.text()
            if text:
                from urllib.parse import unquote, urlparse
                
                # Try to parse as file URLs or paths
                for line in text.strip().split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    
                    if line.startswith('file://'):
                        # Parse file URL
                        try:
                            parsed = urlparse(line)
                            path = unquote(parsed.path)
                            # Handle Windows paths
                            if path.startswith('/') and len(path) > 2 and path[2] == ':':
                                path = path[1:]
                            if path and path not in file_paths:
                                file_paths.append(path)
                        except:
                            pass
                    elif os.path.isabs(line) or line.startswith('/') or (len(line) > 1 and line[1] == ':'):
                        # Looks like an absolute path
                        if line not in file_paths:
                            file_paths.append(line)
        
        # Method 4: Check for DaVinci Resolve specific formats
        # Resolve may use custom MIME types
        for fmt in mime_data.formats():
            if 'resolve' in fmt.lower() or 'bmd' in fmt.lower() or 'davinci' in fmt.lower():
                data = mime_data.data(fmt)
                if data and data.size() > 0:
                    try:
                        decoded = bytes(data.data()).decode('utf-8')
                        # Try to extract file paths from the data
                        from urllib.parse import unquote
                        for line in decoded.split('\n'):
                            line = line.strip()
                            if line.startswith('file://'):
                                path = unquote(line[7:])
                                if path and path not in file_paths:
                                    file_paths.append(path)
                            elif os.path.isabs(line):
                                if line not in file_paths:
                                    file_paths.append(line)
                    except:
                        pass
        
        # Method 5: If no file paths found and we detect Resolve-specific formats,
        # try to get selected clips from Resolve Media Pool via API
        if not file_paths:
            resolve_formats = [fmt for fmt in mime_data.formats()
                             if 'resolve' in fmt.lower() or 'bmd' in fmt.lower()
                             or 'davinci' in fmt.lower() or 'fusion' in fmt.lower()]
            
            if resolve_formats:
                print("  Detected Resolve drag operation, querying Media Pool API...")
                resolve_paths = self._get_resolve_selected_clips()
                if resolve_paths:
                    file_paths.extend(resolve_paths)
        
        return file_paths
    
    def _is_valid_drop(self, mime_data: QMimeData) -> bool:
        """Check if the MIME data contains valid droppable content."""
        # Accept URLs (Finder/Explorer)
        if mime_data.hasUrls():
            return True
        
        # Accept text/uri-list
        if mime_data.hasFormat("text/uri-list"):
            return True
        
        # Accept text that looks like file paths
        if mime_data.hasText():
            text = mime_data.text()
            if text and ("file://" in text or "/" in text or "\\" in text):
                return True
        
        # Accept any DaVinci Resolve specific formats
        # When dragging from Media Pool, Resolve uses custom MIME types
        for fmt in mime_data.formats():
            if 'resolve' in fmt.lower() or 'bmd' in fmt.lower() or 'davinci' in fmt.lower() or 'fusion' in fmt.lower():
                print(f"  Detected Resolve MIME format: {fmt}")
                return True
        
        return False
    
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter event."""
        from datetime import datetime
        f = open("/tmp/medialake_plugin.log", "a")
        f.write(f"{datetime.now()} - dragEnterEvent\n")
        f.close()
        print("Drag Enter Event", file=sys.stderr)
        mime_data = event.mimeData()
        
        # Debug: log all MIME data
        self._debug_mime_data(mime_data, "DragEnter")
        
        if self._is_valid_drop(mime_data):
            event.acceptProposedAction()
            self._highlight_drop_area()
        else:
            event.ignore()
    
    def _highlight_drop_area(self) -> None:
        """Highlight the drop area to indicate valid drop target."""
        self.setStyleSheet("""
            DropArea {
                background-color: #1a3a4a;
                border: 2px dashed #4a90e2;
                border-radius: 5px;
            }
        """)
    
    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Handle drag move event."""
        mime_data = event.mimeData()
        
        if self._is_valid_drop(mime_data):
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dragLeaveEvent(self, event) -> None:
        """Handle drag leave event."""
        self.setStyleSheet("""
            DropArea {
                background-color: #2b2b2b;
                border: 2px dashed #555555;
                border-radius: 5px;
            }
        """)
        event.accept()
    
    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop event."""
        mime_data = event.mimeData()
        
        # Debug: log all MIME data
        self._debug_mime_data(mime_data, "Drop")
        
        if not self._is_valid_drop(mime_data):
            event.ignore()
            self._reset_style()
            return
        
        event.acceptProposedAction()
        
        # Extract file paths from MIME data
        file_paths = self._extract_file_paths(mime_data)
        
        print(f"  Extracted {len(file_paths)} file paths: {file_paths}")
        
        # Filter to only existing files
        valid_paths = []
        for path in file_paths:
            if os.path.isfile(path):
                valid_paths.append(path)
                print(f"  Valid file: {path}")
            else:
                print(f"  File not found: {path}")
        
        if valid_paths:
            self._dropped_files = valid_paths
            self._update_file_preview()
            self.files_dropped.emit(valid_paths)
            print(f"Dropped {len(valid_paths)} valid files")
        else:
            print("No valid files found in drop")
            self._label.setText("No valid files found - try again")
            self._label.setVisible(True)
            self._file_list.setVisible(False)
        
        self._reset_style()
    
    def _reset_style(self) -> None:
        """Reset the drop area style to default."""
        self.setStyleSheet("""
            DropArea {
                background-color: #2b2b2b;
                border: 2px dashed #555555;
                border-radius: 5px;
            }
        """)
    
    def get_dropped_files(self) -> List[str]:
        """Get the list of dropped files."""
        return self._dropped_files
    
    def _update_file_preview(self) -> None:
        """Update the file preview list."""
        self._file_list.clear()
        
        if not self._dropped_files:
            self._label.setVisible(True)
            self._file_list.setVisible(False)
            self._label.setText("Drag files here or use 'Add Selected from Media Pool' button")
            return
        
        # Hide label and show file list
        self._label.setVisible(False)
        self._file_list.setVisible(True)
        
        # Set icon size for better thumbnail display
        self._file_list.setIconSize(QSize(48, 48))
        
        # Add files to list with icons
        for file_path in self._dropped_files:
            filename = os.path.basename(file_path)
            
            # Get file size
            try:
                file_size = os.path.getsize(file_path)
                size_str = self._format_file_size(file_size)
            except:
                size_str = "Unknown size"
            
            # Create list item
            item = QListWidgetItem(f"{filename} ({size_str})")
            
            # Set icon using actual file thumbnail from Finder
            icon = self._get_file_icon(file_path)
            if icon:
                item.setIcon(icon)
            
            # Add tooltip with full path
            item.setToolTip(file_path)
            
            self._file_list.addItem(item)
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    
    def _get_file_icon(self, file_path: str) -> Optional[QIcon]:
        """Get the actual file icon/thumbnail from the system (Finder on macOS).
        
        This uses macOS's NSWorkspace to get the icon that Finder displays,
        which includes content previews for images and videos.
        
        Args:
            file_path: Full path to the file.
            
        Returns:
            QIcon with the system's native file icon/thumbnail.
        """
        try:
            # On macOS, we can use PyObjC to access NSWorkspace which gives us
            # the same icons that Finder uses (including content previews)
            if sys.platform == 'darwin':
                try:
                    from AppKit import NSWorkspace, NSImage
                    from Foundation import NSURL
                    
                    # Get the icon from NSWorkspace (same as Finder uses)
                    workspace = NSWorkspace.sharedWorkspace()
                    file_url = NSURL.fileURLWithPath_(file_path)
                    ns_image = workspace.iconForFile_(file_path)
                    
                    if ns_image:
                        # Get the image representation data
                        tiff_data = ns_image.TIFFRepresentation()
                        if tiff_data:
                            # Convert NSData to bytes
                            data_bytes = tiff_data.bytes().tobytes()
                            
                            # Load into QPixmap
                            pixmap = QPixmap()
                            pixmap.loadFromData(data_bytes)
                            
                            if not pixmap.isNull():
                                return QIcon(pixmap)
                except ImportError:
                    print("PyObjC not available, falling back to QFileIconProvider")
                except Exception as e:
                    print(f"Error using NSWorkspace for {file_path}: {e}")
            
            # Fallback: Use QFileIconProvider (works on all platforms)
            icon_provider = QFileIconProvider()
            file_info = QFileInfo(file_path)
            icon = icon_provider.icon(file_info)
            
            if not icon.isNull():
                return icon
                
        except Exception as e:
            print(f"Error getting file icon for {file_path}: {e}")
        
        # Final fallback to generic file icon
        from PySide6.QtWidgets import QStyle
        style = self.style()
        return style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)
    
    def clear_dropped_files(self) -> None:
        """Clear the list of dropped files."""
        self._dropped_files = []
        self._update_file_preview()


class UploadPanel(QWidget):
    """Panel for uploading files to Media Lake."""
    
    upload_requested = Signal(list, str)  # file_paths, bucket_name
    bucket_refresh_requested = Signal()
    
    def __init__(self, config: Config, parent: Optional[QWidget] = None):
        """Initialize upload panel.
        
        Args:
            config: Application configuration.
            parent: Parent widget.
        """
        super().__init__(parent)
        
        self._config = config
        
        # Setup UI
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel("Upload to Media Lake")
        header_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Bucket selection
        bucket_layout = QHBoxLayout()
        bucket_label = QLabel("Destination Bucket:")
        self._bucket_combo = QComboBox()
        self._bucket_combo.setMinimumWidth(200)
        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.clicked.connect(self.bucket_refresh_requested.emit)
        
        bucket_layout.addWidget(bucket_label)
        bucket_layout.addWidget(self._bucket_combo, 1)
        bucket_layout.addWidget(self._refresh_button)
        layout.addLayout(bucket_layout)
        
        # Drop area
        self._drop_area = DropArea()
        self._drop_area.files_dropped.connect(self._on_files_dropped)
        layout.addWidget(self._drop_area, 1)
        
        # Media Pool selection button
        media_pool_layout = QHBoxLayout()
        media_pool_layout.addStretch()
        self._add_from_media_pool_button = QPushButton("Add Selected from Media Pool")
        self._add_from_media_pool_button.setToolTip("Add currently selected clips from DaVinci Resolve's Media Pool")
        self._add_from_media_pool_button.clicked.connect(self._on_add_from_media_pool)
        media_pool_layout.addWidget(self._add_from_media_pool_button)
        media_pool_layout.addStretch()
        layout.addLayout(media_pool_layout)
        
        # Instructions label
        instructions_label = QLabel(
            "Drag files from Finder/Explorer, or select clips in Media Pool and click the button above"
        )
        instructions_label.setStyleSheet("color: #666; font-style: italic;")
        instructions_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(instructions_label)
        
        # Upload button
        self._upload_button = QPushButton("Upload Selected")
        self._upload_button.setEnabled(False)
        self._upload_button.clicked.connect(self._on_upload_clicked)
        layout.addWidget(self._upload_button)
        
        # Status label
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)
    
    def set_buckets(self, buckets: List[str]) -> None:
        """Set available buckets.
        
        Args:
            buckets: List of bucket names (storageIdentifier values).
        """
        self._bucket_combo.clear()
        for bucket in buckets:
            self._bucket_combo.addItem(bucket, bucket)  # Display name and data are the same
    
    def set_connectors(self, connectors: List[dict]) -> None:
        """Set available connectors for upload.
        
        This populates the dropdown with connector names but stores the
        storageIdentifier (bucket name) as the item data for lookup.
        
        Args:
            connectors: List of connector dicts with 'name', 'storageIdentifier', 'id'.
        """
        self._bucket_combo.clear()
        for connector in connectors:
            name = connector.get("name", "")
            storage_id = connector.get("storageIdentifier", "")
            if name and storage_id:
                # Show the connector name but store storageIdentifier as data
                self._bucket_combo.addItem(f"{name} ({storage_id})", storage_id)
            elif storage_id:
                # Fallback to just showing storageIdentifier
                self._bucket_combo.addItem(storage_id, storage_id)
        
        if self._bucket_combo.count() == 0:
            self._bucket_combo.addItem("No connectors available", "")
    
    def set_selected_files(self, file_paths: List[str]) -> None:
        """Set selected files for upload.
        
        Args:
            file_paths: List of file paths.
        """
        if file_paths:
            self._upload_button.setEnabled(True)
            self._status_label.setText(f"{len(file_paths)} files selected")
        else:
            self._upload_button.setEnabled(False)
            self._status_label.setText("")
    
    def set_status(self, message: str) -> None:
        """Set status message.
        
        Args:
            message: Status message.
        """
        self._status_label.setText(message)
    
    def reset(self) -> None:
        """Reset the panel."""
        self._upload_button.setEnabled(False)
        self._status_label.setText("")
    
    def _on_add_from_media_pool(self) -> None:
        """Handle adding files from Media Pool selection."""
        try:
            resolve_conn = ResolveConnection()
            if not resolve_conn.is_connected:
                resolve_conn.connect()
            
            media_pool = resolve_conn.get_media_pool()
            if not media_pool:
                self.set_status("Error: Could not access Media Pool")
                return
            
            # Get currently selected clips in the media pool
            selected_clips = media_pool.GetSelectedClips()
            
            if not selected_clips:
                self.set_status("No clips selected in Media Pool")
                return
            
            # Extract file paths from each clip
            file_paths = []
            for clip in selected_clips:
                try:
                    clip_property = clip.GetClipProperty()
                    if clip_property and "File Path" in clip_property:
                        file_path = clip_property["File Path"]
                        if file_path and os.path.isfile(file_path):
                            file_paths.append(file_path)
                except Exception as e:
                    print(f"Error getting clip property: {e}")
            
            if file_paths:
                # Store in drop area for upload and update preview
                self._drop_area._dropped_files = file_paths
                self._drop_area._update_file_preview()
                self._on_files_dropped(file_paths)
            else:
                self.set_status("No valid file paths found in selected clips")
                
        except Exception as e:
            self.set_status(f"Error accessing Media Pool: {str(e)}")
            print(f"Error in _on_add_from_media_pool: {e}")
    
    def _on_files_dropped(self, file_paths: List[str]) -> None:
        """Handle files dropped.
        
        Args:
            file_paths: List of file paths.
        """
        if file_paths:
            self.set_selected_files(file_paths)
            
            # Show file names in status (limit to first 3 if many)
            if len(file_paths) <= 3:
                file_names = [os.path.basename(path) for path in file_paths]
                self.set_status(f"Ready to upload: {', '.join(file_names)}")
            else:
                file_names = [os.path.basename(path) for path in file_paths[:3]]
                self.set_status(f"Ready to upload {len(file_paths)} files: {', '.join(file_names)}...")
        else:
            self.set_status("No valid files were dropped")
    
    def _on_upload_clicked(self) -> None:
        """Handle upload button clicked."""
        # Get the storageIdentifier from item data, not the display text
        bucket_name = self._bucket_combo.currentData()
        if not bucket_name:
            self.set_status("Please select a destination connector")
            return
        
        # Get dropped files from the drop area
        file_paths = self._drop_area.get_dropped_files()
        
        if not file_paths:
            self.set_status("Please drop files to upload first")
            return
        
        # Emit signal to request upload with the dropped files
        self.upload_requested.emit(file_paths, bucket_name)
        
        # Clear the dropped files after initiating upload
        self._drop_area.clear_dropped_files()