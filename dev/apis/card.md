# Model cards

`modelly.card` writes, checks and stamps model cards. How to use it is in [Model cards](https://remipelloux.github.io/Modelly/dev/model_cards.html).

The model card file: `card.toml`, read and written without a TOML library to install.

A card is a short TOML file next to the model: what the model is for, what it must not be used for, its data, how it was validated, its known limits and ethical considerations, and a stamp recording which source the validation last passed on. Reading uses `tomllib`; writing produces the same layout every time, so a card regenerated without a change is the same file.

#### `exception CardError`

A card file that cannot be read: bad TOML, a missing key or an unknown schema.

#### `class Check(check: str, test: str)`

One validation: what it checks and the test that checks it.

**Variables:**

- **check** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the claim, in a sentence (“attack rate against the final-size relation”).
- **test** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the pytest target that checks it, relative to the project root (`tests/test_validation.py` or `tests/test_x.py::test_y`).

#### `class Stamp(source: str, modelly: str, date: str)`

When validation last passed: on which source, with which Modelly, on which date.

**Variables:**

- **source** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – `sha256:<hex>` of the model’s source files (`freshness.source_digest`).
- **modelly** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the Modelly version the validation ran with.
- **date** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the date it passed, `YYYY-MM-DD`.

#### `class ModelCard(name: str, title: str, model: str, summary: str, intended_use: tuple[str, ...] = (), out_of_scope: tuple[str, ...] = (), data: tuple[str, ...] = (), limits: tuple[str, ...] = (), ethics: tuple[str, ...] = (), validation: tuple[Check, ...] = (), references: tuple[str, ...] = (), sources: tuple[str, ...] = (), validated: Stamp | None = None)`

A model card; see `docs/model_cards.md` for what each section holds.

**Variables:**

- **name** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – a short identifier (the zoo name, or the project’s).
- **title** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – a human-readable title.
- **model** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the model class, `package.module:Class`.
- **summary** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – one or two sentences.
- **intended_use** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **...**]*) – the questions the model answers, a list of statements.
- **out_of_scope** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **...**]*) – the uses it is not fit for.
- **data** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **...**]*) – the data behind its defaults and inputs.
- **limits** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **...**]*) – its assumptions and where its results stop holding.
- **ethics** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **...**]*) – who decisions taken with it could affect.
- **validation** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*modelly.card.schema.Check*](https://remipelloux.github.io/Modelly/dev/apis/card.html#modelly.card.schema.Check)*, **...**]*) – the checks and their tests.
- **references** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **...**]*) – citations, one string each.
- **sources** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **...**]*) – globs of the files whose change makes the validation stale, relative to the card’s folder; empty means the model class’s module.
- **validated** ([*modelly.card.schema.Stamp*](https://remipelloux.github.io/Modelly/dev/apis/card.html#modelly.card.schema.Stamp)* | **None*) – the last passing validation, or None.

#### `read_card(path: Path) → ModelCard`

The card in `path`.

**Raises:**

[**CardError**](https://remipelloux.github.io/Modelly/dev/apis/card.html#modelly.card.schema.CardError) – when the file is not TOML, lacks a required key, or has another schema.

#### `card_toml(card: ModelCard) → str`

The card as TOML text, in a fixed layout.

#### `write_card(card: ModelCard, path: Path) → None`

Write `card` to `path` with LF line endings.

A card as Markdown, and the skeleton of a new card for a model class.

#### `card_markdown(card: ModelCard, level: int = 2, *, references: bool = True) → str`

The card as Markdown, its title at heading `level`, sections one level below.

`references=False` leaves the references out, for a page that lists them already.

#### `card_skeleton(model_class: type, name: str | None = None) → ModelCard`

A new card for `model_class`: what the code tells, `TODO` for the rest.

Is a card complete, and was its validation run on the model as it is now?

The stamp of a card records a digest of the model’s source files when its validation tests last passed (`stamp`). `problems` compares it with the source today: a model changed since is *stale* until its validation runs again. The digest reads the files with their line endings made LF, so a checkout on Windows gives the digest written on Linux.

#### `source_files(card: ModelCard, folder: Path) → list[Path]`

The files the validation depends on: the `sources` globs, or the model’s module.

#### `source_digest(card: ModelCard, folder: Path) → str`

`sha256:<hex>` over the source files’ names and LF-normalised contents.

#### `problems(card: ModelCard, folder: Path) → list[str]`

What is wrong with `card` (in `folder`); empty when it is complete and fresh.

#### `stamp(path: Path, root: Path, today: date | None = None) → tuple[bool, str]`

Run the card’s validation tests from `root`; on success, stamp the card.

**Returns:**

Whether the tests passed (the card is written only then) and pytest’s output.
