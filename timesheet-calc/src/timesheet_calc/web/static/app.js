"use strict";

// All time math happens on the server (timesheet_calc.core). This script only manages rows and displays results.

const DEBOUNCE_MS = 200;
const STORAGE_KEY = "timesheet-calc:v1";
const DEFAULT_CALC_ROWS = 5;
const DEFAULT_SUM_ROWS = 7;
const MAX_ROWS = 100; // matches schemas.MAX_ROWS
const MAX_FIELD = 16; // matches schemas.MAX_FIELD
const OFFLINE_MESSAGE = "Can't reach the calculator. Check that the server is running, then edit any entry to retry.";
const SIGNED_OUT_MESSAGE = "Your sign-in has expired. Reload the page to sign in again.";
const FORBIDDEN_MESSAGE = "This account isn't allowed to use the calculator.";

const $ = (selector) => document.querySelector(selector);

const blankCalcRows = (count) => Array.from({ length: count }, () => ({ start: "", end: "" }));
const blankSumRows = (count) => Array.from({ length: count }, () => "");
const clip = (value) => String(value ?? "").slice(0, MAX_FIELD);

function loadState() {
  const fallback = {
    calc: blankCalcRows(DEFAULT_CALC_ROWS),
    sum: blankSumRows(DEFAULT_SUM_ROWS),
    mode: "infer",
    decimal: false,
  };
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null");
    if (!saved || typeof saved !== "object") return fallback;
    const calc = Array.isArray(saved.calc) ? saved.calc.slice(0, MAX_ROWS) : [];
    const sum = Array.isArray(saved.sum) ? saved.sum.slice(0, MAX_ROWS) : [];
    return {
      calc: calc.length ? calc.map((row) => ({ start: clip(row?.start), end: clip(row?.end) })) : fallback.calc,
      sum: sum.length ? sum.map(clip) : fallback.sum,
      mode: saved.mode === "strict" ? "strict" : "infer",
      decimal: saved.decimal === true,
    };
  } catch {
    return fallback;
  }
}

const state = loadState();

function saveState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Storage blocked or full: entries simply won't survive a reload.
  }
}

const panels = {
  calc: {
    list: $("#calc-rows"),
    template: $("#calc-row"),
    total: $("#calc-total"),
    totalDecimal: $("#calc-total-decimal"),
    endpoint: "/api/calc",
    rows: () => state.calc,
    blank: () => ({ start: "", end: "" }),
    reset: () => { state.calc = blankCalcRows(DEFAULT_CALC_ROWS); },
    payload: () => ({ entries: state.calc, mode: state.mode }),
    controller: null,
    timer: null,
    lastResponse: null,
  },
  sum: {
    list: $("#sum-rows"),
    template: $("#sum-row"),
    total: $("#sum-total"),
    totalDecimal: $("#sum-total-decimal"),
    endpoint: "/api/sum",
    rows: () => state.sum,
    blank: () => "",
    reset: () => { state.sum = blankSumRows(DEFAULT_SUM_ROWS); },
    payload: () => ({ durations: state.sum }),
    controller: null,
    timer: null,
    lastResponse: null,
  },
};

const statusByPanel = { calc: "", sum: "" };

function setStatus(name, message) {
  statusByPanel[name] = message;
  $("#status").textContent = statusByPanel.calc || statusByPanel.sum;
}

function panelNameOf(element) {
  return element.closest("ol").id === "calc-rows" ? "calc" : "sum";
}

// ---- Rendering ----------------------------------------------------------------------------------------------------

function buildRow(name, row, index) {
  const item = panels[name].template.content.firstElementChild.cloneNode(true);
  const number = index + 1;
  const resultId = `${name}-result-${index}`;
  item.dataset.index = String(index);
  item.querySelector(".result").id = resultId;
  for (const input of item.querySelectorAll("input")) {
    const field = input.dataset.field;
    input.value = name === "calc" ? row[field] : row;
    input.setAttribute("aria-describedby", resultId);
    input.setAttribute("aria-label", name === "calc" ? `Row ${number} ${field} time` : `Row ${number} hours`);
  }
  item.querySelector(".remove").setAttribute("aria-label", `Remove row ${number}`);
  return item;
}

function renderRows(name) {
  const rows = panels[name].rows();
  panels[name].list.replaceChildren(...rows.map((row, index) => buildRow(name, row, index)));
}

function sentenceCase(text) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function punch(stamp) {
  stamp.classList.remove("punched");
  void stamp.offsetWidth; // restart the animation
  stamp.classList.add("punched");
}

function applyResults(name) {
  const panel = panels[name];
  const data = panel.lastResponse;
  if (!data) return;

  const items = panel.list.querySelectorAll(".row");
  data.results.forEach((result, index) => {
    const item = items[index];
    if (!item) return;
    const output = item.querySelector(".result");
    const inputs = item.querySelectorAll("input");
    output.replaceChildren();
    output.classList.toggle("error", Boolean(result.error));
    inputs.forEach((input) => input.removeAttribute("aria-invalid"));

    if (result.error) {
      output.textContent = sentenceCase(result.error);
      inputs.forEach((input) => input.setAttribute("aria-invalid", "true"));
    } else if (result.duration) {
      output.append(result.duration);
      if (state.decimal) {
        const decimal = document.createElement("span");
        decimal.className = "decimal";
        decimal.textContent = `${result.decimal_hours} h`;
        output.append(decimal);
      }
    }
  });

  const changed = panel.total.textContent !== data.total;
  panel.total.textContent = data.total;
  panel.totalDecimal.textContent = state.decimal ? `${data.total_decimal_hours} h` : "";
  if (changed) punch(panel.total.closest(".stamp"));
  if (name === "calc") $("#send-total").disabled = data.total === "0:00";
}

// ---- Server calls -------------------------------------------------------------------------------------------------

async function recalc(name) {
  const panel = panels[name];
  clearTimeout(panel.timer);
  panel.controller?.abort(); // a newer edit supersedes any request still in flight
  const controller = new AbortController();
  panel.controller = controller;

  try {
    const response = await fetch(panel.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(panel.payload()),
      signal: controller.signal,
    });
    if (response.status === 401) {
      setStatus(name, SIGNED_OUT_MESSAGE);
      return;
    }
    if (response.status === 403) {
      setStatus(name, FORBIDDEN_MESSAGE);
      return;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    panel.lastResponse = await response.json();
    applyResults(name);
    setStatus(name, "");
  } catch (error) {
    if (error.name !== "AbortError") setStatus(name, OFFLINE_MESSAGE);
  }
}

function schedule(name) {
  clearTimeout(panels[name].timer);
  panels[name].timer = setTimeout(() => recalc(name), DEBOUNCE_MS);
}

// ---- Row actions --------------------------------------------------------------------------------------------------

function addRow(name) {
  const rows = panels[name].rows();
  if (rows.length >= MAX_ROWS) {
    setStatus(name, `A sheet holds up to ${MAX_ROWS} rows.`);
    return false;
  }
  rows.push(panels[name].blank());
  saveState();
  renderRows(name);
  recalc(name);
  panels[name].list.lastElementChild.querySelector("input").focus();
  return true;
}

function removeRow(name, index) {
  const rows = panels[name].rows();
  rows.splice(index, 1);
  if (rows.length === 0) rows.push(panels[name].blank());
  saveState();
  renderRows(name);
  recalc(name);
}

function clearPanel(name) {
  panels[name].reset();
  saveState();
  renderRows(name);
  recalc(name);
}

function sendTotalToSum() {
  const total = panels.calc.lastResponse?.total;
  if (!total || total === "0:00") return;
  const slot = state.sum.findIndex((value) => value.trim() === "");
  if (slot === -1) {
    if (state.sum.length >= MAX_ROWS) {
      setStatus("sum", `A sheet holds up to ${MAX_ROWS} rows.`);
      return;
    }
    state.sum.push(total);
  } else {
    state.sum[slot] = total;
  }
  saveState();
  renderRows("sum");
  recalc("sum");
}

// ---- Events -------------------------------------------------------------------------------------------------------

for (const [name, panel] of Object.entries(panels)) {
  panel.list.addEventListener("input", (event) => {
    const input = event.target.closest("input");
    if (!input) return;
    const index = Number(input.closest(".row").dataset.index);
    if (name === "calc") {
      state.calc[index][input.dataset.field] = input.value;
    } else {
      state.sum[index] = input.value;
    }
    saveState();
    schedule(name);
  });

  panel.list.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || !event.target.matches("input")) return;
    event.preventDefault();
    const inputs = [...panel.list.querySelectorAll("input")];
    const next = inputs[inputs.indexOf(event.target) + 1];
    if (next) {
      next.focus();
    } else {
      addRow(name);
    }
  });
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  switch (button.dataset.action) {
    case "remove":
      removeRow(panelNameOf(button), Number(button.closest(".row").dataset.index));
      break;
    case "add-calc":
      addRow("calc");
      break;
    case "add-sum":
      addRow("sum");
      break;
    case "clear-calc":
      clearPanel("calc");
      break;
    case "clear-sum":
      clearPanel("sum");
      break;
    case "send-total":
      sendTotalToSum();
      break;
    default:
      break;
  }
});

$("#mode").addEventListener("change", (event) => {
  state.mode = event.target.value === "strict" ? "strict" : "infer";
  saveState();
  recalc("calc");
});

$("#decimal").addEventListener("change", (event) => {
  state.decimal = event.target.checked;
  saveState();
  applyResults("calc"); // display-only: no server round trip needed
  applyResults("sum");
});

// ---- Boot ---------------------------------------------------------------------------------------------------------

$("#mode").value = state.mode;
$("#decimal").checked = state.decimal;
renderRows("calc");
renderRows("sum");
recalc("calc");
recalc("sum");
