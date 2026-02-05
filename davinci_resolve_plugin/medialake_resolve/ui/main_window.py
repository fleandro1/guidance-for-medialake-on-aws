"""Main window for the Media Lake Resolve Plugin."""

from typing import Optional, List, Dict
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QToolBar,
    QStatusBar,
    QPushButton,
    QLabel,
    QMessageBox,
    QProgressBar,
    QMenu,
    QMenuBar,
    QTabWidget,
)
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QAction, QIcon

from medialake_resolve.core.config import Config
from medialake_resolve.core.models import Asset, Collection, SearchResult, AssetVariant, MediaType
from medialake_resolve.core.errors import ResolveNotRunningError
from medialake_resolve.auth.credential_manager import CredentialManager
from medialake_resolve.auth.auth_service import AuthService
from medialake_resolve.auth.token_manager import TokenManager
from medialake_resolve.api.api_client import MediaLakeAPIClient
from medialake_resolve.resolve.connection import ResolveConnection
from medialake_resolve.resolve.project_settings import ResolveProjectSettings
from medialake_resolve.download.download_import_controller import DownloadImportController
from medialake_resolve.ui.login_dialog import LoginDialog
from medialake_resolve.ui.search_panel import SearchPanel
from medialake_resolve.ui.browser_view import BrowserView
from medialake_resolve.ui.preview_panel import PreviewPanel
from medialake_resolve.ui.upload_panel import UploadPanel
from medialake_resolve.upload.upload_controller import UploadController


class MainWindow(QMainWindow):
    """Main application window.
    
    Orchestrates all components and provides the primary UI.
    """
    
    def __init__(self):
        """Initialize main window."""
        super().__init__()
        
        # Initialize components
        self._config = Config.load()
        self._credential_manager = CredentialManager()
        self._token_manager = TokenManager(self._credential_manager)
        self._api_client: Optional[MediaLakeAPIClient] = None
        self._download_controller: Optional[DownloadImportController] = None
        self._upload_controller: Optional[UploadController] = None
        
        # Resolve connection
        self._resolve_connection: Optional[ResolveConnection] = None
        self._project_settings: Optional[ResolveProjectSettings] = None
        
        # State
        self._current_page = 1
        self._total_pages = 1
        self._loading = False
        self._collections: List[Collection] = []
        
        # Thumbnail cache for preview panel
        self._thumbnail_cache: Dict[str, bytes] = {}
        
        # Pending downloads waiting for presigned URLs
        # Maps inventory_id to (asset, variant) tuple
        self._pending_download_urls: Dict[str, tuple] = {}
        
        # Timer for minimum progress bar display time
        self._progress_hide_timer = QTimer(self)
        self._progress_hide_timer.setSingleShot(True)
        self._progress_hide_timer.timeout.connect(self._hide_progress_bar)
        
        # Animation for smooth progress bar updates
        self._progress_animation: Optional[QPropertyAnimation] = None
        
        # Track batch download progress
        self._batch_total_files = 0
        self._batch_completed_files = 0
        self._batch_failed_files = 0
        
        # Track batch upload progress
        self._upload_total_files = 0
        self._upload_completed_files = 0
        self._upload_failed_files = 0
        
        # Track if connectors have been loaded (lazy loading)
        self._connectors_loaded = False
        
        self._setup_ui()
        self._setup_connections()
        self._try_auto_connect()
    
    def _setup_ui(self) -> None:
        """Set up the main window UI."""
        self.setWindowTitle("Media Lake for DaVinci Resolve")
        self.setMinimumSize(1024, 768)
        
        # Set window icon
        try:
            from medialake_resolve.resources import get_app_icon
            self.setWindowIcon(get_app_icon())
        except Exception as e:
            print(f"Failed to load window icon: {e}")
        
        # Create menu bar
        self._create_menu_bar()
        
        # Create toolbar
        self._create_toolbar()
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Tab widget for main content
        self._tab_widget = QTabWidget()
        main_layout.addWidget(self._tab_widget)
        
        # Browse tab
        browse_widget = QWidget()
        browse_layout = QVBoxLayout(browse_widget)
        browse_layout.setContentsMargins(0, 0, 0, 0)
        browse_layout.setSpacing(0)
        
        # Search panel
        self._search_panel = SearchPanel(self._config)
        browse_layout.addWidget(self._search_panel)
        
        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Browser view
        self._browser_view = BrowserView(self._config)
        splitter.addWidget(self._browser_view)
        
        # Preview panel
        self._preview_panel = PreviewPanel()
        splitter.addWidget(self._preview_panel)
        
        # Set splitter sizes
        splitter.setSizes([700, 300])
        
        browse_layout.addWidget(splitter, 1)
        
        # Upload tab
        self._upload_panel = UploadPanel(self._config)
        
        # Add tabs
        self._tab_widget.addTab(browse_widget, "Browse")
        self._tab_widget.addTab(self._upload_panel, "Upload")
        
        # Status bar
        self._create_status_bar()
    
    def _create_menu_bar(self) -> None:
        """Create the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        connect_action = QAction("Connect to Media Lake...", self)
        connect_action.triggered.connect(self._show_login_dialog)
        file_menu.addAction(connect_action)
        
        disconnect_action = QAction("Disconnect", self)
        disconnect_action.triggered.connect(self._disconnect)
        file_menu.addAction(disconnect_action)
        
        file_menu.addSeparator()
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        
        # View menu
        view_menu = menubar.addMenu("View")
        
        grid_action = QAction("Grid View", self)
        grid_action.triggered.connect(lambda: self._browser_view.set_view_mode("grid"))
        view_menu.addAction(grid_action)
        
        list_action = QAction("List View", self)
        list_action.triggered.connect(lambda: self._browser_view.set_view_mode("list"))
        view_menu.addAction(list_action)
        
        view_menu.addSeparator()
        
        refresh_action = QAction("Refresh", self)
        refresh_action.setShortcut("Ctrl+R")
        refresh_action.triggered.connect(self._refresh)
        view_menu.addAction(refresh_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _create_toolbar(self) -> None:
        """Create the toolbar."""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Connection status
        self._connection_label = QLabel("Not connected")
        self._connection_label.setStyleSheet(
            "padding: 4px 12px; color: #888; font-weight: 500; "
            "background-color: #2a2a2d; border-radius: 4px;"
        )
        toolbar.addWidget(self._connection_label)
        
        toolbar.addSeparator()
        
        # Connect button
        self._connect_button = QPushButton("Connect")
        self._connect_button.clicked.connect(self._show_login_dialog)
        toolbar.addWidget(self._connect_button)
        
        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(
            spacer.sizePolicy().horizontalPolicy(),
            spacer.sizePolicy().verticalPolicy(),
        )
        toolbar.addWidget(spacer)
        
        # Download selected button
        self._download_button = QPushButton("Download Selected")
        self._download_button.setEnabled(False)
        self._download_button.clicked.connect(self._download_selected)
        toolbar.addWidget(self._download_button)
        
        # Download proxy button
        self._download_proxy_button = QPushButton("Download Proxies")
        self._download_proxy_button.setEnabled(False)
        self._download_proxy_button.clicked.connect(self._download_selected_proxies)
        toolbar.addWidget(self._download_proxy_button)
        
        # # Upload selected button
        # self._upload_button = QPushButton("Upload Selected")
        # self._upload_button.setEnabled(False)
        # self._upload_button.clicked.connect(self._upload_selected)
        # toolbar.addWidget(self._upload_button)
        
        toolbar.addSeparator()
        
        # Resolve status
        self._resolve_label = QLabel("Resolve: Not connected")
        self._resolve_label.setStyleSheet(
            "padding: 4px 12px; color: #888; font-weight: 500; "
            "background-color: #2a2a2d; border-radius: 4px;"
        )
        toolbar.addWidget(self._resolve_label)
    
    def _create_status_bar(self) -> None:
        """Create the status bar."""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        
        # Status message
        self._status_message = QLabel("Ready")
        status_bar.addWidget(self._status_message)
        
        # Search loading indicator (small spinner)
        self._search_loading_indicator = QProgressBar()
        self._search_loading_indicator.setMaximumWidth(200)
        self._search_loading_indicator.setMaximumHeight(16)
        self._search_loading_indicator.setTextVisible(False)
        self._search_loading_indicator.setRange(0, 0)  # Indeterminate/busy indicator
        self._search_loading_indicator.setVisible(False)
        self._search_loading_indicator.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 2px;
                background-color: #1a1a1a;
            }
            QProgressBar::chunk {
                background-color: #9a9a9a;
                border-radius: 2px;
            }
        """)
        status_bar.addPermanentWidget(self._search_loading_indicator)
        
        # Progress bar (for downloads/uploads)
        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumWidth(200)
        self._progress_bar.setMaximumHeight(16)
        self._progress_bar.setVisible(False)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("%p%")
        status_bar.addPermanentWidget(self._progress_bar)
        
        # Create progress animation
        self._progress_animation = QPropertyAnimation(self._progress_bar, b"value")
        self._progress_animation.setDuration(500)  # 500ms animation
        self._progress_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    def _setup_connections(self) -> None:
        """Set up signal connections."""
        # Token manager
        self._token_manager.token_expired.connect(self._on_token_expired)
        self._token_manager.authentication_required.connect(self._show_login_dialog)
        
        # Search panel
        self._search_panel.search_requested.connect(self._on_search)
        self._search_panel.filters_changed.connect(self._on_filters_changed)
        
        # Browser view
        self._browser_view.asset_selected.connect(self._on_asset_selected)
        self._browser_view.asset_double_clicked.connect(self._on_asset_double_clicked)
        self._browser_view.selection_changed.connect(self._on_selection_changed)
        self._browser_view.load_more_requested.connect(self._load_more_assets)
        self._browser_view.page_changed.connect(self._on_page_changed)
        self._browser_view.page_size_changed.connect(self._on_page_size_changed)
        
        # Preview panel
        self._preview_panel.download_requested.connect(self._on_download_requested)
        
        # Upload panel
        self._upload_panel.upload_requested.connect(self._on_upload_requested)
        self._upload_panel.bucket_refresh_requested.connect(self._refresh_buckets)
        
        # Tab widget - lazy load connectors when upload tab is first accessed
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
    
    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change - lazy load connectors when upload tab is accessed."""
        # Check if upload tab (index 1) is accessed and connectors haven't been loaded yet
        if index == 1 and not self._connectors_loaded and self._api_client:
            self._refresh_buckets()
            self._connectors_loaded = True
    
    def _try_auto_connect(self) -> None:
        """Try to auto-connect with saved credentials."""
        if not self._config.is_configured:
            return
        
        credentials = self._credential_manager.get_credentials()
        if not credentials:
            return
        
        try:
            # Create auth service
            auth_service = AuthService(
                credentials.cognito_user_pool_id,
                credentials.cognito_client_id,
                credentials.cognito_region,
            )
            self._token_manager.set_auth_service(auth_service)
            
            # Try to restore session
            if self._token_manager.restore_session():
                self._on_connected(credentials.username, credentials.medialake_url)
            elif credentials.password:
                # Try to authenticate
                self._token_manager.authenticate(
                    credentials.username,
                    credentials.password,
                )
                self._on_connected(credentials.username, credentials.medialake_url)
        except Exception as e:
            print(f"Auto-connect failed: {e}")
    
    def _show_login_dialog(self) -> None:
        """Show the login dialog."""
        dialog = LoginDialog(
            self._config,
            self._credential_manager,
            self._token_manager,
            self,
        )
        dialog.login_successful.connect(self._on_connected)
        dialog.exec()
    
    def _on_connected(self, username: str, medialake_url: str) -> None:
        """Handle successful connection.
        
        Args:
            username: The authenticated username.
            medialake_url: The Media Lake URL.
        """
        # Update UI
        self._connection_label.setText(f"Connected as {username}")
        self._connection_label.setStyleSheet(
            "padding: 4px 12px; color: #00d4ff; font-weight: 500; "
            "background-color: rgba(0, 212, 255, 0.15); border-radius: 4px; "
            "border: 1px solid rgba(0, 212, 255, 0.3);"
        )
        self._connect_button.setText("Reconnect")
        
        # Initialize API client
        self._api_client = MediaLakeAPIClient(
            medialake_url,
            lambda: self._token_manager.id_token,  # Use id_token for API authorization
            self._config,  # Pass config for confidence threshold
            self,
        )
        
        # Connect API client signals
        self._api_client.collections_loaded.connect(self._on_collections_loaded)
        self._api_client.assets_loaded.connect(self._on_assets_loaded)
        self._api_client.search_completed.connect(self._on_search_completed)
        self._api_client.thumbnail_loaded.connect(self._on_thumbnail_loaded)
        self._api_client.download_url_ready.connect(self._on_download_url_ready)
        self._api_client.buckets_loaded.connect(self._on_buckets_loaded)
        self._api_client.connectors_loaded.connect(self._on_connectors_loaded)
        self._api_client.upload_url_ready.connect(self._on_upload_url_ready)
        self._api_client.error_occurred.connect(self._on_api_error)
        
        # Initialize download controller
        self._download_controller = DownloadImportController(
            self._config,
            lambda: self._token_manager.id_token,  # Use id_token for API authorization
            self,
        )
        self._download_controller.download_started.connect(self._on_download_started)
        self._download_controller.download_progress.connect(self._on_download_progress)
        self._download_controller.download_completed.connect(self._on_download_completed)
        self._download_controller.download_failed.connect(self._on_download_failed)
        self._download_controller.batch_completed.connect(self._on_batch_completed)
        
        # Initialize upload controller
        self._upload_controller = UploadController(
            self._config,
            lambda: self._token_manager.id_token,  # Use id_token for API authorization
            self,
        )
        self._upload_controller.upload_started.connect(self._on_upload_started)
        self._upload_controller.upload_progress.connect(self._on_upload_progress)
        self._upload_controller.upload_completed.connect(self._on_upload_completed)
        self._upload_controller.upload_failed.connect(self._on_upload_failed)
        self._upload_controller.batch_completed.connect(self._on_upload_batch_completed)
        self._upload_controller.upload_url_needed.connect(self._on_upload_url_needed)
        
        # Try to connect to Resolve
        self._connect_to_resolve()
        
        # Load initial data (connectors loaded lazily when upload tab is accessed)
        self._api_client.get_collections()
        self._load_assets()
    
    def _disconnect(self) -> None:
        """Disconnect from Media Lake."""
        self._token_manager.logout()
        
        if self._api_client:
            self._api_client.cancel_all_requests()
            self._api_client = None
        
        if self._download_controller:
            self._download_controller.cancel_all()
            self._download_controller = None
            
        if self._upload_controller:
            self._upload_controller.cancel_all()
            self._upload_controller = None
        
        # Reset connectors loaded flag for lazy loading
        self._connectors_loaded = False
        
        self._connection_label.setText("Not connected")
        self._connection_label.setStyleSheet(
            "padding: 4px 12px; color: #888; font-weight: 500; "
            "background-color: #2a2a2d; border-radius: 4px;"
        )
        self._connect_button.setText("Connect")
        
        self._browser_view.set_assets([])
        self._preview_panel.clear()
        self._search_panel.set_collections([])
    
    def _connect_to_resolve(self) -> None:
        """Try to connect to DaVinci Resolve."""
        try:
            self._resolve_connection = ResolveConnection()
            self._resolve_connection.connect()
            
            self._project_settings = ResolveProjectSettings(self._resolve_connection)
            
            # Set up controllers with Resolve
            if self._download_controller:
                self._download_controller.set_resolve_connection(self._resolve_connection)
                
            if self._upload_controller:
                self._upload_controller.set_resolve_connection(self._resolve_connection)
            
            # Update UI
            version = self._resolve_connection.get_resolve_version()
            project_name = self._project_settings.get_project_name()
            self._resolve_label.setText(f"Resolve Project: {project_name}")
            self._resolve_label.setStyleSheet(
                "padding: 4px 12px; color: #00d4ff; font-weight: 500; "
                "background-color: rgba(0, 212, 255, 0.15); border-radius: 4px; "
                "border: 1px solid rgba(0, 212, 255, 0.3);"
            )
            
        except ResolveNotRunningError:
            self._resolve_label.setText("Resolve: Not running")
            self._resolve_label.setStyleSheet(
                "padding: 4px 12px; color: #ffaa00; font-weight: 500; "
                "background-color: rgba(255, 170, 0, 0.15); border-radius: 4px; "
                "border: 1px solid rgba(255, 170, 0, 0.3);"
            )
        except Exception as e:
            self._resolve_label.setText("Resolve: Error")
            self._resolve_label.setStyleSheet(
                "padding: 4px 12px; color: #ff6b6b; font-weight: 500; "
                "background-color: rgba(255, 107, 107, 0.15); border-radius: 4px; "
                "border: 1px solid rgba(255, 107, 107, 0.3);"
            )
            print(f"Resolve connection error: {e}")
    
    def _load_assets(self) -> None:
        """Load assets with current filters."""
        if not self._api_client or self._loading:
            return
        
        self._loading = True
        self._current_page = 1
        self._set_status("Loading assets...")
        
        collection_id = self._search_panel.get_collection_filter()
        media_type_str = self._search_panel.get_media_type_filter()
        media_type = MediaType(media_type_str) if media_type_str else None
        
        page_size = self._browser_view.get_page_size()
        
        # Use browse_assets (search-based) instead of get_assets due to /assets endpoint issues
        self._api_client.browse_assets(
            collection_id=collection_id,
            media_type=media_type,
            page=1,
            page_size=page_size,
        )
    
    def _load_more_assets(self) -> None:
        """Load more assets (pagination)."""
        if not self._api_client or self._loading:
            return
        
        if self._current_page >= self._total_pages:
            return
        
        self._loading = True
        self._current_page += 1
        
        collection_id = self._search_panel.get_collection_filter()
        media_type_str = self._search_panel.get_media_type_filter()
        media_type = MediaType(media_type_str) if media_type_str else None
        
        page_size = self._browser_view.get_page_size()
        
        # Use browse_assets (search-based) instead of get_assets due to /assets endpoint issues
        self._api_client.browse_assets(
            collection_id=collection_id,
            media_type=media_type,
            page=self._current_page,
            page_size=page_size,
        )
    
    def _on_search(self, query: str, search_type: str, collection_id: Optional[str], media_type: Optional[str]) -> None:
        """Handle search request."""
        print(f"\n=== SEARCH TRIGGERED ===")
        print(f"  Query: '{query}'")
        print(f"  Search Type: {search_type}")
        print(f"  Collection: {collection_id}")
        print(f"  Media Type: {media_type}")
        
        if not self._api_client:
            print("  ERROR: No API client!")
            return
        
        self._loading = True
        self._current_page = 1
        
        # Show loading indicator in status bar
        self._search_loading_indicator.setVisible(True)
        self._set_status(f"Searching for '{query}'...")
        
        media_type_enum = None
        if media_type:
            from medialake_resolve.core.models import MediaType
            try:
                media_type_enum = MediaType(media_type)
            except ValueError:
                pass
        
        page_size = self._browser_view.get_page_size()
        
        self._api_client.search(
            query=query,
            search_type=search_type,
            collection_id=collection_id or None,
            media_type=media_type_enum,
            page=1,
            page_size=page_size,
        )
    
    def _on_filters_changed(self) -> None:
        """Handle filter changes."""
        self._load_assets()
    
    def _on_page_changed(self, page: int) -> None:
        """Handle page change from browser view."""
        if not self._api_client or self._loading:
            return
        
        self._loading = True
        self._current_page = page
        
        # Check if we have an active search query
        query = self._search_panel.get_current_query()
        page_size = self._browser_view.get_page_size()
        
        if query:
            # Re-run search for the new page
            search_type = self._search_panel.get_search_type()
            collection_id = self._search_panel.get_collection_filter()
            media_type_str = self._search_panel.get_media_type_filter()
            
            media_type_enum = None
            if media_type_str:
                try:
                    media_type_enum = MediaType(media_type_str)
                except ValueError:
                    pass
            
            self._api_client.search(
                query=query,
                search_type=search_type,
                collection_id=collection_id or None,
                media_type=media_type_enum,
                page=page,
                page_size=page_size,
            )
        else:
            # Browse assets
            collection_id = self._search_panel.get_collection_filter()
            media_type_str = self._search_panel.get_media_type_filter()
            media_type = MediaType(media_type_str) if media_type_str else None
            
            self._api_client.browse_assets(
                collection_id=collection_id,
                media_type=media_type,
                page=page,
                page_size=page_size,
            )
    
    def _on_page_size_changed(self, page_size: int) -> None:
        """Handle page size change from browser view."""
        # Reload from page 1 with new page size
        self._current_page = 1
        
        query = self._search_panel.get_current_query()
        if query:
            # Re-run search
            self._on_search(
                query,
                self._search_panel.get_search_type(),
                self._search_panel.get_collection_filter(),
                self._search_panel.get_media_type_filter(),
            )
        else:
            self._load_assets()
    
    def _on_collections_loaded(self, collections: List[Collection]) -> None:
        """Handle collections loaded."""
        self._collections = collections
        self._search_panel.set_collections(collections)
    
    def _on_assets_loaded(self, assets: List[Asset], total_count: int) -> None:
        """Handle assets loaded."""
        self._loading = False
        page_size = self._browser_view.get_page_size()
        self._total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 1
        
        # With pagination, always replace assets (don't append)
        self._browser_view.set_assets(assets, append=False)
        
        # Update pagination info in browser view
        self._browser_view.set_pagination_info(self._current_page, self._total_pages, total_count)
        
        self._set_status(f"Loaded {total_count} assets")
        
        # Request thumbnails
        for asset in assets:
            print(f"Asset: {asset.name}, size={asset.file_size}, thumbnail_url={asset.thumbnail_url}")
            if asset.thumbnail_url and self._api_client:
                self._api_client.get_thumbnail(asset.asset_id, asset.thumbnail_url)
    
    def _on_search_completed(self, result: SearchResult) -> None:
        """Handle search completed."""
        print(f"\n=== SEARCH COMPLETED ===")
        print(f"  Query: '{result.query}'")
        print(f"  Search Type: {result.search_type}")
        print(f"  Total Count: {result.total_count}")
        print(f"  Results returned: {len(result.assets)}")
        
        self._loading = False
        self._total_pages = result.total_pages
        
        # Hide loading indicators
        self._search_panel.set_loading(False)
        self._search_loading_indicator.setVisible(False)
        
        # With pagination, always replace assets (don't append)
        self._browser_view.set_assets(result.assets, append=False)
        
        # Update pagination info in browser view
        self._browser_view.set_pagination_info(self._current_page, self._total_pages, result.total_count)
        
        self._set_status(f"Found {result.total_count} results for '{result.query}'")
        
        # Request thumbnails
        for asset in result.assets:
            if asset.thumbnail_url and self._api_client:
                self._api_client.get_thumbnail(asset.asset_id, asset.thumbnail_url)
    
    def _on_thumbnail_loaded(self, asset_id: str, image_data: bytes) -> None:
        """Handle thumbnail loaded."""
        # Cache the thumbnail
        self._thumbnail_cache[asset_id] = image_data
        # Update browser view
        self._browser_view.set_thumbnail(asset_id, image_data)
        # If this is the currently selected asset, update the preview panel
        selected = self._browser_view.get_selected_assets()
        if selected and len(selected) == 1 and selected[0].asset_id == asset_id:
            self._preview_panel.set_preview_image(image_data)
    
    def _on_api_error(self, error_type: str, error_message: str) -> None:
        """Handle API error."""
        self._loading = False
        
        # Hide loading indicators
        self._search_panel.set_loading(False)
        self._search_loading_indicator.setVisible(False)
        
        self._set_status(f"Error: {error_message}")
        
        if error_type == "authentication":
            self._show_login_dialog()
    
    def _on_asset_selected(self, asset: Asset) -> None:
        """Handle asset selected."""
        self._preview_panel.set_asset(asset)
        
        # Set preview image from cache if available
        if asset.asset_id in self._thumbnail_cache:
            self._preview_panel.set_preview_image(self._thumbnail_cache[asset.asset_id])
        elif asset.thumbnail_url and self._api_client:
            # Request thumbnail if not cached
            self._api_client.get_thumbnail(asset.asset_id, asset.thumbnail_url)
    
    def _on_asset_double_clicked(self, asset: Asset) -> None:
        """Handle asset double-clicked."""
        # Download and import
        self._download_asset(asset, AssetVariant.ORIGINAL)
    
    def _on_selection_changed(self, selected_assets: List[Asset]) -> None:
        """Handle selection changed."""
        count = len(selected_assets)
        self._download_button.setEnabled(count > 0)
        self._download_proxy_button.setEnabled(
            count > 0 and any(a.has_proxy for a in selected_assets)
        )
        self._upload_button.setEnabled(count > 0)
    
    def _on_download_requested(self, asset: Asset, variant: str) -> None:
        """Handle download request from preview panel."""
        variant_enum = AssetVariant.PROXY if variant == "proxy" else AssetVariant.ORIGINAL
        self._download_asset(asset, variant_enum)
    
    def _download_selected(self) -> None:
        """Download selected assets."""
        selected = self._browser_view.get_selected_assets()
        if not selected or not self._download_controller or not self._api_client:
            return
        
        if len(selected) > 50:
            QMessageBox.warning(
                self,
                "Too Many Selected",
                "Please select no more than 50 assets at a time.",
            )
            return
        
        # Download each asset (which will request presigned URLs first)
        for asset in selected:
            self._download_asset(asset, AssetVariant.ORIGINAL)
        
        # Initialize batch tracking
        self._batch_total_files = len(selected)
        self._batch_completed_files = 0
        self._batch_failed_files = 0
        
        self._set_status(f"Requesting download URLs for {len(selected)} assets...")
        self._search_loading_indicator.setVisible(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
    
    def _download_selected_proxies(self) -> None:
        """Download proxies for selected assets."""
        selected = self._browser_view.get_selected_assets()
        if not selected or not self._download_controller or not self._api_client:
            return
        
        # Filter to assets with proxies
        with_proxies = [a for a in selected if a.has_proxy]
        
        if not with_proxies:
            QMessageBox.information(
                self,
                "No Proxies Available",
                "None of the selected assets have proxy files available.",
            )
            return
        
        # Download each asset (which will request presigned URLs first)
        for asset in with_proxies:
            self._download_asset(asset, AssetVariant.PROXY)
        
        # Initialize batch tracking
        self._batch_total_files = len(with_proxies)
        self._batch_completed_files = 0
        self._batch_failed_files = 0
        
        self._set_status(f"Requesting download URLs for {len(with_proxies)} proxies...")
        self._search_loading_indicator.setVisible(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
    
    def _download_asset(self, asset: Asset, variant: AssetVariant) -> None:
        """Download a single asset.
        
        First requests a presigned URL from the API, then queues the download.
        
        Args:
            asset: The asset to download.
            variant: Original or proxy variant.
        """
        if not self._download_controller or not self._api_client:
            return
        
        # Get the inventory ID for the asset
        inventory_id = asset.inventory_id or f"urn:medialake:asset:{asset.asset_id}"
        
        print(f"  [Main] Download requested for {asset.name}")
        print(f"  [Main] Inventory ID: {inventory_id}")
        print(f"  [Main] Asset inventory_id field: {asset.inventory_id}")
        
        # Store pending download info
        variant_str = "proxy" if variant == AssetVariant.PROXY else "original"
        self._pending_download_urls[inventory_id] = (asset, variant)
        
        # Request presigned URL
        self._api_client.get_download_url(inventory_id, variant_str)
        self._set_status(f"Getting download URL for {asset.name}...")
    
    def _on_download_url_ready(self, asset_id: str, download_url: str) -> None:
        """Handle presigned download URL received."""
        print(f"  [Main] Download URL ready for {asset_id}")
        print(f"  [Main] Pending downloads: {list(self._pending_download_urls.keys())}")
        
        # Find the pending download
        pending = self._pending_download_urls.pop(asset_id, None)
        if not pending:
            print(f"  [Main] No pending download found for {asset_id}")
            return
        
        asset, variant = pending
        
        if not download_url:
            self._set_status(f"Failed to get download URL for {asset.name}")
            return
        
        print(f"  [Main] Got URL for {asset.name}: {download_url[:80]}...")
        
        # Update the asset with the download URL
        if variant == AssetVariant.PROXY:
            asset.proxy_url = download_url
        else:
            asset.original_url = download_url
        
        # Now queue the actual download
        if self._download_controller:
            print(f"  [Main] Queueing download for {asset.name}")
            self._download_controller.queue_download(asset, variant)
            self._set_status(f"Downloading {asset.name}...")
    
    def _on_download_started(self, task_id: str, asset_name: str) -> None:
        """Handle download started."""
        self._set_status(f"Downloading {asset_name}...")
        # Hide search indicator and show progress bar (only on first download)
        if not self._progress_bar.isVisible():
            self._search_loading_indicator.setVisible(False)
            self._progress_bar.setVisible(True)
            self._progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #555;
                    border-radius: 2px;
                    background-color: #1a1a1a;
                    text-align: center;
                    color: #ffffff;
                }
                QProgressBar::chunk {
                    background-color: #3a7b7c;
                    border-radius: 2px;
                }
            """)
            self._progress_bar.setValue(0)
    
    def _on_download_progress(self, task_id: str, progress: float) -> None:
        """Handle download progress."""
        # Individual file progress is not shown - we track batch progress instead
        # Ensure progress bar is visible
        if not self._progress_bar.isVisible():
            self._progress_bar.setVisible(True)
    
    def _on_download_completed(self, task_id: str, file_path: str) -> None:
        """Handle download completed."""
        self._set_status(f"Downloaded to {file_path}")
        
        # Update batch progress
        self._batch_completed_files += 1
        if self._batch_total_files > 0:
            batch_progress = int((self._batch_completed_files / self._batch_total_files) * 100)
            
            # Animate to the new batch progress
            if self._progress_animation:
                self._progress_animation.stop()
                self._progress_animation.setStartValue(self._progress_bar.value())
                self._progress_animation.setEndValue(batch_progress)
                self._progress_animation.start()
            else:
                self._progress_bar.setValue(batch_progress)
            
            # Check if all expected files are done
            if self._batch_completed_files >= self._batch_total_files:
                self._finalize_batch_download()
    
    def _on_download_failed(self, task_id: str, error_message: str) -> None:
        """Handle download failed."""
        self._set_status(f"Download failed: {error_message}")
        
        # Update batch progress even for failed files
        self._batch_completed_files += 1
        self._batch_failed_files += 1
        if self._batch_total_files > 0:
            batch_progress = int((self._batch_completed_files / self._batch_total_files) * 100)
            
            # Animate to the new batch progress
            if self._progress_animation:
                self._progress_animation.stop()
                self._progress_animation.setStartValue(self._progress_bar.value())
                self._progress_animation.setEndValue(batch_progress)
                self._progress_animation.start()
            else:
                self._progress_bar.setValue(batch_progress)
            
            # Check if all expected files are done
            if self._batch_completed_files >= self._batch_total_files:
                self._finalize_batch_download()
    
    def _finalize_batch_download(self) -> None:
        """Finalize batch download - show completion UI."""
        success_count = self._batch_completed_files - self._batch_failed_files
        fail_count = self._batch_failed_files
        
        # Ensure we're at 100%
        if self._progress_animation:
            self._progress_animation.stop()
            self._progress_animation.setStartValue(self._progress_bar.value())
            self._progress_animation.setEndValue(100)
            self._progress_animation.start()
        else:
            self._progress_bar.setValue(100)
        
        # Show completion message and color
        if fail_count == 0:
            self._set_status(f"Successfully downloaded {success_count} assets")
            self._progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #555;
                    border-radius: 2px;
                    background-color: #1a1a1a;
                    text-align: center;
                    color: #ffffff;
                }
                QProgressBar::chunk {
                    background-color: #9a9a9a;
                    border-radius: 2px;
                }
            """)
        else:
            self._set_status(f"Downloaded {success_count} assets, {fail_count} failed")
            self._progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #f0ad4e;
                    border-radius: 2px;
                    background-color: #1a1a1a;
                    text-align: center;
                    color: #ffffff;
                }
                QProgressBar::chunk {
                    background-color: #f0ad4e;
                    border-radius: 2px;
                }
            """)
        
        # Reset batch tracking
        self._batch_total_files = 0
        self._batch_completed_files = 0
        self._batch_failed_files = 0
        
        # Hide after minimum display time
        if not self._progress_hide_timer.isActive():
            self._progress_hide_timer.start(1500)  # 1.5 seconds

    def _on_batch_completed(self, success_count: int, fail_count: int) -> None:
        """Handle batch download completed."""
        # Ignore batch_completed signals if we haven't finished all our expected files
        # This handles the case where downloads complete before all presigned URLs arrive
        if self._batch_total_files > 0 and self._batch_completed_files < self._batch_total_files:
            return
        
        # Ensure we're at 100%
        if self._progress_animation:
            self._progress_animation.stop()
            self._progress_animation.setStartValue(self._progress_bar.value())
            self._progress_animation.setEndValue(100)
            self._progress_animation.start()
        else:
            self._progress_bar.setValue(100)
        
        # Reset batch tracking
        self._batch_total_files = 0
        self._batch_completed_files = 0
        
        # Show completion message
        if fail_count == 0:
            self._set_status(f"Successfully downloaded {success_count} assets")
            # Show success color
            self._progress_bar.setValue(100)
            self._progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #555;
                    border-radius: 2px;
                    background-color: #1a1a1a;
                    text-align: center;
                    color: #ffffff;
                }
                QProgressBar::chunk {
                    background-color: #9a9a9a;
                    border-radius: 2px;
                }
            """)
        else:
            self._set_status(f"Downloaded {success_count} assets, {fail_count} failed")
            # Show warning color
            self._progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #f0ad4e;
                    border-radius: 2px;
                    background-color: #1a1a1a;
                    text-align: center;
                    color: #ffffff;
                }
                QProgressBar::chunk {
                    background-color: #f0ad4e;
                    border-radius: 2px;
                }
            """)
        
        # Hide after minimum display time
        if not self._progress_hide_timer.isActive():
            self._progress_hide_timer.start(1500)  # 1.5 seconds
    
    def _hide_progress_bar(self) -> None:
        """Hide the progress bar and reset its styling."""
        self._progress_bar.setVisible(False)
        self._progress_bar.setValue(0)
        # Reset to default gray styling
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 2px;
                background-color: #1a1a1a;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #9a9a9a;
                border-radius: 2px;
            }
        """)
    
    def _upload_selected(self) -> None:
        """Upload selected assets from Media Pool."""
        if not self._resolve_connection or not self._upload_controller:
            return
        
        # Switch to upload tab
        self._tab_widget.setCurrentWidget(self._upload_panel)
        
        # Get selected clips from Media Pool
        try:
            media_pool = self._resolve_connection.get_media_pool()
            selected_clips = media_pool.GetCurrentFolder().GetClipList() or []
            
            # Filter to only selected clips
            selected_clips = [clip for clip in selected_clips if clip.GetClipProperty("Selected") == "1"]
            
            if not selected_clips:
                QMessageBox.information(
                    self,
                    "No Clips Selected",
                    "Please select clips in the Media Pool to upload.",
                )
                return
            
            # Get file paths
            file_paths = []
            for clip in selected_clips:
                file_path = clip.GetClipProperty("File Path")
                if file_path:
                    file_paths.append(file_path)
            
            # Update upload panel
            self._upload_panel.set_selected_files(file_paths)
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to get selected clips: {e}",
            )
    
    def _on_upload_requested(self, file_paths: List[str], bucket_name: str) -> None:
        """Handle upload request from upload panel.
        
        Args:
            file_paths: List of file paths to upload.
            bucket_name: The storageIdentifier (bucket name) from the selected connector.
        """
        if not self._upload_controller or not self._api_client:
            return
        
        # Check if we have any connectors loaded
        if not self._upload_controller._connectors:
            QMessageBox.warning(
                self,
                "No Connectors",
                "No storage connectors are available. Please click 'Refresh' to load connectors, or check your Media Lake configuration.",
            )
            return
        
        # Check if the selected bucket/connector exists
        if bucket_name and bucket_name not in self._upload_controller._connectors:
            available = list(self._upload_controller._connectors.keys())
            QMessageBox.warning(
                self,
                "Connector Not Found",
                f"The selected storage connector '{bucket_name}' was not found.\n\n"
                f"Available connectors: {', '.join(available) if available else 'None'}\n\n"
                "Please click 'Refresh' to reload connectors.",
            )
            return
        
        # If file_paths is empty, use selected clips from Media Pool
        if not file_paths:
            try:
                media_pool = self._resolve_connection.get_media_pool()
                selected_clips = media_pool.GetCurrentFolder().GetClipList() or []
                
                # Filter to only selected clips
                selected_clips = [clip for clip in selected_clips if clip.GetClipProperty("Selected") == "1"]
                
                file_paths = []
                for clip in selected_clips:
                    file_path = clip.GetClipProperty("File Path")
                    if file_path:
                        file_paths.append(file_path)
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Failed to get selected clips: {e}",
                )
                return
        
        if not file_paths:
            QMessageBox.information(
                self,
                "No Files Selected",
                "Please select files to upload.",
            )
            return
        
        if len(file_paths) > 50:
            QMessageBox.warning(
                self,
                "Too Many Selected",
                "Please select no more than 50 files at a time.",
            )
            return
        
        # Queue uploads
        self._upload_controller.queue_uploads(file_paths, bucket_name)
        
        # Initialize upload batch tracking
        self._upload_total_files = len(file_paths)
        self._upload_completed_files = 0
        self._upload_failed_files = 0
        
        self._set_status(f"Uploading {len(file_paths)} files to {bucket_name}...")
        self._search_loading_indicator.setVisible(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 2px;
                background-color: #1a1a1a;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #9a9a9a;
                border-radius: 2px;
            }
        """)
        self._progress_bar.setValue(0)
    
    def _refresh_buckets(self) -> None:
        """Refresh the list of available storage connectors.
        
        Note: We only use get_connectors() which returns the configured Media Lake
        storage connectors. The get_buckets() method calls /connectors/s3 which
        returns ALL S3 buckets in the AWS account (for admin use when creating
        new connectors), not the configured connectors.
        """
        if self._api_client:
            self._api_client.get_connectors()  # Load configured connectors for upload
            self._set_status("Refreshing connectors...")
    
    def _on_buckets_loaded(self, buckets: List[str]) -> None:
        """Handle buckets loaded from API.
        
        Note: This handler is kept for backwards compatibility but is no longer
        used since we now only call get_connectors() instead of get_buckets().
        The get_buckets() method calls /connectors/s3 which returns ALL S3 buckets
        in the AWS account, not just the configured Media Lake connectors.
        
        Args:
            buckets: List of bucket names.
        """
        print(f"  [Main] Buckets loaded (deprecated): {buckets}")
        # Don't update the upload panel - connectors_loaded will handle this
    
    def _on_connectors_loaded(self, connectors: List[Dict]) -> None:
        """Handle connectors loaded from API.
        
        Args:
            connectors: List of connector dicts with 'id', 'storageIdentifier', etc.
        """
        print(f"  [Main] Connectors loaded: {len(connectors)} connectors")
        for c in connectors:
            print(f"    - {c.get('name', 'unnamed')}: {c.get('id')} -> {c.get('storageIdentifier')}")
        
        # Pass connectors to upload controller
        if self._upload_controller:
            self._upload_controller.set_connectors(connectors)
        
        # Update upload panel dropdown with connector names
        self._upload_panel.set_connectors(connectors)
        
        if connectors:
            self._set_status(f"Loaded {len(connectors)} storage connectors")
        else:
            self._set_status("No storage connectors available")
    
    def _on_upload_url_needed(self, task_id: str, connector_id: str, filename: str, content_type: str, file_size: int) -> None:
        """Handle upload URL request from upload controller.
        
        This is called when the upload controller needs a presigned URL for an upload.
        
        Args:
            task_id: The task ID.
            connector_id: The connector ID.
            filename: The filename.
            content_type: The content type.
            file_size: The file size in bytes.
        """
        print(f"  [Main] Upload URL needed for task {task_id}")
        print(f"  [Main] Connector: {connector_id}, File: {filename}, Type: {content_type}, Size: {file_size}")
        
        if self._api_client:
            self._api_client.request_asset_upload_url(
                task_id=task_id,
                connector_id=connector_id,
                filename=filename,
                content_type=content_type,
                file_size=file_size,
            )
    
    def _on_upload_url_ready(self, task_id: str, upload_url: str, presigned_fields_json: str) -> None:
        """Handle presigned upload URL received from API.
        
        This routes the URL to the upload controller.
        
        Args:
            task_id: The task ID.
            upload_url: The presigned upload URL.
            presigned_fields_json: JSON string of presigned POST fields.
        """
        print(f"  [Main] Upload URL ready for task {task_id}")
        print(f"  [Main] URL: {upload_url[:80] if upload_url else 'NONE'}...")
        
        if self._upload_controller:
            self._upload_controller.on_upload_url_ready(task_id, upload_url, presigned_fields_json)
    
    def _on_upload_started(self, task_id: str, file_name: str) -> None:
        """Handle upload started."""
        self._set_status(f"Uploading {file_name}...")
        # Hide search indicator and show progress bar (only on first upload)
        if not self._progress_bar.isVisible():
            self._search_loading_indicator.setVisible(False)
            self._progress_bar.setVisible(True)
            self._progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #555;
                    border-radius: 2px;
                    background-color: #1a1a1a;
                    text-align: center;
                    color: #ffffff;
                }
                QProgressBar::chunk {
                    background-color: #9a9a9a;
                    border-radius: 2px;
                }
            """)
            self._progress_bar.setValue(0)
    
    def _on_upload_progress(self, task_id: str, progress: float) -> None:
        """Handle upload progress."""
        # Individual file progress is not shown - we track batch progress instead
        # Ensure progress bar is visible
        if not self._progress_bar.isVisible():
            self._progress_bar.setVisible(True)
    
    def _on_upload_completed(self, task_id: str, file_path: str) -> None:
        """Handle upload completed."""
        file_name = file_path.split("/")[-1]
        self._set_status(f"Uploaded {file_name}")
        
        # Update batch progress
        self._upload_completed_files += 1
        if self._upload_total_files > 0:
            batch_progress = int((self._upload_completed_files / self._upload_total_files) * 100)
            
            # Animate to the new batch progress
            if self._progress_animation:
                self._progress_animation.stop()
                self._progress_animation.setStartValue(self._progress_bar.value())
                self._progress_animation.setEndValue(batch_progress)
                self._progress_animation.start()
            else:
                self._progress_bar.setValue(batch_progress)
            
            # Check if all expected files are done
            if self._upload_completed_files >= self._upload_total_files:
                self._finalize_batch_upload()
    
    def _on_upload_failed(self, task_id: str, error_message: str) -> None:
        """Handle upload failed."""
        self._set_status(f"Upload failed: {error_message}")
        
        # Update batch progress even for failed files
        self._upload_completed_files += 1
        self._upload_failed_files += 1
        if self._upload_total_files > 0:
            batch_progress = int((self._upload_completed_files / self._upload_total_files) * 100)
            
            # Animate to the new batch progress
            if self._progress_animation:
                self._progress_animation.stop()
                self._progress_animation.setStartValue(self._progress_bar.value())
                self._progress_animation.setEndValue(batch_progress)
                self._progress_animation.start()
            else:
                self._progress_bar.setValue(batch_progress)
            
            # Check if all expected files are done
            if self._upload_completed_files >= self._upload_total_files:
                self._finalize_batch_upload()
    
    def _on_upload_batch_completed(self, success_count: int, fail_count: int) -> None:
        """Handle batch upload completed."""
        # Ignore batch_completed signals if we haven't finished all our expected files
        if self._upload_total_files > 0 and self._upload_completed_files < self._upload_total_files:
            return
        
        # If finalize was already called by individual completion handlers, skip
        if self._upload_total_files == 0:
            return
        
        self._finalize_batch_upload()
    
    def _finalize_batch_upload(self) -> None:
        """Finalize batch upload - show completion UI."""
        success_count = self._upload_completed_files - self._upload_failed_files
        fail_count = self._upload_failed_files
        
        # Ensure we're at 100%
        if self._progress_animation:
            self._progress_animation.stop()
            self._progress_animation.setStartValue(self._progress_bar.value())
            self._progress_animation.setEndValue(100)
            self._progress_animation.start()
        else:
            self._progress_bar.setValue(100)
        
        # Show completion message
        if fail_count == 0:
            self._set_status(f"Successfully uploaded {success_count} files")
        else:
            self._set_status(f"Uploaded {success_count} files, {fail_count} failed")
        
        # Reset upload batch tracking
        self._upload_total_files = 0
        self._upload_completed_files = 0
        self._upload_failed_files = 0
        
        # Hide after minimum display time
        if not self._progress_hide_timer.isActive():
            self._progress_hide_timer.start(1500)  # 1.5 seconds
    
    def _on_token_expired(self) -> None:
        """Handle token expired."""
        self._set_status("Session expired. Please reconnect.")
        QMessageBox.warning(
            self,
            "Session Expired",
            "Your session has expired. Please reconnect to Media Lake.",
        )
        self._show_login_dialog()
    
    def _refresh(self) -> None:
        """Refresh the current view."""
        if self._api_client:
            self._api_client.get_collections()
            self._load_assets()
    
    def _set_status(self, message: str) -> None:
        """Set the status bar message.
        
        Args:
            message: The status message.
        """
        self._status_message.setText(message)
    
    def _show_about(self) -> None:
        """Show about dialog."""
        from medialake_resolve.core.version import __version__
        
        QMessageBox.about(
            self,
            "About Media Lake for DaVinci Resolve",
            f"<h3>Media Lake for DaVinci Resolve</h3>"
            f"<p>Version {__version__}</p>"
            f"<p>A plugin for browsing, searching, and importing "
            f"Media Lake assets into DaVinci Resolve.</p>"
            f"<p>© 2025 Media Lake Team</p>",
        )
    
    def closeEvent(self, event) -> None:
        """Handle window close."""
        # Stop downloads
        if self._download_controller:
            self._download_controller.cleanup()
            
        if self._upload_controller:
            self._upload_controller.cleanup()
        
        # Cancel API requests
        if self._api_client:
            self._api_client.cancel_all_requests()
        
        # Save config
        self._config.save()
        
        event.accept()
