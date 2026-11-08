# Session 9: model cards and the hub

**Zoo models:** [Boltzmann wealth exchange](https://remipelloux.github.io/Modelly/dev/zoo/kinetic_wealth.html), [within-host and between-host epidemic](https://remipelloux.github.io/Modelly/dev/zoo/within_host.html)

## Goals

- Write a model card: what the model is for, what it must not be used for, its data, its validation and its limits.
- Tie the card to a test, and see the card go stale when the model changes.
- Find, read and install a published model with `modelly hub`, on line or from a local index.

**Before the session:** [Model cards](https://remipelloux.github.io/Modelly/dev/model_cards.html) and [The model hub](https://remipelloux.github.io/Modelly/dev/hub.html).

## Walk-through

Start from a model that already has a card. Every zoo model has one, at the end of its page:

```text
modelly hub search epidemic
modelly hub info within_host
modelly card show within_host
modelly card check --zoo
```

`hub info` prints the intended and out-of-scope uses; `card show` prints the whole card as Markdown, with its validation table and the date and source digest of its last stamp. `card check --zoo` recomputes the digest of every zoo model and says whether each card is still validated on the code you have. Read the out-of-scope list of `within_host` aloud: the card says what the model cannot answer before anybody asks.

Then install it and run it from its own folder:

```text
modelly hub install within_host outbreak/
cd outbreak
python -c "from model import WithinHost, WithinHostScenario; m = WithinHost(WithinHostScenario(rng=1, hosts=1000, days=30)); m.run(); print(m.attack_rate())"
```

A zoo model is part of Modelly, so `hub install` writes its module and README into the folder, as `modelly zoo copy` does. For people who do not write code, `modelly studio --hub age_seir --no-code` opens the same model in the browser, with its card in the **Card** tab.

## Exercises

**9.1** Search the hub for opinion models. Then list, from Python, what the age-structured SEIR model must not be used for.

Solution

```text
modelly hub search opinion
```

```python
from modelly.hub import load, search

hub = load()
for entry in search(hub, "opinion"):
    print(entry.name, entry.field, entry.summary)
for use in hub.get("age_seir").card["out_of_scope"]:
    print("-", use)
```

Deffuant and Hegselmann-Krause. The SEIR card rules out forecasting a real epidemic, use on a population without a measured contact matrix, and diseases that are not SEIR with geometric periods. A search matches every word against the name, keywords, title, field and summary: `malaria` finds nothing, because no entry uses the word; `vector` finds the vector-borne model.

**9.2** Copy the Boltzmann model, write a card for it with `modelly card new`, fill every `TODO`, add a validation test and stamp the card.

Solution

```text
modelly zoo copy kinetic_wealth my_wealth
cd my_wealth
modelly card new model.py:KineticWealth -o card.toml
modelly card check card.toml
```

`check` lists a `TODO` in every section the code cannot fill, and `never validated`. Write the test, `test_gini.py`:

```python
from model import KineticScenario, KineticWealth, gini_of

def test_gini_reaches_its_stationary_value():
    model = KineticWealth(KineticScenario(rng=1, steps=1000))
    model.run()
    assert abs(gini_of(model) - model.stationary_gini()) < 0.03
```

and fill `card.toml`:

```toml
schema = 1
name = "my_wealth"
title = "Boltzmann wealth exchange, class copy"
model = "model.py:KineticWealth"
summary = "Random pairwise exchange of single units of money."

intended_use = ["Teaching how identical agents trading at random end up unequal."]
out_of_scope = ["Describing a real economy: there is no production, saving or debt."]
data = ["None: every agent starts with the same money."]
limits = ["Money is conserved and never created; agents have no strategy."]
ethics = ["Not a statement about the fairness of real inequality; say so when showing it."]
references = ["Dragulescu, A. and Yakovenko, V. M. (2000). Statistical mechanics of money. European Physical Journal B, 17, 723-729."]
sources = []

[[validation]]
check = "the Gini settles at the exact stationary value, within 0.03"
test = "test_gini.py::test_gini_reaches_its_stationary_value"
```

Then `modelly card stamp card.toml` runs the test and writes the `[validated]` table, and `modelly card check card.toml` prints `1 card(s) complete and validated on the current source`.

**9.3** Make the change of exercise 1.4 (a giver passes two units when it has two) and run `modelly card check` again. What does it say? Stamp again: does the test pass? What does that tell you about the test?

Solution

`card.toml: stale: the model changed since its validation passed`: the digest of `model.py` no longer matches the stamp, and the check exits with status 1 until the tests are run again. `modelly card stamp card.toml` then passes: with `rng=1` the Gini is about 0.555 against an exact 0.545 for the one-unit rule, inside the tolerance of 0.03. The card is right to accept it, since the test passed; the test is too loose to tell the two rules apart. A validation is only as sharp as its tolerance, which is why session 6 derives tolerances from the variance of the estimate.

**9.4** The classroom has no network. Make a local index of the zoo models, point the hub at it, and install `within_host` from it.

Solution

Write the index from Python, which gives the same UTF-8 file on every system:

```python
import json
from pathlib import Path

from modelly.hub import zoo_index

Path("index.json").write_text(json.dumps(zoo_index(), indent=2), encoding="utf-8")
```

Then, in bash:

```text
MODELLY_HUB=index.json modelly hub search wealth
MODELLY_HUB=index.json modelly hub install within_host outbreak/
```

and in PowerShell:

```text
$env:MODELLY_HUB = "index.json"
modelly hub search wealth
modelly hub install within_host outbreak/
```

`modelly hub zoo-index > index.json` prints the same index, but Windows PowerShell 5 writes the redirected file in UTF-16, which the hub cannot read. `MODELLY_HUB` replaces the public index with paths or URLs. The index read last is also cached, so search and info keep working off line once the public index has been read.
