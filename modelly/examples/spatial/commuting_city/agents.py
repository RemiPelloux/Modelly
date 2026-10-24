from itertools import pairwise

from modelly.space.geo import GeoAgent


class Commuter(GeoAgent):
    """A resident who drives between a home and a workplace along the streets.

    Attributes:
        age: the age band from the synthetic population.
        home, work: points in the city's CRS.
        home_node, work_node: the street intersections nearest to them.
        trip_time: the duration of the last trip, in seconds.
    """

    def __init__(self, model, space, home, age):
        super().__init__(space, model, home)
        self.age = age
        self.home = tuple(home)
        self.work = self.home
        self.home_node = model.roads.node_of(self.home)
        self.work_node = self.home_node
        self.trip_time = 0.0

    def take_job(self, point):
        """Work at ``point`` from now on."""
        self.work = tuple(point)
        self.work_node = self.model.roads.node_of(self.work)

    def commute(self, to_work, paths):
        """Drive to work or back home on the current travel times; return the path."""
        origin, destination = (
            (self.home_node, self.work_node)
            if to_work
            else (self.work_node, self.home_node)
        )
        key = (origin, destination)
        if key not in paths:
            paths[key] = self.model.roads.shortest_path(
                origin, destination, weight="travel_time"
            )
        path = paths[key]
        edges = self.model.roads.graph.edges
        self.trip_time = sum(edges[u, v]["travel_time"] for u, v in pairwise(path))
        self.move_to(self.work if to_work else self.home)
        return path
