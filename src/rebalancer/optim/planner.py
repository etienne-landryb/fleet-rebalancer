import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Station:
    station_id: str
    name: str
    lat: float
    lon: float
    capacity: int
    current_bikes: int
    predicted_bikes: int


@dataclass(frozen=True)
class Stop:
    station_id: str
    name: str
    action: str  # "pickup" or "dropoff"
    quantity: int


@dataclass
class Route:
    van_id: int
    stops: list[Stop] = field(default_factory=list)
    total_pickups: int = 0
    total_dropoffs: int = 0
    distance_km: float = 0.0
    duration_min: float = 0.0


@dataclass
class PlanResult:
    routes: list[Route]
    feasible: bool
    objective_value: int
    unserved_stations: list[str] = field(default_factory=list)


@dataclass
class ImpactResult:
    do_nothing_health: float
    planned_health: float
    health_improvement: float
    do_nothing_starving: int
    planned_starving: int
    do_nothing_saturated: int
    planned_saturated: int
    bikes_moved: int


STARVING_THRESHOLD = 0.15
SATURATED_THRESHOLD = 0.85
MAX_ACTIVE_STATIONS = 500


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _build_distance_matrix(stations: list[Station]) -> list[list[int]]:
    """Distance matrix in meters. Index 0 is the depot (centroid of all stations)."""
    n = len(stations)
    lats = [s.lat for s in stations]
    lons = [s.lon for s in stations]
    depot_lat = sum(lats) / n
    depot_lon = sum(lons) / n

    all_points = [(depot_lat, depot_lon)] + [(s.lat, s.lon) for s in stations]
    size = len(all_points)
    matrix = [[0] * size for _ in range(size)]
    for i in range(size):
        for j in range(i + 1, size):
            dist_m = int(
                _haversine_km(
                    all_points[i][0],
                    all_points[i][1],
                    all_points[j][0],
                    all_points[j][1],
                )
                * 1000
            )
            matrix[i][j] = dist_m
            matrix[j][i] = dist_m
    return matrix


def _classify_stations(
    stations: list[Station],
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Identify surplus (pickup) and deficit (dropoff) stations.
    Returns (surplus_list, deficit_list) as [(station_index, quantity), ...]."""
    surplus = []
    deficit = []
    for i, s in enumerate(stations):
        ideal = int(s.capacity * 0.5)
        diff = s.predicted_bikes - ideal
        if s.predicted_bikes / max(s.capacity, 1) >= SATURATED_THRESHOLD and diff > 0:
            surplus.append((i, diff))
        elif s.predicted_bikes / max(s.capacity, 1) <= STARVING_THRESHOLD and diff < 0:
            deficit.append((i, abs(diff)))
    return surplus, deficit


def _limit_active_stations(
    surplus: list[tuple[int, int]],
    deficit: list[tuple[int, int]],
    limit: int = MAX_ACTIVE_STATIONS,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]], set[int]]:
    """Bound the quadratic routing problem for very large networks."""
    candidates = surplus + deficit
    if len(candidates) <= limit:
        return surplus, deficit, set()

    surplus_budget = min(len(surplus), limit // 2)
    deficit_budget = min(len(deficit), limit // 2)
    remaining = limit - surplus_budget - deficit_budget
    if len(surplus) > surplus_budget:
        surplus_budget += min(remaining, len(surplus) - surplus_budget)
        remaining = limit - surplus_budget - deficit_budget
    if len(deficit) > deficit_budget:
        deficit_budget += min(remaining, len(deficit) - deficit_budget)

    selected_surplus = sorted(surplus, key=lambda item: (-item[1], item[0]))[
        :surplus_budget
    ]
    selected_deficit = sorted(deficit, key=lambda item: (-item[1], item[0]))[
        :deficit_budget
    ]
    selected_indices = {index for index, _ in selected_surplus + selected_deficit}
    skipped_indices = {index for index, _ in candidates} - selected_indices
    return selected_surplus, selected_deficit, skipped_indices


class Planner(ABC):
    @abstractmethod
    def solve(
        self,
        stations: list[Station],
        van_count: int,
        van_capacity: int,
        shift_budget_min: int,
    ) -> PlanResult: ...


class ORToolsPlanner(Planner):
    SPEED_KMH = 15  # urban van speed assumption

    def solve(
        self,
        stations: list[Station],
        van_count: int,
        van_capacity: int,
        shift_budget_min: int,
    ) -> PlanResult:
        surplus, deficit = _classify_stations(stations)
        surplus, deficit, skipped_indices = _limit_active_stations(surplus, deficit)

        if skipped_indices:
            logger.warning(
                "Planner capped active stations at %d; skipped %d "
                "lower-priority stations",
                MAX_ACTIVE_STATIONS,
                len(skipped_indices),
            )

        if not surplus and not deficit:
            logger.info("No imbalanced stations — nothing to plan")
            return PlanResult(
                routes=[],
                feasible=True,
                objective_value=0,
                unserved_stations=[stations[i].station_id for i in skipped_indices],
            )

        # Build the node list: depot + surplus stations + deficit stations
        active_indices = []
        demands = [0]  # depot has 0 demand
        node_station_map = {}  # node_index -> (station_index, action, quantity)

        for station_idx, qty in surplus:
            node = len(demands)
            active_indices.append(station_idx)
            # Negative demand = van picks up bikes (gains capacity load)
            demands.append(-qty)
            node_station_map[node] = (station_idx, "pickup", qty)

        for station_idx, qty in deficit:
            node = len(demands)
            active_indices.append(station_idx)
            # Positive demand = van drops off bikes (loses capacity load)
            demands.append(qty)
            node_station_map[node] = (station_idx, "dropoff", qty)

        n_nodes = len(demands)

        if n_nodes <= 1:
            return PlanResult(
                routes=[],
                feasible=True,
                objective_value=0,
                unserved_stations=[stations[i].station_id for i in skipped_indices],
            )

        # Build a distance matrix for only the active nodes + depot
        active_stations = [stations[i] for i in active_indices]
        full_matrix = _build_distance_matrix(active_stations)

        # Time matrix in minutes (distance / speed)
        time_matrix = [
            [
                int(full_matrix[i][j] / 1000 / self.SPEED_KMH * 60)
                for j in range(n_nodes)
            ]
            for i in range(n_nodes)
        ]

        manager = pywrapcp.RoutingIndexManager(n_nodes, van_count, 0)
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index: int, to_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return full_matrix[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Time dimension for shift budget constraint
        def time_callback(from_index: int, to_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return time_matrix[from_node][to_node]

        time_callback_index = routing.RegisterTransitCallback(time_callback)
        routing.AddDimension(
            time_callback_index,
            0,  # no slack
            shift_budget_min,
            True,  # start cumul at zero
            "Time",
        )

        # Capacity dimension
        def demand_callback(from_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            return demands[from_node]

        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,  # no slack
            [van_capacity] * van_count,
            True,  # start cumul at zero
            "Capacity",
        )

        # Allow dropping nodes with a penalty
        penalty = 100_000
        for node in range(1, n_nodes):
            routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

        search_params = pywrapcp.DefaultRoutingSearchParameters()
        search_params.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        search_params.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_params.time_limit.seconds = 5

        solution = routing.SolveWithParameters(search_params)

        if solution is None:
            logger.warning("OR-Tools found no solution")
            return PlanResult(
                routes=[],
                feasible=False,
                objective_value=0,
                unserved_stations=[stations[i].station_id for i in active_indices]
                + [stations[i].station_id for i in skipped_indices],
            )

        routes = []
        unserved = set()
        time_dimension = routing.GetDimensionOrDie("Time")

        for v in range(van_count):
            route = Route(van_id=v)
            index = routing.Start(v)
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                if node != 0 and node in node_station_map:
                    station_idx, action, qty = node_station_map[node]
                    s = stations[station_idx]
                    route.stops.append(
                        Stop(
                            station_id=s.station_id,
                            name=s.name,
                            action=action,
                            quantity=qty,
                        )
                    )
                    if action == "pickup":
                        route.total_pickups += qty
                    else:
                        route.total_dropoffs += qty
                index = solution.Value(routing.NextVar(index))

            end_time = solution.Value(time_dimension.CumulVar(index))
            route.duration_min = end_time

            if route.stops:
                routes.append(route)

        # Identify unserved nodes
        for node in range(1, n_nodes):
            idx = manager.NodeToIndex(node)
            if solution.Value(routing.NextVar(idx)) == idx:
                station_idx = node_station_map[node][0]
                unserved.add(stations[station_idx].station_id)

        # Compute route distances
        for route in routes:
            total_dist = 0.0
            # Recompute from the stop sequence
            prev_node = 0  # depot
            for stop in route.stops:
                # Find the node index for this stop
                for n_idx, (s_idx, _, _) in node_station_map.items():
                    if stations[s_idx].station_id == stop.station_id:
                        total_dist += full_matrix[prev_node][n_idx] / 1000
                        prev_node = n_idx
                        break
            total_dist += full_matrix[prev_node][0] / 1000  # return to depot
            route.distance_km = round(total_dist, 2)

        result = PlanResult(
            routes=routes,
            feasible=True,
            objective_value=solution.ObjectiveValue(),
            unserved_stations=list(unserved)
            + [stations[i].station_id for i in skipped_indices],
        )

        total_moved = sum(r.total_pickups for r in routes)
        logger.info(
            "Plan: %d routes, %d bikes moved, %d unserved stations",
            len(routes),
            total_moved,
            len(result.unserved_stations),
        )
        return result


def simulate_impact(stations: list[Station], plan: PlanResult) -> ImpactResult:
    """Compare network health under do-nothing vs the proposed plan."""
    # Do-nothing: use predicted_bikes as-is
    do_nothing_starving = 0
    do_nothing_saturated = 0
    do_nothing_healthy = 0

    for s in stations:
        fill = s.predicted_bikes / max(s.capacity, 1)
        if fill <= STARVING_THRESHOLD:
            do_nothing_starving += 1
        elif fill >= SATURATED_THRESHOLD:
            do_nothing_saturated += 1
        else:
            do_nothing_healthy += 1

    total = len(stations)
    do_nothing_health = do_nothing_healthy / max(total, 1)

    # Planned: apply pickup/dropoff changes to predicted_bikes
    adjustments: dict[str, int] = {}
    bikes_moved = 0
    for route in plan.routes:
        for stop in route.stops:
            if stop.action == "pickup":
                adjustments[stop.station_id] = (
                    adjustments.get(stop.station_id, 0) - stop.quantity
                )
                bikes_moved += stop.quantity
            else:
                adjustments[stop.station_id] = (
                    adjustments.get(stop.station_id, 0) + stop.quantity
                )

    planned_starving = 0
    planned_saturated = 0
    planned_healthy = 0

    for s in stations:
        adj = adjustments.get(s.station_id, 0)
        new_bikes = max(0, min(s.capacity, s.predicted_bikes + adj))
        fill = new_bikes / max(s.capacity, 1)
        if fill <= STARVING_THRESHOLD:
            planned_starving += 1
        elif fill >= SATURATED_THRESHOLD:
            planned_saturated += 1
        else:
            planned_healthy += 1

    planned_health = planned_healthy / max(total, 1)

    return ImpactResult(
        do_nothing_health=round(do_nothing_health, 4),
        planned_health=round(planned_health, 4),
        health_improvement=round(planned_health - do_nothing_health, 4),
        do_nothing_starving=do_nothing_starving,
        planned_starving=planned_starving,
        do_nothing_saturated=do_nothing_saturated,
        planned_saturated=planned_saturated,
        bikes_moved=bikes_moved,
    )
