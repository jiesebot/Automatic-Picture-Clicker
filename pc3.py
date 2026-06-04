import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from tkinter import ttk
import threading
import time
import os
import json

import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab
from pynput import keyboard


CONFIG_FILENAME = "picture_clicker_config.json"


class PictureClickerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Automatic Picture Clicker")
        self.root.geometry("980x830")

        self.config_path = self.get_config_path()

        self.targets = []
        self.presets = {}
        self.running = False
        self.worker_thread = None

        self.hotkey_listener = None
        self.active_hotkey = None
        self.hotkey_record_window = None

        self.priority_click_counter = 0
        self.last_priority_ui_update = 0.0

        saved_state = self.load_app_state()

        settings = saved_state.get("settings", {})
        self.presets = saved_state.get("presets", {})
        self.priority_click_counter = int(saved_state.get("priority_click_counter", 0))

        self.threshold = tk.DoubleVar(value=settings.get("threshold", 0.85))
        self.scan_delay = tk.DoubleVar(value=settings.get("scan_delay", 0.03))
        self.click_delay = tk.DoubleVar(value=settings.get("click_delay", 0.02))
        self.loop_yield_delay = tk.DoubleVar(value=settings.get("loop_yield_delay", 0.005))

        self.click_all_matches = tk.BooleanVar(value=settings.get("click_all_matches", False))
        self.repeat_while_visible = tk.BooleanVar(value=settings.get("repeat_while_visible", True))
        self.dynamic_prioritization = tk.BooleanVar(value=settings.get("dynamic_prioritization", True))
        self.park_after_click = tk.BooleanVar(value=settings.get("park_after_click", True))

        self.park_x = tk.IntVar(value=settings.get("park_x", 25))
        self.park_y = tk.IntVar(value=settings.get("park_y", 25))

        self.hotkey_var = tk.StringVar(value=settings.get("hotkey", "<ctrl>+<alt>+s"))
        self.preset_var = tk.StringVar(value="")

        for target_data in saved_state.get("targets", []):
            path = target_data.get("path")
            enabled = target_data.get("enabled", True)
            last_clicked_order = target_data.get("last_clicked_order", 0)

            if path:
                self.targets.append(
                    self.load_target_from_path(
                        path,
                        enabled=enabled,
                        last_clicked_order=last_clicked_order
                    )
                )

        self.build_gui()
        self.populate_target_tree()
        self.refresh_preset_menu()
        self.start_hotkey_listener(silent=True)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def get_config_path(self):
        app_data = os.getenv("APPDATA")

        if app_data:
            config_directory = os.path.join(app_data, "PictureClicker")
        else:
            config_directory = os.path.join(os.path.expanduser("~"), ".picture_clicker")

        os.makedirs(config_directory, exist_ok=True)

        return os.path.join(config_directory, CONFIG_FILENAME)

    def load_app_state(self):
        if not os.path.exists(self.config_path):
            return {
                "settings": {},
                "targets": [],
                "presets": {},
                "priority_click_counter": 0
            }

        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:
            return {
                "settings": {},
                "targets": [],
                "presets": {},
                "priority_click_counter": 0
            }

    def save_app_state(self):
        state = {
            "settings": self.get_current_settings(),
            "targets": [
                {
                    "path": target["path"],
                    "enabled": target["enabled"],
                    "last_clicked_order": int(target.get("last_clicked_order", 0))
                }
                for target in self.targets
            ],
            "presets": self.presets,
            "priority_click_counter": int(self.priority_click_counter)
        }

        with open(self.config_path, "w", encoding="utf-8") as file:
            json.dump(state, file, indent=4)

    def get_current_settings(self):
        return {
            "threshold": self.threshold.get(),
            "scan_delay": self.scan_delay.get(),
            "click_delay": self.click_delay.get(),
            "loop_yield_delay": self.loop_yield_delay.get(),
            "click_all_matches": self.click_all_matches.get(),
            "repeat_while_visible": self.repeat_while_visible.get(),
            "dynamic_prioritization": self.dynamic_prioritization.get(),
            "park_after_click": self.park_after_click.get(),
            "park_x": self.park_x.get(),
            "park_y": self.park_y.get(),
            "hotkey": self.hotkey_var.get().strip()
        }

    def apply_settings(self, settings):
        self.threshold.set(settings.get("threshold", 0.85))
        self.scan_delay.set(settings.get("scan_delay", 0.03))
        self.click_delay.set(settings.get("click_delay", 0.02))
        self.loop_yield_delay.set(settings.get("loop_yield_delay", 0.005))

        self.click_all_matches.set(settings.get("click_all_matches", False))
        self.repeat_while_visible.set(settings.get("repeat_while_visible", True))
        self.dynamic_prioritization.set(settings.get("dynamic_prioritization", True))
        self.park_after_click.set(settings.get("park_after_click", True))

        self.park_x.set(settings.get("park_x", 25))
        self.park_y.set(settings.get("park_y", 25))

        self.hotkey_var.set(settings.get("hotkey", "<ctrl>+<alt>+s"))
        self.start_hotkey_listener(silent=True)
        self.populate_target_tree()

    def build_gui(self):
        title = tk.Label(
            self.root,
            text="Automatic Picture Clicker",
            font=("Arial", 18, "bold")
        )
        title.pack(pady=10)

        picture_section = tk.LabelFrame(self.root, text="Pictures")
        picture_section.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)

        columns = ("enabled", "priority", "name", "status", "path")

        self.target_tree = ttk.Treeview(
            picture_section,
            columns=columns,
            show="headings",
            selectmode="extended",
            height=13
        )

        self.target_tree.heading("enabled", text="Enabled")
        self.target_tree.heading("priority", text="Priority")
        self.target_tree.heading("name", text="Picture")
        self.target_tree.heading("status", text="Status")
        self.target_tree.heading("path", text="Path")

        self.target_tree.column("enabled", width=80, anchor=tk.CENTER, stretch=False)
        self.target_tree.column("priority", width=80, anchor=tk.CENTER, stretch=False)
        self.target_tree.column("name", width=180, anchor=tk.W)
        self.target_tree.column("status", width=90, anchor=tk.CENTER, stretch=False)
        self.target_tree.column("path", width=540, anchor=tk.W)

        self.target_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=(8, 0), pady=8)

        scrollbar = ttk.Scrollbar(
            picture_section,
            orient=tk.VERTICAL,
            command=self.target_tree.yview
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=8, padx=(0, 8))

        self.target_tree.configure(yscrollcommand=scrollbar.set)
        self.target_tree.bind("<Button-1>", self.on_target_tree_click)

        picture_button_frame = tk.Frame(self.root)
        picture_button_frame.pack(pady=6)

        tk.Button(
            picture_button_frame,
            text="Add Images",
            command=self.add_images,
            width=15
        ).grid(row=0, column=0, padx=5)

        tk.Button(
            picture_button_frame,
            text="Remove Selected",
            command=self.remove_selected,
            width=15
        ).grid(row=0, column=1, padx=5)

        tk.Button(
            picture_button_frame,
            text="Enable Selected",
            command=self.enable_selected,
            width=15
        ).grid(row=0, column=2, padx=5)

        tk.Button(
            picture_button_frame,
            text="Disable Selected",
            command=self.disable_selected,
            width=15
        ).grid(row=0, column=3, padx=5)

        tk.Button(
            picture_button_frame,
            text="Reset Priority",
            command=self.reset_priority,
            width=15
        ).grid(row=0, column=4, padx=5)

        tk.Button(
            picture_button_frame,
            text="Clear All",
            command=self.clear_all,
            width=15
        ).grid(row=0, column=5, padx=5)

        settings = tk.LabelFrame(self.root, text="Settings")
        settings.pack(fill=tk.X, padx=15, pady=8)

        tk.Label(settings, text="Match threshold:").grid(row=0, column=0, sticky="w", padx=10, pady=5)

        tk.Scale(
            settings,
            from_=0.50,
            to=1.00,
            resolution=0.01,
            orient=tk.HORIZONTAL,
            variable=self.threshold,
            length=300
        ).grid(row=0, column=1, sticky="w", padx=10, pady=5)

        tk.Label(settings, text="Scan delay seconds:").grid(row=1, column=0, sticky="w", padx=10, pady=5)

        tk.Entry(
            settings,
            textvariable=self.scan_delay,
            width=10
        ).grid(row=1, column=1, sticky="w", padx=10, pady=5)

        tk.Label(settings, text="Delay after click seconds:").grid(row=2, column=0, sticky="w", padx=10, pady=5)

        tk.Entry(
            settings,
            textvariable=self.click_delay,
            width=10
        ).grid(row=2, column=1, sticky="w", padx=10, pady=5)

        tk.Label(settings, text="Loop yield delay seconds:").grid(row=3, column=0, sticky="w", padx=10, pady=5)

        tk.Entry(
            settings,
            textvariable=self.loop_yield_delay,
            width=10
        ).grid(row=3, column=1, sticky="w", padx=10, pady=5)

        tk.Checkbutton(
            settings,
            text="Click every match, not just the best match per image",
            variable=self.click_all_matches
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        tk.Checkbutton(
            settings,
            text="Keep clicking while matching image remains visible",
            variable=self.repeat_while_visible
        ).grid(row=5, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        tk.Checkbutton(
            settings,
            text="Prioritize less recently clicked pictures first",
            variable=self.dynamic_prioritization,
            command=self.populate_target_tree
        ).grid(row=6, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        tk.Label(
            settings,
            text="In priority mode, one matching picture is clicked per scan, then moved to the back of the search order.",
            fg="gray"
        ).grid(row=7, column=0, columnspan=2, sticky="w", padx=30, pady=(0, 5))

        tk.Checkbutton(
            settings,
            text="Move cursor to top-left area after each click",
            variable=self.park_after_click
        ).grid(row=8, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        park_frame = tk.Frame(settings)
        park_frame.grid(row=9, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        tk.Label(park_frame, text="Top-left park X:").pack(side=tk.LEFT)
        tk.Entry(park_frame, textvariable=self.park_x, width=6).pack(side=tk.LEFT, padx=(5, 15))

        tk.Label(park_frame, text="Y:").pack(side=tk.LEFT)
        tk.Entry(park_frame, textvariable=self.park_y, width=6).pack(side=tk.LEFT, padx=5)

        hotkey_frame = tk.LabelFrame(self.root, text="Hotkey")
        hotkey_frame.pack(fill=tk.X, padx=15, pady=8)

        tk.Label(hotkey_frame, text="Start/stop hotkey:").grid(row=0, column=0, sticky="w", padx=10, pady=8)

        tk.Entry(
            hotkey_frame,
            textvariable=self.hotkey_var,
            width=25
        ).grid(row=0, column=1, sticky="w", padx=10, pady=8)

        tk.Button(
            hotkey_frame,
            text="Record Hotkey",
            command=self.open_hotkey_recorder,
            width=15
        ).grid(row=0, column=2, sticky="w", padx=5, pady=8)

        tk.Button(
            hotkey_frame,
            text="Apply Hotkey",
            command=self.apply_hotkey_button,
            width=15
        ).grid(row=0, column=3, sticky="w", padx=5, pady=8)

        tk.Label(
            hotkey_frame,
            text="Examples: Ctrl+Alt+S, F8, Ctrl+Shift+X",
            fg="gray"
        ).grid(row=0, column=4, sticky="w", padx=10, pady=8)

        preset_frame = tk.LabelFrame(self.root, text="Setting Presets")
        preset_frame.pack(fill=tk.X, padx=15, pady=8)

        tk.Label(preset_frame, text="Preset:").grid(row=0, column=0, sticky="w", padx=10, pady=8)

        self.preset_combo = ttk.Combobox(
            preset_frame,
            textvariable=self.preset_var,
            width=28,
            state="normal"
        )
        self.preset_combo.grid(row=0, column=1, sticky="w", padx=10, pady=8)

        tk.Button(
            preset_frame,
            text="Save Preset",
            command=self.save_preset,
            width=14
        ).grid(row=0, column=2, padx=5, pady=8)

        tk.Button(
            preset_frame,
            text="Load Preset",
            command=self.load_preset,
            width=14
        ).grid(row=0, column=3, padx=5, pady=8)

        tk.Button(
            preset_frame,
            text="Delete Preset",
            command=self.delete_preset,
            width=14
        ).grid(row=0, column=4, padx=5, pady=8)

        control_frame = tk.Frame(self.root)
        control_frame.pack(pady=12)

        self.start_button = tk.Button(
            control_frame,
            text="Start",
            command=self.start,
            width=15,
            bg="#2e7d32",
            fg="white"
        )
        self.start_button.grid(row=0, column=0, padx=10)

        self.stop_button = tk.Button(
            control_frame,
            text="Stop",
            command=self.stop,
            width=15,
            bg="#b71c1c",
            fg="white",
            state=tk.DISABLED
        )
        self.stop_button.grid(row=0, column=1, padx=10)

        tk.Button(
            control_frame,
            text="Save Settings Now",
            command=self.save_settings_now,
            width=18
        ).grid(row=0, column=2, padx=10)

        self.status_label = tk.Label(
            self.root,
            text="Status: stopped",
            font=("Arial", 10)
        )
        self.status_label.pack(pady=4)

        note = tk.Label(
            self.root,
            text=(
                "Click the Enabled column to toggle individual pictures. "
                "Priority 1 is searched first. After a picture is clicked, it moves to the back of the priority order."
            ),
            wraplength=900,
            fg="gray"
        )
        note.pack(pady=4)

    def open_hotkey_recorder(self):
        if self.hotkey_record_window is not None and self.hotkey_record_window.winfo_exists():
            self.hotkey_record_window.lift()
            self.hotkey_record_window.focus_force()
            return

        window = tk.Toplevel(self.root)
        self.hotkey_record_window = window

        window.title("Record Hotkey")
        window.geometry("420x210")
        window.resizable(False, False)
        window.transient(self.root)
        window.grab_set()

        instruction = tk.Label(
            window,
            text="Press the hotkey combination you want to use.",
            font=("Arial", 12, "bold")
        )
        instruction.pack(pady=(20, 8))

        detail = tk.Label(
            window,
            text="Examples: Ctrl + Alt + S, F8, Ctrl + Shift + X\nPress Esc to cancel.",
            fg="gray"
        )
        detail.pack(pady=5)

        preview_var = tk.StringVar(value="Waiting for hotkey...")

        preview = tk.Label(
            window,
            textvariable=preview_var,
            font=("Arial", 14),
            fg="#1565c0"
        )
        preview.pack(pady=15)

        button_frame = tk.Frame(window)
        button_frame.pack(pady=8)

        def cancel_recording():
            window.grab_release()
            window.destroy()

        tk.Button(
            button_frame,
            text="Cancel",
            command=cancel_recording,
            width=12
        ).pack(side=tk.LEFT, padx=5)

        window.bind("<KeyPress>", lambda event: self.handle_hotkey_record_keypress(event, window, preview_var))

        window.focus_force()

    def handle_hotkey_record_keypress(self, event, window, preview_var):
        keysym = event.keysym

        if keysym == "Escape":
            window.grab_release()
            window.destroy()
            return

        if keysym in {
            "Control_L", "Control_R",
            "Shift_L", "Shift_R",
            "Alt_L", "Alt_R",
            "Meta_L", "Meta_R",
            "Super_L", "Super_R"
        }:
            preview_var.set("Now press the main key...")
            return

        hotkey = self.build_hotkey_from_tk_event(event)

        if not hotkey:
            preview_var.set("That key is not supported. Try another combo.")
            return

        preview_var.set(f"Recorded: {self.format_hotkey_for_display(hotkey)}")

        self.hotkey_var.set(hotkey)
        self.start_hotkey_listener(silent=False)
        self.save_app_state()

        self.root.after(350, lambda: self.close_hotkey_record_window(window))

    def close_hotkey_record_window(self, window):
        if window is not None and window.winfo_exists():
            try:
                window.grab_release()
            except Exception:
                pass

            window.destroy()

    def build_hotkey_from_tk_event(self, event):
        modifiers = []

        if event.state & 0x0004:
            modifiers.append("<ctrl>")

        if event.state & 0x0008:
            modifiers.append("<alt>")

        if event.state & 0x0001:
            modifiers.append("<shift>")

        key = self.convert_tk_key_to_pynput_hotkey_key(event)

        if not key:
            return None

        parts = modifiers + [key]

        return "+".join(parts)

    def convert_tk_key_to_pynput_hotkey_key(self, event):
        keysym = event.keysym
        char = event.char

        if keysym.startswith("F") and keysym[1:].isdigit():
            return f"<{keysym.lower()}>"

        special_key_map = {
            "space": "<space>",
            "Return": "<enter>",
            "Tab": "<tab>",
            "BackSpace": "<backspace>",
            "Delete": "<delete>",
            "Insert": "<insert>",
            "Home": "<home>",
            "End": "<end>",
            "Prior": "<page_up>",
            "Next": "<page_down>",
            "Up": "<up>",
            "Down": "<down>",
            "Left": "<left>",
            "Right": "<right>",
            "Caps_Lock": "<caps_lock>",
            "Num_Lock": "<num_lock>",
            "Scroll_Lock": "<scroll_lock>",
            "Pause": "<pause>",
            "Print": "<print_screen>"
        }

        if keysym in special_key_map:
            return special_key_map[keysym]

        if char and len(char) == 1:
            if char.isalnum():
                return char.lower()

        if len(keysym) == 1 and keysym.isalnum():
            return keysym.lower()

        return None

    def format_hotkey_for_display(self, hotkey):
        display = hotkey
        replacements = {
            "<ctrl>": "Ctrl",
            "<alt>": "Alt",
            "<shift>": "Shift",
            "<cmd>": "Cmd",
            "<enter>": "Enter",
            "<space>": "Space",
            "<tab>": "Tab",
            "<backspace>": "Backspace",
            "<delete>": "Delete",
            "<insert>": "Insert",
            "<home>": "Home",
            "<end>": "End",
            "<page_up>": "Page Up",
            "<page_down>": "Page Down",
            "<up>": "Up",
            "<down>": "Down",
            "<left>": "Left",
            "<right>": "Right"
        }

        for raw, pretty in replacements.items():
            display = display.replace(raw, pretty)

        for i in range(1, 25):
            display = display.replace(f"<f{i}>", f"F{i}")

        display = display.replace("+", " + ")

        return display

    def load_target_from_path(self, path, enabled=True, last_clicked_order=0):
        image = None
        width = 0
        height = 0
        missing = False

        if os.path.exists(path):
            image = cv2.imread(path, cv2.IMREAD_COLOR)

            if image is not None:
                height, width = image.shape[:2]
            else:
                missing = True
        else:
            missing = True

        return {
            "path": path,
            "name": os.path.basename(path),
            "image": image,
            "width": width,
            "height": height,
            "enabled": bool(enabled),
            "missing": missing,
            "last_clicked_order": int(last_clicked_order or 0)
        }

    def get_priority_map(self):
        ordered_targets = self.get_enabled_targets_ordered()
        priority_map = {}

        for rank, target in enumerate(ordered_targets, start=1):
            priority_map[target["path"]] = rank

        return priority_map

    def populate_target_tree(self):
        for item in self.target_tree.get_children():
            self.target_tree.delete(item)

        priority_map = self.get_priority_map()

        for index, target in enumerate(self.targets):
            enabled_text = "☑" if target["enabled"] else "☐"
            status_text = "Missing" if target["missing"] or target["image"] is None else "Ready"
            priority_text = str(priority_map[target["path"]]) if target["path"] in priority_map else "-"

            self.target_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    enabled_text,
                    priority_text,
                    target["name"],
                    status_text,
                    target["path"]
                )
            )

    def on_target_tree_click(self, event):
        region = self.target_tree.identify("region", event.x, event.y)
        column = self.target_tree.identify_column(event.x)
        row_id = self.target_tree.identify_row(event.y)

        if region == "cell" and column == "#1" and row_id:
            index = int(row_id)

            if 0 <= index < len(self.targets):
                self.targets[index]["enabled"] = not self.targets[index]["enabled"]
                self.populate_target_tree()
                self.save_app_state()

            return "break"

        return None

    def add_images(self):
        files = filedialog.askopenfilenames(
            title="Select target images",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp"),
                ("All files", "*.*")
            ]
        )

        existing_paths = {target["path"] for target in self.targets}

        for file_path in files:
            if file_path in existing_paths:
                continue

            target = self.load_target_from_path(file_path, enabled=True, last_clicked_order=0)

            if target["image"] is None:
                messagebox.showwarning("Invalid image", f"Could not load:\n{file_path}")
                continue

            self.targets.append(target)
            existing_paths.add(file_path)

        self.populate_target_tree()
        self.save_app_state()

    def remove_selected(self):
        selected = sorted(
            [int(item_id) for item_id in self.target_tree.selection()],
            reverse=True
        )

        for index in selected:
            if 0 <= index < len(self.targets):
                del self.targets[index]

        self.populate_target_tree()
        self.save_app_state()

    def enable_selected(self):
        for item_id in self.target_tree.selection():
            index = int(item_id)

            if 0 <= index < len(self.targets):
                self.targets[index]["enabled"] = True

        self.populate_target_tree()
        self.save_app_state()

    def disable_selected(self):
        for item_id in self.target_tree.selection():
            index = int(item_id)

            if 0 <= index < len(self.targets):
                self.targets[index]["enabled"] = False

        self.populate_target_tree()
        self.save_app_state()

    def reset_priority(self):
        for target in self.targets:
            target["last_clicked_order"] = 0

        self.priority_click_counter = 0
        self.populate_target_tree()
        self.save_app_state()
        self.status_label.config(text="Status: priority reset")

    def clear_all(self):
        if not self.targets:
            return

        confirmed = messagebox.askyesno(
            "Clear all pictures",
            "Remove all loaded pictures from the program?"
        )

        if not confirmed:
            return

        self.targets.clear()
        self.priority_click_counter = 0
        self.populate_target_tree()
        self.save_app_state()

    def refresh_preset_menu(self):
        preset_names = sorted(self.presets.keys())
        self.preset_combo["values"] = preset_names

    def save_preset(self):
        preset_name = self.preset_var.get().strip()

        if not preset_name:
            preset_name = simpledialog.askstring(
                "Save Preset",
                "Enter a name for this preset:"
            )

            if not preset_name:
                return

            preset_name = preset_name.strip()

        if not preset_name:
            return

        try:
            self.validate_settings()
        except Exception as error:
            messagebox.showerror("Invalid setting", str(error))
            return

        self.presets[preset_name] = self.get_current_settings()
        self.preset_var.set(preset_name)
        self.refresh_preset_menu()
        self.save_app_state()

        self.status_label.config(text=f"Status: preset saved - {preset_name}")

    def load_preset(self):
        preset_name = self.preset_var.get().strip()

        if preset_name not in self.presets:
            messagebox.showwarning("Preset not found", "Choose an existing preset to load.")
            return

        self.apply_settings(self.presets[preset_name])
        self.save_app_state()

        self.status_label.config(text=f"Status: preset loaded - {preset_name}")

    def delete_preset(self):
        preset_name = self.preset_var.get().strip()

        if preset_name not in self.presets:
            messagebox.showwarning("Preset not found", "Choose an existing preset to delete.")
            return

        confirmed = messagebox.askyesno(
            "Delete Preset",
            f"Delete preset '{preset_name}'?"
        )

        if not confirmed:
            return

        del self.presets[preset_name]
        self.preset_var.set("")
        self.refresh_preset_menu()
        self.save_app_state()

        self.status_label.config(text=f"Status: preset deleted - {preset_name}")

    def apply_hotkey_button(self):
        self.start_hotkey_listener(silent=False)
        self.save_app_state()

    def start_hotkey_listener(self, silent=False):
        hotkey = self.hotkey_var.get().strip()

        if not hotkey:
            if not silent:
                messagebox.showwarning("Invalid hotkey", "Hotkey cannot be empty.")
            return

        if self.hotkey_listener is not None:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass

            self.hotkey_listener = None
            self.active_hotkey = None

        try:
            self.hotkey_listener = keyboard.GlobalHotKeys({
                hotkey: self.on_hotkey_pressed
            })

            self.hotkey_listener.start()
            self.active_hotkey = hotkey

            if not silent:
                self.status_label.config(
                    text=f"Status: hotkey applied - {self.format_hotkey_for_display(hotkey)}"
                )

        except Exception as error:
            self.hotkey_listener = None
            self.active_hotkey = None

            if not silent:
                messagebox.showerror(
                    "Hotkey Error",
                    f"Could not apply hotkey:\n{hotkey}\n\n{error}"
                )
            else:
                self.root.after(
                    0,
                    lambda: self.status_label.config(text=f"Status: hotkey error - {error}")
                )

    def on_hotkey_pressed(self):
        self.root.after(0, self.toggle_running_from_hotkey)

    def toggle_running_from_hotkey(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def validate_settings(self):
        if self.threshold.get() < 0.0 or self.threshold.get() > 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0.")

        if self.scan_delay.get() < 0:
            raise ValueError("Scan delay cannot be negative.")

        if self.click_delay.get() < 0:
            raise ValueError("Click delay cannot be negative.")

        if self.loop_yield_delay.get() < 0:
            raise ValueError("Loop yield delay cannot be negative.")

        if self.park_x.get() < 0 or self.park_y.get() < 0:
            raise ValueError("Park coordinates cannot be negative.")

    def target_is_usable(self, target):
        return target["enabled"] and target["image"] is not None and not target["missing"]

    def get_enabled_targets(self):
        return [
            target
            for target in self.targets
            if self.target_is_usable(target)
        ]

    def get_enabled_targets_ordered(self):
        enabled_with_index = [
            (index, target)
            for index, target in enumerate(self.targets)
            if self.target_is_usable(target)
        ]

        if self.dynamic_prioritization.get():
            enabled_with_index.sort(
                key=lambda item: (
                    int(item[1].get("last_clicked_order", 0)),
                    item[0]
                )
            )

        return [target for index, target in enabled_with_index]

    def mark_target_clicked(self, target):
        self.priority_click_counter += 1
        target["last_clicked_order"] = self.priority_click_counter

        now = time.time()
        if now - self.last_priority_ui_update >= 0.25:
            self.last_priority_ui_update = now
            self.root.after(0, self.populate_target_tree)

    def start(self):
        if self.running:
            return

        try:
            self.validate_settings()
        except Exception as error:
            messagebox.showerror("Invalid setting", str(error))
            return

        enabled_targets = self.get_enabled_targets()

        if not enabled_targets:
            messagebox.showwarning(
                "No enabled pictures",
                "Enable at least one valid picture before starting."
            )
            return

        self.running = True

        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_label.config(text="Status: running")

        self.save_app_state()

        self.worker_thread = threading.Thread(target=self.clicker_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        self.running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text="Status: stopped")
        self.populate_target_tree()
        self.save_app_state()

    def clicker_loop(self):
        while self.running:
            try:
                if self.dynamic_prioritization.get():
                    found_anything = self.priority_scan_once()
                else:
                    found_anything = self.normal_scan_once()

                if found_anything:
                    self.root.after(
                        0,
                        lambda: self.status_label.config(text="Status: running - match clicked")
                    )
                else:
                    self.root.after(
                        0,
                        lambda: self.status_label.config(text="Status: running - scanning")
                    )

                time.sleep(self.scan_delay.get())

            except Exception as error:
                error_message = str(error)

                self.root.after(
                    0,
                    lambda msg=error_message: self.status_label.config(text=f"Error: {msg}")
                )

                self.running = False
                break

        self.root.after(0, self.stop)

    def priority_scan_once(self):
        screenshot = self.take_screenshot()

        for target in list(self.get_enabled_targets_ordered()):
            if not self.running:
                break

            matches = self.find_matches(
                screenshot=screenshot,
                template=target["image"],
                threshold=self.threshold.get()
            )

            if not matches:
                continue

            clicked = self.click_matches(matches)

            if clicked:
                self.mark_target_clicked(target)

            return clicked

        return False

    def normal_scan_once(self):
        screenshot = self.take_screenshot()
        found_anything = False

        for target in list(self.get_enabled_targets()):
            if not self.running:
                break

            matches = self.find_matches(
                screenshot=screenshot,
                template=target["image"],
                threshold=self.threshold.get()
            )

            if not matches:
                continue

            clicked = self.click_matches(matches)

            if clicked:
                found_anything = True
                self.mark_target_clicked(target)

            if self.repeat_while_visible.get():
                repeated = self.repeat_click_while_visible(target)
                found_anything = found_anything or repeated

        return found_anything

    def repeat_click_while_visible(self, target):
        clicked_anything = False

        while self.running and self.repeat_while_visible.get():
            if not target["enabled"]:
                break

            screenshot = self.take_screenshot()

            matches = self.find_matches(
                screenshot=screenshot,
                template=target["image"],
                threshold=self.threshold.get()
            )

            if not matches:
                break

            clicked = self.click_matches(matches)

            if clicked:
                clicked_anything = True
                self.mark_target_clicked(target)

            time.sleep(self.loop_yield_delay.get())

        return clicked_anything

    def click_matches(self, matches):
        clicked_anything = False

        if self.click_all_matches.get():
            points_to_click = matches
        else:
            points_to_click = [matches[0]]

        for x, y in points_to_click:
            if not self.running:
                break

            self.click_at(x, y)
            clicked_anything = True
            time.sleep(self.click_delay.get())

        return clicked_anything

    def take_screenshot(self):
        image = ImageGrab.grab(all_screens=True)
        screenshot = np.array(image)

        screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)

        return screenshot

    def find_matches(self, screenshot, template, threshold):
        screenshot_height, screenshot_width = screenshot.shape[:2]
        template_height, template_width = template.shape[:2]

        if template_width > screenshot_width or template_height > screenshot_height:
            return []

        result = cv2.matchTemplate(
            screenshot,
            template,
            cv2.TM_CCOEFF_NORMED
        )

        locations = np.where(result >= threshold)

        raw_points = []

        for pt in zip(*locations[::-1]):
            center_x = pt[0] + template_width // 2
            center_y = pt[1] + template_height // 2
            score = result[pt[1], pt[0]]

            raw_points.append((center_x, center_y, score))

        raw_points.sort(key=lambda point: point[2], reverse=True)

        filtered_points = []
        min_distance = max(template_width, template_height) // 2

        for x, y, score in raw_points:
            too_close = False

            for fx, fy in filtered_points:
                if abs(x - fx) < min_distance and abs(y - fy) < min_distance:
                    too_close = True
                    break

            if not too_close:
                filtered_points.append((int(x), int(y)))

        return filtered_points

    def click_at(self, x, y):
        pyautogui.click(x=int(x), y=int(y))

        if self.park_after_click.get():
            self.park_cursor()

    def park_cursor(self):
        pyautogui.moveTo(
            int(self.park_x.get()),
            int(self.park_y.get()),
            duration=0
        )

    def save_settings_now(self):
        try:
            self.validate_settings()
            self.populate_target_tree()
            self.save_app_state()
            self.status_label.config(text="Status: settings saved")
        except Exception as error:
            messagebox.showerror("Invalid setting", str(error))

    def on_close(self):
        self.running = False

        try:
            self.save_app_state()
        except Exception:
            pass

        if self.hotkey_listener is not None:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass

        self.root.destroy()


if __name__ == "__main__":
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.0

    root = tk.Tk()
    app = PictureClickerGUI(root)
    root.mainloop()