"""Controller for managing downloads and imports into Resolve."""

import uuid
from typing import List, Optional, Dict, Callable
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThread
from PySide6.QtNetwork import QNetworkAccessManager

from medialake_resolve.core.models import (
    Asset,
    DownloadTask,
    DownloadStatus,
    AssetVariant,
)
from medialake_resolve.core.config import Config
from medialake_resolve.download.download_worker import DownloadWorker, DownloadThread
from medialake_resolve.resolve.connection import ResolveConnection
from medialake_resolve.resolve.project_settings import ResolveProjectSettings
from medialake_resolve.resolve.media_importer import ResolveMediaImporter


class DownloadImportController(QObject):
    """Orchestrates downloading assets and importing them into Resolve.
    
    Features:
    - Queue management for batch downloads (max 50 per batch)
    - Concurrent download limiting
    - Progress tracking
    - Automatic import to Resolve Media Pool
    - Proxy linking
    
    Signals:
        queue_updated: Emitted when download queue changes. (pending_count, active_count)
        download_started: Emitted when a download starts. (task_id, asset_name)
        download_progress: Emitted for progress updates. (task_id, progress_percent)
        download_completed: Emitted on completion. (task_id, file_path)
        download_failed: Emitted on failure. (task_id, error_message)
        batch_completed: Emitted when all downloads in batch complete. (success_count, fail_count)
        import_completed: Emitted when import to Resolve completes. (task_id, success)
    """
    
    # Maximum assets per batch
    MAX_BATCH_SIZE = 50
    
    # Signals
    queue_updated = Signal(int, int)
    download_started = Signal(str, str)
    download_progress = Signal(str, float)
    download_completed = Signal(str, str)
    download_failed = Signal(str, str)
    batch_completed = Signal(int, int)
    import_completed = Signal(str, bool)
    
    def __init__(
        self,
        config: Config,
        token_provider: Callable[[], Optional[str]],
        parent: Optional[QObject] = None,
    ):
        """Initialize download controller.
        
        Args:
            config: Application configuration.
            token_provider: Callable that returns current access token.
            parent: Parent QObject.
        """
        super().__init__(parent)
        
        self._config = config
        self._token_provider = token_provider
        
        # Download queue and tracking
        self._pending_tasks: List[DownloadTask] = []
        self._active_tasks: Dict[str, DownloadTask] = {}
        self._completed_tasks: Dict[str, DownloadTask] = {}
        
        # Workers and threads for concurrent downloads
        self._workers: List[DownloadWorker] = []
        self._threads: List[DownloadThread] = []
        
        # Resolve integration
        self._resolve_connection: Optional[ResolveConnection] = None
        self._project_settings: Optional[ResolveProjectSettings] = None
        self._media_importer: Optional[ResolveMediaImporter] = None
        
        # Track original/proxy pairs for linking
        self._proxy_link_map: Dict[str, str] = {}  # original_task_id -> proxy_path
        
        # Track downloaded originals by asset ID for later proxy linking
        self._downloaded_originals: Dict[str, str] = {}  # asset_id -> original_file_path
        
        # Track downloaded proxies by asset ID for linking when original is downloaded later
        self._downloaded_proxies: Dict[str, str] = {}  # asset_id -> proxy_file_path
        
        # Initialize workers
        self._init_workers()
    
    def _init_workers(self) -> None:
        """Initialize download workers and threads."""
        for i in range(self._config.max_concurrent_downloads):
            thread = DownloadThread(self)
            worker = DownloadWorker()
            worker.moveToThread(thread)
            
            # Connect worker signals
            worker.download_started.connect(self._on_worker_started)
            worker.download_progress.connect(self._on_worker_progress)
            worker.download_completed.connect(self._on_worker_completed)
            worker.download_failed.connect(self._on_worker_failed)
            worker.download_cancelled.connect(self._on_worker_cancelled)
            
            self._workers.append(worker)
            self._threads.append(thread)
            thread.start()
    
    def set_resolve_connection(self, connection: ResolveConnection) -> None:
        """Set the Resolve connection for imports.
        
        Args:
            connection: ResolveConnection instance.
        """
        self._resolve_connection = connection
        self._project_settings = ResolveProjectSettings(connection)
        self._media_importer = ResolveMediaImporter(connection)
    
    def queue_download(
        self,
        asset: Asset,
        variant: AssetVariant = AssetVariant.ORIGINAL,
        destination_path: Optional[str] = None,
    ) -> Optional[DownloadTask]:
        """Add an asset to the download queue.
        
        Args:
            asset: The asset to download.
            variant: Whether to download original or proxy.
            destination_path: Custom destination path. Auto-determined if not provided.
            
        Returns:
            The created DownloadTask, or None if queue is full.
        """
        # Check batch size limit
        total_queued = len(self._pending_tasks) + len(self._active_tasks)
        if total_queued >= self.MAX_BATCH_SIZE:
            return None
        
        # Determine destination path
        if not destination_path:
            destination_path = self._get_download_path(asset, variant)
        
        # Create task
        task = DownloadTask(
            task_id=str(uuid.uuid4()),
            asset=asset,
            variant=variant,
            destination_path=destination_path,
            status=DownloadStatus.PENDING,
        )
        
        # Set total bytes if known
        if variant == AssetVariant.PROXY and asset.proxy_file_size:
            task.total_bytes = asset.proxy_file_size
        elif variant == AssetVariant.ORIGINAL:
            task.total_bytes = asset.file_size
        
        self._pending_tasks.append(task)
        self._emit_queue_updated()
        
        # Try to start download
        self._process_queue()
        
        return task
    
    def queue_downloads(
        self,
        assets: List[Asset],
        variant: AssetVariant = AssetVariant.ORIGINAL,
    ) -> List[DownloadTask]:
        """Queue multiple assets for download.
        
        Args:
            assets: List of assets to download.
            variant: Whether to download originals or proxies.
            
        Returns:
            List of created DownloadTasks.
        """
        # Limit to max batch size
        assets_to_queue = assets[:self.MAX_BATCH_SIZE]
        
        tasks = []
        for asset in assets_to_queue:
            task = self.queue_download(asset, variant)
            if task:
                tasks.append(task)
        
        return tasks
    
    def queue_download_with_proxy(
        self,
        asset: Asset,
    ) -> tuple:
        """Queue both original and proxy for download, with auto-linking.
        
        Args:
            asset: The asset to download.
            
        Returns:
            Tuple of (original_task, proxy_task) or (None, None) if failed.
        """
        if not asset.has_proxy:
            # No proxy available, just download original
            original_task = self.queue_download(asset, AssetVariant.ORIGINAL)
            return (original_task, None)
        
        # Queue original
        original_task = self.queue_download(asset, AssetVariant.ORIGINAL)
        if not original_task:
            return (None, None)
        
        # Queue proxy
        proxy_task = self.queue_download(asset, AssetVariant.PROXY)
        
        if proxy_task:
            # Track for linking after both complete
            self._proxy_link_map[original_task.task_id] = proxy_task.destination_path
        
        return (original_task, proxy_task)
    
    def cancel_download(self, task_id: str) -> bool:
        """Cancel a pending or active download.
        
        Args:
            task_id: The task ID to cancel.
            
        Returns:
            True if task was cancelled.
        """
        # Check pending tasks
        for i, task in enumerate(self._pending_tasks):
            if task.task_id == task_id:
                task.status = DownloadStatus.CANCELLED
                self._pending_tasks.pop(i)
                self._emit_queue_updated()
                return True
        
        # Check active tasks
        if task_id in self._active_tasks:
            # Find worker handling this task and cancel
            for worker in self._workers:
                if (worker._current_task and 
                    worker._current_task.task_id == task_id):
                    worker.cancel()
                    return True
        
        return False
    
    def cancel_all(self) -> None:
        """Cancel all pending and active downloads."""
        # Cancel all pending
        for task in self._pending_tasks:
            task.status = DownloadStatus.CANCELLED
        self._pending_tasks.clear()
        
        # Cancel all active
        for worker in self._workers:
            worker.cancel()
        
        self._emit_queue_updated()
    
    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """Get a task by ID.
        
        Args:
            task_id: The task ID.
            
        Returns:
            The DownloadTask or None.
        """
        # Check pending
        for task in self._pending_tasks:
            if task.task_id == task_id:
                return task
        
        # Check active
        if task_id in self._active_tasks:
            return self._active_tasks[task_id]
        
        # Check completed
        if task_id in self._completed_tasks:
            return self._completed_tasks[task_id]
        
        return None
    
    def get_queue_status(self) -> dict:
        """Get current queue status.
        
        Returns:
            Dict with queue statistics.
        """
        return {
            "pending": len(self._pending_tasks),
            "active": len(self._active_tasks),
            "completed": len([t for t in self._completed_tasks.values() 
                            if t.status == DownloadStatus.COMPLETED]),
            "failed": len([t for t in self._completed_tasks.values() 
                          if t.status == DownloadStatus.FAILED]),
        }
    
    def _get_download_path(self, asset: Asset, variant: AssetVariant) -> str:
        """Determine download path based on Resolve project settings.
        
        Args:
            asset: The asset being downloaded.
            variant: Original or proxy variant.
            
        Returns:
            Absolute path for download destination.
        """
        # Check if name already includes extension
        if asset.file_extension and asset.name.lower().endswith(f".{asset.file_extension.lower()}"):
            filename = asset.name
        else:
            filename = f"{asset.name}.{asset.file_extension}" if asset.file_extension else asset.name
        
        # Try to use Resolve project settings, fall back to config cache if unavailable
        if self._project_settings:
            try:
                if variant == AssetVariant.PROXY:
                    return str(self._project_settings.get_proxy_download_path(filename))
                else:
                    return str(self._project_settings.get_original_download_path(filename))
            except Exception as e:
                print(f"  [Controller] Could not get Resolve path, using fallback: {e}")
                # Fall through to use config cache directory
        
        # Fallback to config cache directory
        if variant == AssetVariant.PROXY:
            return str(self._config.download_cache_dir / "proxies" / filename)
        else:
            return str(self._config.download_cache_dir / "originals" / filename)
    
    def _process_queue(self) -> None:
        """Process pending downloads if workers are available."""
        print(f"  [Controller] _process_queue called, pending: {len(self._pending_tasks)}, workers: {len(self._workers)}")
        
        for i, worker in enumerate(self._workers):
            if not self._pending_tasks:
                break
            
            # Check if worker is idle
            print(f"  [Controller] Worker {i} current_task: {worker._current_task}")
            if worker._current_task is None:
                task = self._pending_tasks.pop(0)
                self._active_tasks[task.task_id] = task
                
                print(f"  [Controller] Assigning task {task.task_id} to worker {i}")
                print(f"  [Controller] Task download_url: {task.download_url[:80] if task.download_url else 'NONE'}...")
                
                # Start download
                token = self._token_provider()
                worker.download(task, token)
                print(f"  [Controller] Called worker.download()")
        
        self._emit_queue_updated()
    
    def _on_worker_started(self, task_id: str) -> None:
        """Handle worker download started."""
        task = self._active_tasks.get(task_id)
        if task:
            self.download_started.emit(task_id, task.asset.name)
    
    def _on_worker_progress(self, task_id: str, bytes_downloaded: int, total_bytes: int) -> None:
        """Handle worker progress update."""
        if total_bytes > 0:
            progress = (bytes_downloaded / total_bytes) * 100
            self.download_progress.emit(task_id, progress)
    
    def _on_worker_completed(self, task_id: str, file_path: str) -> None:
        """Handle worker download completed."""
        task = self._active_tasks.pop(task_id, None)
        if task:
            self._completed_tasks[task_id] = task
            self.download_completed.emit(task_id, file_path)
            
            # Auto-import to Resolve if enabled
            if self._config.auto_import_to_resolve:
                self._import_to_resolve(task)
            
            # Check if this completes a batch
            self._check_batch_complete()
        
        # Process more from queue
        self._process_queue()
    
    def _on_worker_failed(self, task_id: str, error_message: str) -> None:
        """Handle worker download failed."""
        task = self._active_tasks.pop(task_id, None)
        if task:
            self._completed_tasks[task_id] = task
            self.download_failed.emit(task_id, error_message)
            
            # Check if this completes a batch
            self._check_batch_complete()
        
        # Process more from queue
        self._process_queue()
    
    def _on_worker_cancelled(self, task_id: str) -> None:
        """Handle worker download cancelled."""
        task = self._active_tasks.pop(task_id, None)
        if task:
            self._completed_tasks[task_id] = task
        
        # Process more from queue
        self._process_queue()
    
    def _import_to_resolve(self, task: DownloadTask) -> None:
        """Import completed download into Resolve Media Pool.
        
        Args:
            task: The completed download task.
        """
        if not self._media_importer:
            self.import_completed.emit(task.task_id, False)
            return
        
        try:
            # Build metadata from asset
            metadata = {
                "MediaLake Asset ID": task.asset.asset_id,
                "MediaLake Collection": task.asset.collection_id,
            }
            
            # Check if this is a proxy
            if task.variant == AssetVariant.PROXY:
                # Track this proxy for later linking if original is downloaded afterward
                self._downloaded_proxies[task.asset.asset_id] = task.destination_path
                
                # Check if the original was already downloaded (either in this session
                # via queue_download_with_proxy, or separately)
                original_path = self._downloaded_originals.get(task.asset.asset_id)
                
                if original_path and self._config.auto_link_proxies:
                    # Link proxy to the existing original in Media Pool
                    print(f"  [Controller] Linking proxy to original: {original_path}")
                    try:
                        result = self._media_importer.link_proxy_to_original(
                            original_path,
                            task.destination_path,
                        )
                        success = result if result else False
                        self.import_completed.emit(task.task_id, success)
                    except Exception as e:
                        print(f"  [Controller] Failed to link proxy: {e}")
                        # Fall back to importing as standalone
                        results = self._media_importer.import_media(
                            [task.destination_path],
                            {task.destination_path: metadata},
                        )
                        result = results[0] if results else None
                        success = result.success if result else False
                        self.import_completed.emit(task.task_id, success)
                else:
                    # No original found yet, import proxy as standalone
                    # It will be linked when the original is downloaded later
                    print(f"  [Controller] Importing proxy as standalone (original not yet downloaded)")
                    results = self._media_importer.import_media(
                        [task.destination_path],
                        {task.destination_path: metadata},
                    )
                    result = results[0] if results else None
                    success = result.success if result else False
                    self.import_completed.emit(task.task_id, success)
                return
            
            # For originals, track the download path for future proxy linking
            self._downloaded_originals[task.asset.asset_id] = task.destination_path
            
            # Check if we have a proxy to link:
            # 1. From queue_download_with_proxy (same batch)
            # 2. From a previously downloaded proxy (downloaded separately before original)
            proxy_path = self._proxy_link_map.pop(task.task_id, None)
            
            # Also check if a proxy was downloaded separately before this original
            previously_imported_proxy = False
            if not proxy_path:
                proxy_path = self._downloaded_proxies.get(task.asset.asset_id)
                if proxy_path:
                    previously_imported_proxy = True
            
            if proxy_path and self._config.auto_link_proxies:
                # If proxy was previously imported as standalone, we need to:
                # 1. Remove the standalone proxy from Media Pool
                # 2. Import original with proxy linked
                if previously_imported_proxy:
                    print(f"  [Controller] Removing standalone proxy from Media Pool: {proxy_path}")
                    self._media_importer.remove_media_by_path(proxy_path)
                
                # Import with proxy linking
                result = self._media_importer.import_with_proxy(
                    task.destination_path,
                    proxy_path,
                    metadata,
                )
            else:
                # Import without proxy
                results = self._media_importer.import_media(
                    [task.destination_path],
                    {task.destination_path: metadata},
                )
                result = results[0] if results else None
            
            success = result.success if result else False
            self.import_completed.emit(task.task_id, success)
            
        except Exception as e:
            print(f"Import error: {e}")
            self.import_completed.emit(task.task_id, False)
    
    def _check_batch_complete(self) -> None:
        """Check if all downloads in batch are complete."""
        if not self._pending_tasks and not self._active_tasks:
            success_count = len([t for t in self._completed_tasks.values() 
                               if t.status == DownloadStatus.COMPLETED])
            fail_count = len([t for t in self._completed_tasks.values() 
                            if t.status == DownloadStatus.FAILED])
            
            # Clear completed tasks to prevent duplicate batch_completed signals
            self._completed_tasks.clear()
            
            self.batch_completed.emit(success_count, fail_count)
    
    def _emit_queue_updated(self) -> None:
        """Emit queue updated signal."""
        self.queue_updated.emit(
            len(self._pending_tasks),
            len(self._active_tasks)
        )
    
    def cleanup(self) -> None:
        """Clean up workers and threads."""
        self.cancel_all()
        
        for thread in self._threads:
            thread.quit()
            thread.wait()
        
        self._workers.clear()
        self._threads.clear()
