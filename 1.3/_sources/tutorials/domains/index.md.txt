# Domain tutorials

One tutorial per field, each built on a model of the [zoo](../../zoo/index.md): build the
model, run it, plot it, and answer one question with it. Every tutorial is executed when the
documentation is built, and runs in a few seconds.

| Tutorial | Field | Zoo models | The question |
|---|---|---|---|
| [Epidemiology](epidemiology.md) | epidemiology | age-structured SEIR | how many get infected, and which intervention protects whom |
| [Ecology](ecology.md) | ecology | forest fire, energy budgets | when does fire cross a landscape; how many can it feed |
| [Economics](economics.md) | economics | Boltzmann, Bouchaud-Mezard | where inequality comes from |
| [Sociology and political science](sociology.md) | sociology, political science | Deffuant, Hegselmann-Krause, Axelrod | consensus or camps |
| [Transport](transport.md) | transport, urban | Nagel-Schreckenberg | how jams form, and a road's capacity |
| [Energy](energy.md) | energy | Bass diffusion | how fast rooftop solar spreads, and whether the network matters |

To work on one as a notebook, copy its zoo model into a folder first, for example
`modelly zoo copy age_seir my_epidemic` (the same in bash and PowerShell), and import from
the copy instead of from `modelly.zoo`.

```{toctree}
:hidden: true

epidemiology
ecology
economics
sociology
transport
energy
```
