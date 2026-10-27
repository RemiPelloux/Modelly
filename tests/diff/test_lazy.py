"""``import modelly.diff`` works without importing JAX (it runs without JAX installed)."""

import subprocess
import sys


def test_import_does_not_load_jax():
    """The package, its zoo twins and their names import with JAX untouched."""
    code = (
        "import sys, modelly.diff, modelly.zoo.bass_diffusion.differentiable, "
        "modelly.zoo.bouchaud_mezard.differentiable\n"
        "print(any(m.split('.')[0] in ('jax', 'jaxlib') for m in sys.modules))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "False"
