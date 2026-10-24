"""Citizens with a persona who ask a language model what they now think of a proposal."""

from collections import Counter

from modelly import Agent
from modelly.llm import LLMAgent

OPINIONS = ("support", "neutral", "oppose")
REASON_CHARS = 200
SCHEMA = {
    "type": "object",
    "required": ["opinion"],
    "additionalProperties": False,
    "properties": {
        "opinion": {"enum": list(OPINIONS)},
        "reason": {"type": "string", "maxLength": REASON_CHARS},
    },
}
PROPOSAL = "a protected bike lane on the main street"
PERSONAS = (
    "a retired teacher who values safety and is slow to change your mind",
    "a shop owner worried about parking for customers",
    "a student who cycles to class every day",
    "a nurse working night shifts across town",
    "a hurried commuter who answers in a rush",
    "a parent of two young children",
    "a delivery driver who knows every street",
    "a stubborn local councillor who rarely changes position",
)


class Citizen(LLMAgent, Agent):
    """A town resident: a persona, an opinion, and the friends it hears from."""

    def __init__(self, model, persona, opinion):
        """Set the persona (the system prompt) and the starting opinion."""
        super().__init__(model)
        self.persona = (
            f"You are {persona}. You live in a small town that is debating "
            f"{PROPOSAL}. Answer as this person would."
        )
        self.opinion = opinion
        self.friends = []

    def prompt(self):
        """What the citizen is asked each step: its view and its friends' views."""
        counts = Counter(friend.opinion for friend in self.friends)
        heard = ", ".join(f"{counts[o]} {o}" for o in OPINIONS)
        return (
            f"Your current view of {PROPOSAL}: {self.opinion}. Of your {len(self.friends)} "
            f"friends: {heard}. After talking with them this week, what is your "
            "opinion now?"
        )
