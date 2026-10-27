// Smoke test of the pure wheel in Pyodide (CPython compiled to WebAssembly), under node.
//
//   npm install pyodide@<version>          # next to this script, or anywhere on NODE_PATH
//   node scripts/pyodide-smoke.mjs dist/modelly_abm-X.Y.Z-py3-none-any.whl
//
// Loads Pyodide with its sqlite3 and networkx packages, installs the wheel with micropip
// (numpy, pandas and scipy come from the Pyodide distribution, tqdm from PyPI), imports
// modelly, checks that the pure-Python twins are in use, and runs one bundled example for
// a few steps. Exits 1 on any failure.
import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { loadPyodide } from "pyodide";

const SMOKE = `
import modelly
from modelly.core import rng
from modelly.examples.basic.boltzmann_wealth_model.model import (
    BoltzmannScenario,
    BoltzmannWealth,
)

assert not rng.NATIVE, "a compiled module loaded inside WebAssembly"
model = BoltzmannWealth(BoltzmannScenario(rng=42))
model.run_for(10)
frame = model.datacollector.get_model_vars_dataframe()
assert len(frame) == 11 and frame["Gini"].between(0, 1).all(), frame
f"modelly {modelly.__version__} in Pyodide: Boltzmann wealth, 10 steps, Gini {frame['Gini'].iloc[-1]:.3f}"
`;

async function main(wheel) {
  const pyodide = await loadPyodide();
  // sqlite3 is a separate package in Pyodide and `import modelly` needs it (the SQL
  // recorder); networkx because importing any bundled example imports them all.
  await pyodide.loadPackage(["micropip", "sqlite3", "networkx"]);
  const target = `/tmp/${basename(wheel)}`;
  pyodide.FS.writeFile(target, readFileSync(wheel));
  const micropip = pyodide.pyimport("micropip");
  await micropip.install(`emfs:${target}`);
  console.log(await pyodide.runPythonAsync(SMOKE));
}

if (process.argv.length !== 3) {
  console.error("usage: node scripts/pyodide-smoke.mjs <pure wheel>");
  process.exit(2);
}
main(process.argv[2]).catch((error) => {
  console.error(error);
  process.exit(1);
});
