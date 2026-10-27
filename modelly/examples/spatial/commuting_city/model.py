"""
Commuting City
==============

Residents of a synthetic city drive to work in the morning and home in the evening.
Each step is one trip. Workplaces are chosen with a gravity rule (more jobs and
shorter free-flow travel times attract more workers); routes are shortest paths on
the current travel times, and the flows of one trip slow the streets for the next
(the BPR congestion function). Needs the ``geo`` extra.
"""

from collections import Counter
from itertools import pairwise

import numpy as np

from modelly import Model
from modelly.data.collector import DataCollector
from modelly.examples.spatial.commuting_city.agents import Commuter
from modelly.examples.spatial.commuting_city.city import city_zones, street_graph
from modelly.population import synthesize_population
from modelly.scenarios import Scenario
from modelly.space.geo import GeoSpace, RoadNetwork

AGES = ["18-34", "35-64", "65+"]
AGE_SHARES = [0.35, 0.45, 0.20]
WORKER_SHARE = 0.6
# Seed table (age x works): few people over 65 still work.
SEED = np.array([[1.0, 0.5], [1.0, 0.3], [0.05, 1.0]])
CENTRE_JOBS = 5.0  # jobs per central zone, relative to an outer zone
BPR_POWER = 4
SECONDS_PER_MINUTE = 60.0


class CommutingScenario(Scenario):
    """Scenario parameters for the commuting model.

    Args:
        blocks: zones per side of the square city.
        block_size: side of a zone, in metres.
        residents: residents per outer zone (nobody lives in the centre).
        beta: how strongly travel time deters a job, per second.
        capacity: commuters per street and trip before it slows down.
        congestion: the BPR coefficient (delay at capacity, as a share of free flow).
    """

    blocks: int = 4
    block_size: float = 500.0
    residents: int = 30
    beta: float = 0.004
    capacity: float = 15.0
    congestion: float = 0.15


def split(total, shares):
    """Whole counts in proportion to ``shares`` that add up to ``total``."""
    counts = np.floor(np.asarray(shares) * total).astype(int)
    counts[0] += total - counts.sum()
    return counts.tolist()


class CommutingCity(Model):
    """Workers commute between home and work zones on a congestible street network."""

    def __init__(self, scenario: CommutingScenario = CommutingScenario):
        super().__init__(scenario=scenario)
        zones = city_zones(scenario.blocks, scenario.block_size)
        self.space = GeoSpace(zones, random=self.random)
        self.roads = RoadNetwork(
            street_graph(scenario.blocks, scenario.block_size), random=self.random
        )
        self.roads.add_travel_times(speed=1.0)  # every street carries its own speed
        self.free_flow = {
            (u, v): data["travel_time"]
            for u, v, data in self.roads.graph.edges(data=True)
        }
        self.populate()
        self.assign_jobs()
        self.to_work = True
        self.flows = Counter()
        self.datacollector = DataCollector(
            model_reporters={
                "mean_trip_minutes": "mean_trip_minutes",
                "congested_streets": "congested_streets",
                "in_centre": "in_centre",
            }
        )

    def populate(self):
        """Create residents from a synthetic population of every outer zone."""
        outer = self.space.regions.index[~self.space.regions["centre"]]
        n = self.scenario.residents
        marginals = {
            zone: {
                "age": split(n, AGE_SHARES),
                "works": split(n, [WORKER_SHARE, 1 - WORKER_SHARE]),
            }
            for zone in outer
        }
        people = synthesize_population(
            {"age": AGES, "works": [True, False]}, marginals, self.rng, seed=SEED
        )
        workers = people[people.works.astype(bool)]
        for zone, group in workers.groupby("region", sort=False):
            homes = self.space.random_points(zone, len(group), self.rng)
            for home, age in zip(homes, group.age):
                Commuter(self, self.space, home, age)

    def assign_jobs(self):
        """Pick a work zone for every commuter by the gravity rule, then a point in it."""
        zones = self.space.regions
        jobs = np.where(zones["centre"], CENTRE_JOBS, 1.0)
        centroids = zones.geometry.centroid
        zone_rows = self.roads.nearest_nodes(
            np.column_stack([centroids.x, centroids.y])
        )
        commuters = list(self.agents_by_type[Commuter])
        homes = [c.home_node for c in commuters]
        times = self.roads.distance_matrix(homes, weight="travel_time")[:, zone_rows]
        weights = jobs * np.exp(-self.scenario.beta * times)
        for commuter, row in zip(commuters, weights):
            label = zones.index[self.rng.choice(len(zones), p=row / row.sum())]
            commuter.take_job(self.space.random_points(label, 1, self.rng)[0])

    def step(self):
        """One trip for everybody, then the streets' travel times follow the flows."""
        self.flows = Counter()
        paths = {}
        for commuter in self.agents_by_type[Commuter]:
            path = commuter.commute(self.to_work, paths)
            self.flows.update(frozenset(edge) for edge in pairwise(path))
        self.to_work = not self.to_work
        self.update_travel_times()
        self.datacollector.collect(self)

    def update_travel_times(self):
        """BPR: ``time = free * (1 + congestion * (flow / capacity) ** 4)``."""
        s = self.scenario
        for (u, v), free in self.free_flow.items():
            load = self.flows[frozenset((u, v))] / s.capacity
            self.roads.graph.edges[u, v]["travel_time"] = free * (
                1 + s.congestion * load**BPR_POWER
            )
        self.roads.invalidate("travel_time")

    @property
    def mean_trip_minutes(self):
        trips = [c.trip_time for c in self.agents_by_type[Commuter]]
        return float(np.mean(trips)) / SECONDS_PER_MINUTE if trips else 0.0

    @property
    def congested_streets(self):
        return sum(1 for flow in self.flows.values() if flow > self.scenario.capacity)

    @property
    def in_centre(self):
        counts = self.space.region_counts()
        return int(counts[self.space.regions["centre"]].sum())
