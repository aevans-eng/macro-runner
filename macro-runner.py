"""
Macro Runner — schedule sequences of keystrokes and text with delays.
Supports recording, save/load, looping, and window targeting.
Usage: python macro-runner.py
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import json
import pyautogui
import pygetwindow as gw
from pynput import keyboard as kb

pyautogui.FAILSAFE = True  # move mouse to top-left corner to abort

MACRO_FILE_TYPES = [("Macro files", "*.json"), ("All files", "*.*")]


class MacroRunner:
    def __init__(self, root):
        self.root = root
        root.title("Macro Runner")
        root.resizable(False, False)

        self.steps = []
        self.running = False
        self.recording = False
        self.cancel_flag = threading.Event()
        self._record_listener = None
        self._record_buffer = []
        self._record_last_time = None

        self._build_ui()

    def _build_ui(self):
        # --- Add Step Frame ---
        add_frame = ttk.LabelFrame(self.root, text="Add Step", padding=8)
        add_frame.pack(padx=10, pady=(10, 5), fill="x")

        ttk.Label(add_frame, text="Type:").grid(row=0, column=0, sticky="w")
        self.step_type = ttk.Combobox(
            add_frame,
            values=["Type Text", "Press Key", "Wait (sec)"],
            state="readonly", width=14,
        )
        self.step_type.current(0)
        self.step_type.grid(row=0, column=1, padx=4)

        ttk.Label(add_frame, text="Value:").grid(row=0, column=2, sticky="w")
        self.step_value = ttk.Entry(add_frame, width=25)
        self.step_value.grid(row=0, column=3, padx=4)

        ttk.Button(add_frame, text="Add", command=self._add_step).grid(row=0, column=4, padx=4)

        self.hint = ttk.Label(
            add_frame,
            text="Keys: enter, tab, space, esc, backspace, up, down, left, right, f1-f12, ctrl, alt, shift",
            foreground="gray",
        )
        self.hint.grid(row=1, column=0, columnspan=5, sticky="w", pady=(4, 0))

        # --- Target Window ---
        win_frame = ttk.LabelFrame(self.root, text="Target Window", padding=8)
        win_frame.pack(padx=10, pady=5, fill="x")

        self.window_var = tk.StringVar(value="(active window)")
        self.window_combo = ttk.Combobox(
            win_frame, textvariable=self.window_var, state="readonly", width=50,
        )
        self.window_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(win_frame, text="Identify", command=self._identify_window).pack(side="left", padx=(4, 0))
        ttk.Button(win_frame, text="Refresh", command=self._refresh_windows).pack(side="left", padx=(4, 0))
        self._refresh_windows()

        # --- Steps List ---
        list_frame = ttk.LabelFrame(self.root, text="Steps", padding=8)
        list_frame.pack(padx=10, pady=5, fill="both", expand=True)

        self.listbox = tk.Listbox(list_frame, height=10, width=60, font=("Consolas", 10))
        self.listbox.pack(side="left", fill="both", expand=True)

        btn_col = ttk.Frame(list_frame)
        btn_col.pack(side="right", fill="y", padx=(4, 0))
        ttk.Button(btn_col, text="Up", width=8, command=self._move_up).pack(pady=2)
        ttk.Button(btn_col, text="Down", width=8, command=self._move_down).pack(pady=2)
        ttk.Button(btn_col, text="Delete", width=8, command=self._delete_step).pack(pady=2)
        ttk.Button(btn_col, text="Clear", width=8, command=self._clear_steps).pack(pady=2)
        ttk.Separator(btn_col, orient="horizontal").pack(fill="x", pady=6)
        self.record_btn = ttk.Button(btn_col, text="Record", width=8, command=self._toggle_record)
        self.record_btn.pack(pady=2)
        ttk.Separator(btn_col, orient="horizontal").pack(fill="x", pady=6)
        ttk.Button(btn_col, text="Save", width=8, command=self._save_macro).pack(pady=2)
        ttk.Button(btn_col, text="Load", width=8, command=self._load_macro).pack(pady=2)

        # --- Run Options ---
        run_frame = ttk.Frame(self.root, padding=8)
        run_frame.pack(padx=10, pady=(5, 10), fill="x")

        ttk.Label(run_frame, text="Delay:").pack(side="left")
        self.delay_h = ttk.Entry(run_frame, width=3)
        self.delay_h.insert(0, "0")
        self.delay_h.pack(side="left", padx=1)
        ttk.Label(run_frame, text="h").pack(side="left")

        self.delay_m = ttk.Entry(run_frame, width=3)
        self.delay_m.insert(0, "0")
        self.delay_m.pack(side="left", padx=1)
        ttk.Label(run_frame, text="m").pack(side="left")

        self.delay_s = ttk.Entry(run_frame, width=3)
        self.delay_s.insert(0, "5")
        self.delay_s.pack(side="left", padx=1)
        ttk.Label(run_frame, text="s").pack(side="left")

        ttk.Separator(run_frame, orient="vertical").pack(side="left", fill="y", padx=8)

        ttk.Label(run_frame, text="Repeat:").pack(side="left")
        self.loop_count = ttk.Entry(run_frame, width=4)
        self.loop_count.insert(0, "1")
        self.loop_count.pack(side="left", padx=2)
        ttk.Label(run_frame, text="x").pack(side="left")

        self.run_btn = ttk.Button(run_frame, text="Run", command=self._run_macro)
        self.run_btn.pack(side="right", padx=4)
        self.cancel_btn = ttk.Button(run_frame, text="Cancel", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="right", padx=4)

        # --- Status ---
        self.status = ttk.Label(
            self.root,
            text="Ready. Failsafe: move mouse to top-left corner.",
            foreground="gray",
        )
        self.status.pack(padx=10, pady=(0, 8))

    # ---- Window Management ----

    def _refresh_windows(self):
        self._windows = []
        seen_titles = {}
        all_wins = [w for w in gw.getAllWindows() if w.title.strip() and w.visible]

        for w in all_wins:
            t = w.title.strip()
            seen_titles[t] = seen_titles.get(t, 0) + 1

        used_titles = {}
        for w in all_wins:
            t = w.title.strip()
            if seen_titles[t] > 1:
                idx = used_titles.get(t, 0) + 1
                used_titles[t] = idx
                label = f"{t}  [{idx}: pos {w.left},{w.top}]"
            else:
                label = t
            self._windows.append((label, w))

        display = ["(active window)"] + [label for label, _ in self._windows]
        self.window_combo["values"] = display
        if self.window_var.get() not in display:
            self.window_var.set("(active window)")

    def _get_selected_window(self):
        target = self.window_var.get()
        if target == "(active window)":
            return None
        for label, w in self._windows:
            if label == target:
                return w
        return None

    def _identify_window(self):
        target = self.window_var.get()
        if target == "(active window)":
            messagebox.showinfo("Identify", "Select a specific window first.")
            return
        win = self._get_selected_window()
        if win is None:
            messagebox.showerror("Error", "Window no longer exists. Hit Refresh.")
            return

        def _flash():
            try:
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(0.5)
                win.minimize()
                time.sleep(0.4)
                win.restore()
                time.sleep(0.5)
                self.root.after(0, self.root.lift)
                self.root.after(0, self.root.focus_force)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Identify failed: {e}"))

        threading.Thread(target=_flash, daemon=True).start()

    def _focus_target_window(self):
        target = self.window_var.get()
        if target == "(active window)":
            return True
        win = self._get_selected_window()
        if win is None:
            self.root.after(0, self._set_status, f"Window not found: {target}", "red")
            return False
        try:
            if win.isMinimized:
                win.restore()
            win.activate()
            time.sleep(0.3)
        except Exception as e:
            self.root.after(0, self._set_status, f"Could not focus window: {e}", "red")
            return False
        return True

    # ---- Step Management ----

    def _add_step(self):
        stype = self.step_type.get()
        val = self.step_value.get().strip()
        if not val:
            return
        if stype == "Wait (sec)":
            try:
                float(val)
            except ValueError:
                messagebox.showerror("Error", "Wait value must be a number (seconds).")
                return
        self.steps.append((stype, val))
        self.listbox.insert(tk.END, f"[{stype}]  {val}")
        self.step_value.delete(0, tk.END)

    def _move_up(self):
        sel = self.listbox.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        self.steps[i], self.steps[i - 1] = self.steps[i - 1], self.steps[i]
        self._refresh_list()
        self.listbox.selection_set(i - 1)

    def _move_down(self):
        sel = self.listbox.curselection()
        if not sel or sel[0] == len(self.steps) - 1:
            return
        i = sel[0]
        self.steps[i], self.steps[i + 1] = self.steps[i + 1], self.steps[i]
        self._refresh_list()
        self.listbox.selection_set(i + 1)

    def _delete_step(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        self.steps.pop(sel[0])
        self._refresh_list()

    def _clear_steps(self):
        self.steps.clear()
        self._refresh_list()

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for stype, val in self.steps:
            self.listbox.insert(tk.END, f"[{stype}]  {val}")

    # ---- Recording ----

    # Map pynput special keys to pyautogui key names
    _KEY_MAP = {
        kb.Key.enter: "enter", kb.Key.tab: "tab", kb.Key.space: "space",
        kb.Key.backspace: "backspace", kb.Key.delete: "delete",
        kb.Key.esc: "esc", kb.Key.up: "up", kb.Key.down: "down",
        kb.Key.left: "left", kb.Key.right: "right",
        kb.Key.shift: "shift", kb.Key.shift_r: "shift",
        kb.Key.ctrl_l: "ctrl", kb.Key.ctrl_r: "ctrl",
        kb.Key.alt_l: "alt", kb.Key.alt_r: "alt",
        kb.Key.caps_lock: "capslock",
    }
    for _i in range(1, 13):
        _KEY_MAP[getattr(kb.Key, f"f{_i}")] = f"f{_i}"

    def _toggle_record(self):
        if self.recording:
            self._stop_record()
        else:
            self._start_record()

    def _start_record(self):
        self.recording = True
        self._record_buffer = []
        self._record_last_time = time.time()
        self._record_text_acc = ""  # accumulate typed characters
        self.record_btn.config(text="Stop Rec")
        self._set_status("Recording... press Esc to stop, or click Stop Rec.", "red")

        def on_press(key):
            if not self.recording:
                return False

            now = time.time()
            gap = now - self._record_last_time
            self._record_last_time = now

            # Esc stops recording
            if key == kb.Key.esc:
                self.root.after(0, self._stop_record)
                return False

            # If it's a printable character, accumulate into text
            try:
                char = key.char
                if char is not None:
                    # flush a wait if there's a meaningful gap
                    if gap >= 0.5 and (self._record_text_acc or self._record_buffer):
                        self._flush_text_acc()
                        self._record_buffer.append(("Wait (sec)", f"{gap:.1f}"))
                    self._record_text_acc += char
                    return
            except AttributeError:
                pass

            # It's a special key — flush any accumulated text first
            if gap >= 0.5 and (self._record_text_acc or self._record_buffer):
                self._flush_text_acc()
                self._record_buffer.append(("Wait (sec)", f"{gap:.1f}"))
            self._flush_text_acc()

            key_name = self._KEY_MAP.get(key)
            if key_name:
                self._record_buffer.append(("Press Key", key_name))

        self._record_listener = kb.Listener(on_press=on_press)
        self._record_listener.start()

    def _flush_text_acc(self):
        if self._record_text_acc:
            self._record_buffer.append(("Type Text", self._record_text_acc))
            self._record_text_acc = ""

    def _stop_record(self):
        self.recording = False
        if self._record_listener:
            self._record_listener.stop()
            self._record_listener = None
        self._flush_text_acc()

        if self._record_buffer:
            self.steps.extend(self._record_buffer)
            self._refresh_list()
            self._set_status(f"Recorded {len(self._record_buffer)} steps.", "green")
        else:
            self._set_status("Recording stopped (no input captured).", "gray")

        self._record_buffer = []
        self.record_btn.config(text="Record")

    # ---- Save / Load ----

    def _save_macro(self):
        if not self.steps:
            messagebox.showinfo("Info", "Nothing to save.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=MACRO_FILE_TYPES, title="Save Macro",
        )
        if not path:
            return
        data = {
            "steps": [{"type": t, "value": v} for t, v in self.steps],
            "delay_h": self.delay_h.get(),
            "delay_m": self.delay_m.get(),
            "delay_s": self.delay_s.get(),
            "loop": self.loop_count.get(),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        self._set_status(f"Saved to {path}", "green")

    def _load_macro(self):
        path = filedialog.askopenfilename(filetypes=MACRO_FILE_TYPES, title="Load Macro")
        if not path:
            return
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load: {e}")
            return

        self.steps = [(s["type"], s["value"]) for s in data.get("steps", [])]
        self._refresh_list()

        # restore settings
        for entry, key in [(self.delay_h, "delay_h"), (self.delay_m, "delay_m"),
                           (self.delay_s, "delay_s"), (self.loop_count, "loop")]:
            if key in data:
                entry.delete(0, tk.END)
                entry.insert(0, data[key])

        self._set_status(f"Loaded {len(self.steps)} steps from {path}", "green")

    # ---- Execution ----

    def _get_delay_seconds(self):
        try:
            h = int(self.delay_h.get() or 0)
            m = int(self.delay_m.get() or 0)
            s = int(self.delay_s.get() or 0)
            return h * 3600 + m * 60 + s
        except ValueError:
            messagebox.showerror("Error", "Delay values must be integers.")
            return None

    def _set_status(self, text, color="gray"):
        self.status.config(text=text, foreground=color)

    def _run_macro(self):
        if not self.steps:
            messagebox.showinfo("Info", "Add at least one step.")
            return
        delay = self._get_delay_seconds()
        if delay is None:
            return
        try:
            loops = max(1, int(self.loop_count.get() or 1))
        except ValueError:
            messagebox.showerror("Error", "Repeat count must be an integer.")
            return

        self.running = True
        self.cancel_flag.clear()
        self.run_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")

        thread = threading.Thread(target=self._execute, args=(delay, loops), daemon=True)
        thread.start()

    def _cancel(self):
        self.cancel_flag.set()

    def _execute(self, delay, loops):
        try:
            # Countdown
            remaining = delay
            while remaining > 0 and not self.cancel_flag.is_set():
                h, rem = divmod(remaining, 3600)
                m, s = divmod(rem, 60)
                self.root.after(0, self._set_status, f"Starting in {h:02d}:{m:02d}:{s:02d}...", "blue")
                time.sleep(1)
                remaining -= 1

            if self.cancel_flag.is_set():
                self.root.after(0, self._set_status, "Cancelled.", "red")
                self.root.after(0, self._reset_buttons)
                return

            for loop in range(loops):
                if self.cancel_flag.is_set():
                    break

                loop_label = f" (loop {loop + 1}/{loops})" if loops > 1 else ""

                # Focus target window at start of each loop
                if not self._focus_target_window():
                    self.root.after(0, self._reset_buttons)
                    return

                for i, (stype, val) in enumerate(self.steps):
                    if self.cancel_flag.is_set():
                        break

                    self.root.after(
                        0, self._set_status,
                        f"Step {i + 1}/{len(self.steps)}{loop_label}: {stype} — {val}",
                        "green",
                    )

                    if stype == "Type Text":
                        if val.isascii():
                            pyautogui.typewrite(val, interval=0.03)
                        else:
                            pyautogui.write(val)
                    elif stype == "Press Key":
                        keys = [k.strip() for k in val.split("+")]
                        if len(keys) > 1:
                            pyautogui.hotkey(*keys)
                        else:
                            pyautogui.press(keys[0])
                    elif stype == "Wait (sec)":
                        wait = float(val)
                        end = time.time() + wait
                        while time.time() < end:
                            if self.cancel_flag.is_set():
                                break
                            time.sleep(0.2)

            if self.cancel_flag.is_set():
                self.root.after(0, self._set_status, "Cancelled.", "red")
            else:
                self.root.after(0, self._set_status, "Done!", "green")
        except pyautogui.FailSafeException:
            self.root.after(0, self._set_status, "FAILSAFE triggered (mouse in corner). Stopped.", "red")
        except Exception as e:
            self.root.after(0, self._set_status, f"Error: {e}", "red")
        finally:
            self.running = False
            self.root.after(0, self._reset_buttons)

    def _reset_buttons(self):
        self.run_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    MacroRunner(root)
    root.mainloop()
