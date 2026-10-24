"""``modelly new``: write a project that is seeded, tested and linted from the first commit.

A template is a folder of plain text files under ``modelly/new/templates/``. ``{name}``
placeholders (only the keys of ``Placeholders``) are replaced with ``str.replace``, so
the templates need no template engine and any other brace in them is left as it is.
"""

from __future__ import annotations

import keyword
import re
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path

import modelly

__all__ = ["TEMPLATES", "ProjectError", "Template", "create_project", "placeholders"]


@dataclass(frozen=True)
class Template:
    """A project template: what it models and the extra it needs from modelly-abm."""

    summary: str
    extra: str = ""


TEMPLATES = {
    "grid": Template("traders exchanging wealth on a grid (cells, Column attributes)"),
    "network": Template("an infection spreading over a contact network", "network"),
    "continuous": Template("random walkers in a continuous, wrapping space"),
    "cohort": Template("colonies counted by age class with CohortTable"),
}

# (file under templates/, path in the project); the template's own files come first.
COMMON_FILES = (
    ("common/pyproject.toml.tmpl", "pyproject.toml"),
    ("common/README.md.tmpl", "README.md"),
    ("common/gitignore.tmpl", ".gitignore"),
    ("common/__init__.py.tmpl", "{package}/__init__.py"),
    ("common/test_determinism.py.tmpl", "tests/test_determinism.py"),
)
MODULES = ("scenario.py", "agents.py", "model.py")
PROJECT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")
MODEL_SUFFIX = "Model"


class ProjectError(ValueError):
    """The project cannot be written: a bad name, an unknown template or a used folder."""


@dataclass(frozen=True)
class Placeholders:
    """The values substituted into the templates."""

    project: str
    package: str
    title: str
    model_class: str
    scenario_class: str
    template: str
    description: str
    requirement: str

    def render(self, text: str) -> str:
        """``text`` with every ``{key}`` of these placeholders replaced."""
        for key, value in asdict(self).items():
            text = text.replace("{" + key + "}", value)
        return text


def package_name(project: str) -> str:
    """The Python package of a project: ``Forest-Fire`` -> ``forest_fire``.

    Raises:
        ProjectError: when ``project`` is not a project name or gives no package name.
    """
    if not PROJECT_NAME.match(project):
        raise ProjectError(
            f"{project!r} is not a project name: start with a letter, then letters, digits, - _ ."
        )
    package = re.sub(r"[^a-z0-9]+", "_", project.lower()).strip("_")
    if keyword.iskeyword(package) or not package.isidentifier():
        raise ProjectError(
            f"{project!r} does not give a Python package name ({package!r})"
        )
    return package


def placeholders(project: str, template: str) -> Placeholders:
    """The placeholder values for a project named ``project``.

    Raises:
        ProjectError: when the name is not a valid project name or the template unknown.
    """
    if template not in TEMPLATES:
        raise ProjectError(f"unknown template {template!r} (see --list-templates)")
    package = package_name(project)
    words = package.split("_")
    base = "".join(word.capitalize() for word in words if word)
    base = base.removesuffix(MODEL_SUFFIX) or base
    version = ".".join(modelly.__version__.split(".")[:2])
    extra = f"[{TEMPLATES[template].extra}]" if TEMPLATES[template].extra else ""
    return Placeholders(
        project=project,
        package=package,
        title=" ".join(word.capitalize() for word in words if word),
        model_class=base + MODEL_SUFFIX,
        scenario_class=base + "Scenario",
        template=template,
        description=f"An agent-based model: {TEMPLATES[template].summary}.",
        requirement=f"modelly-abm{extra}>={version}",
    )


def project_files(template: str) -> list[tuple[str, str]]:
    """(template file, project path) for every file a ``template`` project has."""
    own = [(f"{template}/{module}.tmpl", f"{{package}}/{module}") for module in MODULES]
    return [*own, *COMMON_FILES]


def create_project(target: str | Path, template: str = "grid") -> list[Path]:
    """Write a new project into the folder ``target``; return the files written.

    Raises:
        ProjectError: when the name or template is bad, or ``target`` is not empty.
    """
    target = Path(target)
    values = placeholders(target.resolve().name, template)
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ProjectError(f"{target} exists and is not empty: nothing was written")
    root = files(__name__).joinpath("templates")
    written = []
    for source, destination in project_files(template):
        path = target / values.render(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = root.joinpath(*source.split("/")).read_text(encoding="utf-8")
        path.write_text(values.render(text), encoding="utf-8", newline="\n")
        written.append(path)
    return written
