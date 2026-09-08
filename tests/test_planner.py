from rebalancer.optim.planner import (
    ORToolsPlanner,
    Planner,
    PlanResult,
    Route,
    Station,
    Stop,
    _classify_stations,
    _haversine_km,
    _limit_active_stations,
    simulate_impact,
)


def _nyc_stations() -> list[Station]:
    """Small hand-checkable set: 2 surplus, 2 deficit, 1 healthy."""
    return [
        Station("1", "Penn Station", 40.750, -73.992, 40, 20, 38),  # saturated
        Station("2", "Times Square", 40.758, -73.985, 30, 15, 28),  # saturated
        Station("3", "Central Park", 40.768, -73.970, 50, 25, 4),  # starving
        Station("4", "Grand Central", 40.753, -73.977, 30, 15, 3),  # starving
        Station("5", "Union Square", 40.736, -73.990, 40, 20, 20),  # healthy
    ]


class TestClassifyStations:
    def test_identifies_surplus_and_deficit(self):
        stations = _nyc_stations()
        surplus, deficit = _classify_stations(stations)
        surplus_ids = [stations[i].station_id for i, _ in surplus]
        deficit_ids = [stations[i].station_id for i, _ in deficit]
        assert "1" in surplus_ids
        assert "2" in surplus_ids
        assert "3" in deficit_ids
        assert "4" in deficit_ids
        assert "5" not in surplus_ids and "5" not in deficit_ids

    def test_healthy_network_has_no_imbalance(self):
        stations = [
            Station("1", "A", 40.0, -74.0, 20, 10, 10),
            Station("2", "B", 40.1, -74.1, 20, 10, 10),
        ]
        surplus, deficit = _classify_stations(stations)
        assert len(surplus) == 0
        assert len(deficit) == 0


class TestHaversine:
    def test_same_point_is_zero(self):
        assert _haversine_km(40.0, -74.0, 40.0, -74.0) == 0.0

    def test_known_distance(self):
        d = _haversine_km(40.750, -73.992, 40.758, -73.985)
        assert 0.5 < d < 2.0


class TestORToolsPlanner:
    def test_implements_planner_interface(self):
        assert issubclass(ORToolsPlanner, Planner)

    def test_no_imbalance_returns_empty(self):
        stations = [
            Station("1", "A", 40.0, -74.0, 20, 10, 10),
            Station("2", "B", 40.1, -74.1, 20, 10, 10),
        ]
        planner = ORToolsPlanner()
        result = planner.solve(
            stations, van_count=1, van_capacity=20, shift_budget_min=120
        )
        assert result.feasible
        assert len(result.routes) == 0

    def test_basic_rebalancing(self):
        stations = _nyc_stations()
        planner = ORToolsPlanner()
        result = planner.solve(
            stations, van_count=2, van_capacity=20, shift_budget_min=120
        )
        assert result.feasible
        assert len(result.routes) > 0

        for route in result.routes:
            assert route.van_id >= 0
            assert len(route.stops) > 0
            for stop in route.stops:
                assert stop.action in ("pickup", "dropoff")
                assert stop.quantity > 0

    def test_respects_van_capacity(self):
        stations = _nyc_stations()
        planner = ORToolsPlanner()
        result = planner.solve(
            stations, van_count=2, van_capacity=10, shift_budget_min=120
        )
        assert result.feasible
        for route in result.routes:
            load = 0
            for stop in route.stops:
                if stop.action == "pickup":
                    load += stop.quantity
                else:
                    load -= stop.quantity
                assert load <= 10, f"Van {route.van_id} exceeded capacity: {load}"

    def test_shift_budget_respected(self):
        stations = _nyc_stations()
        planner = ORToolsPlanner()
        result = planner.solve(
            stations, van_count=2, van_capacity=20, shift_budget_min=120
        )
        for route in result.routes:
            assert route.duration_min <= 120

    def test_single_van_feasible(self):
        stations = _nyc_stations()
        planner = ORToolsPlanner()
        result = planner.solve(
            stations, van_count=1, van_capacity=20, shift_budget_min=120
        )
        assert result.feasible
        assert len(result.routes) <= 1

    def test_large_active_set_is_bounded_by_priority(self):
        surplus = [(index, index + 1) for index in range(400)]
        deficit = [(index + 400, index + 1) for index in range(400)]

        selected_surplus, selected_deficit, skipped = _limit_active_stations(
            surplus, deficit, limit=100
        )

        assert len(selected_surplus) + len(selected_deficit) == 100
        assert selected_surplus[0] == (399, 400)
        assert selected_deficit[0] == (799, 400)
        assert len(skipped) == 700


class TestSimulateImpact:
    def test_no_plan_shows_no_improvement(self):
        stations = _nyc_stations()
        empty_plan = PlanResult(routes=[], feasible=True, objective_value=0)
        impact = simulate_impact(stations, empty_plan)
        assert impact.health_improvement == 0.0
        assert impact.bikes_moved == 0

    def test_plan_improves_health(self):
        stations = _nyc_stations()
        route = Route(
            van_id=0,
            stops=[
                Stop("1", "Penn Station", "pickup", 10),
                Stop("3", "Central Park", "dropoff", 10),
            ],
            total_pickups=10,
            total_dropoffs=10,
        )
        plan = PlanResult(routes=[route], feasible=True, objective_value=100)
        impact = simulate_impact(stations, plan)
        assert impact.health_improvement > 0
        assert impact.planned_health > impact.do_nothing_health
        assert impact.bikes_moved == 10
        assert impact.planned_starving <= impact.do_nothing_starving

    def test_healthy_network_stays_healthy(self):
        stations = [
            Station("1", "A", 40.0, -74.0, 20, 10, 10),
            Station("2", "B", 40.1, -74.1, 20, 10, 10),
        ]
        empty_plan = PlanResult(routes=[], feasible=True, objective_value=0)
        impact = simulate_impact(stations, empty_plan)
        assert impact.do_nothing_health == 1.0
        assert impact.planned_health == 1.0
        assert impact.do_nothing_starving == 0
        assert impact.do_nothing_saturated == 0
