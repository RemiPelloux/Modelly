# Modelly: Agent-based modeling in Python

```{image} https://joss.theoj.org/papers/10.21105/joss.07668/status.svg
:target: https://doi.org/10.21105/joss.07668
```

```{image} https://github.com/RemiPelloux/Modelly/workflows/build/badge.svg
:target: https://github.com/RemiPelloux/Modelly/actions
```

```{image} https://codecov.io/gh/RemiPelloux/Modelly/branch/main/graph/badge.svg
:target: https://codecov.io/gh/RemiPelloux/Modelly
```

```{image} https://img.shields.io/badge/code%20style-black-000000.svg
:target: https://github.com/psf/black
```

```{image} https://img.shields.io/badge/chat-Discord-5865F2?logo=discord&logoColor=white
:target: https://discord.gg/UUGJvdtEJu
```

[Modelly] is an Apache2 licensed agent-based modeling (or ABM) framework in Python.

Modelly allows users to quickly create agent-based models using built-in core components (such as spatial grids and agent schedulers) or customized implementations; visualize them using a browser-based interface; and analyze their results using Python's data analysis tools. Modelly's goal is to make simulations accessible to everyone, so humanity can more effectively understand and solve complex problems.

![A screenshot of the Wolf Sheep model in Modelly|100%](images/wolf_sheep.png)
*A visualisation of the Wolf Sheep model build with Modelly. An online demo is [available here](https://py.cafe/app/EwoutH/modelly-solara-basic-examples).*

## Features

- Built-in core modeling components
- Flexible agent and model management through AgentSet
- Browser-based Solara visualization
- Built-in tools for data collection and analysis
- Example model library

## Using Modelly
### Installation Options
To install our latest stable Modelly 3 release, run:

```bash
pip install -U modelly
```
Development of Modelly 4 has started. To install our latest Modelly 4 pre-release, use:
```bash
pip install -U --pre modelly
```
To also install our recommended dependencies:
```bash
pip install -U modelly[rec]
```

The `[rec]` option installs additional recommended dependencies needed for visualization, plotting, and network modeling capabilities.

On a Mac, this command might cause an error stating `zsh: no matches found: modelly[all]`.
In that case, change the command to `pip install -U "modelly[rec]"`.

Furthermore, if you are using `nix`, Modelly comes with a flake with devShells and a runnable app:

```bash
nix run github:project-RemiPelloux/Modelly # for default Python shell
```

For development shell, clone the repository and run the following command from
repository root:

```bash
nix develop .#uv2nix # pure shell
```

### Resources

For help getting started with Modelly, check out these resources:

- [Getting started] - Learn about Modelly's core concepts and components
- [Modelly Examples] - Browse user-contributed models and implementations
- [Modelly releases] - Check what's new in the latest Modelly version
- [Modelly Extensions] - Overview of modelly's Extensions
- [GitHub Discussions] - Ask questions and discuss Modelly
- [Discord] - Real-time chat with the Modelly community

### Development and Support

Modelly is an open source project and welcomes contributions:

- [GitHub Repository] - Access the source code
- [Issue Tracker] - Report bugs or suggest features
- [Contributors Guide] - Learn how to contribute

### Citing Modelly

To cite Modelly in your publication, you can refer to our peer-reviewed article in the Journal of Open Source Software (JOSS):
- ter Hoeven, E., Kwakkel, J., Hess, V., Pike, T., Wang, B., rht, & Kazil, J. (2025). Modelly 3: Agent-based modeling with Python in 2025. Journal of Open Source Software, 10(107), 7668. https://doi.org/10.21105/joss.07668

Our [CITATION.cff](https://github.com/RemiPelloux/Modelly/blob/main/CITATION.cff) can be used to generate APA, BibTeX and other citation formats.

The original Modelly conference paper from 2015 is [available here](http://conference.scipy.org.s3-website-us-east-1.amazonaws.com/proceedings/scipy2015/jacqueline_kazil.html).

```{toctree}
:hidden: true
:maxdepth: 7

Getting started <getting_started>
Use Modelly in your project <using_modelly_in_your_project>
Overview <overview>
Examples <examples>
API Documentation <apis/api_main>

```

# Indices and tables

- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`

[contributors guide]: https://github.com/RemiPelloux/Modelly
[github repository]: https://github.com/RemiPelloux/Modelly/
[github discussions]: https://github.com/RemiPelloux/Modelly/discussions
[Modelly releases]: https://github.com/RemiPelloux/Modelly/releases
[issue tracker]: https://github.com/RemiPelloux/Modelly/issues
[discord]: https://discord.gg/UUGJvdtEJu
[modelly]: https://github.com/RemiPelloux/Modelly/
[modelly overview]: overview
[modelly examples]: https://modelly.readthedocs.io/stable/examples.html
[Getting started]: getting_started
[Modelly Extensions]: modelly_extension.md
