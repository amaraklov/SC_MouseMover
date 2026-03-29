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
    ? {
        outerFill: "#6a3328",
        outerStroke: "#ff967e",
        innerFill: "rgba(255,126,104,0.16)",
      }
    : {
        outerFill: "#30261a",
        outerStroke: "#ffd27d",
        innerFill: "rgba(255,179,71,0.08)",
      };
}

function applyButtonState(outer, inner, isOn) {
  const colors = buttonColors(isOn);
  outer.setAttribute("fill", colors.outerFill);
  outer.setAttribute("stroke", colors.outerStroke);
  inner.setAttribute("fill", colors.innerFill);
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
  els.statusStrip.textContent = state.mouseOn || state.keyOn ? "SYSTEM ACTIVE" : "SELF STATUS";

  applyButtonState(els.mouseBtnOuter, els.mouseBtnInner, state.mouseOn);
  applyButtonState(els.keyBtnOuter, els.keyBtnInner, state.keyOn);
  applyButtonState(els.f11BtnOuter, els.f11BtnInner, state.keyOn);
  applyButtonState(els.f12BtnOuter, els.f12BtnInner, state.mouseOn);

  els.toggleMouseBtn.querySelector("strong").textContent =
    state.mouseOn ? "F12 Toggle Mouse — ON" : "F12 Toggle Mouse — OFF";
  els.toggleKeyBtn.querySelector("strong").textContent =
    state.keyOn ? "F11 Toggle Key Spam — ON" : "F11 Toggle Key Spam — OFF";
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

  if (window.pywebview?.api) {
    await window.pywebview.api.update_settings(settings);
  }
}

async function toggleMouse() {
  if (window.pywebview?.api) {
    const newState = await window.pywebview.api.toggle_mouse();
    Object.assign(state, newState);
    render();
  }
}

async function toggleKey() {
  if (window.pywebview?.api) {
    const newState = await window.pywebview.api.toggle_key();
    Object.assign(state, newState);
    render();
  }
}

window.app = {
  updateFromPython(newState) {
    Object.assign(state, newState);
    render();
  },
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
els.mouseBtnGroup?.addEventListener("click", toggleMouse);
els.keyBtnGroup?.addEventListener("click", toggleKey);
els.f11BtnGroup?.addEventListener("click", toggleKey);
els.f12BtnGroup?.addEventListener("click", toggleMouse);

window.addEventListener("pywebviewready", async () => {
  const initial = await window.pywebview.api.get_state();
  Object.assign(state, initial);
  render();
});

render();