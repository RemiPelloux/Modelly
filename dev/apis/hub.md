# Model hub

`modelly.hub` finds, installs, publishes and checks models on the hub. How to use it is in [The model hub](https://remipelloux.github.io/Modelly/dev/hub.html).

One model on the hub: what it is, where its code is, how it was validated, how to cite it.

An index (`index.json`) is `{"schema": 1, "models": [entry, ...]}`. An entry names the model (`name`, `title`, `field`, `summary`, `keywords`), its `version`, the `target` to build it (`package.module:Class`), where its code comes from (`source`), the Modelly versions it supports (`modelly`), its model card, and optionally a DOI, a run bundle to verify and a Sigstore signature. `kind` is `"zoo"` for a model shipped inside Modelly, `"package"` for one installed from a URL or from PyPI.

#### `exception EntryError`

An index entry that does not follow the schema; the message says what is wrong.

#### `class Source(requirement: str, url: str | None = None, sha256: str | None = None)`

Where the model’s code comes from.

**Variables:**

- **requirement** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – what pip installs (`"modelly-abm>=1.5"`, `"seir-plus==1.0"`).
- **url** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | **None*) – a wheel or sdist to download instead of the index, or None.
- **sha256** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | **None*) – the file’s hash, required with `url`.

#### `class Artifact(url: str, sha256: str, identity: str = '', issuer: str = '')`

A file the entry points to (a run bundle, a signature), with its hash.

**Variables:**

- **url** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – where to download it.
- **sha256** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – its hash.
- **issuer** (*identity**,*) – for a Sigstore signature, the signer’s identity and its OIDC issuer, which verification requires.

#### `class HubEntry(name: str, title: str, field: str, summary: str, version: str, kind: str, target: str, modelly: str, source: Source, keywords: tuple[str, ...]=(), authors: tuple[str, ...]=(), license: str = '', card: dict[str, ~typing.Any]=<factory>, doi: str | None = None, bundle: Artifact | None = None, signature: Artifact | None = None)`

A model on the hub; see the module docstring for the fields.

#### `to_dict() → dict[str, Any]`

The entry as JSON-ready data, without empty optional fields.

#### `classmethod from_dict(data: dict[str, Any]) → HubEntry`

An entry from index data, checked.

**Raises:**

[**EntryError**](https://remipelloux.github.io/Modelly/dev/apis/hub.html#modelly.hub.entry.EntryError) – when a field is missing, unknown or malformed.

#### `check(data: dict[str, Any]) → list[str]`

Every way `data` breaks the entry schema; empty when it is a valid entry.

Hub indexes: where they are, how they are read, and searching them.

The default index is the public one, `DEFAULT_INDEX`. `MODELLY_HUB` (paths or URLs separated by `os.pathsep`) replaces it, for a private or a local index; installed packages add more through the `modelly.hub_sources` entry-point group, each entry point naming a URL string or a function returning one or several. An index is read over HTTPS or from a file; the last copy read is cached, and used when the network is not there.

#### `exception HubError`

An index that cannot be read or does not follow the schema.

#### `cache_dir() → Path`

Where the hub caches indexes: `MODELLY_CACHE`, or the platform’s user cache.

#### `sources() → list[str]`

The indexes to read, in order: `MODELLY_HUB` or the default, then the plugins’.

#### `fetch(source: str) → dict[str, Any]`

The index data at `source` (a path or a URL); the cached copy when offline.

**Raises:**

[**HubError**](https://remipelloux.github.io/Modelly/dev/apis/hub.html#modelly.hub.index.HubError) – when it cannot be read and there is no cached copy, or is not an index.

#### `class Hub(entries: tuple[HubEntry, ...], sources: tuple[str, ...])`

The models of every index read, the first index winning a name.

#### `get(name: str) → HubEntry`

The entry called `name`.

**Raises:**

[**KeyError**](https://docs.python.org/3/builtins/exceptions.html#KeyError) – if no index has it.

#### `load(where: list[str] | None = None) → Hub`

Read the indexes `where` (by default `sources()`) into one `Hub`.

#### `search(hub: Hub, query: str = '', field: str | None = None) → list[HubEntry]`

The entries matching every word of `query` (and `field`), best first.

Installing a hub model: check it supports this Modelly, fetch it, verify it, install it.

A zoo model is part of Modelly: installing it writes its module and README into a folder, as `modelly zoo copy` does. A package is installed with pip into the running environment: from its `url` when the entry has one (downloaded, checked against its sha256 and, when the entry is signed and `sigstore` is installed, against its signature, before pip sees it), or from PyPI by its requirement. pip is run as `python -m pip` of the running interpreter, so the model lands in the environment that runs Modelly, on every operating system.

#### `class Installed(entry: HubEntry, files: list[Path] = <factory>, commands: list[list[str]] = <factory>)`

What `install` did: the files written or fetched and the commands run.

#### `sha256_of(path: Path) → str`

The hex sha256 of a file.

#### `download(url: str, sha256: str, folder: Path) → Path`

`url` saved in `folder`, checked against `sha256`; a file path is copied.

**Raises:**

[**HubError**](https://remipelloux.github.io/Modelly/dev/apis/hub.html#modelly.hub.index.HubError) – when the hash differs (the file is deleted).

#### `compatible(entry: HubEntry) → None`

Refuse an entry whose `modelly` specifier excludes the running Modelly.

#### `install(entry: HubEntry, folder: Path | None = None, runner: Runner = <function run>) → Installed`

Install `entry`: a zoo model into `folder`, a package into this environment.

**Raises:**

[**HubError**](https://remipelloux.github.io/Modelly/dev/apis/hub.html#modelly.hub.index.HubError) – for an incompatible Modelly, a bad hash or signature, or a pip failure.

Publishing to the hub: an entry for a project (or a zoo model), archived and signed.

`project_entry(folder)` reads a project’s `pyproject.toml` (`[project]` and the `[tool.modelly.hub]` table: `target` and `field`), its `card.toml`, which must be complete and validated on the current source, and its built wheel in `dist/`. `publish` optionally signs the wheel (Sigstore) and archives it on Zenodo for a DOI, then writes `hub-entry.json`: the entry to add to the index by pull request.

`zoo_index()` is the index of the zoo models, which are part of Modelly itself.

#### `supported() → str`

The specifier of this Modelly’s minor version up to the next major: `">=1.5,<2"`.

#### `zoo_entry(zoo: ZooModel) → HubEntry`

The hub entry of a zoo model, its card included.

#### `zoo_index() → dict[str, Any]`

The index of every zoo model.

#### `project_entry(folder: Path) → tuple[HubEntry, Path]`

The entry of the project in `folder` and its wheel.

**Raises:**

[**HubError**](https://remipelloux.github.io/Modelly/dev/apis/hub.html#modelly.hub.index.HubError) – without a `[tool.modelly.hub]` table, a fresh card or a wheel.

#### `class Published(entry: HubEntry, path: Path, commands: list[list[str]] = <factory>, doi: str | None = None)`

What `publish` did.

#### `class Signer(identity: str, issuer: str = 'https://github.com/login/oauth')`

Who signs: the identity and OIDC issuer Sigstore will bind the signature to.

#### `publish(folder: Path, zenodo: Zenodo | None = None, signer: Signer | None = None, dry_run: bool = True) → Published`

Write `hub-entry.json`; sign the wheel and archive it on Zenodo when asked.

The checks every index change passes before it is merged (the hub repository runs them).

`check_index(path)` reads an index and reports, per entry: the schema, a unique name, a `modelly` specifier that parses, a model card with every section and a validation stamp, and, with `download=True`, that each file the entry points to has the sha256 it records.

#### `check_entry(entry: dict[str, Any], download_files: bool = False) → list[str]`

Every problem of one entry.

#### `check_index(path: Path, download_files: bool = False) → dict[str, list[str]]`

The problems of each entry of the index at `path`, by name (`""` for the index).

Archiving a hub package on Zenodo, for a DOI, through Zenodo’s deposit API.

`Zenodo(token).deposit(files, metadata)` creates a deposition, uploads the files to its bucket, sets the metadata and publishes it, returning the DOI and the files’ URLs. The token is read from `ZENODO_TOKEN` by the command line and is never written anywhere. `sandbox` (the default of the command line) uses sandbox.zenodo.org, whose DOIs are not real, to try a publication first. `DryRun` is a transport that sends nothing and records the requests, so a dry run shows exactly what would be sent.

Reference: [https://developers.zenodo.org/](https://developers.zenodo.org/) (REST API, depositions and bucket uploads).

#### `class Transport(*args, **kwargs)`

Sends one request and returns the decoded JSON reply.

#### `http(method: str, url: str, token: str, body: bytes | None, content_type: str) → dict`

The real transport, over HTTPS.

#### `class DryRun(requests: list[tuple[str, str, int]]=<factory>)`

A transport that sends nothing: it records each request and answers like Zenodo.

#### `class Deposit(doi: str, record: str, files: dict[str, str])`

A published deposition: its DOI and the URL of each file, by name.

#### `metadata(title: str, description: str, version: str, authors: Sequence[str], keywords: Sequence[str], license_id: str) → dict[str, Any]`

Zenodo metadata for a software deposit.

#### `class Zenodo(token: str, sandbox: bool = True, transport: Transport = <function http>)`

A client of one Zenodo instance with one token.

#### `transport(url: str, token: str, body: bytes | None, content_type: str) → dict`

The real transport, over HTTPS.

#### `property base: str`

The instance’s address.

#### `deposit(files: Sequence[Path], meta: dict[str, Any]) → Deposit`

Create, upload, describe and publish; the DOI and the file URLs.

Signing and verifying hub packages with Sigstore, through the `sigstore` command.

Signing opens a browser for the publisher to log in (Sigstore’s keyless signing: the signature binds the file to that identity, recorded in a public transparency log), so it is something the publisher runs, never a test. `sign(path, dry_run=True)` returns the command without running it. Verification needs the identity and issuer the index records. Without the `sigstore` package (`pip install sigstore`), verification is skipped with a warning, since the sha256 in the index has already been checked.

#### `available() → bool`

Whether the `sigstore` package is installed.

#### `sign_command(path: Path) → list[str]`

The command that signs `path`, writing `<path>.sigstore.json`.

#### `sign(path: ~pathlib.Path, dry_run: bool = True, runner: ~collections.abc.Callable[[...], ~typing.Any] = <function run>) → tuple[list[str], Path | None]`

Sign `path`: the command, and the bundle written (None on a dry run).

**Raises:**

[**HubError**](https://remipelloux.github.io/Modelly/dev/apis/hub.html#modelly.hub.index.HubError) – when `sigstore` is missing or signing fails.

#### `verify(path: Path, bundle: Path, signature: Any, runner: Callable[[...], Any]) → bool`

Check `path` against its Sigstore `bundle`; False when sigstore is missing.

**Raises:**

[**HubError**](https://remipelloux.github.io/Modelly/dev/apis/hub.html#modelly.hub.index.HubError) – when the signature does not verify for the recorded identity.
