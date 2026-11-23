# Domain tutorials

One tutorial per field, each built on a model of the [zoo](https://remipelloux.github.io/Modelly/dev/zoo/index.html): build the model, run it, plot it, and answer one question with it. Every tutorial is executed when the documentation is built, and runs in a few seconds.

Tutorial

Field

Zoo models

The question

[Epidemiology](https://remipelloux.github.io/Modelly/dev/tutorials/domains/epidemiology.html)

epidemiology

age-structured SEIR

how many get infected, and which intervention protects whom

[Ecology](https://remipelloux.github.io/Modelly/dev/tutorials/domains/ecology.html)

ecology

forest fire, energy budgets

when does fire cross a landscape; how many can it feed

[Economics](https://remipelloux.github.io/Modelly/dev/tutorials/domains/economics.html)

economics

Boltzmann, Bouchaud-Mezard

where inequality comes from

[Sociology and political science](https://remipelloux.github.io/Modelly/dev/tutorials/domains/sociology.html)

sociology, political science

Deffuant, Hegselmann-Krause, Axelrod

consensus or camps

[Transport](https://remipelloux.github.io/Modelly/dev/tutorials/domains/transport.html)

transport, urban

Nagel-Schreckenberg

how jams form, and a road’s capacity

[Energy](https://remipelloux.github.io/Modelly/dev/tutorials/domains/energy.html)

energy

Bass diffusion

how fast rooftop solar spreads, and whether the network matters

To work on one as a notebook, copy its zoo model into a folder first, for example `modelly zoo copy age_seir my_epidemic` (the same in bash and PowerShell), and import from the copy instead of from `modelly.zoo`.
