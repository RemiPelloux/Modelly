# The model hub

The hub is where Modelly models are published, found, installed and cited. It is a static index (`index.json`) in the public repository [RemiPelloux/modelly-hub](https://github.com/RemiPelloux/modelly-hub), served on GitHub Pages and changed by pull request after automatic checks. There is no server and no account: the index is a file, and the models’ archives live on Zenodo, which gives each one a DOI.

```bash
modelly hub search malaria                 # models matching every word, best first
modelly hub info within_host               # what it is for, its limits, how to cite it
modelly hub install within_host outbreak/  # a zoo model into a folder
modelly hub install seir_plus              # a package, into this environment
```

## Finding and installing

`modelly hub search` reads the public index and lists the models whose name, keywords, title, field or summary contain every word, best match first; `--field ecology` narrows the list. `modelly hub info NAME` shows the summary, the intended and out-of-scope uses from the [model card](https://remipelloux.github.io/Modelly/model_cards.html), the Modelly versions the model supports and its DOI.

`modelly hub install NAME` first checks that the model supports the running Modelly. A zoo model is part of Modelly, so installing it writes its module and README into a folder, as `modelly zoo copy` does. A package is installed with pip into the running environment: from its archive when the entry has one, downloaded and checked against the sha256 the index records (and against its Sigstore signature, when the entry is signed and the `sigstore` package is installed) before pip sees it; otherwise from PyPI by its pinned requirement.

The index read last is cached, so search and info work offline. `MODELLY_HUB` (paths or URLs separated by `:`, or `;` on Windows) replaces the public index, for a private one or a local file; a package can add indexes through the `modelly.hub_sources` [plugin group](https://remipelloux.github.io/Modelly/plugins.html).

## What an entry holds

```json
{
  "name": "within_host",
  "title": "Within-host and between-host epidemic",
  "field": "epidemiology",
  "summary": "Hosts infect each other; each infection is a viral ODE inside its host.",
  "version": "1.5.0",
  "kind": "zoo",
  "target": "modelly.zoo.within_host.model:WithinHost",
  "modelly": ">=1.5,<2",
  "source": {"requirement": "modelly-abm>=1.5,<2"},
  "card": {"intended_use": ["..."], "validation": ["..."], "validated": {"source": "sha256:..."}},
  "doi": "10.5281/zenodo.1234567",
  "signature": {"url": "...", "sha256": "...", "identity": "...", "issuer": "..."}
}
```

`kind` is `zoo` for a model shipped inside Modelly and `package` for one installed from an archive or PyPI; `source` says where its code is, with a `url` and its `sha256` for an archive. The card is the model’s card, validation stamp included.

## Publishing a model

A project is ready for the hub when it has:

- a `[tool.modelly.hub]` table in `pyproject.toml` with the model’s `target` (`package.module:Class`) and `field`;
- a [model card](https://remipelloux.github.io/Modelly/model_cards.html) that is complete and validated on the current source (`modelly card stamp card.toml`);
- a wheel in `dist/` (`python -m build`).

```bash
modelly hub publish .                                  # hub-entry.json, nothing sent
modelly hub publish . --zenodo --sign you@example.org  # shows what would be sent and run
ZENODO_TOKEN=... modelly hub publish . --zenodo --no-dry-run              # the sandbox
ZENODO_TOKEN=... modelly hub publish . --zenodo --production --no-dry-run # a real DOI
```

Publishing is a dry run unless `--no-dry-run` is given: it writes `hub-entry.json` and prints every request it would send to Zenodo and the signing command it would run. With `--no-dry-run`, `--zenodo` creates a Zenodo deposition, uploads the wheel (and its signature), sets the metadata and publishes it, then records the DOI and the file’s URL and hash in the entry; the token comes from `ZENODO_TOKEN` and is never written anywhere. The sandbox (sandbox.zenodo.org) is the default, so a first publication can be tried without minting a real DOI; `--production` uses zenodo.org. `--sign IDENTITY` signs the wheel with Sigstore’s keyless signing, which opens a browser to log in as that identity; it needs `pip install sigstore`.

Then open a pull request adding the entry to `index.json` in [modelly-hub](https://github.com/RemiPelloux/modelly-hub). The repository’s checks run `modelly hub check` on the index: the schema, unique names, a Modelly specifier that parses, a complete card with a validation stamp, and the hash of every file the entry points to.

## Checking an index

```bash
modelly hub check index.json    # exit 1 and one line per problem
modelly hub zoo-index           # the index of the zoo models, as the hub lists them
```

From Python:

```python
from modelly.hub import install, load, search

hub = load()
for entry in search(hub, "epidemic", field="epidemiology"):
    print(entry.name, entry.summary)
install(hub.get("within_host"), "outbreak/")
```
