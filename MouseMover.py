import json
import math
import random
import sys
import threading
import time
from pathlib import Path

import webview
from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key, Listener as KeyboardListener
from pynput.mouse import Controller as MouseController


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
                <text id="svgMouseInterval" x="86" y="132" fill="#ffd893" font-size="27" filter="url(#softGlow)">4800 ms</text>

                <text x="706" y="98" fill="#ffcc79" font-size="34" font-weight="700" letter-spacing="3" filter="url(#softGlow)">KEY LOOP</text>
                <text id="svgKeyInterval" x="706" y="132" fill="#ffd893" font-size="27" filter="url(#softGlow)">2.50 s</text>

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
                <div class="label">Key Spam</div>
                <div class="value" id="keyStateLabel">OFF</div>
            </div>

            <div class="card fields">
                <label class="field">
                    <span>Interval ms</span>
                    <input id="intervalInput" type="number" min="1" step="1" value="4800" />
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
                    <span>Key Interval</span>
                    <input id="keyIntervalInput" type="number" min="0.1" step="0.1" value="2.5" />
                </label>
            </div>

            <div class="stack">
                <button id="toggleMouseBtn" class="mini-button">
                    <strong>F12 Toggle Mouse - OFF</strong>
                    <span>Global hotkey, no focus required</span>
                </button>
                <button id="toggleKeyBtn" class="mini-button">
                    <strong>F11 Toggle Key Spam - OFF</strong>
                    <span>Sends [ at configured interval</span>
                </button>
            </div>
        </aside>
    </div>

    <script>
        const state = {
            mouseOn: false,
            keyOn: false,
            intervalMs: 4800,
            maxPixels: 96,
            movesBeforeReturn: 16,
            smoothSteps: 12,
            moveDuration: 0.18,
            keyInterval: 2.5,
        };

        const els = {
            intervalInput: document.getElementById("intervalInput"),
            maxPixelsInput: document.getElementById("maxPixelsInput"),
            movesInput: document.getElementById("movesInput"),
            smoothInput: document.getElementById("smoothInput"),
            durationInput: document.getElementById("durationInput"),
            keyIntervalInput: document.getElementById("keyIntervalInput"),
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
            els.keyIntervalInput.value = state.keyInterval;

            els.mouseStateLabel.textContent = state.mouseOn ? "ON" : "OFF";
            els.keyStateLabel.textContent = state.keyOn ? `${state.keyInterval.toFixed(2)}s / [` : "OFF";
            els.svgMouseInterval.textContent = `${state.intervalMs} ms`;
            els.svgKeyInterval.textContent = `${state.keyInterval.toFixed(2)} s`;
            els.statusStrip.setAttribute("fill", state.mouseOn || state.keyOn ? "#ffd183" : "#ffe57a");

            applyButtonState(els.mouseBtnOuter, els.mouseBtnInner, state.mouseOn);
            applyButtonState(els.keyBtnOuter, els.keyBtnInner, state.keyOn);
            applyButtonState(els.f11BtnOuter, els.f11BtnInner, state.keyOn);
            applyButtonState(els.f12BtnOuter, els.f12BtnInner, state.mouseOn);

            els.toggleMouseBtn.querySelector("strong").textContent =
                state.mouseOn ? "F12 Toggle Mouse - ON" : "F12 Toggle Mouse - OFF";
            els.toggleKeyBtn.querySelector("strong").textContent =
                state.keyOn ? "F11 Toggle Key Spam - ON" : "F11 Toggle Key Spam - OFF";
        }

        function collectSettings() {
            return {
                intervalMs: parseInt(els.intervalInput.value || "4800", 10),
                maxPixels: parseInt(els.maxPixelsInput.value || "96", 10),
                movesBeforeReturn: parseInt(els.movesInput.value || "16", 10),
                smoothSteps: parseInt(els.smoothInput.value || "12", 10),
                moveDuration: parseFloat(els.durationInput.value || "0.18"),
                keyInterval: parseFloat(els.keyIntervalInput.value || "2.5"),
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
            els.keyIntervalInput,
        ].forEach((input) => input.addEventListener("change", pushSettings));

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

        self.mouse_stop_event = threading.Event()
        self.key_stop_event = threading.Event()

        self.mouse_thread = None
        self.key_thread = None
        self.hotkey_listener = None
        self.pressed_hotkeys = set()

        self.window = None
        self.lock = threading.Lock()

        self.interval_ms = 4800
        self.max_pixels = 96
        self.moves_before_return = 16
        self.smooth_steps = 12
        self.move_duration = 0.18
        self.key_interval = 2.5

        self.origin = None
        self.move_count = 0

    def attach_window(self, window):
        self.window = window

    def emit_state(self):
        if not self.window:
            return

        state = {
            "mouseOn": self.mouse_running,
            "keyOn": self.key_running,
            "intervalMs": self.interval_ms,
            "maxPixels": self.max_pixels,
            "movesBeforeReturn": self.moves_before_return,
            "smoothSteps": self.smooth_steps,
            "moveDuration": self.move_duration,
            "keyInterval": self.key_interval,
        }

        js = f"window.app && window.app.updateFromPython({json.dumps(state)});"
        try:
            self.window.evaluate_js(js)
        except Exception:
            pass

    def start_hotkeys(self):
        if self.hotkey_listener is not None:
            return

        def on_press(key):
            try:
                if key in self.pressed_hotkeys:
                    return

                if key == Key.f12:
                    self.pressed_hotkeys.add(key)
                    self.toggle_mouse()
                elif key == Key.f11:
                    self.pressed_hotkeys.add(key)
                    self.toggle_key()
            except Exception:
                pass

        def on_release(key):
            try:
                self.pressed_hotkeys.discard(key)
            except Exception:
                pass

        self.hotkey_listener = KeyboardListener(on_press=on_press, on_release=on_release)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()

    def stop_hotkeys(self):
        if self.hotkey_listener is not None:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
            self.hotkey_listener = None
        self.pressed_hotkeys.clear()

    def update_settings(self, settings):
        with self.lock:
            self.interval_ms = max(1, int(settings.get("intervalMs", self.interval_ms)))
            self.max_pixels = max(0, min(255, int(settings.get("maxPixels", self.max_pixels))))
            self.moves_before_return = max(
                1, int(settings.get("movesBeforeReturn", self.moves_before_return))
            )
            self.smooth_steps = max(1, int(settings.get("smoothSteps", self.smooth_steps)))
            self.move_duration = max(0.0, float(settings.get("moveDuration", self.move_duration)))
            self.key_interval = max(0.1, float(settings.get("keyInterval", self.key_interval)))

        self.emit_state()
        return {"ok": True}

    def get_state(self):
        return {
            "mouseOn": self.mouse_running,
            "keyOn": self.key_running,
            "intervalMs": self.interval_ms,
            "maxPixels": self.max_pixels,
            "movesBeforeReturn": self.moves_before_return,
            "smoothSteps": self.smooth_steps,
            "moveDuration": self.move_duration,
            "keyInterval": self.key_interval,
        }

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

        self.key_stop_event.clear()
        self.key_running = True

        self.key_thread = threading.Thread(target=self.key_loop, daemon=True)
        self.key_thread.start()

    def stop_key(self):
        self.key_stop_event.set()
        self.key_running = False

    def shutdown(self):
        self.stop_mouse()
        self.stop_key()
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
        start_x, start_y = self.mouse.position
        prev_x, prev_y = start_x, start_y

        if dx == 0 and dy == 0:
            return

        if steps <= 1 or duration <= 0:
            self.mouse.position = (start_x + dx, start_y + dy)
            return

        sleep_time = duration / steps

        for i in range(1, steps + 1):
            if self.mouse_stop_event.is_set():
                return

            t = i / steps
            eased = self.ease_in_out(t)

            target_x = round(start_x + dx * eased)
            target_y = round(start_y + dy * eased)

            if (target_x, target_y) != (prev_x, prev_y):
                self.mouse.position = (target_x, target_y)
                prev_x, prev_y = target_x, target_y

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

    def key_loop(self):
        try:
            while not self.key_stop_event.is_set():
                self.keyboard.press("[")
                self.keyboard.release("[")

                interval = self.key_interval * random.uniform(0.95, 1.05)
                if self.key_stop_event.wait(interval):
                    break
        finally:
            self.key_running = False
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


def ui_path():
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    return (base / "ui" / "svg_control_panel_restored.html").as_uri()


if __name__ == "__main__":
    engine = MouseDriftEngine()
    api = Api(engine)

    window = webview.create_window(
        "Mouse Drift HUD",
        url=ui_path(),
        js_api=api,
        width=930,
        height=670,
    )

    engine.attach_window(window)
    engine.start_hotkeys()

    try:
        webview.start()
    finally:
        engine.shutdown()