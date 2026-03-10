"""
Simple Macro Runner — schedule sequences of keystrokes and text with delays.
Usage: python macro-runner.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import pyautogui
import pygetwindow as gw

pyautogui.FAILSAFE = True  # move mouse to top-left corner to abort

class MacroRunner:
    def __init__(self, root):
        self.root = root
        root.title("Macro Runner")
        root.resizable(False, False)

        self.steps = []
        self.running = False
        self.cancel_flag = threading.Event()

        self._build_ui()

    def _build_ui(self):
        # --- Add Step Frame ---
        add_frame = ttk.LabelFrame(self.root, text="Add Step", padding=8)
        add_frame.pack(padx=10, pady=(10, 5), fill="x")

        ttk.Label(add_frame, text="Type:").grid(row=0, column=0, sticky="w")
        self.step_type = ttk.Combobox(add_frame, values=["Type Text", "Press Key", "Wait (sec)"], state="readonly", width=14)
        self.step_type.current(0)
        self.step_type.grid(row=0, column=1, padx=4)

        ttk.Label(add_frame, text="Value:").grid(row=0, column=2, sticky="w")
        self.step_value = ttk.Entry(add_frame, width=30)
        self.step_value.grid(row=0, column=3, padx=4)

        ttk.Button(add_frame, text="Add", command=self._add_step).grid(row=0, column=4, padx=4)

        # key hint
        self.hint = ttk.Label(add_frame, text="Keys: enter, tab, space, esc, backspace, up, down, left, right, f1-f12, ctrl, alt, shift", foreground="gray")
        self.hint.grid(row=1, column=0, columnspan=5, sticky="w", pady=(4, 0))

        # --- Target Window ---
        win_frame = ttk.LabelFrame(self.root, text="Target Window", padding=8)
        win_frame.pack(padx=10, pady=5, fill="x")

        self.window_var = tk.StringVar(value="(active window)")
        self.window_combo = ttk.Combobox(win_frame, textvariable=self.window_var, state="readonly", width=55)
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
        ttk.Button(btn_col, text="Up", width=6, command=self._move_up).pack(pady=2)
        ttk.Button(btn_col, text="Down", width=6, command=self._move_down).pack(pady=2)
        ttk.Button(btn_col, text="Delete", width=6, command=self._delete_step).pack(pady=2)
        ttk.Button(btn_col, text="Clear", width=6, command=self._clear_steps).pack(pady=2)

        # --- Initial Delay + Run ---
        run_frame = ttk.Frame(self.root, padding=8)
        run_frame.pack(padx=10, pady=(5, 10), fill="x")

        ttk.Label(run_frame, text="Start delay:").pack(side="left")
        self.delay_h = ttk.Entry(run_frame, width=4)
        self.delay_h.insert(0, "0")
        self.delay_h.pack(side="left", padx=2)
        ttk.Label(run_frame, text="h").pack(side="left")

        self.delay_m = ttk.Entry(run_frame, width=4)
        self.delay_m.insert(0, "0")
        self.delay_m.pack(side="left", padx=2)
        ttk.Label(run_frame, text="m").pack(side="left")

        self.delay_s = ttk.Entry(run_frame, width=4)
        self.delay_s.insert(0, "5")
        self.delay_s.pack(side="left", padx=2)
        ttk.Label(run_frame, text="s").pack(side="left")

        self.run_btn = ttk.Button(run_frame, text="Run Macro", command=self._run_macro)
        self.run_btn.pack(side="right", padx=4)
        self.cancel_btn = ttk.Button(run_frame, text="Cancel", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="right", padx=4)

        # --- Status ---
        self.status = ttk.Label(self.root, text="Ready. Move mouse to top-left corner to emergency stop.", foreground="gray")
        self.status.pack(padx=10, pady=(0, 8))

    def _refresh_windows(self):
        self._windows = []  # list of (display_label, window_object)
        seen_titles = {}
        all_wins = [w for w in gw.getAllWindows() if w.title.strip() and w.visible]

        # count duplicates first
        for w in all_wins:
            t = w.title.strip()
            seen_titles[t] = seen_titles.get(t, 0) + 1

        # build labels — disambiguate duplicates with position
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

    def _identify_window(self):
        """Briefly flash the selected window so the user can see which one it is."""
        target = self.window_var.get()
        if target == "(active window)":
            messagebox.showinfo("Identify", "Select a specific window first.")
            return
        win = None
        for label, w in self._windows:
            if label == target:
                win = w
                break
        if win is None:
            messagebox.showerror("Error", "Window no longer exists. Hit Refresh.")
            return

        def _flash():
            try:
                orig_title = win.title
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(0.4)
                # flash by minimizing and restoring
                win.minimize()
                time.sleep(0.3)
                win.restore()
                time.sleep(0.3)
                win.minimize()
                time.sleep(0.3)
                win.restore()
                time.sleep(0.5)
                # return focus to macro runner
                self.root.after(0, self.root.lift)
                self.root.after(0, self.root.focus_force)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Identify failed: {e}"))

        threading.Thread(target=_flash, daemon=True).start()

    def _focus_target_window(self):
        """Focus the selected target window. Returns True on success."""
        target = self.window_var.get()
        if target == "(active window)":
            return True
        # find the exact window object we stored
        win = None
        for label, w in self._windows:
            if label == target:
                win = w
                break
        if win is None:
            self.root.after(0, self._set_status, f"Window not found: {target}", "red")
            return False
        try:
            if win.isMinimized:
                win.restore()
            win.activate()
            time.sleep(0.3)  # give OS time to focus
        except Exception as e:
            self.root.after(0, self._set_status, f"Could not focus window: {e}", "red")
            return False
        return True

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
        display = f"[{stype}]  {val}"
        self.listbox.insert(tk.END, display)
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
        i = sel[0]
        self.steps.pop(i)
        self._refresh_list()

    def _clear_steps(self):
        self.steps.clear()
        self._refresh_list()

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for stype, val in self.steps:
            self.listbox.insert(tk.END, f"[{stype}]  {val}")

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

        self.running = True
        self.cancel_flag.clear()
        self.run_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")

        thread = threading.Thread(target=self._execute, args=(delay,), daemon=True)
        thread.start()

    def _cancel(self):
        self.cancel_flag.set()

    def _execute(self, delay):
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

            # Focus target window
            if not self._focus_target_window():
                self.root.after(0, self._reset_buttons)
                return

            # Execute steps
            for i, (stype, val) in enumerate(self.steps):
                if self.cancel_flag.is_set():
                    self.root.after(0, self._set_status, "Cancelled.", "red")
                    self.root.after(0, self._reset_buttons)
                    return

                self.root.after(0, self._set_status, f"Step {i + 1}/{len(self.steps)}: {stype} — {val}", "green")

                if stype == "Type Text":
                    pyautogui.typewrite(val, interval=0.03) if val.isascii() else pyautogui.write(val)
                elif stype == "Press Key":
                    # support combos like "ctrl+a"
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

            if not self.cancel_flag.is_set():
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
