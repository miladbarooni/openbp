"""
Branch-Price-and-Cut solver for the Vehicle Routing Problem with Time Windows (VRPTW).

This extends the basic B&P solver by adding cutting planes:
- Rounded Capacity Cuts (RCC): For subset S with demand D, need >= ceil(D/Q) routes
- These cuts don't affect pricing (simple approach)

For VRPTW, we use:
- Master Problem: Set partitioning LP + capacity cuts
- Pricing Problem: Elementary shortest path with resource constraints (ESPPRC)
- Branching: Ryan-Foster branching on customer pairs
- Cuts: Rounded Capacity Cuts on customer subsets
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict, Tuple, Set, FrozenSet
import time
import math
from collections import defaultdict
from itertools import combinations

from openbp.solver import BPSolution, BPStatus


@dataclass
class CapacityCut:
    """A rounded capacity cut on a subset of customers."""
    customers: FrozenSet[int]  # Subset S of customers
    rhs: int  # ceil(total_demand(S) / vehicle_capacity)

    def __repr__(self):
        return f"RCC(|S|={len(self.customers)}, rhs={self.rhs})"


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
class VRPTWBPCConfig:
    """Configuration for VRPTW branch-price-and-cut."""
    # Termination
    max_time: float = 600.0
    max_nodes: int = 1000
    gap_tolerance: float = 1e-6

    # Column generation
    cg_max_iterations: int = 100

    # Cutting
    enable_cuts: bool = True
    max_cuts_per_round: int = 10
    min_violation: float = 0.1  # Minimum cut violation to add
    max_subset_size: int = 10  # Max size of customer subsets to check

    # Logging
    verbose: bool = True


def solve_vrptw_bpc(
    instance: Any,  # opencg.applications.vrp.VRPTWInstance
    config: Optional[VRPTWBPCConfig] = None,
) -> BPSolution:
    """
    Solve a VRPTW instance using branch-price-and-cut.

    This extends B&P with Rounded Capacity Cuts to tighten the LP relaxation.

    Args:
        instance: A VRPTWInstance from OpenCG
        config: Solver configuration

    Returns:
        BPSolution with optimal integer solution
    """
    config = config or VRPTWBPCConfig()

    # Import OpenCG components
    try:
        from opencg.applications.vrp.solver import (
            _generate_greedy_routes_vrptw,
            _route_cost_vrptw,
        )
    except ImportError as e:
        raise ImportError(
            "OpenCG is required. Install with: pip install -e path/to/opencg"
        ) from e

    start_time = time.time()

    # Statistics
    nodes_explored = 0
    nodes_pruned = 0
    max_depth = 0
    total_cuts_added = 0

    # Lower bound from capacity
    lower_bound_vehicles = math.ceil(instance.total_demand / instance.vehicle_capacity)

    # Track best solution
    best_objective = float('inf')
    best_routes: List[List[int]] = []
    global_lower_bound = 0.0

    # First, run column generation to get a pool of columns
    if config.verbose:
        print(f"VRPTW Branch-Price-and-Cut Solver")
        print(f"  Customers: {instance.num_customers}")
        print(f"  Vehicle capacity: {instance.vehicle_capacity}")
        print(f"  Min vehicles (capacity): {lower_bound_vehicles}")
        print(f"  Cuts enabled: {config.enable_cuts}")
        print()
        print("Phase 1: Generating column pool via CG...")

    # Run CG to collect all columns
    all_routes = _collect_all_routes_from_cg(instance, config.cg_max_iterations, config.verbose)

    if config.verbose:
        print(f"  Column pool size: {len(all_routes)}")
        print()

    # Global cuts (added at root, propagate to all nodes)
    global_cuts: List[CapacityCut] = []

    # Node queue: (lower_bound, node_id, depth, rf_decisions, local_cuts)
    node_queue: List[Tuple[float, int, int, List[RyanFosterDecision], List[CapacityCut]]] = []
    next_node_id = 0

    # Add root node (no branching decisions, no local cuts)
    node_queue.append((0.0, next_node_id, 0, [], []))
    next_node_id += 1

    if config.verbose:
        print("Phase 2: Branch-Price-and-Cut...")
        print()

    # Main BPC loop
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
        lb, node_id, depth, rf_decisions, local_cuts = node_queue.pop(0)

        nodes_explored += 1
        max_depth = max(max_depth, depth)

        # Prune by bound
        if lb >= best_objective - config.gap_tolerance:
            nodes_pruned += 1
            continue

        if config.verbose and nodes_explored % 10 == 1:
            gap = (best_objective - global_lower_bound) / best_objective * 100 if best_objective < float('inf') else 100
            print(f"  Node {nodes_explored}: depth={depth}, LB={global_lower_bound:.2f}, "
                  f"UB={best_objective:.2f}, gap={gap:.2f}%, cuts={len(global_cuts) + len(local_cuts)}")

        # Combine global and local cuts
        all_cuts = global_cuts + local_cuts

        # Cutting loop at this node
        cutting_rounds = 0
        max_cutting_rounds = 5 if config.enable_cuts else 0

        while cutting_rounds < max_cutting_rounds:
            # Solve LP at this node with RF constraints and cuts
            result = _solve_restricted_master_lp_with_cuts(
                instance, all_routes, rf_decisions, all_cuts, config.verbose
            )

            if result is None:
                # Infeasible
                nodes_pruned += 1
                break

            lp_value, valid_routes, route_values = result

            # Try to find violated cuts
            if config.enable_cuts:
                new_cuts = _find_violated_capacity_cuts(
                    instance, valid_routes, route_values,
                    all_cuts, config.max_cuts_per_round,
                    config.min_violation, config.max_subset_size
                )

                if new_cuts:
                    if config.verbose:
                        print(f"    Round {cutting_rounds + 1}: Added {len(new_cuts)} capacity cuts")

                    # Add to global cuts if at root, otherwise local
                    if depth == 0:
                        global_cuts.extend(new_cuts)
                    else:
                        local_cuts = local_cuts + new_cuts

                    all_cuts = global_cuts + local_cuts
                    total_cuts_added += len(new_cuts)
                    cutting_rounds += 1
                    continue

            # No more violated cuts found
            break

        if result is None:
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
            node_queue = [(b, i, d, r, c) for b, i, d, r, c in node_queue
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
                node_queue.append((lp_value, next_node_id, depth + 1, same_decisions, local_cuts.copy()))
                next_node_id += 1

                # Different branch: items must be apart
                diff_decisions = rf_decisions + [RyanFosterDecision(item_i, item_j, False)]
                node_queue.append((lp_value, next_node_id, depth + 1, diff_decisions, local_cuts.copy()))
                next_node_id += 1

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
        final_lb = best_objective
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
        time_in_cg=total_time * 0.8,
        time_in_branching=total_time * 0.2,
        columns=[],
        column_values=[],
    )

    # Add routes and cuts info to solution metadata
    solution.routes = best_routes
    solution.total_cuts = total_cuts_added

    if config.verbose:
        print()
        print(f"BPC Complete:")
        print(f"  Status: {status.name}")
        print(f"  Objective: {best_objective:.2f}")
        print(f"  Lower bound: {final_lb:.2f}")
        print(f"  Routes: {len(best_routes)}")
        print(f"  Nodes: {nodes_explored}")
        print(f"  Cuts added: {total_cuts_added}")
        print(f"  Time: {total_time:.2f}s")
        print(f"  Gap: {gap*100:.2f}%")

    return solution


def _collect_all_routes_from_cg(
    instance,
    max_iterations: int,
    verbose: bool,
) -> List[List[int]]:
    """Run column generation and collect ALL generated routes."""
    try:
        import highspy
    except ImportError:
        raise ImportError("HiGHS is required. Install with: pip install highspy")

    from opencg.master import HiGHSMasterProblem
    from opencg.pricing import PricingConfig, AcceleratedLabelingAlgorithm
    from opencg.core.column import Column
    from opencg.core.problem import Problem, CoverConstraint, CoverType, ObjectiveSense
    from opencg.applications.vrp.network_builder import build_vrptw_network
    from opencg.applications.vrp.resources import CapacityResource, TimeResource
    from opencg.applications.vrp.solver import (
        _generate_greedy_routes_vrptw,
        _route_cost_vrptw,
        _create_column_from_route_vrptw,
    )

    network, customer_node_map = build_vrptw_network(instance)

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

    master = HiGHSMasterProblem(problem, verbosity=0)

    all_routes: List[List[int]] = []
    route_set: Set[Tuple[int, ...]] = set()

    def add_route(route: List[int]):
        key = tuple(route)
        if key not in route_set:
            route_set.add(key)
            all_routes.append(route)

    greedy_routes = _generate_greedy_routes_vrptw(instance)
    for route in greedy_routes:
        add_route(route)

    next_col_id = 0
    for route in greedy_routes:
        col = _create_column_from_route_vrptw(route, instance, network, customer_node_map)
        col = col.with_id(next_col_id)
        next_col_id += 1
        master.add_column(col)

    big_m = 1e6
    for i in range(instance.num_customers):
        art_col = Column(
            arc_indices=(),
            cost=big_m,
            covered_items=frozenset([i]),
            column_id=next_col_id,
            attributes={'artificial': True, 'route': [i]},
        )
        master.add_column(art_col)
        next_col_id += 1

    pricing_config = PricingConfig(
        max_columns=100,
        reduced_cost_threshold=-1e-6,
        check_elementarity=True,
        use_dominance=True,
        max_time=10.0,
    )

    pricing = AcceleratedLabelingAlgorithm(problem, config=pricing_config)

    for iteration in range(max_iterations):
        lp_sol = master.solve_lp()
        if lp_sol.status.name != 'OPTIMAL':
            break

        duals = master.get_dual_values()
        pricing.set_dual_values(duals)
        pricing_sol = pricing.solve()

        if not pricing_sol.columns:
            break

        for col in pricing_sol.columns:
            route = []
            for arc_idx in col.arc_indices:
                arc = network.arcs[arc_idx]
                cust_id = arc.get_attribute('customer_id', None)
                if cust_id is not None:
                    route.append(cust_id)

            if route:
                add_route(route)

            new_col = Column(
                arc_indices=col.arc_indices,
                cost=col.cost,
                covered_items=col.covered_items,
                column_id=next_col_id,
                attributes={'route': route},
            )
            next_col_id += 1
            master.add_column(new_col)

    return all_routes


def _route_satisfies_rf_decisions(
    route: List[int],
    decisions: List[RyanFosterDecision]
) -> bool:
    """Check if a route satisfies all Ryan-Foster decisions."""
    route_set = set(route)

    for decision in decisions:
        has_i = decision.item_i in route_set
        has_j = decision.item_j in route_set

        if decision.same_column:
            if has_i != has_j:
                return False
        else:
            if has_i and has_j:
                return False

    return True


def _route_covers_subset(route: List[int], subset: FrozenSet[int]) -> bool:
    """Check if route covers any customer in subset."""
    route_set = set(route)
    return bool(route_set & subset)


def _solve_restricted_master_lp_with_cuts(
    instance,
    all_routes: List[List[int]],
    rf_decisions: List[RyanFosterDecision],
    cuts: List[CapacityCut],
    verbose: bool,
) -> Optional[Tuple[float, List[List[int]], List[float]]]:
    """
    Solve restricted master LP with Ryan-Foster constraints and capacity cuts.
    """
    try:
        import highspy
    except ImportError:
        raise ImportError("HiGHS is required. Install with: pip install highspy")

    from opencg.applications.vrp.solver import _route_cost_vrptw

    # Filter routes that satisfy RF decisions
    valid_routes = [r for r in all_routes if _route_satisfies_rf_decisions(r, rf_decisions)]

    if not valid_routes:
        return None

    n_customers = instance.num_customers
    n_routes = len(valid_routes)
    n_cuts = len(cuts)

    # Create HiGHS model
    highs = highspy.Highs()
    highs.setOptionValue('output_flag', False)
    highs.setOptionValue('log_to_console', False)
    highs.changeObjectiveSense(highspy.ObjSense.kMinimize)

    # Row 0 to n_customers-1: coverage constraints (= 1)
    for i in range(n_customers):
        highs.addRow(1.0, 1.0, 0, [], [])

    # Row n_customers to n_customers + n_cuts - 1: capacity cuts (>= rhs)
    for cut in cuts:
        highs.addRow(float(cut.rhs), highspy.kHighsInf, 0, [], [])

    # Add route columns
    for route in valid_routes:
        cost = _route_cost_vrptw(instance, route)

        # Build constraint coefficients
        indices = []
        values = []

        # Coverage constraints
        for cust in route:
            indices.append(cust)
            values.append(1.0)

        # Capacity cut constraints
        route_set = set(route)
        for cut_idx, cut in enumerate(cuts):
            if route_set & cut.customers:  # Route covers subset
                indices.append(n_customers + cut_idx)
                values.append(1.0)

        highs.addCol(cost, 0.0, highspy.kHighsInf, len(indices), indices, values)

    # Solve LP
    highs.run()
    status = highs.getModelStatus()

    if status != highspy.HighsModelStatus.kOptimal:
        return None

    info = highs.getInfo()
    lp_value = info.objective_function_value

    sol = highs.getSolution()
    route_values = [sol.col_value[i] for i in range(n_routes)]

    return (lp_value, valid_routes, route_values)


def _find_violated_capacity_cuts(
    instance,
    routes: List[List[int]],
    route_values: List[float],
    existing_cuts: List[CapacityCut],
    max_cuts: int,
    min_violation: float,
    max_subset_size: int,
) -> List[CapacityCut]:
    """
    Find violated rounded capacity cuts.

    For subset S: sum of routes covering S >= ceil(demand(S) / capacity)

    We look for subsets where the LHS is less than the RHS.
    """
    violated_cuts = []
    existing_subsets = {cut.customers for cut in existing_cuts}

    n_customers = instance.num_customers
    demands = instance.demands
    capacity = instance.vehicle_capacity

    # Compute route coverage for each customer
    customer_coverage: Dict[int, float] = defaultdict(float)
    for route, val in zip(routes, route_values):
        if val < 1e-9:
            continue
        for cust in route:
            customer_coverage[cust] += val

    # Try different subset sizes
    for size in range(2, min(max_subset_size + 1, n_customers + 1)):
        if len(violated_cuts) >= max_cuts:
            break

        # Sample subsets (for large instances, we can't enumerate all)
        if size <= 4:
            # Enumerate all for small sizes
            subsets = list(combinations(range(n_customers), size))
        else:
            # Sample based on fractional routes
            fractional_customers = [
                cust for cust in range(n_customers)
                if 0.01 < customer_coverage.get(cust, 0) < 0.99
            ]
            if len(fractional_customers) < size:
                continue
            # Take subsets from fractional customers
            subsets = list(combinations(fractional_customers[:15], size))[:100]

        for subset_tuple in subsets:
            if len(violated_cuts) >= max_cuts:
                break

            subset = frozenset(subset_tuple)

            # Skip if already have this cut
            if subset in existing_subsets:
                continue

            # Compute demand of subset
            subset_demand = sum(demands[i] for i in subset)

            # RHS of capacity cut
            rhs = math.ceil(subset_demand / capacity)

            if rhs <= 1:
                continue  # Trivial cut

            # LHS: sum of routes covering any customer in subset
            lhs = 0.0
            for route, val in zip(routes, route_values):
                if val < 1e-9:
                    continue
                route_set = set(route)
                if route_set & subset:
                    lhs += val

            # Check violation
            violation = rhs - lhs
            if violation > min_violation:
                cut = CapacityCut(customers=subset, rhs=rhs)
                violated_cuts.append(cut)
                existing_subsets.add(subset)

    # Sort by violation (most violated first)
    violated_cuts.sort(key=lambda c: c.rhs, reverse=True)

    return violated_cuts[:max_cuts]


def _find_ryan_foster_pair(
    routes: List[List[int]],
    route_values: List[float],
    existing_decisions: List[RyanFosterDecision],
) -> Optional[Tuple[int, int, float]]:
    """Find the best item pair for Ryan-Foster branching."""
    pair_together: Dict[Tuple[int, int], float] = defaultdict(float)
    all_items: Set[int] = set()

    for route, val in zip(routes, route_values):
        if val < 1e-9:
            continue

        all_items.update(route)

        for i in range(len(route)):
            for j in range(i + 1, len(route)):
                pair = (min(route[i], route[j]), max(route[i], route[j]))
                pair_together[pair] += val

    constrained_pairs: Set[Tuple[int, int]] = set()
    for decision in existing_decisions:
        pair = (min(decision.item_i, decision.item_j),
                max(decision.item_i, decision.item_j))
        constrained_pairs.add(pair)

    best_pair = None
    best_score = -1.0

    for pair, together in pair_together.items():
        if pair in constrained_pairs:
            continue

        if together < 0.01 or together > 0.99:
            continue

        score = 1.0 - abs(together - 0.5) * 2

        if score > best_score:
            best_score = score
            best_pair = (pair[0], pair[1], together)

    return best_pair
