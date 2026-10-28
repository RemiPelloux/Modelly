# Web

Modelly in the browser: `modelly export-web` and the Python its pages run in Pyodide. How to
use it is in [Modelly in the browser](../browser.md).

| Module | Contents |
|---|---|
| `modelly.web.export` | `WebExport`, `export_web`, `PYODIDE_VERSION` |
| `modelly.web.packages` | the Pyodide packages a model needs |
| `modelly.web.wheel` | the pure-Python wheel a site ships |
| `modelly.web.runtime` | `BrowserRun`, what the page's Web Worker calls |
| `modelly.web.snapshot` | the series and agent places the page draws |

```{eval-rst}
.. automodule:: modelly.web.export
   :members:
```

```{eval-rst}
.. automodule:: modelly.web.packages
   :members:
```

```{eval-rst}
.. automodule:: modelly.web.wheel
   :members:
```

```{eval-rst}
.. automodule:: modelly.web.runtime
   :members:
```

```{eval-rst}
.. automodule:: modelly.web.snapshot
   :members:
```
