"""Opinion dynamics with persona agents who decide through a language model.

Citizens sit on a small-world friendship network (a ring where each knows its nearest
neighbours, with a few ties rewired at random). Each step every citizen is asked, with
its persona as the system prompt, what it now thinks given its friends' views; the
replies are validated against a schema and applied together, in agent order.

By default the "model" is a local function (``responder.town_responder``), so the
example runs offline. ``replay_client()`` replays the bundled cache instead: the same
decisions with no provider call at all.
"""

from pathlib import Path

from modelly import DataCollector, Model
from modelly.examples.llm.llm_opinions.agents import OPINIONS, PERSONAS, SCHEMA, Citizen
from modelly.examples.llm.llm_opinions.responder import town_responder
from modelly.llm import Client, FakeProvider, ResponseCache, decide_all

REPLAY_CACHE = Path(__file__).parent / "resources" / "replay.jsonl.gz"
# The run the bundled cache was recorded from.
REPLAY_STEPS = 2
REPLAY_SEED = 42
DEFAULT_AGENTS = 200
DEFAULT_DEGREE = 4
DEFAULT_REWIRE = 0.1


def fake_client(cache=None):
    """A client answering with ``town_responder``; recording into ``cache`` if given."""
    return Client(
        FakeProvider(town_responder), cache=ResponseCache() if cache is None else cache
    )


def replay_client(path=REPLAY_CACHE):
    """A client that answers only from the cache at ``path``; a miss raises CacheMiss."""
    cache = ResponseCache.from_file(path, mode="read-only")
    return Client(FakeProvider(town_responder), cache=cache)


def share_support(model):
    """Share of citizens who support the proposal."""
    return sum(a.opinion == "support" for a in model.agents) / len(model.agents)


class LLMOpinions(Model):
    """Persona agents on a friendship network, deciding their opinion each step."""

    def __init__(
        self,
        n_agents=DEFAULT_AGENTS,
        degree=DEFAULT_DEGREE,
        rewire=DEFAULT_REWIRE,
        client=None,
        rng=REPLAY_SEED,
    ):
        """Create the citizens, their friendships and the language-model client."""
        super().__init__(rng=rng)
        self.llm = client or fake_client()
        for _ in range(n_agents):
            Citizen(self, self.random.choice(PERSONAS), self.random.choice(OPINIONS))
        self.citizens = list(self.agents)
        self.connect(degree, rewire)
        self.datacollector = DataCollector({"support": share_support})
        self.datacollector.collect(self)

    def connect(self, degree, rewire):
        """A ring lattice of ``degree`` neighbours with each tie rewired with ``rewire``."""
        n = len(self.citizens)
        for i, citizen in enumerate(self.citizens):
            for offset in range(1, degree // 2 + 1):
                j = (i + offset) % n
                if self.random.random() < rewire:
                    j = self.random.randrange(n)
                other = self.citizens[j]
                if other is not citizen and other not in citizen.friends:
                    citizen.friends.append(other)
                    other.friends.append(citizen)

    def step(self):
        """Every citizen decides at once; the new opinions apply together."""
        decisions = decide_all(self.citizens, Citizen.prompt, SCHEMA)
        for citizen, decision in zip(self.citizens, decisions):
            citizen.opinion = decision["opinion"]
        self.datacollector.collect(self)

    def opinions(self):
        """Every citizen's opinion, in agent order."""
        return [citizen.opinion for citizen in self.citizens]


def record_replay(path=REPLAY_CACHE, steps=REPLAY_STEPS):
    """Run the default model with the local responder and export its cache to ``path``.

    This is how the bundled ``resources/replay.jsonl.gz`` was made; with a real
    provider in ``fake_client``'s place it records a study's replies the same way.
    """
    model = LLMOpinions()
    for _ in range(steps):
        model.step()
    return model.llm.cache.export(path)
