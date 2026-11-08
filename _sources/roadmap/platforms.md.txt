# Platforms: Windows, macOS and Linux

**Rule:** a feature ships only when it works on Windows, macOS and Linux, with the same results
for the same seed. A feature that cannot (for example, a SLURM executor, which needs a Linux
cluster) must still be usable from all three: you submit from your Windows or macOS laptop, the
cluster runs Linux.

## Support matrix

Wheels carry the compiled modules; every other platform installs the pure-Python wheel, which
gives the same results, more slowly.

| Platform | 1.2.0 (today) | 1.3.0 | 1.4.0 | 1.5.0 | 2.0.0 |
|---|---|---|---|---|---|
| Linux x86-64 (manylinux) | compiled | compiled | compiled | compiled | compiled, abi3 |
| Linux ARM64 (manylinux) | compiled | compiled | compiled | compiled | compiled, abi3 |
| Linux musllinux (Alpine), x86-64 and ARM64 | compiled | compiled | compiled | compiled | compiled, abi3 |
| macOS Apple silicon (ARM64) | compiled | compiled | compiled | compiled | compiled, abi3 |
| macOS Intel (x86-64) | compiled | compiled | compiled | compiled | compiled, abi3 |
| Windows x86-64 | compiled | compiled | compiled | compiled | compiled, abi3 |
| Windows ARM64 | pure | compiled | compiled | compiled | compiled, abi3 |
| Free-threaded CPython (3.14t and later), all of the above | pure | compiled | compiled | compiled | compiled |
| Browser (Pyodide, WebAssembly) | not supported | pure (experimental) | compiled | compiled | compiled |

| Python | 1.2.0 | 1.3.0 | 1.4.0 | 1.5.0 | 2.0.0 |
|---|---|---|---|---|---|
| 3.12 | yes | yes | yes | yes | no |
| 3.13 | yes | yes | yes | yes | yes |
| 3.14 | yes | yes | yes | yes | yes |
| 3.15 | yes | yes | yes | yes | yes |
| 3.16 | no | no | yes (when released) | yes | yes |

"abi3" in 2.0.0 means one wheel per platform serves every supported Python version (the stable
ABI), so a new Python release works on day one.

## Optional features by platform

Some features depend on optional libraries or hardware. The rule is the same: every one has a
path on every operating system, and the docs say which.

| Feature | Linux | macOS | Windows | Notes |
|---|---|---|---|---|
| Process executor (`run_grid`, experiments) | yes | yes | yes | Windows and macOS start workers with `spawn`: model classes and reporters must be importable at module level (lint rule in 1.3) |
| Thread executor | yes | yes | yes | Needs a free-threaded build for real parallelism |
| Dask and Ray executors | yes | yes | yes | Wheels on all three |
| SLURM and PBS executors | cluster side | submit side | submit side | The cluster runs Linux; submission over SSH works from any OS |
| MPI (distributed runs, 1.4) | Open MPI, MPICH | Open MPI | MS-MPI | Through `mpi4py`; Dask and Ray backends need no MPI |
| GPU arrays (1.3 preview, 1.4 GA) | CUDA (CuPy), JAX | JAX on Metal, else CPU | CUDA (CuPy) | Results compared against numpy; differences documented |
| Geospatial (1.3) | yes | yes | yes | GeoPandas, Shapely, pyproj and rasterio ship wheels for all three; no system GDAL needed |
| Animations (1.3) | yes | yes | yes | `imageio-ffmpeg` bundles ffmpeg; no system install |
| Studio (1.3) | yes | yes | yes | Opens in the default browser; tested in Chromium, Firefox, Safari and Edge |
| Editor integration, LSP (1.3) | yes | yes | yes | VS Code, PyCharm, Neovim |
| R and Julia bindings (1.5) | yes | yes | yes | reticulate and PythonCall |

## Engineering rules that keep it true

1. **CI tests on all three.** The `build` workflow already runs the suite on Ubuntu, macOS and
   Windows; every new test runs there. The release workflow builds and import-tests wheels for
   each platform before anything is published.
2. **A local gate that runs everywhere.** `scripts/ci-local.sh` is bash. 1.3.0 adds
   `python -m modelly.dev gate`, the same stages in Python, so contributors on Windows run the
   same gate without WSL or Git Bash.
3. **No Unix tools in library code.** No calls to `sh`, `taskset`, `curl` or `sed` from
   `modelly/`. Scripts that users run (data downloads, benchmarks) are Python, not bash.
   `modelly bench` pins CPUs with `psutil` where the OS allows it (Linux, Windows) and says so
   where it does not (macOS).
4. **Paths and text.** `pathlib` everywhere; every `open()` of a text file names
   `encoding="utf-8"` (Windows defaults to a legacy code page); manifests store paths
   relative and in POSIX form; hashes are taken over bytes, never over text with platform line
   endings. The ruff rule for unspecified encodings is turned on in 1.3.
5. **Files that are written while read.** Checkpoints and result stores are written to a
   temporary file and moved into place with `os.replace`, which is atomic on all three and
   avoids Windows sharing violations.
6. **Native code for three compilers.** Every C module builds with GCC, Clang and MSVC, at
   warning level `-Wall` / `/W4`, with no compiler extensions outside an `#ifdef`. Thread
   safety is checked with ThreadSanitizer on Linux and macOS and by the free-threaded test suite
   on all three.
7. **Optional dependencies must have wheels for all three.** A library that needs a system
   install on one OS is not accepted as a dependency of a shipped feature.
8. **Determinism across platforms.** The determinism suite (1.3) runs every example, compiled
   and pure, saved and loaded, on all three and compares the outputs byte for byte; floating-point
   outputs that legitimately differ (for example a GPU reduction) are listed with their tolerance.
9. **Docs for both shells.** Where a command differs between bash and PowerShell, the docs
   show both.

## Per-release platform work

| Release | Platform work |
|---|---|
| 1.3.0 | Windows ARM64 wheels; free-threaded wheels on all three; `python -m modelly.dev gate`; unspecified-encoding rule; cross-platform determinism suite; `spawn`-safe lint rule; Pyodide pure-wheel smoke test |
| 1.4.0 | WebAssembly build of the compiled modules; MPI on all three (MS-MPI on Windows); GPU backends per platform; PGO wheels per compiler (GCC, Clang, MSVC) measured separately |
| 1.5.0 | R and Julia bindings tested on all three; Studio accessibility audit on all three browsers' engines; installer guide for locked-down Windows machines (no admin rights) |
| 2.0.0 | Stable ABI (abi3) wheels; Python 3.13 minimum; a single test and release matrix for every platform in the support table |
