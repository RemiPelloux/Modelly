// The Web Worker that runs the model: Pyodide, the packages, Modelly and the model's code.
// The page posts {type: "init" | "build" | "run" | "stop" | "colour", ...}; the worker
// answers "progress", "ready", "state", "idle" or "error". A run advances the model in
// slices of about 50 ms (modelly.web.runtime.STEP_BUDGET_S) and yields between them, so a
// "stop" posted during a long run is handled after the current slice.

const MODEL_DIR = "/home/pyodide/model";
// Standard-library modules that some Pyodide releases ship as separate packages (sqlite3
// before Pyodide 314; `import modelly` needs it): loaded when the lock file lists them.
const UNVENDORED = ["sqlite3"];
let py = null;
let run = null;
let stopping = false;

const post = (type, extra = {}) => postMessage({ type, ...extra });
const nextTick = () => new Promise((resolve) => setTimeout(resolve));

// The wheel URLs of `names` and of the shared libraries they link to. A Python package
// the model was not seen to import is left out, even when Pyodide lists it as a
// dependency (networkx lists matplotlib): that is what keeps the first load small.
function packageUrls(lock, names, indexURL) {
  const wanted = new Set(names);
  const urls = new Map();
  const missing = [];
  const visit = (name) => {
    const pkg = lock.packages[name];
    if (!pkg) return void missing.push(name);
    if (urls.has(name)) return;
    urls.set(name, new URL(pkg.file_name, indexURL).href);
    for (const dep of pkg.depends) {
      if (wanted.has(dep) || lock.packages[dep]?.package_type === "shared_library") visit(dep);
    }
  };
  names.forEach(visit);
  return { urls: [...urls.values()], missing };
}

async function installModel(manifest, base) {
  await py.loadPackage(new URL(manifest.wheel, base).href);
  if (!manifest.model_archive) return;
  const response = await fetch(new URL(manifest.model_archive, base));
  py.unpackArchive(await response.arrayBuffer(), "zip", { extractDir: MODEL_DIR });
  py.pyimport("sys").path.insert(0, MODEL_DIR);
}

async function init({ manifest, base }) {
  const start = performance.now();
  const { loadPyodide } = await import(`${manifest.pyodide.url}pyodide.mjs`);
  post("progress", { text: "Starting Python…" });
  py = await loadPyodide({ indexURL: manifest.pyodide.url });
  post("progress", { text: `Loading ${manifest.packages.join(", ")}…` });
  const stdlib = UNVENDORED.filter((name) => py.lockfile.packages[name]);
  const names = [...manifest.packages, ...stdlib];
  const { urls, missing } = packageUrls(py.lockfile, names, manifest.pyodide.url);
  await py.loadPackage(urls, { messageCallback: () => {} });
  post("progress", { text: "Loading Modelly and the model…" });
  await installModel(manifest, base);
  const runtime = py.pyimport("modelly.web.runtime");
  run = runtime.BrowserRun(manifest.target);
  const seconds = (performance.now() - start) / 1000;
  const native = runtime.native_modules().toJs();
  post("ready", { seconds, native, missing, python: py.runPython("import sys; sys.version.split()[0]") });
}

function build({ values, seed, colour }) {
  run.build(JSON.stringify(values), seed);
  post("state", { state: run.state_json(colour) });
  post("idle", { stopped: false });
}

async function runSteps({ steps, colour }) {
  stopping = false;
  let left = steps;
  while (left > 0 && !stopping) {
    const done = run.advance(left);
    left -= done;
    post("state", { state: run.state_json(colour) });
    if (done === 0) break;
    await nextTick();
  }
  post("idle", { stopped: stopping });
}

const handlers = {
  init,
  build,
  run: runSteps,
  stop: () => { stopping = true; },
  colour: ({ colour }) => post("state", { state: run.state_json(colour) }),
};

onmessage = async ({ data }) => {
  try {
    await handlers[data.type](data);
  } catch (error) {
    post("error", { message: String(error.message ?? error) });
  }
};
