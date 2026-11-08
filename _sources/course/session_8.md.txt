# Session 8: from the zoo to your own project

**Zoo model:** any; the students choose

## Goals

- Start a project from a zoo model and change it into the model of a question of your own.
- Keep it reproducible and checked: a seed in the scenario, `modelly lint` clean, a test
  that runs the validation of the zoo model you started from, and one of your own.
- Present a seeded experiment and one figure.

**Before the session:** [Use Modelly in your project](../using_modelly_in_your_project.md)
and [Checking a model](../lint.md).

## Exercises

**8.1** Copy a zoo model into a new folder and run it from there.

<details>
<summary>Solution</summary>

```text
modelly zoo list
modelly zoo copy vector_borne my_malaria
cd my_malaria
python -c "from model import VectorBorne, VectorScenario; m = VectorBorne(VectorScenario(rng=1)); m.run(); print(m.attack_rate())"
```

The commands are the same in bash and PowerShell. The copy is a single `model.py` plus a
README; it imports only public `modelly` modules.

</details>

**8.2** Copy the zoo's validation test for your model from `tests/zoo/` into your folder,
change its import to `from model import ...` and run it with `pytest`.

<details>
<summary>Solution</summary>

```text
pytest test_vector_borne.py
```

It keeps passing as long as your changes leave the validated behaviour alone; when it fails,
you know exactly which assumption you changed.

</details>

**8.3** Make one change that answers your question (a new parameter in the scenario, a new
rule in the step) and write a test that checks it on a case where you know the answer.

<details>
<summary>Solution</summary>

For example, bed nets that cut the biting rate `a` by a share `coverage`: add
`coverage: float = 0.0` to the scenario, multiply `a` by `1 - coverage` where it is used,
and test that `r0()` scales as `(1 - coverage)^2`, because the Ross-Macdonald R0 is
proportional to `a^2`.

</details>

**8.4** Run `modelly lint` on your folder and fix what it reports. Then profile one run.

<details>
<summary>Solution</summary>

```text
modelly lint .
modelly profile model.py:VectorBorne
```

`MDL0xx` findings are reproducibility bugs and must be fixed; `MDL1xx` are costs that grow
too fast, worth fixing when the profile shows the step is slow.

</details>
