# Model cards

A model card is a short, standard description that goes with a model. It says what the model is for, what it must not be used for, which data it rests on, how it was validated, its known limits and the people decisions taken with it could affect. Every [zoo model](https://remipelloux.github.io/Modelly/zoo/index.html) has one, shown at the end of its page. `modelly card` writes one for your model, checks it, and keeps track of whether its validation still holds.

```bash
modelly card new model.py:Epidemic -o card.toml   # a skeleton from the code
modelly card stamp card.toml                      # run the validation tests; stamp on success
modelly card check card.toml                      # complete, and validated on this source?
modelly card show card.toml                       # as Markdown, for a README or a paper
```

## What a card holds

The card is a `card.toml` file next to the model:

```toml
schema = 1
name = "epidemic"
title = "Household epidemic"
model = "model.py:Epidemic"
summary = "An SIR epidemic in households, for comparing school closures."

intended_use = ["Comparing closure policies in relative terms, on stated contact rates."]
out_of_scope = ["Forecasting case counts: nothing is calibrated to a real outbreak."]
data = ["Household sizes from the 2021 census table bundled in data/households.csv."]
limits = ["Homogeneous mixing outside households; no age structure."]
ethics = ["Closure decisions affect children and parents unequally; show intervals."]
references = ["Ball, F. et al. (1997). Epidemics with two levels of mixing. Ann. Appl. Prob."]
sources = []

[[validation]]
check = "final size against the household final-size relation, three seeds"
test = "tests/test_validation.py::test_final_size"
```

Section

What goes in it

intended_use

the questions the model is built to answer, and for whom

out_of_scope

uses it is not fit for, and why

data

the data behind the defaults and inputs, or that there is none

validation

each check: the claim, and the pytest target that checks it

limits

assumptions, and the regimes where results stop being trustworthy

ethics

who could be affected by decisions taken with it, and how

references

the papers the model and its validation come from

sources

globs of the files the validation depends on; empty means the model’s module

`modelly card new` fills what the code tells (the name, the model target, a summary from the class docstring) and leaves a `TODO` in every section only you can write. A card with a `TODO`, an empty section or no validation test is incomplete.

## Stale validation

`modelly card stamp card.toml` runs the card’s validation tests with pytest, from the current folder (`--root` to choose another). When they pass, it writes a `[validated]` table: a digest of the model’s source files, the Modelly version and the date. When they fail, it prints pytest’s output and leaves the card as it was.

```toml
[validated]
source = "sha256:6a004228a934a9d59400cb7b31af0b0c140936de7e90e92b47c76c84d4f7f834"
modelly = "1.5.0"
date = "2026-11-03"
```

`modelly card check` recomputes the digest. If the model changed since the stamp, the card is **stale**: its validation passed on code that is no longer there, and the check fails until the tests are run again. The digest reads the files with LF line endings, so a Windows checkout gives the digest written on Linux or macOS. By default it covers the model class’s module; list more files in `sources` (`["src/epidemic/*.py"]`, relative to the card) when the model spans several.

`modelly card check --zoo` checks every zoo card. The test suite does the same, so a change to a zoo model fails the tests until its card is stamped again.

## In a project

Put `modelly card check` in your tests or your pre-commit configuration, next to `modelly lint`:

```yaml
- repo: https://github.com/RemiPelloux/Modelly
  rev: v1.5.0
  hooks:
    - id: modelly-lint
    - id: modelly-card-check
```

`modelly card show` prints the card as Markdown for a README, a supplement or the [provenance bundle](https://remipelloux.github.io/Modelly/provenance.html) of a study. From Python:

```python
from modelly.card import card_markdown, problems, read_card

card = read_card("card.toml")
problems(card, ".")  # [] when complete and validated on this source
print(card_markdown(card))
```
