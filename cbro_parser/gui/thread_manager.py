"""Thread management for GUI application with proper cleanup."""

import threading
from typing import Any, Callable


class ThreadManager:
    """Manages background threads with proper shutdown handling.

    Provides:
    - Thread tracking (know what's running)
    - Shutdown event (threads can check and exit gracefully)
    - Graceful shutdown with timeout
    - Cleanup of completed threads
    """

    def __init__(self):
        """Initialize the thread manager."""
        self._threads: dict[str, threading.Thread] = {}
        self._shutdown_event = threading.Event()
        self._lock = threading.Lock()

    def start_thread(
        self,
        name: str,
        target: Callable[[threading.Event, ...], Any],
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> threading.Thread:
        """Start a managed thread.

        Args:
            name: Unique name for this thread.
            target: Function to run. First argument will be the shutdown event.
            args: Additional positional arguments for target.
            kwargs: Additional keyword arguments for target.

        Returns:
            The started Thread object.
        """
        if kwargs is None:
            kwargs = {}

        def wrapper():
            try:
                target(self._shutdown_event, *args, **kwargs)
            finally:
                # Thread completed - will be cleaned up later
                pass

        thread = threading.Thread(target=wrapper, name=name, daemon=True)

        with self._lock:
            self._threads[name] = thread

        thread.start()
        return thread

    def active_thread_count(self) -> int:
        """Return the number of currently active threads."""
        self.cleanup_completed()
        with self._lock:
            return len(self._threads)

    def active_thread_names(self) -> list[str]:
        """Return names of currently active threads."""
        self.cleanup_completed()
        with self._lock:
            return list(self._threads.keys())

    def cleanup_completed(self) -> None:
        """Remove completed threads from tracking."""
        with self._lock:
            completed = [
                name for name, thread in self._threads.items() if not thread.is_alive()
            ]
            for name in completed:
                del self._threads[name]

    def is_shutting_down(self) -> bool:
        """Check if shutdown has been initiated."""
        return self._shutdown_event.is_set()

    def shutdown(self, timeout: float = 5.0) -> None:
        """Gracefully shutdown all managed threads.

        Args:
            timeout: Maximum seconds to wait for threads to complete.
        """
        # Signal all threads to stop
        self._shutdown_event.set()

        # Wait for each thread with proportional timeout
        with self._lock:
            threads = list(self._threads.values())

        if not threads:
            return

        per_thread_timeout = timeout / len(threads)
        for thread in threads:
            thread.join(timeout=per_thread_timeout)

        # Clean up
        self.cleanup_completed()
