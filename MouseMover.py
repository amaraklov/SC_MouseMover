import ctypes
import json
import math
import random
import re
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

# ---------- SendInput helpers — works with DirectInput / Raw Input games ----------

class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx",          wintypes.LONG),
        ("dy",          wintypes.LONG),
        ("mouseData",   wintypes.DWORD),
        ("dwFlags",     wintypes.DWORD),
        ("time",        wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         wintypes.WORD),
        ("wScan",       wintypes.WORD),
        ("dwFlags",     wintypes.DWORD),
        ("time",        wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("_u", _INPUT_UNION)]


_INPUT_MOUSE    = 0
_INPUT_KEYBOARD = 1
_MOUSEEVENTF_MOVE     = 0x0001
_KEYEVENTF_SCANCODE   = 0x0008
_KEYEVENTF_KEYUP      = 0x0002
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# Scan codes for keys Star Citizen commonly binds to accept actions
_SCAN_CODES: dict[str, int] = {
    "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05,
    "5": 0x06, "6": 0x07, "7": 0x08, "8": 0x09,
    "9": 0x0A, "0": 0x0B,
    "[": 0x1A, "]": 0x1B,
    "-": 0x0C, "=": 0x0D,
}


def _get_scan_code(char: str) -> int:
    sc = _SCAN_CODES.get(char)
    if sc is not None:
        return sc
    vk = ctypes.windll.user32.VkKeyScanA(ctypes.c_char(char.encode()))
    return ctypes.windll.user32.MapVirtualKeyW(vk & 0xFF, 0)


def _is_star_citizen_foreground() -> bool:
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return False

    # Prefer process-name matching; window titles can change after alt-tab.
    try:
        pid = wintypes.DWORD(0)
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value:
            h_process = ctypes.windll.kernel32.OpenProcess(
                _PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
            )
            if h_process:
                try:
                    buf_size = wintypes.DWORD(1024)
                    exe_buf = ctypes.create_unicode_buffer(1024)
                    ok = ctypes.windll.kernel32.QueryFullProcessImageNameW(
                        h_process, 0, exe_buf, ctypes.byref(buf_size)
                    )
                    if ok:
                        exe_name = Path(exe_buf.value).name.lower()
                        if "starcitizen" in exe_name:
                            return True
                finally:
                    ctypes.windll.kernel32.CloseHandle(h_process)
    except Exception:
        pass

    title_len = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    if title_len <= 0:
        return False

    title_buf = ctypes.create_unicode_buffer(title_len + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, title_buf, title_len + 1)
    title = title_buf.value.lower()
    return "star citizen" in title or "starcitizen" in title


def _is_process_elevated() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _send_mouse_move_legacy(dx: int, dy: int) -> None:
    ctypes.windll.user32.mouse_event(_MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)


def _send_mouse_move(dx: int, dy: int) -> None:
    """Send relative movement; use a Star Citizen-specific fallback path when needed."""
    if dx == 0 and dy == 0:
        return

    # Import engine singleton if available
    engine = globals().get("engine")
    input_mode = getattr(engine, "input_mode", "auto")

    if input_mode == "legacy":
        _send_mouse_move_legacy(dx, dy)
        return
    elif input_mode == "sendinput":
        inp = _INPUT()
        inp.type = _INPUT_MOUSE
        inp._u.mi.dx = dx
        inp._u.mi.dy = dy
        inp._u.mi.mouseData = 0
        inp._u.mi.dwFlags = _MOUSEEVENTF_MOVE
        inp._u.mi.time = 0
        inp._u.mi.dwExtraInfo = None
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
        return
    # auto mode: prefer SendInput, fallback to legacy if Star Citizen is foreground
    if _is_star_citizen_foreground():
        _send_mouse_move_legacy(dx, dy)
        return
    inp = _INPUT()
    inp.type = _INPUT_MOUSE
    inp._u.mi.dx = dx
    inp._u.mi.dy = dy
    inp._u.mi.mouseData = 0
    inp._u.mi.dwFlags = _MOUSEEVENTF_MOVE
    inp._u.mi.time = 0
    inp._u.mi.dwExtraInfo = None
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def _send_key_scancode(char: str) -> None:
    """Press and release a key by scan code via SendInput (works in DirectInput games)."""
    sc = _get_scan_code(char)
    down = _INPUT()
    down.type = _INPUT_KEYBOARD
    down._u.ki.wVk = 0
    down._u.ki.wScan = sc
    down._u.ki.dwFlags = _KEYEVENTF_SCANCODE
    down._u.ki.time = 0
    down._u.ki.dwExtraInfo = None

    up = _INPUT()
    up.type = _INPUT_KEYBOARD
    up._u.ki.wVk = 0
    up._u.ki.wScan = sc
    up._u.ki.dwFlags = _KEYEVENTF_SCANCODE | _KEYEVENTF_KEYUP
    up._u.ki.time = 0
    up._u.ki.dwExtraInfo = None

    arr = (_INPUT * 2)(down, up)
    ctypes.windll.user32.SendInput(2, arr, ctypes.sizeof(_INPUT))

import webview
from pynput.keyboard import Controller as KeyboardController
from pynput.mouse import Controller as MouseController


VK_F11 = 0x7A
VK_F12 = 0x7B
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
HOTKEY_ID_F11 = 1
HOTKEY_ID_F12 = 2
MOD_NOREPEAT = 0x4000


EMBEDDED_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Mouse Drift HUD</title>
    <style>
        :root {
            --bg-1: #05080d;
            --bg-2: #0a1320;
            --panel: rgba(30, 24, 16, 0.95);
            --line: rgba(255, 191, 95, 0.48);
            --text: #ffd28c;
            --muted: #ad8751;
            --amber: #ffd27d;
            --amber-fill: #30261a;
            --amber-inner: rgba(255, 179, 71, 0.08);
            --red: #ff967e;
            --red-fill: #6a3328;
            --red-inner: rgba(255, 126, 104, 0.16);
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            background:
                radial-gradient(circle at 50% 14%, rgba(255, 179, 71, 0.14), transparent 34%),
                linear-gradient(180deg, var(--bg-1), var(--bg-2));
            color: var(--text);
            font-family: "Segoe UI", "Trebuchet MS", sans-serif;
            padding: 18px;
        }

        .wrap {
            width: min(1200px, 96vw);
            display: grid;
            grid-template-columns: minmax(0, 1fr) 320px;
            gap: 18px;
            align-items: stretch;
        }

        .panel,
        .side {
            border-radius: 20px;
            border: 1px solid rgba(255, 188, 92, 0.2);
            background: linear-gradient(180deg, rgba(39, 31, 20, 0.94), rgba(20, 18, 14, 0.98));
            box-shadow:
                0 0 0 1px rgba(255, 188, 92, 0.12),
                inset 0 0 40px rgba(255, 179, 71, 0.06),
                0 16px 40px rgba(0, 0, 0, 0.42);
        }

        .panel { padding: 14px; }
        .side {
            padding: 14px;
            display: grid;
            grid-template-rows: auto auto auto auto;
            gap: 12px;
        }

        .svg-shell {
            display: block;
            width: 100%;
            aspect-ratio: 16 / 9;
        }

        .card {
            border-radius: 14px;
            border: 1px solid rgba(255, 191, 95, 0.22);
            background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,179,71,0.03));
            padding: 10px;
        }

        .label {
            font-size: 11px;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            color: var(--muted);
            margin-bottom: 4px;
        }

        .value {
            font-size: 24px;
            font-weight: 700;
        }

        .fields {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }

        .field {
            display: grid;
            gap: 4px;
        }

        .field span {
            font-size: 11px;
            color: var(--muted);
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        input {
            width: 100%;
            border-radius: 8px;
            border: 1px solid rgba(255, 191, 95, 0.28);
            background: rgba(17, 15, 12, 0.86);
            color: var(--text);
            padding: 8px;
            font-size: 14px;
        }

        .stack {
            display: grid;
            gap: 8px;
        }

        .mini-button {
            width: 100%;
            border-radius: 10px;
            border: 1px solid rgba(255, 191, 95, 0.26);
            background: linear-gradient(180deg, rgba(255,191,95,0.08), rgba(255,191,95,0.02));
            color: var(--text);
            padding: 9px 10px;
            text-align: left;
            cursor: pointer;
        }

        .mini-button strong {
            display: block;
            font-size: 13px;
            letter-spacing: 0.06em;
        }

        .mini-button span {
            display: block;
            margin-top: 2px;
            color: var(--muted);
            font-size: 11px;
        }

        @media (max-width: 980px) {
            .wrap { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="wrap">
        <div class="panel">
            <svg class="svg-shell" viewBox="0 0 1200 760" xmlns="http://www.w3.org/2000/svg" aria-label="Mouse Drift HUD">
                <defs>
                    <filter id="softGlow" x="-30%" y="-30%" width="160%" height="160%">
                        <feGaussianBlur stdDeviation="4" result="blur"/>
                        <feMerge>
                            <feMergeNode in="blur"/>
                            <feMergeNode in="SourceGraphic"/>
                        </feMerge>
                    </filter>
                </defs>

                <rect x="36" y="36" rx="38" ry="38" width="940" height="620" fill="rgba(28,23,15,0.95)" stroke="var(--line)" stroke-width="3"/>
                <rect x="58" y="58" rx="26" ry="26" width="896" height="480" fill="rgba(255,191,95,0.04)" stroke="rgba(255,191,95,0.14)"/>

                <text x="86" y="98" fill="#ffcc79" font-size="34" font-weight="700" letter-spacing="3" filter="url(#softGlow)">MOUSE DRIFT</text>
                <text id="svgMouseInterval" x="86" y="132" fill="#ffd893" font-size="27" filter="url(#softGlow)">3000 ms</text>

                <text x="706" y="98" fill="#ffcc79" font-size="34" font-weight="700" letter-spacing="3" filter="url(#softGlow)">AUTO ACCEPT</text>
                <text id="svgKeyInterval" x="706" y="132" fill="#ffd893" font-size="27" filter="url(#softGlow)">3.00 s delay</text>

                <rect id="statusStrip" x="158" y="548" width="700" height="46" rx="4" fill="#ffe57a" filter="url(#softGlow)"/>
                <text x="508" y="578" text-anchor="middle" fill="#9b611d" font-size="32" letter-spacing="7">SELF STATUS</text>

                <g id="mouseBtnGroup" style="cursor:pointer" transform="translate(286,612)">
                    <rect id="mouseBtnOuter" x="0" y="0" width="82" height="74" rx="14" fill="#30261a" stroke="#ffd27d" stroke-width="3"/>
                    <rect id="mouseBtnInner" x="8" y="8" width="66" height="58" rx="10" fill="rgba(255,179,71,0.08)"/>
                    <text x="41" y="46" text-anchor="middle" fill="#ffd27d" font-size="28" font-weight="700" filter="url(#softGlow)">MSE</text>
                </g>

                <g id="keyBtnGroup" style="cursor:pointer" transform="translate(386,612)">
                    <rect id="keyBtnOuter" x="0" y="0" width="82" height="74" rx="14" fill="#30261a" stroke="#ffd27d" stroke-width="3"/>
                    <rect id="keyBtnInner" x="8" y="8" width="66" height="58" rx="10" fill="rgba(255,179,71,0.08)"/>
                    <text x="41" y="46" text-anchor="middle" fill="#ffd27d" font-size="28" font-weight="700" filter="url(#softGlow)">KEY</text>
                </g>

                <g id="f11BtnGroup" style="cursor:pointer" transform="translate(586,612)">
                    <rect id="f11BtnOuter" x="0" y="0" width="82" height="74" rx="14" fill="#30261a" stroke="#ffd27d" stroke-width="3"/>
                    <rect id="f11BtnInner" x="8" y="8" width="66" height="58" rx="10" fill="rgba(255,179,71,0.08)"/>
                    <text x="41" y="46" text-anchor="middle" fill="#ffd27d" font-size="26" font-weight="700" filter="url(#softGlow)">F11</text>
                </g>

                <g id="f12BtnGroup" style="cursor:pointer" transform="translate(686,612)">
                    <rect id="f12BtnOuter" x="0" y="0" width="82" height="74" rx="14" fill="#30261a" stroke="#ffd27d" stroke-width="3"/>
                    <rect id="f12BtnInner" x="8" y="8" width="66" height="58" rx="10" fill="rgba(255,179,71,0.08)"/>
                    <text x="41" y="46" text-anchor="middle" fill="#ffd27d" font-size="26" font-weight="700" filter="url(#softGlow)">F12</text>
                </g>
            </svg>
        </div>

        <aside class="side">
            <div class="card">
                <div class="label">Mouse State</div>
                <div class="value" id="mouseStateLabel">OFF</div>
            </div>

            <div class="card">
                <div class="label">Auto Accept</div>
                <div class="value" id="keyStateLabel">OFF</div>
            </div>

            <div class="card fields">
                <label class="field">
                    <span>Interval ms</span>
                    <input id="intervalInput" type="number" min="1" step="1" value="3000" />
                </label>
                <label class="field">
                    <span>Max Pixels</span>
                    <input id="maxPixelsInput" type="number" min="1" step="1" value="96" />
                </label>
                <label class="field">
                    <span>Moves Return</span>
                    <input id="movesInput" type="number" min="1" step="1" value="16" />
                </label>
                <label class="field">
                    <span>Smooth Steps</span>
                    <input id="smoothInput" type="number" min="1" step="1" value="12" />
                </label>
                <label class="field">
                    <span>Move Duration</span>
                    <input id="durationInput" type="number" min="0" step="0.01" value="0.18" />
                </label>
                <label class="field">
                    <span>Key Delay s</span>
                    <input id="acceptDelayInput" type="number" min="0" step="0.5" value="3" />
                </label>
            </div>

            <div class="stack">
                <button id="toggleMouseBtn" class="mini-button">
                    <strong>F12 Toggle Mouse - OFF</strong>
                    <span>Global hotkey, no focus required</span>
                </button>
                <button id="toggleKeyBtn" class="mini-button">
                    <strong>F11 Toggle Auto Accept - OFF</strong>
                    <span>Sends [ after delay when contract shared</span>
                </button>
            </div>
        </aside>
    </div>

    <script>
        const state = {
            mouseOn: false,
            keyOn: false,
            intervalMs: 3000,
            maxPixels: 96,
            movesBeforeReturn: 16,
            smoothSteps: 12,
            moveDuration: 0.18,
            acceptDelay: 3.0,
        };

        const els = {
            intervalInput: document.getElementById("intervalInput"),
            maxPixelsInput: document.getElementById("maxPixelsInput"),
            movesInput: document.getElementById("movesInput"),
            smoothInput: document.getElementById("smoothInput"),
            durationInput: document.getElementById("durationInput"),
            acceptDelayInput: document.getElementById("acceptDelayInput"),
            mouseStateLabel: document.getElementById("mouseStateLabel"),
            keyStateLabel: document.getElementById("keyStateLabel"),
            svgMouseInterval: document.getElementById("svgMouseInterval"),
            svgKeyInterval: document.getElementById("svgKeyInterval"),
            statusStrip: document.getElementById("statusStrip"),
            mouseBtnOuter: document.getElementById("mouseBtnOuter"),
            mouseBtnInner: document.getElementById("mouseBtnInner"),
            keyBtnOuter: document.getElementById("keyBtnOuter"),
            keyBtnInner: document.getElementById("keyBtnInner"),
            f11BtnOuter: document.getElementById("f11BtnOuter"),
            f11BtnInner: document.getElementById("f11BtnInner"),
            f12BtnOuter: document.getElementById("f12BtnOuter"),
            f12BtnInner: document.getElementById("f12BtnInner"),
            mouseBtnGroup: document.getElementById("mouseBtnGroup"),
            keyBtnGroup: document.getElementById("keyBtnGroup"),
            f11BtnGroup: document.getElementById("f11BtnGroup"),
            f12BtnGroup: document.getElementById("f12BtnGroup"),
            toggleMouseBtn: document.getElementById("toggleMouseBtn"),
            toggleKeyBtn: document.getElementById("toggleKeyBtn"),
        };

        function buttonColors(isOn) {
            return isOn
                ? { outerFill: "#6a3328", outerStroke: "#ff967e", innerFill: "rgba(255,126,104,0.16)" }
                : { outerFill: "#30261a", outerStroke: "#ffd27d", innerFill: "rgba(255,179,71,0.08)" };
        }

        function applyButtonState(outer, inner, isOn) {
            const c = buttonColors(isOn);
            outer.setAttribute("fill", c.outerFill);
            outer.setAttribute("stroke", c.outerStroke);
            inner.setAttribute("fill", c.innerFill);
        }

        function render() {
            els.intervalInput.value = state.intervalMs;
            els.maxPixelsInput.value = state.maxPixels;
            els.movesInput.value = state.movesBeforeReturn;
            els.smoothInput.value = state.smoothSteps;
            els.durationInput.value = state.moveDuration;
            if (els.acceptDelayInput) els.acceptDelayInput.value = state.acceptDelay ?? 3.0;
            els.svgKeyInterval.textContent = `${(state.acceptDelay ?? 3.0).toFixed(2)} s delay`;

            els.mouseStateLabel.textContent = state.mouseOn ? "ON" : "OFF";
            els.keyStateLabel.textContent = state.keyOn ? `delay ${(state.acceptDelay ?? 3.0).toFixed(2)}s` : "OFF";
            els.svgMouseInterval.textContent = `${state.intervalMs} ms`;

            els.statusStrip.setAttribute("fill", state.mouseOn || state.keyOn ? "#ffd183" : "#ffe57a");

            applyButtonState(els.mouseBtnOuter, els.mouseBtnInner, state.mouseOn);
            applyButtonState(els.keyBtnOuter, els.keyBtnInner, state.keyOn);
            applyButtonState(els.f11BtnOuter, els.f11BtnInner, state.keyOn);
            applyButtonState(els.f12BtnOuter, els.f12BtnInner, state.mouseOn);

            els.toggleMouseBtn.querySelector("strong").textContent =
                state.mouseOn ? "F12 Toggle Mouse - ON" : "F12 Toggle Mouse - OFF";
            els.toggleKeyBtn.querySelector("strong").textContent =
                state.keyOn ? "F11 Toggle Auto Accept - ON" : "F11 Toggle Auto Accept - OFF";
        }

        function collectSettings() {
            return {
                intervalMs: parseInt(els.intervalInput.value || "3000", 10),
                maxPixels: parseInt(els.maxPixelsInput.value || "96", 10),
                movesBeforeReturn: parseInt(els.movesInput.value || "16", 10),
                smoothSteps: parseInt(els.smoothInput.value || "12", 10),
                moveDuration: parseFloat(els.durationInput.value || "0.18"),
                acceptDelay: parseFloat(els.acceptDelayInput?.value || "3.0"),
            };
        }

        async function pushSettings() {
            const settings = collectSettings();
            Object.assign(state, settings);
            render();

            if (window.pywebview && window.pywebview.api) {
                await window.pywebview.api.update_settings(settings);
            }
        }

        async function toggleMouse() {
            if (window.pywebview && window.pywebview.api) {
                const newState = await window.pywebview.api.toggle_mouse();
                Object.assign(state, newState);
                render();
            }
        }

        async function toggleKey() {
            if (window.pywebview && window.pywebview.api) {
                const newState = await window.pywebview.api.toggle_key();
                Object.assign(state, newState);
                render();
            }
        }

        window.app = {
            updateFromPython(newState) {
                Object.assign(state, newState);
                render();
            }
        };

        [
            els.intervalInput,
            els.maxPixelsInput,
            els.movesInput,
            els.smoothInput,
            els.durationInput,
            els.acceptDelayInput,
        ].forEach((input) => input && input.addEventListener("change", pushSettings));

        els.toggleMouseBtn.addEventListener("click", toggleMouse);
        els.toggleKeyBtn.addEventListener("click", toggleKey);
        els.mouseBtnGroup.addEventListener("click", toggleMouse);
        els.keyBtnGroup.addEventListener("click", toggleKey);
        els.f11BtnGroup.addEventListener("click", toggleKey);
        els.f12BtnGroup.addEventListener("click", toggleMouse);

        window.addEventListener("pywebviewready", async () => {
            const initial = await window.pywebview.api.get_state();
            Object.assign(state, initial);
            render();
        });

        render();
    </script>
</body>
</html>
"""


class MouseDriftEngine:
    def __init__(self):
        self.mouse = MouseController()
        self.keyboard = KeyboardController()

        self.mouse_running = False
        self.key_running = False
        self.death_watch_running = False

        self.mouse_stop_event = threading.Event()
        self.log_stop_event = threading.Event()  # controls the shared log-reading thread

        self.mouse_thread = None
        self.log_thread = None
        self.hotkey_thread = None
        self.hotkey_thread_id = 0
        self.hotkey_stop_event = threading.Event()

        self.window = None
        self.lock = threading.Lock()

        self.interval_ms = 3000
        self.max_pixels = 96
        self.moves_before_return = 16
        self.smooth_steps = 12
        self.move_duration = 0.18
        self.accept_delay = 0.5
        self.accept_timeout_sec = 60.0
        self.mission_detect_count = 0
        self.total_bracket_presses = 0
        self.last_mission_detect_ts = 0.0

        self.death_list = []
        self.local_player_name = None
        self.last_location_hint = "Unknown"
        self.last_location_source = ""

        self.log_path = self.find_default_log_path()
        self.log_offset = 0
        self.last_accept_ts = 0.0
        self.accept_spam_active = False
        self.accept_spam_deadline_ts = 0.0
        self.next_accept_press_ts = 0.0

        self.origin = None
        self.move_count = 0

        self.input_mode = "auto"  # "auto", "sendinput", "legacy"
        self._load_settings()

    def _settings_path(self):
        if hasattr(sys, "_MEIPASS"):
            base = Path(sys.executable).parent
        else:
            base = Path(__file__).resolve().parent
        return base / "mousedrift_settings.json"

    def _load_settings(self):
        try:
            data = json.loads(self._settings_path().read_text(encoding="utf-8"))
            if data.get("deathWatchOn"):
                self.death_watch_running = True  # will auto-start after window attaches
            if data.get("inputMode") in ("auto", "sendinput", "legacy"):
                self.input_mode = data["inputMode"]
        except Exception:
            pass

    def _save_settings(self):
        try:
            data = {"deathWatchOn": self.death_watch_running, "inputMode": self.input_mode}
            self._settings_path().write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass

    def find_default_log_path(self):
        install_root = Path(r"C:\Program Files\Roberts Space Industries\StarCitizen")
        # Default to LIVE; users can still override from the UI/API.
        return str(install_root / "LIVE" / "Game.log")

    def attach_window(self, window):
        self.window = window
        self._ensure_log_thread_running(reset_offset=True)
        self.emit_state()

    def emit_state(self):
        if not self.window:
            return

        state = {
            "mouseOn": self.mouse_running,
            "keyOn": self.key_running,
            "deathWatchOn": self.death_watch_running,
            "intervalMs": self.interval_ms,
            "maxPixels": self.max_pixels,
            "movesBeforeReturn": self.moves_before_return,
            "smoothSteps": self.smooth_steps,
            "moveDuration": self.move_duration,
            "acceptDelay": self.accept_delay,
            "missionDetectCount": self.mission_detect_count,
            "totalBracketPresses": self.total_bracket_presses,
            "lastMissionDetectTs": self.last_mission_detect_ts,
            "logPath": self.log_path,
            "logExists": Path(self.log_path).is_file(),
            "deaths": list(self.death_list),
            "inputMode": self.input_mode,
        }

        js = f"window.app && window.app.updateFromPython({json.dumps(state)});"
        try:
            self.window.evaluate_js(js)
        except Exception:
            pass

    def start_hotkeys(self):
        if self.hotkey_thread is not None:
            return

        def hotkey_loop():
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            self.hotkey_thread_id = kernel32.GetCurrentThreadId()

            registered = []

            try:
                if user32.RegisterHotKey(None, HOTKEY_ID_F12, MOD_NOREPEAT, VK_F12):
                    registered.append(HOTKEY_ID_F12)
                if user32.RegisterHotKey(None, HOTKEY_ID_F11, MOD_NOREPEAT, VK_F11):
                    registered.append(HOTKEY_ID_F11)

                if not registered:
                    return

                msg = wintypes.MSG()
                while not self.hotkey_stop_event.is_set():
                    result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                    if result <= 0:
                        break

                    if msg.message == WM_HOTKEY:
                        if msg.wParam == HOTKEY_ID_F12:
                            self.toggle_mouse()
                        elif msg.wParam == HOTKEY_ID_F11:
                            self.toggle_key()
            finally:
                for hotkey_id in registered:
                    try:
                        user32.UnregisterHotKey(None, hotkey_id)
                    except Exception:
                        pass
                self.hotkey_thread_id = 0

        self.hotkey_stop_event.clear()
        self.hotkey_thread = threading.Thread(target=hotkey_loop, daemon=True)
        self.hotkey_thread.start()

    def stop_hotkeys(self):
        if self.hotkey_thread is not None:
            self.hotkey_stop_event.set()
            if self.hotkey_thread_id:
                try:
                    ctypes.windll.user32.PostThreadMessageW(self.hotkey_thread_id, WM_QUIT, 0, 0)
                except Exception:
                    pass
            self.hotkey_thread = None

    def update_settings(self, settings):
        with self.lock:
            self.interval_ms = max(1, int(settings.get("intervalMs", self.interval_ms)))
            self.max_pixels = max(0, min(255, int(settings.get("maxPixels", self.max_pixels))))
            self.moves_before_return = max(
                1, int(settings.get("movesBeforeReturn", self.moves_before_return))
            )
            self.smooth_steps = max(1, int(settings.get("smoothSteps", self.smooth_steps)))
            self.move_duration = max(0.0, float(settings.get("moveDuration", self.move_duration)))
            self.accept_delay = max(0.01, float(settings.get("acceptDelay", self.accept_delay)))
            if settings.get("inputMode") in ("auto", "sendinput", "legacy"):
                self.input_mode = settings["inputMode"]
                self._save_settings()
        self.emit_state()
        return {"ok": True}

    def get_state(self):
        return {
            "mouseOn": self.mouse_running,
            "keyOn": self.key_running,
            "deathWatchOn": self.death_watch_running,
            "intervalMs": self.interval_ms,
            "maxPixels": self.max_pixels,
            "movesBeforeReturn": self.moves_before_return,
            "smoothSteps": self.smooth_steps,
            "moveDuration": self.move_duration,
            "acceptDelay": self.accept_delay,
            "missionDetectCount": self.mission_detect_count,
            "totalBracketPresses": self.total_bracket_presses,
            "lastMissionDetectTs": self.last_mission_detect_ts,
            "logPath": self.log_path,
            "logExists": Path(self.log_path).is_file(),
            "deaths": list(self.death_list),
            "inputMode": self.input_mode,
        }

    def set_log_path(self, path):
        if not path:
            return {"ok": False, "error": "empty-path"}

        normalized = str(Path(path))
        with self.lock:
            self.log_path = normalized
        self.reset_log_offset_to_end()
        self.emit_state()
        return {"ok": True, "path": self.log_path, "exists": Path(self.log_path).is_file()}

    def choose_log_file(self):
        if not self.window:
            return {"ok": False, "error": "window-not-ready"}

        try:
            selected = self.window.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=("Log files (*.log)", "All files (*.*)"),
            )
        except Exception:
            return {"ok": False, "error": "dialog-failed"}

        if not selected:
            return {"ok": False, "cancelled": True}

        return self.set_log_path(selected[0])

    def reset_log_offset_to_end(self):
        path = Path(self.log_path)
        if not path.is_file():
            self.log_offset = 0
            return

        try:
            with path.open("rb") as handle:
                handle.seek(0, 2)
                self.log_offset = handle.tell()
        except OSError:
            self.log_offset = 0

    def try_detect_player_name(self, line):
        """Detect the local character name from AccountLoginCharacterStatus log events."""
        if self.local_player_name:
            return
        if "AccountLoginCharacterStatus_Character" in line:
            m = re.search(r"name='([^']+)'", line)
            if not m:
                m = re.search(r"character[^']*'([^']+)'", line, re.IGNORECASE)
            if m:
                self.local_player_name = m.group(1)
                print(f"[DEATH] Detected local player: {self.local_player_name}")

    def is_actor_death_line(self, line):
        if not self.local_player_name:
            return False
        return "CActor::Kill:" in line and f"CActor::Kill: '{self.local_player_name}'" in line

    def parse_death_line(self, line):
        m = re.search(
            r"CActor::Kill: '[^']+' \[\d+\].*?killed by '([^']+)' \[\d+\] using '([^']+)'",
            line,
        )
        if not m:
            return None
        killer = m.group(1)
        weapon = re.sub(r'_\d+$', '', m.group(2))
        ts_match = re.match(r'<\d{4}-\d{2}-\d{2}T(\d{2}:\d{2}:\d{2})\.', line)
        time_str = ts_match.group(1) if ts_match else ""
        return {"killer": killer, "weapon": weapon, "time": time_str}

    def parse_line_time(self, line):
        ts_match = re.match(r'<\d{4}-\d{2}-\d{2}T(\d{2}:\d{2}:\d{2})\.', line)
        return ts_match.group(1) if ts_match else ""

    def extract_location_hint_from_line(self, line):
        m = re.search(r"locationName\[([^\]]+)\]", line)
        if m:
            return m.group(1), "locationName"

        m = re.search(r"Added notification \"([^\"]+)\"", line)
        if m:
            msg = m.group(1).strip()
            if any(token in msg for token in ("Armistice Zone", "Jurisdiction", "Medical Bed", "Incapacitated")):
                return msg, "notification"

        m = re.search(r"\bLocation\[([^\]]+)\]", line)
        if m:
            return f"Location {m.group(1)}", "location-id"

        return None, None

    def update_location_hint(self, line):
        hint, source = self.extract_location_hint_from_line(line)
        if hint:
            self.last_location_hint = hint
            self.last_location_source = source or ""

    def is_incapacitated_line(self, line):
        return "Incapacitated:" in line and "Time to Death" in line

    def is_corpse_recovery_line(self, line):
        return "CSCActorCorpseUtils::PopulateItemPortForItemRecoveryEntitlement" in line

    def add_death_event(self, killer, weapon, time_str, location_hint=None, location_source=None):
        location_value = location_hint or self.last_location_hint or "Unknown"
        source_value = location_source if location_source is not None else self.last_location_source
        entry = {
            "killer": killer,
            "weapon": weapon,
            "time": time_str,
            "location": location_value,
            "locationSource": source_value,
        }
        if self.death_list and self.death_list[0] == entry:
            return
        self.death_list.insert(0, entry)
        if len(self.death_list) > 50:
            self.death_list = self.death_list[:50]
        self.emit_state()

    def is_contract_shared_line(self, line):
        return "contract shared:" in line.lower()

    def is_contract_accepted_line(self, line):
        return "Contract Accepted:" in line

    def extract_accept_key(self, line):
        return "["

    def press_accept_key(self, key_text):
        _send_key_scancode(key_text if key_text else "[")

    def process_new_log_data(self, blob):
        now = time.time()
        watch_deaths = True
        watch_missions = self.key_running

        for raw_line in blob.splitlines():
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            if watch_deaths:
                self.try_detect_player_name(line)
                self.update_location_hint(line)

            if watch_deaths and self.is_actor_death_line(line):
                death = self.parse_death_line(line)
                if death:
                    line_loc, line_loc_source = self.extract_location_hint_from_line(line)
                    self.add_death_event(
                        death["killer"],
                        death["weapon"],
                        death["time"],
                        location_hint=line_loc,
                        location_source=line_loc_source,
                    )
                    print(f"[DEATH] Killed by {death['killer']} with {death['weapon']}")
                continue

            if watch_deaths and (self.is_incapacitated_line(line) or self.is_corpse_recovery_line(line)):
                # Newer log builds often omit killer/weapon in CActor::Kill, so we still show a death marker.
                weapon = "unknown weapon"
                if self.is_incapacitated_line(line):
                    weapon = "incapacitated"
                line_loc, line_loc_source = self.extract_location_hint_from_line(line)
                self.add_death_event(
                    "Unknown",
                    weapon,
                    self.parse_line_time(line),
                    location_hint=line_loc,
                    location_source=line_loc_source,
                )
                print("[DEATH] Fallback death signal detected (killer/weapon unavailable in log line).")
                continue

            if not watch_missions:
                continue

            if self.is_contract_accepted_line(line):
                if self.accept_spam_active:
                    self.accept_spam_active = False
                    print("[ACCEPT] Contract Accepted detected. Stopping spam.")
                    self.emit_state()
                continue

            if not self.is_contract_shared_line(line):
                continue

            self.accept_spam_active = True
            self.accept_spam_deadline_ts = now + self.accept_timeout_sec
            self.next_accept_press_ts = now
            self.mission_detect_count += 1
            self.last_mission_detect_ts = now
            print(
                f"[ACCEPT] Contract Shared detected. Spamming [ every {self.accept_delay:.2f}s "
                f"for up to {self.accept_timeout_sec:.0f}s or until Contract Accepted:"
            )
            print(f"         Line: {line[:120]}")
            self.emit_state()

    def tick_accept_spam(self):
        if not self.accept_spam_active:
            return

        now = time.time()
        if now >= self.accept_spam_deadline_ts:
            self.accept_spam_active = False
            print("[ACCEPT] Timeout reached (60s). Stopping spam.")
            self.emit_state()
            return

        if now < self.next_accept_press_ts:
            return

        _send_key_scancode("[")
        self.total_bracket_presses += 1
        self.last_accept_ts = now
        self.next_accept_press_ts = now + self.accept_delay
        print("[ACCEPT] [ sent.")
        self.emit_state()

    def _log_thread_needed(self):
        return self.key_running or self.death_watch_running or (self.window is not None)

    def _ensure_log_thread_running(self, reset_offset=False):
        if reset_offset:
            self.reset_log_offset_to_end()
        if self.log_thread is not None and self.log_thread.is_alive():
            return
        self.log_stop_event.clear()
        self.log_thread = threading.Thread(target=self.log_loop, daemon=True)
        self.log_thread.start()

    def _stop_log_thread_if_idle(self):
        if self._log_thread_needed():
            return
        self.log_stop_event.set()


    def toggle_mouse(self):
        if self.mouse_running:
            self.stop_mouse()
        else:
            self.start_mouse()
        self.emit_state()
        return self.get_state()

    def toggle_key(self):
        if self.key_running:
            self.stop_key()
        else:
            self.start_key()
        self.emit_state()
        return self.get_state()

    def toggle_death_watch(self):
        if self.death_watch_running:
            self.stop_death_watch()
        else:
            self.start_death_watch()
        self.emit_state()
        return self.get_state()

    def start_mouse(self):
        if self.mouse_running:
            return

        self.origin = self.mouse.position
        self.move_count = 0
        self.mouse_stop_event.clear()
        self.mouse_running = True

        self.mouse_thread = threading.Thread(target=self.mouse_loop, daemon=True)
        self.mouse_thread.start()

    def stop_mouse(self):
        self.mouse_stop_event.set()
        self.mouse_running = False

    def start_key(self):
        if self.key_running:
            return

        self.last_accept_ts = 0.0
        self.accept_spam_active = False
        self.accept_spam_deadline_ts = 0.0
        self.next_accept_press_ts = 0.0
        self.key_running = True
        self._ensure_log_thread_running(reset_offset=True)

    def stop_key(self):
        self.accept_spam_active = False
        self.key_running = False
        self._stop_log_thread_if_idle()

    def start_death_watch(self):
        if self.death_watch_running:
            return
        self.death_watch_running = True
        self._save_settings()
        self._ensure_log_thread_running(reset_offset=True)

    def stop_death_watch(self):
        self.death_watch_running = False
        self._save_settings()
        self._stop_log_thread_if_idle()

    def shutdown(self):
        self.stop_mouse()
        self.stop_key()
        self.stop_death_watch()
        self.log_stop_event.set()
        self.stop_hotkeys()

    def random_vector(self, max_pixels):
        if max_pixels <= 0:
            return 0, 0

        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(1, max_pixels) * random.uniform(0.4, 1.0)

        dx = int(math.cos(angle) * distance)
        dy = int(math.sin(angle) * distance)

        if dx == 0 and dy == 0 and max_pixels > 0:
            dx = 1

        return dx, dy

    def ease_in_out(self, t):
        return 0.5 - 0.5 * math.cos(math.pi * t)

    def smooth_move_relative(self, dx, dy, duration, steps):
        if dx == 0 and dy == 0:
            return

        if steps <= 1 or duration <= 0:
            _send_mouse_move(dx, dy)
            return

        sleep_time = duration / steps
        prev_eased_x = 0.0
        prev_eased_y = 0.0

        for i in range(1, steps + 1):
            if self.mouse_stop_event.is_set():
                return

            t = i / steps
            eased = self.ease_in_out(t)

            cur_eased_x = dx * eased
            cur_eased_y = dy * eased
            step_dx = round(cur_eased_x) - round(prev_eased_x)
            step_dy = round(cur_eased_y) - round(prev_eased_y)

            if step_dx != 0 or step_dy != 0:
                _send_mouse_move(step_dx, step_dy)

            prev_eased_x = cur_eased_x
            prev_eased_y = cur_eased_y

            time.sleep(sleep_time)

    def move_back_to_origin(self):
        current_x, current_y = self.mouse.position
        origin_x, origin_y = self.origin
        dx = origin_x - current_x
        dy = origin_y - current_y

        if dx == 0 and dy == 0:
            return

        self.smooth_move_relative(dx, dy, self.move_duration, self.smooth_steps)

    def mouse_loop(self):
        try:
            while not self.mouse_stop_event.is_set():
                if self.move_count < self.moves_before_return:
                    dx, dy = self.random_vector(self.max_pixels)
                    self.smooth_move_relative(dx, dy, self.move_duration, self.smooth_steps)
                    self.move_count += 1
                else:
                    self.move_back_to_origin()
                    self.move_count = 0
                    self.origin = self.mouse.position

                interval = (self.interval_ms / 1000.0) * random.uniform(0.9, 1.1)
                if self.mouse_stop_event.wait(interval):
                    break
        finally:
            self.mouse_running = False
            self.emit_state()

    def log_loop(self):
        try:
            while not self.log_stop_event.is_set():
                if not self._log_thread_needed():
                    break

                path = Path(self.log_path)
                if not path.is_file():
                    if self.log_stop_event.wait(0.8):
                        break
                    continue

                try:
                    size = path.stat().st_size
                except OSError:
                    if self.log_stop_event.wait(0.8):
                        break
                    continue

                if size < self.log_offset:
                    self.log_offset = 0

                if size > self.log_offset:
                    try:
                        with path.open("rb") as handle:
                            handle.seek(self.log_offset)
                            blob = handle.read(size - self.log_offset)
                            self.log_offset = handle.tell()
                        self.process_new_log_data(blob)
                    except OSError:
                        if self.log_stop_event.wait(0.8):
                            break

                if self.key_running:
                    self.tick_accept_spam()

                if self.log_stop_event.wait(0.2):
                    break
        finally:
            self.log_thread = None
            self.emit_state()


class Api:
    def __init__(self, engine):
        self.engine = engine

    def get_state(self):
        return self.engine.get_state()

    def update_settings(self, settings):
        return self.engine.update_settings(settings)

    def toggle_mouse(self):
        return self.engine.toggle_mouse()

    def toggle_key(self):
        return self.engine.toggle_key()

    def toggle_death_watch(self):
        return self.engine.toggle_death_watch()

    def choose_log_file(self):
        return self.engine.choose_log_file()

    def set_log_file(self, path):
        return self.engine.set_log_path(path)


def ui_path():
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    return (base / "ui" / "svg_control_panel_restored.html").as_uri()


if __name__ == "__main__":
    if not _is_process_elevated():
        print("[WARN] Running without Administrator rights. If Star Citizen is elevated, global hotkeys/input injection may fail.")

    engine = MouseDriftEngine()
    api = Api(engine)

    window = webview.create_window(
        "Mouse Drift HUD",
        url=ui_path(),
        js_api=api,
        width=1260,
        height=670,
    )

    engine.attach_window(window)
    engine.start_hotkeys()

    try:
        webview.start()
    finally:
        engine.shutdown()