# Macro Runner

A simple GUI macro tool for scheduling keyboard input sequences to specific windows.

Built for cases like: type `continue`, press Enter, in 4 hours — aimed at a specific terminal.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

## Install

```bash
pip install pyautogui
```

`tkinter` and `pygetwindow` come bundled (tkinter with Python, pygetwindow with pyautogui).

## Usage

```bash
python macro-runner.py
```

### Adding steps

| Step type  | Value examples              | What it does                     |
|------------|-----------------------------|----------------------------------|
| Type Text  | `continue`, `hello world`   | Types the text character by character |
| Press Key  | `enter`, `tab`, `ctrl+a`    | Presses a key or key combo       |
| Wait (sec) | `2`, `0.5`                  | Pauses between steps             |

### Targeting a window

The **Target Window** dropdown lists all visible windows. If two windows share the same title, they're disambiguated with position coordinates.

- **Identify** — flashes the selected window (minimize/restore) so you can see which one it is
- **Refresh** — rescans open windows

If set to `(active window)`, the macro runs against whatever window is focused when the countdown ends.

### Start delay

Set hours, minutes, and seconds before the macro begins executing. The countdown shows in the status bar.

### Stopping

- **Cancel** button stops the macro mid-execution
- **Emergency stop** — move your mouse to the top-left corner of the screen (pyautogui failsafe)

## Example: type "continue" + Enter in 4 hours

1. Add step: **Type Text** → `continue`
2. Add step: **Press Key** → `enter`
3. Select your target terminal from the dropdown
4. Set start delay to **4h 0m 0s**
5. Click **Run Macro**

## Key names

Standard pyautogui key names: `enter`, `tab`, `space`, `esc`, `backspace`, `delete`, `up`, `down`, `left`, `right`, `f1`-`f12`, `ctrl`, `alt`, `shift`, `win`.

Combos use `+`: `ctrl+a`, `ctrl+shift+s`, `alt+f4`.

## License

MIT
