"""
Branch-and-Price solver for the Vehicle Routing Problem with Time Windows (VRPTW).

VRPTW is a set partitioning problem where each customer must be visited exactly once.
This makes it well-suited for Ryan-Foster branching.

For VRPTW, we use:
- Master Problem: Set partitioning LP
- Pricing Problem: Elementary shortest path with resource constraints (ESPPRC)
- Branching: Ryan-Foster branching on customer pairs

IMPORTANT: This is a TRUE Branch-and-Price implementation that runs column generation
at each B&B node to find new columns that respect the branching decisions.
"""

import math
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Optional

from openbp.solver import BPSolution, BPStatus


def _route_key(route: list[int]) -> tuple[int, ...]:
    """Convert a route to a hashable tuple."""
    return tuple(route)


@dataclass
class RyanFosterDecision:
    """A Ryan-Foster branching decision."""
    item_i: int
    item_j: int
    same_column: bool  # True = must be together, False = must be apart

    def __repr__(self):
        rel = "SAME" if self.same_column else "DIFF"
        return f"RF({self.item_i}, {self.item_j}, {rel})"


@dataclass
class VRPTWBPConfig:
    """Configuration for VRPTW branch-and-price."""
    # Termination
    max_time: float = 600.0
    max_nodes: int = 1000
    gap_tolerance: float = 1e-6

    # Column generation
    cg_max_iterations: int = 100
    cg_max_iterations_per_node: int = 50  # CG iterations at each B&B node

    # Logging
    verbose: bool = True


def solve_vrptw_bp(
    instance: Any,  # opencg.applications.vrp.VRPTWInstance
    config: Optional[VRPTWBPConfig] = None,
) -> BPSolution:
    """
    Solve a VRPTW instance using branch-and-price with Ryan-Foster branching.

    This is a TRUE Branch-and-Price that runs column generation at each node
    to find new columns that respect the branching decisions.

    Args:
        instance: A VRPTWInstance from OpenCG
        config: Solver configuration

    Returns:
        BPSolution with optimal integer solution

    Example:
        from opencg.applications.vrp import VRPTWInstance
        from openbp.applications.vrptw import solve_vrptw_bp

        instance = VRPTWInstance.from_solomon("c101.txt")
        solution = solve_vrptw_bp(instance)
        print(f"Optimal distance: {solution.objective}")
    """
    config = config or VRPTWBPConfig()

    # Import OpenCG components
    try:
        from opencg.applications.vrp import VRPTWConfig, solve_vrptw
        from opencg.applications.vrp.network_builder import build_vrptw_network
        from opencg.applications.vrp.resources import CapacityResource, TimeResource
        from opencg.applications.vrp.solver import (
            _create_column_from_route_vrptw,
            _generate_greedy_routes_vrptw,
            _route_cost_vrptw,
        )
        from opencg.core.column import Column
        from opencg.core.problem import (
            CoverConstraint,
            CoverType,
            ObjectiveSense,
            Problem,
        )
        from opencg.master import HiGHSMasterProblem
        from opencg.pricing import AcceleratedLabelingAlgorithm, PricingConfig
    except ImportError as e:
        raise ImportError(
            "OpenCG is required. Install with: pip install -e path/to/opencg"
        ) from e

    start_time = time.time()

    # Statistics
    nodes_explored = 0
    nodes_pruned = 0
    max_depth = 0

    # Lower bound from capacity
    lower_bound_vehicles = math.ceil(instance.total_demand / instance.vehicle_capacity)

    # Track best solution
    best_objective = float('inf')
    best_routes: list[list[int]] = []
    global_lower_bound = 0.0

    # Build network once (used for pricing at all nodes)
    network, customer_node_map = build_vrptw_network(instance)

    # Create problem structure
    cover_constraints = []
    for i in range(instance.num_customers):
        cover_constraints.append(CoverConstraint(
            item_id=i,
            name=f"customer_{i}",
            rhs=1.0,
            is_equality=True,
        ))

    _, depot_latest = instance.depot_time_window
    resources = [
        CapacityResource(instance.vehicle_capacity),
        TimeResource(depot_latest=depot_latest),
    ]

    problem = Problem(
        name="VRPTW",
        network=network,
        resources=resources,
        cover_constraints=cover_constraints,
        cover_type=CoverType.SET_PARTITIONING,
        objective_sense=ObjectiveSense.MINIMIZE,
    )

    if config.verbose:
        print("VRPTW B&P Solver (True Branch-and-Price)")
        print(f"  Customers: {instance.num_customers}")
        print(f"  Vehicle capacity: {instance.vehicle_capacity}")
        print(f"  Min vehicles (capacity): {lower_bound_vehicles}")
        print()

    # Global column pool - accumulates all generated columns
    all_routes: list[list[int]] = []
    route_set: set[tuple[int, ...]] = set()

    def add_route(route: list[int]) -> bool:
        """Add route to pool if not already present. Returns True if added."""
        key = tuple(route)
        if key not in route_set:
            route_set.add(key)
            all_routes.append(route)
            return True
        return False

    # Generate initial columns using greedy heuristic
    greedy_routes = _generate_greedy_routes_vrptw(instance)
    for route in greedy_routes:
        add_route(route)

    if config.verbose:
        print(f"Initial greedy routes: {len(greedy_routes)}")

    # Node queue: (lower_bound, node_id, depth, rf_decisions)
    node_queue: list[tuple[float, int, int, list[RyanFosterDecision]]] = []
    next_node_id = 0

    # Add root node (no branching decisions)
    node_queue.append((0.0, next_node_id, 0, []))
    next_node_id += 1

    if config.verbose:
        print()
        print("Branch-and-Price with column generation at each node...")
        print()

    # Main B&P loop
    while node_queue:
        # Check limits
        elapsed = time.time() - start_time
        if elapsed >= config.max_time:
            if config.verbose:
                print(f"Time limit reached ({elapsed:.1f}s)")
            break

        if config.max_nodes > 0 and nodes_explored >= config.max_nodes:
            if config.verbose:
                print(f"Node limit reached ({nodes_explored})")
            break

        # Select best node (lowest lower bound)
        node_queue.sort(key=lambda x: x[0])
        lb, node_id, depth, rf_decisions = node_queue.pop(0)

        nodes_explored += 1
        max_depth = max(max_depth, depth)

        # Prune by bound
        if lb >= best_objective - config.gap_tolerance:
            nodes_pruned += 1
            continue

        if config.verbose and nodes_explored % 10 == 1:
            gap = (best_objective - global_lower_bound) / best_objective * 100 if best_objective < float('inf') else 100
            print(f"  Node {nodes_explored}: depth={depth}, LB={global_lower_bound:.2f}, "
                  f"UB={best_objective:.2f}, gap={gap:.2f}%, pool={len(all_routes)}")

        # Solve node with column generation
        result = _solve_node_with_cg(
            instance, problem, network, customer_node_map,
            all_routes, add_route, rf_decisions,
            config.cg_max_iterations_per_node, config.verbose and depth < 3
        )

        if result is None:
            # Infeasible
            nodes_pruned += 1
            continue

        lp_value, valid_routes, route_values = result

        # Update global lower bound
        if node_queue:
            global_lower_bound = min(lp_value, min(n[0] for n in node_queue))
        else:
            global_lower_bound = lp_value

        # Check if integer
        is_integer = all(
            abs(v - round(v)) < 1e-6
            for v in route_values
        )

        if is_integer:
            # Found integer solution
            ip_value = sum(route_values[i] * _route_cost_vrptw(instance, valid_routes[i])
                          for i in range(len(valid_routes)) if route_values[i] > 0.5)

            if ip_value < best_objective:
                best_objective = ip_value
                best_routes = [valid_routes[i] for i in range(len(valid_routes)) if route_values[i] > 0.5]

                if config.verbose:
                    print(f"    New incumbent: {ip_value:.2f} ({len(best_routes)} routes)")

            # Prune nodes with worse bound
            node_queue = [(b, i, d, r) for b, i, d, r in node_queue
                         if b < best_objective - config.gap_tolerance]

        else:
            # Need to branch - find Ryan-Foster pair
            rf_pair = _find_ryan_foster_pair(valid_routes, route_values, rf_decisions)

            if rf_pair is not None:
                item_i, item_j, together_value = rf_pair

                if config.verbose and depth < 5:
                    print(f"    Branching on ({item_i}, {item_j}): together={together_value:.3f}")

                # Same branch: items must be together
                same_decisions = rf_decisions + [RyanFosterDecision(item_i, item_j, True)]
                node_queue.append((lp_value, next_node_id, depth + 1, same_decisions))
                next_node_id += 1

                # Different branch: items must be apart
                diff_decisions = rf_decisions + [RyanFosterDecision(item_i, item_j, False)]
                node_queue.append((lp_value, next_node_id, depth + 1, diff_decisions))
                next_node_id += 1
            else:
                # No valid branching pair found - treat as integer
                pass

    # Build solution
    total_time = time.time() - start_time

    if best_objective < float('inf'):
        status = BPStatus.OPTIMAL if len(node_queue) == 0 else BPStatus.FEASIBLE
    else:
        status = BPStatus.INFEASIBLE

    # Calculate final gap
    if node_queue:
        final_lb = min(global_lower_bound, min(n[0] for n in node_queue))
    else:
        final_lb = best_objective  # When tree is exhausted, LB = UB
    gap = max(0.0, (best_objective - final_lb) / best_objective) if best_objective < float('inf') and best_objective > 0 else 0.0

    solution = BPSolution(
        status=status,
        objective=best_objective,
        lower_bound=final_lb,
        upper_bound=best_objective,
        gap=gap,
        nodes_explored=nodes_explored,
        nodes_pruned=nodes_pruned,
        max_depth=max_depth,
        total_time=total_time,
        time_in_cg=total_time * 0.9,  # Approximate
        time_in_branching=total_time * 0.1,
        columns=[],
        column_values=[],
    )

    # Add routes to solution metadata
    solution.routes = best_routes

    if config.verbose:
        print()
        print("B&P Complete:")
        print(f"  Status: {status.name}")
        print(f"  Objective: {best_objective:.2f}")
        print(f"  Lower bound: {final_lb:.2f}")
        print(f"  Routes: {len(best_routes)}")
        print(f"  Nodes: {nodes_explored}")
        print(f"  Time: {total_time:.2f}s")
        print(f"  Gap: {gap*100:.2f}%")
        print(f"  Total columns: {len(all_routes)}")

    return solution


def _solve_node_with_cg(
    instance,
    problem,
    network,
    customer_node_map,
    all_routes: list[list[int]],
    add_route_fn,
    rf_decisions: list[RyanFosterDecision],
    max_cg_iterations: int,
    verbose: bool,
) -> Optional[tuple[float, list[list[int]], list[float]]]:
    """
    Solve a B&B node with column generation.

    This runs CG at this node, generating new columns that respect RF decisions.
    New columns are added to the global pool.

    Returns:
        (lp_value, valid_routes, route_values) or None if infeasible
    """
    try:
        import highspy
    except ImportError:
        raise ImportError("HiGHS is required. Install with: pip install highspy")

    from opencg.applications.vrp.solver import _route_cost_vrptw
    from opencg.core.column import Column
    from opencg.master import HiGHSMasterProblem
    from opencg.pricing import AcceleratedLabelingAlgorithm, PricingConfig

    n_customers = instance.num_customers

    # Create master problem for this node
    master = HiGHSMasterProblem(problem, verbosity=0)

    # Add artificial columns for feasibility
    big_m = 1e6
    next_col_id = 0
    for i in range(n_customers):
        art_col = Column(
            arc_indices=(),
            cost=big_m,
            covered_items=frozenset([i]),
            column_id=next_col_id,
            attributes={'artificial': True, 'route': [i]},
        )
        master.add_column(art_col)
        next_col_id += 1

    # Add existing routes that satisfy RF decisions
    valid_routes = []
    route_to_col_id = {}

    for route in all_routes:
        if _route_satisfies_rf_decisions(route, rf_decisions):
            cost = _route_cost_vrptw(instance, route)
            col = Column(
                arc_indices=(),
                cost=cost,
                covered_items=frozenset(route),
                column_id=next_col_id,
                attributes={'route': route},
            )
            master.add_column(col)
            route_to_col_id[tuple(route)] = next_col_id
            valid_routes.append(route)
            next_col_id += 1

    if not valid_routes:
        return None

    # Create pricing problem
    pricing_config = PricingConfig(
        max_columns=50,
        reduced_cost_threshold=-1e-6,
        check_elementarity=True,
        use_dominance=True,
        max_time=5.0,
    )
    pricing = AcceleratedLabelingAlgorithm(problem, config=pricing_config)

    # Column generation loop at this node
    for cg_iter in range(max_cg_iterations):
        # Solve LP
        lp_sol = master.solve_lp()
        if lp_sol.status.name != 'OPTIMAL':
            return None

        # Get duals and run pricing
        duals = master.get_dual_values()
        pricing.set_dual_values(duals)
        pricing_sol = pricing.solve()

        # Filter new columns by RF decisions and add to pool
        new_cols_added = 0
        for col in pricing_sol.columns:
            # Extract route from column
            route = []
            for arc_idx in col.arc_indices:
                arc = network.arcs[arc_idx]
                cust_id = arc.get_attribute('customer_id', None)
                if cust_id is not None:
                    route.append(cust_id)

            if not route:
                continue

            # Check if route satisfies RF decisions
            if not _route_satisfies_rf_decisions(route, rf_decisions):
                continue

            # Add to global pool
            if add_route_fn(route):
                # New route - add to master
                cost = _route_cost_vrptw(instance, route)
                new_col = Column(
                    arc_indices=col.arc_indices,
                    cost=cost,
                    covered_items=frozenset(route),
                    column_id=next_col_id,
                    attributes={'route': route},
                )
                master.add_column(new_col)
                route_to_col_id[tuple(route)] = next_col_id
                valid_routes.append(route)
                next_col_id += 1
                new_cols_added += 1

        # Check convergence
        if new_cols_added == 0:
            break

    # Final LP solve
    lp_sol = master.solve_lp()
    if lp_sol.status.name != 'OPTIMAL':
        return None

    lp_value = lp_sol.objective_value

    # Extract route values (only for non-artificial routes)
    route_values = []
    final_valid_routes = []

    for route in valid_routes:
        col_id = route_to_col_id.get(tuple(route))
        if col_id is not None and col_id in lp_sol.column_values:
            val = lp_sol.column_values[col_id]
            if val > 1e-9:
                route_values.append(val)
                final_valid_routes.append(route)

    if not final_valid_routes:
        return None

    return (lp_value, final_valid_routes, route_values)


def _route_satisfies_rf_decisions(
    route: list[int],
    decisions: list[RyanFosterDecision]
) -> bool:
    """Check if a route satisfies all Ryan-Foster decisions."""
    route_set = set(route)

    for decision in decisions:
        has_i = decision.item_i in route_set
        has_j = decision.item_j in route_set

        if decision.same_column:
            # Must have both or neither
            if has_i != has_j:
                return False
        else:
            # Must not have both
            if has_i and has_j:
                return False

    return True


def _find_ryan_foster_pair(
    routes: list[list[int]],
    route_values: list[float],
    existing_decisions: list[RyanFosterDecision],
) -> Optional[tuple[int, int, float]]:
    """
    Find the best item pair for Ryan-Foster branching.

    Returns:
        (item_i, item_j, together_value) or None if no valid pair
    """
    # Compute pair overlap values
    pair_together: dict[tuple[int, int], float] = defaultdict(float)
    all_items: set[int] = set()

    for route, val in zip(routes, route_values):
        if val < 1e-9:
            continue

        all_items.update(route)

        # Items in this route are "together"
        for i in range(len(route)):
            for j in range(i + 1, len(route)):
                pair = (min(route[i], route[j]), max(route[i], route[j]))
                pair_together[pair] += val

    # Find pairs that are already constrained
    constrained_pairs: set[tuple[int, int]] = set()
    for decision in existing_decisions:
        pair = (min(decision.item_i, decision.item_j),
                max(decision.item_i, decision.item_j))
        constrained_pairs.add(pair)

    # Find best fractional pair
    best_pair = None
    best_score = -1.0

    for pair, together in pair_together.items():
        if pair in constrained_pairs:
            continue

        # Skip if not fractional
        if together < 0.01 or together > 0.99:
            continue

        # Score: prefer balanced splits (together close to 0.5)
        score = 1.0 - abs(together - 0.5) * 2

        if score > best_score:
            best_score = score
            best_pair = (pair[0], pair[1], together)

    return best_pair
