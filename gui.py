"""Jednoduché Tk GUI pro lokálního hlasového asistenta."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from llama_module import (
    ANALYTICAL_PRESETS,
    DEFAULT_ANALYTICAL_PRESET,
    generate_response,
)


class AssistantGUI(tk.Tk):
    """GUI s výběrem modelu, online režimu a analytické metodiky."""

    def __init__(self, llm, config: dict):
        super().__init__()
        self.llm = llm
        self.config = config
        llama_config = config.setdefault("llama", {})
        self.selected_model = tk.StringVar(value=str(llama_config.get("model", "")))
        self.online_mode = tk.BooleanVar(value=bool(llama_config.get("online_mode", False)))
        self.analytical_preset = tk.StringVar(
            value=str(
                llama_config.get("analytical_preset", DEFAULT_ANALYTICAL_PRESET)
            )
        )
        self._create_widgets()

    def _create_widgets(self):
        self.title("Český hlasový asistent")
        self.geometry("760x560")

        sidebar = ttk.Frame(self, padding=12)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Label(sidebar, text="Model").pack(anchor="w")
        ttk.Entry(sidebar, textvariable=self.selected_model, width=28).pack(
            fill=tk.X, pady=(0, 12)
        )
        ttk.Checkbutton(
            sidebar, text="Online režim", variable=self.online_mode
        ).pack(anchor="w", pady=(0, 12))
        ttk.Label(sidebar, text="Analytická metodika").pack(anchor="w")
        ttk.Combobox(
            sidebar,
            textvariable=self.analytical_preset,
            values=list(ANALYTICAL_PRESETS),
            state="readonly",
            width=28,
        ).pack(fill=tk.X)

        content = ttk.Frame(self, padding=(0, 12, 12, 12))
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.output = scrolledtext.ScrolledText(content, state=tk.DISABLED, wrap=tk.WORD)
        self.output.pack(fill=tk.BOTH, expand=True)
        self.input = ttk.Entry(content)
        self.input.pack(fill=tk.X, pady=(12, 0))
        self.input.bind("<Return>", lambda _event: self.send_message())
        ttk.Button(content, text="Odeslat", command=self.send_message).pack(
            anchor="e", pady=(8, 0)
        )

    def send_message(self):
        user_text = self.input.get().strip()
        if not user_text:
            return
        self.input.delete(0, tk.END)
        llama_config = self.config.setdefault("llama", {})
        llama_config.update(
            {
                "model": self.selected_model.get().strip(),
                "online_mode": self.online_mode.get(),
                "analytical_preset": self.analytical_preset.get(),
            }
        )
        self._append(f"Vy: {user_text}\n")
        threading.Thread(
            target=self._generate_in_background,
            args=(user_text,),
            daemon=True,
        ).start()

    def _generate_in_background(self, user_text: str):
        try:
            response = generate_response(self.llm, user_text, self.config)
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Generování", str(exc)))
            return
        self.after(0, lambda: self._append(f"Asistent: {response}\n"))

    def _append(self, text: str):
        self.output.configure(state=tk.NORMAL)
        self.output.insert(tk.END, text)
        self.output.see(tk.END)
        self.output.configure(state=tk.DISABLED)


def launch_gui(llm, config: dict) -> None:
    """Spustí GUI a předá řízení Tk event loopu."""
    app = AssistantGUI(llm, config)
    app.mainloop()
