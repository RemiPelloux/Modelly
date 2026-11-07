// The runner page: the parameter panel, the run controls and the worker that runs Python.
// <body data-state> is idle, loading, ready, running or error, <body data-steps> the steps
// run and <body data-running> the model's running flag, for scripts and tests that drive
// the page. ?lazy=1 waits for a click before
// downloading Python (an embedded page in the docs).

import { drawPlot, drawSpace } from "./draw.js";

const $ = (id) => document.getElementById(id);
const manifest = await (await fetch("modelly.json")).json();
const worker = new Worker("worker.js", { type: "module" });
const series = {};
// The panel's inputs by parameter name, not by form name: a parameter may be called steps.
const fields = new Map();
const RUN_BUTTONS = ["reset", "step", "run"];

function setState(state, text) {
  document.body.dataset.state = state;
  $("status").textContent = text;
  for (const id of RUN_BUTTONS) $(id).disabled = state !== "ready";
  $("stop").disabled = state !== "running";
}

function input(parameter) {
  const { kind, default: value, choices } = parameter;
  if (kind === "choice") {
    const select = document.createElement("select");
    select.append(...choices.map((label, i) => new Option(label, i, false, i === value)));
    return select;
  }
  const element = document.createElement("input");
  const types = { bool: "checkbox", int: "number", float: "number", fraction: "range", text: "text" };
  element.type = types[kind] ?? "text";
  if (kind === "int") element.step = "1";
  if (kind === "float") element.step = "any";
  if (kind === "fraction") Object.assign(element, { min: 0, max: 1, step: 0.01 });
  if (kind === "bool") element.checked = value;
  else element.value = value;
  element.disabled = kind === "fixed";
  return element;
}

function buildPanel() {
  for (const parameter of manifest.parameters) {
    const label = document.createElement("label");
    const element = input(parameter);
    fields.set(parameter.name, element);
    label.append(parameter.name, element);
    if (parameter.kind === "fraction") {
      const shown = document.createElement("output");
      shown.value = element.value;
      element.addEventListener("input", () => (shown.value = element.value));
      label.append(shown);
    }
    $("parameters").append(label);
  }
  $("seed").value = manifest.seed;
  $("steps").value = manifest.steps;
}

function values() {
  const read = (p, e) => (p.kind === "bool" ? e.checked : p.kind === "text" ? e.value : Number(e.value));
  const editable = manifest.parameters.filter((p) => p.kind !== "fixed");
  return Object.fromEntries(editable.map((p) => [p.name, read(p, fields.get(p.name))]));
}

function colourOptions(attributes) {
  const select = $("colour");
  const wanted = ["class", ...attributes];
  if ([...select.options].map((o) => o.value).join() === wanted.join()) return;
  const current = select.value;
  select.replaceChildren(...wanted.map((name) => new Option(name, name, false, name === current)));
}

function show(text) {
  const state = JSON.parse(text);
  for (const [name, rows] of Object.entries(state.series ?? {})) (series[name] ??= []).push(...rows);
  drawSpace($("space"), $("space-legend"), state.space);
  drawPlot($("plot"), $("plot-legend"), series);
  colourOptions(state.attributes);
  document.body.dataset.steps = state.steps;
  document.body.dataset.running = state.running;
  const ended = state.running ? "" : " · the model stopped";
  $("status").textContent = `step ${state.steps} · time ${state.time}${ended}`;
}

const send = (type, extra = {}) => worker.postMessage({ type, colour: $("colour").value, ...extra });

function reset() {
  for (const name of Object.keys(series)) delete series[name];
  setState("running", "building the model…");
  send("build", { values: values(), seed: Number($("seed").value) });
}

function start(steps) {
  setState("running", "running…");
  send("run", { steps });
}

const handlers = {
  progress: ({ text }) => setState("loading", text),
  ready: ({ seconds, native, missing, python }) => {
    const compiled = native.length ? `compiled: ${native.join(", ")}` : "pure Python";
    const absent = missing.length ? `; not in Pyodide: ${missing.join(", ")}` : "";
    const loaded = `loaded in ${seconds.toFixed(1)} s`;
    $("versions").textContent = `Modelly ${manifest.modelly} (${compiled}), Python ${python}, Pyodide ${manifest.pyodide.version}, ${loaded}${absent}.`;
    reset();
  },
  state: ({ state }) => show(state),
  idle: () => setState("ready", $("status").textContent),
  error: ({ message }) => setState("error", message),
};

worker.onmessage = ({ data }) => handlers[data.type](data);
worker.onerror = (event) => setState("error", event.message ?? "the worker failed to start");

function boot() {
  $("start").hidden = true;
  setState("loading", "Downloading Python…");
  worker.postMessage({ type: "init", manifest, base: new URL(".", location.href).href });
}

buildPanel();
$("reset").addEventListener("click", reset);
$("step").addEventListener("click", () => start(1));
$("run").addEventListener("click", () => start(Number($("steps").value)));
$("stop").addEventListener("click", () => send("stop"));
$("colour").addEventListener("change", () => send("colour"));
if (new URLSearchParams(location.search).get("lazy") === "1") {
  $("start").hidden = false;
  $("start").disabled = false;
  $("start").addEventListener("click", boot);
  $("status").textContent = "Press Start to download Python and the model (14 MB or more, cached afterwards).";
} else {
  boot();
}
