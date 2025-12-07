"""Main tkinter GUI application for CBRO Parser."""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import requests

from ..cache.sqlite_cache import SQLiteCache
from ..cbl.writer import CBLWriter
from ..comicvine.api_client import ComicVineClient
from ..comicvine.matcher import SeriesMatcher
from ..comicvine.rate_limiter import RateLimiter
from ..config import Config, get_config
from ..models import MatchedBook, ReadingList, ReadingOrderEntry
from ..scraper.cbro_scraper import CBROScraper
from ..scraper.index_scraper import IndexScraper
from .progress_dialog import ProgressDialog
from .thread_manager import ThreadManager


class CBROParserApp:
    """Main GUI application for CBRO Parser."""

    def __init__(self, root: tk.Tk):
        """
        Initialize the application.

        Args:
            root: The root tkinter window.
        """
        self.root = root
        self.root.title("CBRO Parser - Comic Book Reading Order Parser")
        self.root.geometry("700x600")
        self.root.minsize(600, 500)

        # Initialize config
        try:
            self.config = get_config()
        except ValueError as e:
            messagebox.showerror(
                "Configuration Error",
                f"Failed to load configuration:\n\n{e}\n\n"
                "Please ensure your .env file contains COMICVINE_API.",
            )
            self.root.destroy()
            return

        # Initialize components
        self.cache = SQLiteCache(
            self.config.cache_db_path, self.config.cache_expiry_days
        )
        self.rate_limiter = RateLimiter(
            max_requests=self.config.cv_rate_limit_requests,
            window_seconds=self.config.cv_rate_limit_window_seconds,
            min_interval=self.config.cv_safe_delay_seconds,
        )

        # Thread management for proper cleanup
        self.thread_manager = ThreadManager()

        # Set up window close handler for graceful shutdown
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Data
        self.reading_orders: list[ReadingOrderEntry] = []
        self.filtered_orders: list[ReadingOrderEntry] = []
        self.selected_items: set[str] = set()  # URLs of selected items

        # Build UI
        self._build_ui()

        # Start loading reading orders in background
        self._start_loading_orders()

    def _build_ui(self) -> None:
        """Build the user interface."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Output directory row
        dir_frame = ttk.Frame(main_frame)
        dir_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(dir_frame, text="Output Directory:").pack(side=tk.LEFT)

        self.output_dir_var = tk.StringVar(
            value=str(self.config.default_output_dir.absolute())
        )
        self.output_dir_entry = ttk.Entry(
            dir_frame, textvariable=self.output_dir_var, width=50
        )
        self.output_dir_entry.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)

        ttk.Button(dir_frame, text="Browse", command=self._browse_output_dir).pack(
            side=tk.LEFT
        )

        # Filter row
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT)

        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", self._on_filter_changed)
        self.filter_entry = ttk.Entry(
            filter_frame, textvariable=self.filter_var, width=25
        )
        self.filter_entry.pack(side=tk.LEFT, padx=(10, 15))

        ttk.Label(filter_frame, text="Publisher:").pack(side=tk.LEFT)

        self.publisher_var = tk.StringVar(value="All")
        self.publisher_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.publisher_var,
            values=["All", "Marvel", "DC", "Other"],
            state="readonly",
            width=8,
        )
        self.publisher_combo.pack(side=tk.LEFT, padx=(5, 15))
        self.publisher_combo.bind("<<ComboboxSelected>>", self._on_filter_changed)

        ttk.Label(filter_frame, text="Category:").pack(side=tk.LEFT)

        self.category_var = tk.StringVar(value="All")
        self.category_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.category_var,
            values=["All", "Characters", "Events", "Master Reading Order"],
            state="readonly",
            width=18,
        )
        self.category_combo.pack(side=tk.LEFT, padx=(5, 0))
        self.category_combo.bind("<<ComboboxSelected>>", self._on_filter_changed)

        # Select all checkbox
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill=tk.X)

        self.select_all_var = tk.BooleanVar()
        self.select_all_check = ttk.Checkbutton(
            select_frame,
            text="Select All",
            variable=self.select_all_var,
            command=self._toggle_select_all,
        )
        self.select_all_check.pack(side=tk.LEFT)

        # List frame with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

        # Create a canvas with scrollbar for the checkbox list
        self.canvas = tk.Canvas(list_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.canvas.yview
        )
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor=tk.NW)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

        # Status bar
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(0, 10))

        self.selected_label = ttk.Label(status_frame, text="Selected: 0")
        self.selected_label.pack(side=tk.LEFT)

        self.api_label = ttk.Label(
            status_frame,
            text=f"API Remaining: {self.rate_limiter.remaining_requests()}/200",
        )
        self.api_label.pack(side=tk.RIGHT)

        self.status_label = ttk.Label(status_frame, text="Loading reading orders...")
        self.status_label.pack(side=tk.LEFT, padx=(20, 0))

        # Button row
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        self.generate_btn = ttk.Button(
            button_frame,
            text="Generate Reading Lists",
            command=self._generate_reading_lists,
            state=tk.DISABLED,
        )
        self.generate_btn.pack(side=tk.LEFT)

        ttk.Button(button_frame, text="Exit", command=self.root.quit).pack(
            side=tk.RIGHT
        )

        ttk.Button(
            button_frame, text="Refresh List", command=self._refresh_orders
        ).pack(side=tk.RIGHT, padx=(0, 10))

    def _browse_output_dir(self) -> None:
        """Open directory browser for output directory."""
        directory = filedialog.askdirectory(
            initialdir=self.output_dir_var.get(),
            title="Select Output Directory",
        )
        if directory:
            self.output_dir_var.set(directory)

    def _on_filter_changed(self, *args) -> None:
        """Handle filter text or publisher change."""
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Apply current filter to the reading order list."""
        filter_text = self.filter_var.get().lower().strip()
        publisher = self.publisher_var.get()
        category = self.category_var.get()

        self.filtered_orders = []
        for order in self.reading_orders:
            # Check publisher filter
            if publisher != "All":
                if publisher == "Other":
                    # "Other" means not Marvel and not DC
                    if order.publisher in ("Marvel", "DC"):
                        continue
                elif order.publisher != publisher:
                    continue

            # Check category filter
            if category != "All":
                # Map display category to data category
                category_map = {
                    "Characters": "characters",
                    "Events": "events",
                    "Master Reading Order": "master",
                }
                expected_category = category_map.get(category, category.lower())
                if order.category != expected_category:
                    continue

            # Check text filter
            if filter_text and filter_text not in order.name.lower():
                continue

            self.filtered_orders.append(order)

        self._rebuild_list()

    def _rebuild_list(self) -> None:
        """Rebuild the checkbox list with filtered items."""
        # Clear existing checkboxes
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Create new checkboxes
        self.checkboxes: dict[str, tk.BooleanVar] = {}

        for order in self.filtered_orders:
            var = tk.BooleanVar(value=order.url in self.selected_items)
            self.checkboxes[order.url] = var

            cb = ttk.Checkbutton(
                self.scrollable_frame,
                text=order.display_name(),
                variable=var,
                command=lambda url=order.url: self._on_item_toggled(url),
            )
            cb.pack(anchor=tk.W, pady=1)

        self._update_status()

    def _on_item_toggled(self, url: str) -> None:
        """Handle individual checkbox toggle."""
        if self.checkboxes[url].get():
            self.selected_items.add(url)
        else:
            self.selected_items.discard(url)

        self._update_status()

    def _toggle_select_all(self) -> None:
        """Toggle select all checkbox."""
        select = self.select_all_var.get()

        for url, var in self.checkboxes.items():
            var.set(select)
            if select:
                self.selected_items.add(url)
            else:
                self.selected_items.discard(url)

        self._update_status()

    def _update_status(self) -> None:
        """Update status bar labels."""
        self.selected_label.config(text=f"Selected: {len(self.selected_items)}")
        self.api_label.config(
            text=f"API Remaining: {self.rate_limiter.remaining_requests()}/200"
        )

        # Enable/disable generate button
        if self.selected_items:
            self.generate_btn.config(state=tk.NORMAL)
        else:
            self.generate_btn.config(state=tk.DISABLED)

    def _on_mousewheel(self, event) -> None:
        """Handle mouse wheel scrolling."""
        if event.num == 4:  # Linux scroll up
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:  # Linux scroll down
            self.canvas.yview_scroll(1, "units")
        else:  # Windows/Mac
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _start_loading_orders(self) -> None:
        """Start loading reading orders - from cache first, then refresh."""
        # Try to load from cache first for instant startup
        scraper = IndexScraper(self.config)
        cached = scraper.load_cached_orders()

        if cached:
            self.reading_orders = cached
            self.filtered_orders = cached.copy()
            self.status_label.config(
                text=f"Loaded {len(cached)} reading orders (from cache, refreshing...)"
            )
            self._rebuild_list()

        # Start background refresh with proper thread management
        self.thread_manager.start_thread("load_orders", self._load_orders_thread)

    def _load_orders_thread(self, shutdown_event: threading.Event) -> None:
        """Background thread to fetch fresh reading orders."""
        try:
            # Check for early shutdown
            if shutdown_event.is_set():
                return

            scraper = IndexScraper(self.config)
            fresh_orders = scraper.fetch_all_reading_orders(
                progress_callback=self._loading_progress_callback
            )

            # Check for shutdown before updating UI
            if shutdown_event.is_set():
                return

            # Update with fresh data
            self.reading_orders = fresh_orders
            self.filtered_orders = fresh_orders.copy()

            # Update UI on main thread
            self.root.after(0, self._on_orders_loaded)
        except requests.RequestException as e:
            if shutdown_event.is_set():
                return
            # If we have cached data, just show a warning
            if self.reading_orders:
                self.root.after(
                    0,
                    lambda: self.status_label.config(
                        text=f"Using cached data ({len(self.reading_orders)} orders) - refresh failed"
                    ),
                )
            else:
                self.root.after(
                    0, lambda: self._on_loading_error(f"Network error: {e}")
                )
        except OSError as e:
            if shutdown_event.is_set():
                return
            self.root.after(0, lambda: self._on_loading_error(f"File error: {e}"))

    def _loading_progress_callback(
        self, current: int, total: int, message: str
    ) -> None:
        """Callback for loading progress updates."""
        self.root.after(
            0,
            lambda: self.status_label.config(text=f"Refreshing: {message}"),
        )

    def _on_orders_loaded(self) -> None:
        """Called when reading orders are loaded."""
        self.status_label.config(
            text=f"Loaded {len(self.reading_orders)} reading orders"
        )
        self._rebuild_list()
        self._apply_filter()  # Reapply current filter

    def _on_loading_error(self, error: str) -> None:
        """Called when loading fails."""
        self.status_label.config(text=f"Error: {error}")
        messagebox.showerror(
            "Loading Error", f"Failed to load reading orders:\n\n{error}"
        )

    def _refresh_orders(self) -> None:
        """Refresh the reading order list."""
        self.status_label.config(text="Refreshing reading orders...")
        self._start_loading_orders()

    def _generate_reading_lists(self) -> None:
        """Generate reading lists for selected items."""
        if not self.selected_items:
            messagebox.showwarning(
                "No Selection", "Please select at least one reading order."
            )
            return

        output_dir = Path(self.output_dir_var.get())
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True)
            except OSError as e:
                messagebox.showerror(
                    "Error", f"Failed to create output directory:\n\n{e}"
                )
                return

        # Get selected orders
        selected_orders = [
            order for order in self.reading_orders if order.url in self.selected_items
        ]

        # Show progress dialog and start processing
        progress = ProgressDialog(
            self.root, "Generating Reading Lists", len(selected_orders)
        )

        self.thread_manager.start_thread(
            "generate_lists",
            self._generate_thread,
            args=(selected_orders, output_dir, progress),
        )

    def _generate_thread(
        self,
        shutdown_event: threading.Event,
        orders: list[ReadingOrderEntry],
        output_dir: Path,
        progress: ProgressDialog,
    ) -> None:
        """Background thread for generating reading lists."""
        cv_client = ComicVineClient(self.config, self.rate_limiter)
        scraper = CBROScraper(self.config)
        matcher = SeriesMatcher(cv_client, self.cache, interactive=False)
        writer = CBLWriter()

        successful = 0
        failed = 0

        for i, order in enumerate(orders):
            if progress.cancelled or shutdown_event.is_set():
                break

            # Update progress
            self.root.after(
                0,
                lambda o=order, idx=i: progress.update(idx, f"Processing: {o.name}"),
            )

            try:
                # Fetch and parse reading order
                parsed_issues = scraper.fetch_reading_order(order.url)

                # Log parsing result
                self.root.after(
                    0,
                    lambda o=order, t=len(parsed_issues): progress.log(
                        f"Parsed {o.name}: found {t} issues"
                    ),
                )

                # Match issues - keep all in original order
                all_books = []
                unmatched_series = {}  # series -> list of issue numbers
                matched_count = 0

                for parsed in parsed_issues:
                    matched = matcher.match_issue(parsed)
                    if matched:
                        all_books.append(matched)
                        matched_count += 1
                    else:
                        # Create unmatched book entry to preserve reading order
                        unmatched_book = MatchedBook(
                            series=parsed.series_name,
                            number=parsed.issue_number,
                            volume=parsed.volume_hint or parsed.year_hint or "0",
                            year=parsed.year_hint or "0",
                            format_type=parsed.format_type,
                            confidence=0.0,
                        )
                        all_books.append(unmatched_book)
                        # Track for logging
                        if parsed.series_name not in unmatched_series:
                            unmatched_series[parsed.series_name] = []
                        unmatched_series[parsed.series_name].append(parsed.issue_number)

                # Create reading list with all issues
                reading_list = ReadingList(name=order.name, books=all_books)

                # Write to file
                # Organize by publisher/category
                subdir = output_dir / order.publisher / order.category.title()
                output_path = subdir / f"{order.name}.cbl"
                writer.write(reading_list, output_path)

                # Log result with unmatched details
                unmatched_count = len(parsed_issues) - matched_count
                self.root.after(
                    0,
                    lambda o=order, m=matched_count, t=len(parsed_issues): progress.log(
                        f"  -> Matched: {m}/{t}"
                    ),
                )

                # Log unmatched series
                if unmatched_series:
                    for series_name, issues in list(unmatched_series.items())[:5]:
                        issue_str = ", #".join(issues[:3])
                        suffix = f"... ({len(issues)} total)" if len(issues) > 3 else ""
                        self.root.after(
                            0,
                            lambda s=series_name, i=issue_str, x=suffix: progress.log(
                                f"     Unmatched: {s} #{i}{x}"
                            ),
                        )
                    if len(unmatched_series) > 5:
                        self.root.after(
                            0,
                            lambda n=len(unmatched_series) - 5: progress.log(
                                f"     ... and {n} more series"
                            ),
                        )

                successful += 1

            except requests.RequestException as e:
                self.root.after(
                    0,
                    lambda o=order, err=str(e): progress.log(
                        f"Network error: {o.name} - {err}"
                    ),
                )
                failed += 1
            except OSError as e:
                self.root.after(
                    0,
                    lambda o=order, err=str(e): progress.log(
                        f"File error: {o.name} - {err}"
                    ),
                )
                failed += 1
            except ValueError as e:
                self.root.after(
                    0,
                    lambda o=order, err=str(e): progress.log(
                        f"Parse error: {o.name} - {err}"
                    ),
                )
                failed += 1

            # Update API remaining display
            self.root.after(0, self._update_status)

        # Complete
        self.root.after(
            0,
            lambda: progress.complete(
                f"Completed: {successful} successful, {failed} failed"
            ),
        )

    def _on_closing(self) -> None:
        """Handle window close with graceful thread shutdown."""
        # Check if any threads are running
        active_count = self.thread_manager.active_thread_count()
        if active_count > 0:
            # Give threads a chance to finish gracefully
            self.status_label.config(text="Shutting down background tasks...")
            self.root.update()
            self.thread_manager.shutdown(timeout=2.0)

        self.root.destroy()


def run_app() -> None:
    """Run the CBRO Parser GUI application."""
    root = tk.Tk()
    app = CBROParserApp(root)
    root.mainloop()


if __name__ == "__main__":
    run_app()
