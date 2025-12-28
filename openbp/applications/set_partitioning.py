"""
Branch-and-Price solver for generic Set Partitioning/Covering problems.

Set Partitioning: Select a minimum cost subset of columns such that
each row is covered exactly once.

Set Covering: Select a minimum cost subset of columns such that
each row is covered at least once.

This solver works with any problem built using OpenCG's Problem class.
"""

from dataclasses import dataclass
from typing import Optional, Any

from openbp.solver import BranchAndPrice, BPConfig, BPSolution
from openbp.branching import RyanFosterBranching, VariableBranching
from openbp.branching.base import CompositeBranchingStrategy
from openbp.selection import BestFirstSelection, HybridSelection


@dataclass
class SetPartitioningConfig:
    """Configuration for set partitioning B&P."""
    # Termination
    max_time: float = 3600.0
    max_nodes: int = 0
    gap_tolerance: float = 1e-6

    # Node selection
    node_selection: str = "hybrid"  # hybrid works well for set partitioning

    # Branching
    use_ryan_foster: bool = True  # Use Ryan-Foster when applicable
    fallback_to_variable: bool = True  # Fall back to variable branching

    # Logging
    verbose: bool = True


def solve_set_partitioning(
    problem: Any,  # opencg.Problem
    config: Optional[SetPartitioningConfig] = None,
) -> BPSolution:
    """
    Solve a set partitioning/covering problem using branch-and-price.

    Uses Ryan-Foster branching when applicable (items appearing
    together/separately in columns), with variable branching as fallback.

    Args:
        problem: An OpenCG Problem instance
        config: Solver configuration

    Returns:
        BPSolution with optimal integer solution

    Example:
        from opencg import Problem
        from openbp.applications import solve_set_partitioning

        # Load or build problem
        problem = Problem.from_file("instance.txt")

        solution = solve_set_partitioning(problem)
        print(f"Optimal: {solution.objective}")
    """
    config = config or SetPartitioningConfig()

    # Build branching strategy
    if config.use_ryan_foster:
        strategies = [RyanFosterBranching()]
        if config.fallback_to_variable:
            strategies.append(VariableBranching())
        branching = CompositeBranchingStrategy(strategies)
    else:
        branching = VariableBranching()

    # Build node selection
    if config.node_selection == "hybrid":
        selection = HybridSelection()
    else:
        selection = BestFirstSelection()

    # Create B&P config
    bp_config = BPConfig(
        max_time=config.max_time,
        max_nodes=config.max_nodes,
        gap_tolerance=config.gap_tolerance,
        node_selection=config.node_selection,
        verbose=config.verbose,
    )

    # Create and run solver
    solver = BranchAndPrice(
        problem,
        branching_strategy=branching,
        node_selection=selection,
        config=bp_config,
    )

    return solver.solve()
