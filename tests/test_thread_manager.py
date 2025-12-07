"""Tests for thread management in GUI application.

Regression tests for: Daemon Threads Without Cleanup bug
- gui/app.py:339,418 creates daemon threads with no proper shutdown handling
- Threads should be tracked, have cancellation mechanism, and clean up on shutdown
"""

import threading
import time
import pytest

from cbro_parser.gui.thread_manager import ThreadManager


class TestThreadManager:
    """Tests for ThreadManager class."""

    def test_tracks_started_threads(self):
        """Test that started threads are tracked."""
        manager = ThreadManager()

        def dummy_task(shutdown_event):
            while not shutdown_event.is_set():
                time.sleep(0.01)

        manager.start_thread("test_thread", dummy_task)

        assert manager.active_thread_count() == 1
        assert "test_thread" in manager.active_thread_names()

        manager.shutdown(timeout=1.0)

    def test_provides_shutdown_event_to_threads(self):
        """Test that threads receive a shutdown event they can check."""
        manager = ThreadManager()
        received_event = []

        def capture_event(shutdown_event):
            received_event.append(shutdown_event)
            # Exit immediately
            return

        manager.start_thread("test_thread", capture_event)
        time.sleep(0.1)  # Give thread time to start

        assert len(received_event) == 1
        assert isinstance(received_event[0], threading.Event)

        manager.shutdown(timeout=1.0)

    def test_thread_exits_on_shutdown_event(self):
        """Test that threads exit when shutdown event is set."""
        manager = ThreadManager()
        thread_running = threading.Event()
        thread_exited = threading.Event()

        def cooperative_task(shutdown_event):
            thread_running.set()
            while not shutdown_event.is_set():
                time.sleep(0.01)
            thread_exited.set()

        manager.start_thread("cooperative", cooperative_task)

        # Wait for thread to start
        assert thread_running.wait(timeout=1.0), "Thread didn't start"
        assert manager.active_thread_count() == 1

        # Trigger shutdown
        manager.shutdown(timeout=1.0)

        # Thread should have exited
        assert thread_exited.is_set(), "Thread didn't exit on shutdown"
        assert manager.active_thread_count() == 0

    def test_shutdown_waits_for_threads(self):
        """Test that shutdown waits for threads to complete."""
        manager = ThreadManager()
        work_done = threading.Event()

        def slow_task(shutdown_event):
            # Simulate some work that takes time
            time.sleep(0.1)
            work_done.set()

        manager.start_thread("slow_task", slow_task)

        # Shutdown should wait for the thread
        manager.shutdown(timeout=2.0)

        assert work_done.is_set(), "Shutdown didn't wait for thread to complete"

    def test_shutdown_respects_timeout(self):
        """Test that shutdown returns after timeout even if threads are stuck."""
        manager = ThreadManager()
        thread_started = threading.Event()

        def stuck_task(shutdown_event):
            thread_started.set()
            # Ignore shutdown event (bad behavior we need to handle)
            while True:
                time.sleep(0.1)

        manager.start_thread("stuck_task", stuck_task)
        thread_started.wait(timeout=1.0)

        start = time.time()
        manager.shutdown(timeout=0.2)
        elapsed = time.time() - start

        # Should return within timeout + some tolerance
        assert elapsed < 0.5, f"Shutdown took too long: {elapsed}s"

    def test_removes_completed_threads(self):
        """Test that completed threads are removed from tracking."""
        manager = ThreadManager()

        def quick_task(shutdown_event):
            # Exit immediately
            return

        manager.start_thread("quick", quick_task)

        # Wait for thread to complete
        time.sleep(0.1)

        # Clean up completed threads
        manager.cleanup_completed()

        assert manager.active_thread_count() == 0

    def test_multiple_threads(self):
        """Test managing multiple threads."""
        manager = ThreadManager()
        started = threading.Barrier(3)  # 2 threads + main

        def task1(shutdown_event):
            started.wait()
            while not shutdown_event.is_set():
                time.sleep(0.01)

        def task2(shutdown_event):
            started.wait()
            while not shutdown_event.is_set():
                time.sleep(0.01)

        manager.start_thread("task1", task1)
        manager.start_thread("task2", task2)

        # Wait for both to start
        started.wait(timeout=1.0)

        assert manager.active_thread_count() == 2
        assert "task1" in manager.active_thread_names()
        assert "task2" in manager.active_thread_names()

        manager.shutdown(timeout=1.0)

        assert manager.active_thread_count() == 0

    def test_is_shutting_down(self):
        """Test that is_shutting_down returns correct state."""
        manager = ThreadManager()

        assert not manager.is_shutting_down()

        manager.shutdown(timeout=0.1)

        assert manager.is_shutting_down()

    def test_thread_can_pass_additional_args(self):
        """Test that additional arguments can be passed to thread function."""
        manager = ThreadManager()
        received_args = []

        def task_with_args(shutdown_event, arg1, arg2, kwarg1=None):
            received_args.extend([arg1, arg2, kwarg1])

        manager.start_thread(
            "with_args",
            task_with_args,
            args=("hello", 42),
            kwargs={"kwarg1": "world"}
        )

        time.sleep(0.1)
        manager.shutdown(timeout=1.0)

        assert received_args == ["hello", 42, "world"]
