"""Progress dialog for CBRO Parser processing."""

import tkinter as tk
from tkinter import ttk


class ProgressDialog:
    """Modal dialog showing processing progress."""

    def __init__(self, parent: tk.Tk, title: str, total_items: int):
        """
        Initialize the progress dialog.

        Args:
            parent: Parent window.
            title: Dialog title.
            total_items: Total number of items to process.
        """
        self.parent = parent
        self.total_items = total_items
        self.cancelled = False

        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x350")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Prevent closing with X button during processing
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Center on parent
        self._center_on_parent()

        # Build UI
        self._build_ui()

    def _center_on_parent(self) -> None:
        """Center dialog on parent window."""
        self.dialog.update_idletasks()

        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_w = self.parent.winfo_width()
        parent_h = self.parent.winfo_height()

        dialog_w = self.dialog.winfo_width()
        dialog_h = self.dialog.winfo_height()

        x = parent_x + (parent_w - dialog_w) // 2
        y = parent_y + (parent_h - dialog_h) // 2

        self.dialog.geometry(f"+{x}+{y}")

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        main_frame = ttk.Frame(self.dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Current item label
        self.current_label = ttk.Label(
            main_frame, text="Starting...", font=("TkDefaultFont", 10, "bold")
        )
        self.current_label.pack(anchor=tk.W)

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            main_frame,
            variable=self.progress_var,
            maximum=self.total_items,
            mode="determinate",
        )
        self.progress_bar.pack(fill=tk.X, pady=(10, 5))

        # Progress text
        self.progress_text = ttk.Label(main_frame, text="0 / 0")
        self.progress_text.pack(anchor=tk.W)

        # Log area
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 10))

        self.log_text = tk.Text(
            log_frame,
            height=10,
            width=50,
            state=tk.DISABLED,
            wrap=tk.WORD,
            font=("TkFixedFont", 9),
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        log_scrollbar = ttk.Scrollbar(
            log_frame, orient=tk.VERTICAL, command=self.log_text.yview
        )
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=log_scrollbar.set)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        self.cancel_btn = ttk.Button(
            button_frame, text="Cancel", command=self._on_cancel
        )
        self.cancel_btn.pack(side=tk.RIGHT)

        self.close_btn = ttk.Button(
            button_frame, text="Close", command=self._on_close, state=tk.DISABLED
        )
        self.close_btn.pack(side=tk.RIGHT, padx=(0, 10))

    def update(self, current: int, message: str) -> None:
        """
        Update progress.

        Args:
            current: Current item index (0-based).
            message: Status message.
        """
        self.progress_var.set(current)
        self.current_label.config(text=message)
        self.progress_text.config(text=f"{current + 1} / {self.total_items}")
        self.dialog.update()

    def log(self, message: str) -> None:
        """
        Add a message to the log.

        Args:
            message: Message to log.
        """
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.dialog.update()

    def complete(self, message: str) -> None:
        """
        Mark processing as complete.

        Args:
            message: Completion message.
        """
        self.progress_var.set(self.total_items)
        self.current_label.config(text=message)
        self.progress_text.config(
            text=f"{self.total_items} / {self.total_items}"
        )

        # Enable close button, disable cancel
        self.cancel_btn.config(state=tk.DISABLED)
        self.close_btn.config(state=tk.NORMAL)

        self.dialog.update()

    def _on_cancel(self) -> None:
        """Handle cancel button or window close."""
        self.cancelled = True
        self.current_label.config(text="Cancelling...")
        self.cancel_btn.config(state=tk.DISABLED)

    def _on_close(self) -> None:
        """Handle close button."""
        self.dialog.destroy()
