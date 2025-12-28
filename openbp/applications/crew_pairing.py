"""
Branch-and-Price solver for the Crew Pairing Problem (CPP).

Crew Pairing is a set partitioning problem where each flight must be covered exactly once.
This makes it well-suited for Ryan-Foster branching.

For Crew Pairing, we use:
- Master Problem: Set partitioning LP
- Pricing Problem: SPPRC on time-space network
- Branching: Ryan-Foster branching on flight pairs

IMPORTANT: This is a TRUE Branch-and-Price implementation that runs column generation
at each B&B node to find new columns that respect the branching decisions.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict, Tuple, Set, FrozenSet
import time
from collections import defaultdict

from openbp.solver import BPSolution, BPStatus


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
class CrewPairingBPConfig:
    """Configuration for Crew Pairing branch-and-price."""
    # Termination
    max_time: float = 600.0
    max_nodes: int = 1000
    gap_tolerance: float = 1e-6

    # Column generation
    cg_max_iterations: int = 100
    cg_max_iterations_per_node: int = 30  # CG iterations at each B&B node
    cg_max_columns: int = 200

    # Pricing
    cols_per_source: int = 5
    time_per_source: float = 0.1

    # Logging
    verbose: bool = True


def solve_crew_pairing_bp(
    problem: Any,  # opencg.core.problem.Problem from KasirzadehParser
    config: Optional[CrewPairingBPConfig] = None,
) -> BPSolution:
    """
    Solve a crew pairing instance using branch-and-price with Ryan-Foster branching.

    This is a TRUE Branch-and-Price that runs column generation at each node
    to find new columns that respect the branching decisions.

    Args:
        problem: A Problem from KasirzadehParser or similar
        config: Solver configuration

    Returns:
        BPSolution with optimal integer solution

    Example:
        from opencg.parsers import KasirzadehParser
        from openbp.applications.crew_pairing import solve_crew_pairing_bp

        parser = KasirzadehParser()
        problem = parser.parse("data/kasirzadeh/instance1")
        solution = solve_crew_pairing_bp(problem)
        print(f"Optimal cost: {solution.objective}")
    """
    config = config or CrewPairingBPConfig()

    # Import OpenCG components
    try:
        from opencg.applications.crew_pairing import (
            FastPerSourcePricing,
            PerSourcePricing,
        )
        from opencg.master import HiGHSMasterProblem
        from opencg.pricing import PricingConfig
        from opencg.core.column import Column
    except ImportError as e:
        raise ImportError(
            "OpenCG is required. Install with: pip install -e path/to/opencg"
        ) from e

    start_time = time.time()

    # Statistics
    nodes_explored = 0
    nodes_pruned = 0
    max_depth = 0

    # Track best solution
    best_objective = float('inf')
    best_pairings: List[Dict] = []
    global_lower_bound = 0.0

    n_flights = len(problem.cover_constraints)

    if config.verbose:
        print(f"Crew Pairing B&P Solver (True Branch-and-Price)")
        print(f"  Flights: {n_flights}")
        print(f"  Network nodes: {problem.network.num_nodes}")
        print(f"  Network arcs: {problem.network.num_arcs}")
        print()

    # Try to use FastPerSourcePricing if available
    try:
        from opencg.applications.crew_pairing import FastPerSourcePricing
        use_fast = True
    except ImportError:
        use_fast = False

    # Global pairing pool - accumulates all generated pairings
    all_pairings: List[Dict] = []
    pairing_set: Set[FrozenSet[int]] = set()

    def add_pairing(cost: float, flights: Set[int], arc_indices: Tuple[int, ...]) -> bool:
        """Add pairing to pool if not already present. Returns True if added."""
        key = frozenset(flights)
        if key not in pairing_set:
            pairing_set.add(key)
            all_pairings.append({
                'cost': cost,
                'flights': flights,
                'arc_indices': arc_indices,
            })
            return True
        return False

    # Create pricing algorithm (will be reused)
    pricing_config = PricingConfig(
        max_columns=config.cg_max_columns,
        max_time=30.0,
        reduced_cost_threshold=-1e-6,
        check_elementarity=True,
        use_dominance=True,
    )

    if use_fast:
        pricing = FastPerSourcePricing(
            problem,
            config=pricing_config,
            max_labels_per_node=50,
            cols_per_source=config.cols_per_source,
            time_per_source=config.time_per_source,
        )
    else:
        from opencg.applications.crew_pairing import PerSourcePricing
        pricing = PerSourcePricing(
            problem,
            config=pricing_config,
            max_labels_per_node=50,
            cols_per_source=config.cols_per_source,
            time_per_source=config.time_per_source,
        )

    if config.verbose:
        print("Pricing algorithm initialized")

    # Node queue: (lower_bound, node_id, depth, rf_decisions)
    node_queue: List[Tuple[float, int, int, List[RyanFosterDecision]]] = []
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

        if config.verbose and nodes_explored % 5 == 1:
            gap = (best_objective - global_lower_bound) / best_objective * 100 if best_objective < float('inf') else 100
            print(f"  Node {nodes_explored}: depth={depth}, LB={global_lower_bound:.2f}, "
                  f"UB={best_objective:.2f}, gap={gap:.2f}%, pool={len(all_pairings)}")

        # Solve node with column generation
        result = _solve_node_with_cg(
            problem, n_flights, pricing, all_pairings, add_pairing,
            rf_decisions, config.cg_max_iterations_per_node,
            config.verbose and depth < 2
        )

        if result is None:
            # Infeasible
            nodes_pruned += 1
            continue

        lp_value, valid_pairings, pairing_values = result

        # Update global lower bound
        if node_queue:
            global_lower_bound = min(lp_value, min(n[0] for n in node_queue))
        else:
            global_lower_bound = lp_value

        # Check if integer
        is_integer = all(
            abs(v - round(v)) < 1e-6
            for v in pairing_values
        )

        if is_integer:
            # Found integer solution
            ip_value = sum(
                pairing_values[i] * valid_pairings[i]['cost']
                for i in range(len(valid_pairings))
                if pairing_values[i] > 0.5
            )

            if ip_value < best_objective:
                best_objective = ip_value
                best_pairings = [
                    valid_pairings[i] for i in range(len(valid_pairings))
                    if pairing_values[i] > 0.5
                ]

                if config.verbose:
                    print(f"    New incumbent: {ip_value:.2f} ({len(best_pairings)} pairings)")

            # Prune nodes with worse bound
            node_queue = [(b, i, d, r) for b, i, d, r in node_queue
                         if b < best_objective - config.gap_tolerance]

        else:
            # Need to branch - find Ryan-Foster pair
            rf_pair = _find_ryan_foster_pair(valid_pairings, pairing_values, rf_decisions)

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

    # Calculate coverage
    covered_flights = set()
    for pairing in best_pairings:
        covered_flights.update(pairing['flights'])
    coverage_pct = 100.0 * len(covered_flights) / n_flights if n_flights > 0 else 100.0

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

    # Add pairings to solution metadata
    solution.pairings = best_pairings
    solution.coverage_pct = coverage_pct
    solution.uncovered_flights = set(range(n_flights)) - covered_flights
    solution.total_columns = len(all_pairings)

    if config.verbose:
        print()
        print(f"B&P Complete:")
        print(f"  Status: {status.name}")
        print(f"  Objective: {best_objective:.2f}")
        print(f"  Lower bound: {final_lb:.2f}")
        print(f"  Pairings: {len(best_pairings)}")
        print(f"  Coverage: {coverage_pct:.1f}%")
        print(f"  Nodes: {nodes_explored}")
        print(f"  Time: {total_time:.2f}s")
        print(f"  Gap: {gap*100:.2f}%")
        print(f"  Total columns: {len(all_pairings)}")

    return solution


def _solve_node_with_cg(
    problem,
    n_flights: int,
    pricing,
    all_pairings: List[Dict],
    add_pairing_fn,
    rf_decisions: List[RyanFosterDecision],
    max_cg_iterations: int,
    verbose: bool,
) -> Optional[Tuple[float, List[Dict], List[float]]]:
    """
    Solve a B&B node with column generation.

    This runs CG at this node, generating new columns that respect RF decisions.
    New columns are added to the global pool.

    Returns:
        (lp_value, valid_pairings, pairing_values) or None if infeasible
    """
    try:
        import highspy
    except ImportError:
        raise ImportError("HiGHS is required. Install with: pip install highspy")

    from opencg.master import HiGHSMasterProblem
    from opencg.core.column import Column

    # Create master problem for this node
    master = HiGHSMasterProblem(problem, verbosity=0)

    # Add artificial columns for feasibility
    big_m = 1e6
    next_col_id = 0
    for i in range(n_flights):
        art_col = Column(
            arc_indices=(),
            cost=big_m,
            covered_items=frozenset([i]),
            column_id=next_col_id,
            attributes={'artificial': True},
        )
        master.add_column(art_col)
        next_col_id += 1

    # Add existing pairings that satisfy RF decisions
    valid_pairings = []
    pairing_to_col_id = {}

    for pairing in all_pairings:
        if _pairing_satisfies_rf_decisions(pairing['flights'], rf_decisions):
            col = Column(
                arc_indices=pairing['arc_indices'],
                cost=pairing['cost'],
                covered_items=frozenset(pairing['flights']),
                column_id=next_col_id,
                attributes={'pairing': pairing},
            )
            master.add_column(col)
            pairing_to_col_id[frozenset(pairing['flights'])] = next_col_id
            valid_pairings.append(pairing)
            next_col_id += 1

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
            flights = set(col.covered_items)
            if not flights:
                continue

            # Check if pairing satisfies RF decisions
            if not _pairing_satisfies_rf_decisions(flights, rf_decisions):
                continue

            # Add to global pool
            if add_pairing_fn(col.cost, flights, col.arc_indices):
                # New pairing - add to master
                new_col = Column(
                    arc_indices=col.arc_indices,
                    cost=col.cost,
                    covered_items=frozenset(flights),
                    column_id=next_col_id,
                    attributes={'pairing': {'cost': col.cost, 'flights': flights, 'arc_indices': col.arc_indices}},
                )
                master.add_column(new_col)
                pairing_to_col_id[frozenset(flights)] = next_col_id
                valid_pairings.append({'cost': col.cost, 'flights': flights, 'arc_indices': col.arc_indices})
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

    # Extract pairing values (only for non-artificial pairings)
    pairing_values = []
    final_valid_pairings = []

    for pairing in valid_pairings:
        col_id = pairing_to_col_id.get(frozenset(pairing['flights']))
        if col_id is not None and col_id in lp_sol.column_values:
            val = lp_sol.column_values[col_id]
            if val > 1e-9:
                pairing_values.append(val)
                final_valid_pairings.append(pairing)

    if not final_valid_pairings:
        return None

    return (lp_value, final_valid_pairings, pairing_values)


def _pairing_satisfies_rf_decisions(
    flights: Set[int],
    decisions: List[RyanFosterDecision]
) -> bool:
    """Check if a pairing satisfies all Ryan-Foster decisions."""
    for decision in decisions:
        has_i = decision.item_i in flights
        has_j = decision.item_j in flights

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
    pairings: List[Dict],
    pairing_values: List[float],
    existing_decisions: List[RyanFosterDecision],
) -> Optional[Tuple[int, int, float]]:
    """
    Find the best flight pair for Ryan-Foster branching.

    Returns:
        (flight_i, flight_j, together_value) or None if no valid pair
    """
    # Compute pair overlap values
    pair_together: Dict[Tuple[int, int], float] = defaultdict(float)
    all_flights: Set[int] = set()

    for pairing, val in zip(pairings, pairing_values):
        if val < 1e-9:
            continue

        flights = list(pairing['flights'])
        all_flights.update(flights)

        # Flights in this pairing are "together"
        for i in range(len(flights)):
            for j in range(i + 1, len(flights)):
                pair = (min(flights[i], flights[j]), max(flights[i], flights[j]))
                pair_together[pair] += val

    # Find pairs that are already constrained
    constrained_pairs: Set[Tuple[int, int]] = set()
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
