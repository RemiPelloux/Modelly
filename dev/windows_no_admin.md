# Installing on a locked-down Windows machine

A work or university laptop often has no administrator rights, a proxy, and sometimes no direct internet access. Modelly installs and runs without any of them: it needs no administrator rights, no compiler (the wheels include the compiled modules, for x64 and ARM64) and no service, and Studio listens on this computer only.

## 1. Python, without administrator rights

Use one of these; each installs for your account only.

- **The python.org installer.** Run it, tick *Install for current user only* (or leave *Install launcher for all users* unticked), and tick *Add python.exe to PATH*.
- **winget**, if your machine has it: `winget install Python.Python.3.13 --scope user`.
- **uv**, a single program in your user folder that installs Python and packages:

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv python install 3.13
```

- **The Microsoft Store** Python, where the Store is allowed.

Check it works: `py --version` (the launcher) or `python --version`.

## 2. A virtual environment and Modelly

```powershell
py -3.13 -m venv $HOME\modelly-env
& $HOME\modelly-env\Scripts\python.exe -m pip install "modelly-abm[viz,experiments]"
& $HOME\modelly-env\Scripts\python.exe -m modelly --version
```

Calling the environment’s `python.exe` by its path, as above, needs no activation script. If you prefer to activate it and PowerShell refuses to run `Activate.ps1` (“running scripts is disabled”), allow scripts for this window only, which needs no rights:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& $HOME\modelly-env\Scripts\Activate.ps1
```

With uv instead: `uv venv $HOME\modelly-env --python 3.13`, then `uv pip install --python $HOME\modelly-env "modelly-abm[viz,experiments]"`.

## 3. Behind a proxy

pip reads the proxy from the environment, and uses the certificates Windows trusts (so a company’s own certificate authority works without extra steps on pip 24.2 or later):

```powershell
$env:HTTPS_PROXY = "http://proxy.example.org:8080"
python -m pip install "modelly-abm[viz,experiments]"
```

If pip still reports a certificate error, ask your IT department for the company’s root certificate as a `.pem` file and point pip at it: `python -m pip config set global.cert C:\path\company-root.pem`.

## 4. Without internet access

Download the wheels on a machine that has access, with the same Python version and architecture, then carry the folder over:

```powershell
# on the connected machine
python -m pip download "modelly-abm[viz,experiments]" -d modelly-wheels --platform win_amd64 --python-version 3.13 --only-binary=:all:
# on the offline machine
python -m pip install --no-index --find-links modelly-wheels "modelly-abm[viz,experiments]"
```

Use `--platform win_arm64` for an ARM laptop. Studio loads its page’s JavaScript and fonts from a cache; fill it once on the connected machine, `python -m modelly.studio.assets --fetch`, and copy the cache folder it prints, or run that command on the offline machine while it is briefly online ([Studio](https://remipelloux.github.io/Modelly/dev/studio.html#platforms-and-network)).

## 5. Running Studio

```powershell
python -m modelly studio path\to\model.py:MyModel
```

Studio listens on `127.0.0.1`, this computer only, so Windows Defender Firewall does not ask for an exception and no administrator is needed. The browser opens on `http://127.0.0.1:8765`; if port 8765 is taken, pass `--port 0` for a free one.

## The R and Julia packages

Both need no administrator rights either. R installs packages into your user library when the system one is not writable (R asks once to create it). `modelly::install_modelly()` creates a Python environment in your user folder. `Modelly.jl`’s first `using Modelly` installs Python and Modelly into Julia’s depot, also in your user folder (see [From R and Julia](https://remipelloux.github.io/Modelly/dev/r_and_julia.html)).
