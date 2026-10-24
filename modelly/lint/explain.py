"""The long form of each rule, printed by ``python -m modelly.lint --explain CODE``."""

from __future__ import annotations

import textwrap
from dataclasses import dataclass

from modelly.lint.rules import GUIDE, RULES

WIDTH = 88
INDENT = "    "


@dataclass(frozen=True)
class Explanation:
    """Why a rule matters, a source that breaks it and the same source fixed."""

    why: str
    bad: str
    good: str


EXPLANATIONS = {
    "MDL001": Explanation(
        "A model is reproducible when its seed fixes every draw. The global `random` and "
        "`np.random` streams, an unseeded `random.Random()` or `default_rng()`, and "
        "`SystemRandom` are not owned by the model, so two runs with one seed differ.",
        "if random.random() < self.p:\n    self.move()",
        "if self.random.random() < self.p:   # or self.rng.random() for numpy\n    self.move()",
    ),
    "MDL002": Explanation(
        "Agent.__init__ registers the agent with the model and gives it a unique_id; "
        "Model.__init__ sets up the generators and the agent registry. Skipping the call "
        "raises nothing at once and fails later, far from the cause.",
        "class Sheep(Agent):\n    def __init__(self, model):\n        self.energy = 5",
        "class Sheep(Agent):\n    def __init__(self, model):\n        super().__init__(model)\n        self.energy = 5",
    ),
    "MDL003": Explanation(
        "A set of objects iterates in an order that follows memory addresses, which change "
        "from run to run, so any draw or update that depends on the order changes too.",
        "for agent in set(self.cell.neighborhood.agents):\n    agent.trade(self)",
        "for agent in self.cell.neighborhood.agents:   # or sorted(..., key=lambda a: a.unique_id)\n    agent.trade(self)",
    ),
    "MDL004": Explanation(
        "A list, dict or set in a class body is created once, when the class is defined, "
        "and every instance shares it: one agent's append shows up in all of them.",
        "class Trader(Agent):\n    partners = []",
        "class Trader(Agent):\n    def __init__(self, model):\n        super().__init__(model)\n        self.partners = []",
    ),
    "MDL005": Explanation(
        "time.time(), datetime.now(), uuid.uuid4(), os.urandom() and the secrets module "
        "return a new value on every run. Inside a model or agent they make the outcome "
        "depend on the machine and the moment, not on the seed.",
        "class Sheep(Agent):\n    def step(self):\n        self.born = datetime.now()",
        "class Sheep(Agent):\n    def step(self):\n        self.born = self.model.time",
    ),
    "MDL006": Explanation(
        "id() is a memory address and hash() of a str or bytes is salted per process "
        "(PYTHONHASHSEED). Sorting by them, bucketing by them or seeding from them gives a "
        "different result on every run.",
        "queue = sorted(self.agents, key=id)\ngroup = hash(self.name) % 4",
        "queue = sorted(self.agents, key=lambda a: a.unique_id)\ngroup = self.unique_id % 4",
    ),
    "MDL007": Explanation(
        "Iterating an AgentSet walks a snapshot taken when the loop starts, so an agent "
        "removed by an earlier iteration is still visited and acts after its death. "
        "agents.do and shuffle_do skip removed agents.",
        "for wolf in self.agents_by_type[Wolf]:\n    wolf.prey.remove()",
        'self.agents_by_type[Wolf].shuffle_do("hunt")   # hunt() calls self.prey.remove()',
    ),
    "MDL008": Explanation(
        "A module-level variable outlives the model. Two models in one process (a batch "
        "run, a test suite, a notebook re-run) share and keep mutating it, so a run depends "
        "on what ran before it.",
        "BORN = 0\nclass Sheep(Agent):\n    def step(self):\n        global BORN\n        BORN += 1",
        "class Sheep(Agent):\n    def step(self):\n        self.model.born += 1",
    ),
    "MDL009": Explanation(
        "model.agents and model.agents_by_type are the registry itself. Adding or removing "
        "there skips the per-type sets, the column tables and the data collectors, which "
        "then disagree with each other.",
        "self.model.agents.discard(self)",
        "self.remove()",
    ),
    "MDL012": Explanation(
        "A reply from a web service or a language model differs from one call to the next "
        "and the service may change or vanish. Called through requests, httpx, urllib, or "
        "the openai and anthropic SDKs, nothing records it, so the run cannot be replayed, "
        "audited or budgeted. modelly.llm caches every reply under a key of the call, "
        "replays offline and stops at a budget.",
        "class Voter(Agent):\n    def step(self):\n"
        "        r = client.messages.create(model=M, messages=[...])\n"
        "        self.vote = r.content[0].text",
        "class Voter(LLMAgent, Agent):\n    def step(self):\n"
        '        self.vote = self.decide(prompt, {"enum": ["yes", "no"]})',
    ),
    "MDL101": Explanation(
        "A loop, comprehension, select, agg, groupby, sort or map over the whole population "
        "inside an agent method visits every agent once per agent: N^2 per step.",
        "def step(self):\n    near = [a for a in self.model.agents if dist(a, self) < 2]",
        "def step(self):\n    near = self.cell.get_neighborhood(radius=2).agents",
    ),
    "MDL102": Explanation(
        "Two nested loops over the population compare every pair of agents: N^2 per step, "
        "even when only neighbours can interact.",
        "for a in self.agents:\n    for b in self.agents:\n        a.meet(b)",
        "for a in self.agents:\n    for b in a.cell.neighborhood.agents:\n        a.meet(b)",
    ),
    "MDL103": Explanation(
        "A hand-written `for a in self.agents: a.step()` is agents.do('step'), a fixed order, "
        "and it still visits agents removed earlier in the loop. Most models mean "
        "shuffle_do, a new random order each step.",
        "for agent in self.agents:\n    agent.step()",
        'self.agents.shuffle_do("step")',
    ),
    "MDL104": Explanation(
        "deepcopy walks the whole object graph, which for an agent includes the model, the "
        "space and every other agent. Done each step it costs more than the step itself.",
        "def step(self):\n    self.previous = copy.deepcopy(self)",
        "def step(self):\n    self.previous_energy = self.energy",
    ),
    "MDL105": Explanation(
        "A step with many branches hides its phase order and resists vectorising. Named "
        "phases make the order explicit and can each move to the model as column updates.",
        "def step(self):\n    if ...: ...\n    elif ...: ...   # thirteen more",
        "def step(self):\n    self.move()\n    self.eat()\n    self.reproduce()",
    ),
    "MDL106": Explanation(
        "Building a DataFrame or calling pd.concat copies every row each time, so recording "
        "a table step by step is quadratic in the number of steps.",
        "def step(self):\n    self.log = pd.concat([self.log, pd.DataFrame([row])])",
        "def step(self):\n    self.rows.append(row)   # pd.DataFrame(self.rows) once, after the run",
    ),
    "MDL107": Explanation(
        "A loop that only updates Column attributes calls the Column property once per "
        "agent. The same update on the column's numpy array runs in C, once per step.",
        "for sheep in self.agents_by_type[Sheep]:\n    sheep.energy -= 1",
        "table = self.columns[Sheep]\ntable.energy -= 1",
    ),
}


def block(source: str) -> str:
    """Indent a code example."""
    return textwrap.indent(source, INDENT)


def explain(code: str) -> str:
    """The long form of rule ``code``.

    Raises:
        KeyError: when ``code`` is not a rule.
    """
    rule = RULES[code.upper()]
    text = EXPLANATIONS[rule.code]
    return "\n".join(
        [
            f"{rule.code} ({rule.severity}): {rule.message}",
            "",
            textwrap.fill(text.why, WIDTH),
            "",
            "Instead:",
            textwrap.fill(
                rule.hint, WIDTH, initial_indent=INDENT, subsequent_indent=INDENT
            ),
            "",
            "Bad:",
            block(text.bad),
            "",
            "Good:",
            block(text.good),
            "",
            f"Silence one line with `# noqa: {rule.code}`. More: {GUIDE}#{rule.code.lower()}",
        ]
    )
