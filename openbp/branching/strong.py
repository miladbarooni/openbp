"""
Strong branching for variable selection.

Strong branching evaluates the LP bound improvement for each
branching candidate by actually solving the LP relaxations.
This provides better variable selection at the cost of more
LP solves per node.
"""

from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass

from openbp.branching.base import BranchingStrategy, BranchingCandidate

try:
    from openbp._core import BranchingDecision
except ImportError:
    from openbp.core.node import BranchingDecision


@dataclass
class StrongBranchingConfig:
    """Configuration for strong branching."""
    # Maximum number of candidates to evaluate with strong branching
    max_candidates: int = 5
    # Maximum LP iterations per candidate (0 = full solve)
    max_lp_iterations: int = 100
    # Score weight: score = alpha * left_bound + (1-alpha) * right_bound
    alpha: float = 0.5
    # Whether to use reliability branching (limit strong branching)
    use_reliability: bool = True
    # Minimum number of strong branching evaluations before using pseudo-costs
    reliability_threshold: int = 8


class StrongBranching(BranchingStrategy):
    """
    Strong branching with LP evaluation.

    Instead of using heuristic scores, strong branching:
    1. Takes the top candidates from a base strategy
    2. For each candidate, solves the LP with each branching constraint
    3. Scores candidates by the improvement in LP bound

    This is expensive but provides much better node selection,
    often reducing the total number of nodes explored.

    Reliability Branching:
    --------------------
    After evaluating a variable enough times, we can use pseudo-costs
    (average improvement per unit fractionality) instead of re-solving.
    This reduces the computational cost while maintaining quality.

    Usage:
        # Wrap another strategy with strong branching
        base = VariableBranching()
        strong = StrongBranching(base, lp_solver=my_solver)
    """

    def __init__(
        self,
        base_strategy: BranchingStrategy,
        lp_solver: Optional[Callable[[List[Any]], float]] = None,
        max_candidates: int = 5,
        max_lp_iterations: int = 100,
        alpha: float = 0.5,
        use_reliability: bool = True,
        reliability_threshold: int = 8,
    ):
        """
        Initialize strong branching.

        Args:
            base_strategy: Strategy to get initial candidates
            lp_solver: Function to solve LP with branching constraints
                      Signature: solve(constraints) -> bound
            max_candidates: Maximum candidates to evaluate
            max_lp_iterations: LP iteration limit per evaluation
            alpha: Weight for combining left/right bounds
            use_reliability: Whether to use pseudo-costs
            reliability_threshold: Evaluations before using pseudo-costs
        """
        super().__init__("StrongBranching")
        self.base_strategy = base_strategy
        self.lp_solver = lp_solver
        self.config = StrongBranchingConfig(
            max_candidates=max_candidates,
            max_lp_iterations=max_lp_iterations,
            alpha=alpha,
            use_reliability=use_reliability,
            reliability_threshold=reliability_threshold,
        )

        # Pseudo-cost tracking for reliability branching
        # Maps variable index -> (sum_improvement, count)
        self._pseudo_costs_up: Dict[int, tuple] = {}
        self._pseudo_costs_down: Dict[int, tuple] = {}

    def select_branching_candidates(
        self,
        node,  # BPNode
        columns,  # List[Column]
        column_values: List[float],
        duals: Dict[int, float],
    ) -> List[BranchingCandidate]:
        """
        Select candidates using strong branching.

        Args:
            node: Current B&P node
            columns: Columns in the LP
            column_values: LP solution values
            duals: Dual values

        Returns:
            Candidates sorted by strong branching score
        """
        # Get base candidates
        base_candidates = self.base_strategy.select_branching_candidates(
            node, columns, column_values, duals
        )

        if not base_candidates:
            return []

        # Limit candidates for strong branching
        candidates_to_eval = base_candidates[: self.config.max_candidates]
        current_bound = node.lower_bound()

        evaluated = []
        for candidate in candidates_to_eval:
            # Check if we can use pseudo-costs instead
            var_idx = candidate.metadata.get("variable_index", -1)

            if self.config.use_reliability and var_idx >= 0:
                if self._can_use_pseudo_cost(var_idx):
                    # Estimate using pseudo-costs
                    frac = candidate.metadata.get("fractionality", 0.5)
                    score = self._estimate_with_pseudo_cost(var_idx, frac)
                    evaluated.append(BranchingCandidate(
                        score=score,
                        decisions=candidate.decisions,
                        description=candidate.description + " [pseudo-cost]",
                        metadata=candidate.metadata,
                    ))
                    continue

            # Strong branching: evaluate LP bounds
            if self.lp_solver is not None:
                left_bound, right_bound = self._evaluate_candidate(
                    candidate, current_bound
                )

                # Compute score (product score works well in practice)
                left_gain = max(0, left_bound - current_bound)
                right_gain = max(0, right_bound - current_bound)

                # Product score: rewards balanced improvement
                score = (left_gain + 1e-6) * (right_gain + 1e-6)

                # Update pseudo-costs
                if var_idx >= 0:
                    frac = candidate.metadata.get("fractionality", 0.5)
                    self._update_pseudo_cost(var_idx, frac, left_gain, right_gain)

                evaluated.append(BranchingCandidate(
                    score=score,
                    decisions=candidate.decisions,
                    description=candidate.description + f" [strong: {left_gain:.2f}/{right_gain:.2f}]",
                    metadata={
                        **candidate.metadata,
                        "left_bound": left_bound,
                        "right_bound": right_bound,
                        "left_gain": left_gain,
                        "right_gain": right_gain,
                    },
                ))
            else:
                # No LP solver - just use base score
                evaluated.append(candidate)

        # Sort by strong branching score
        evaluated.sort(key=lambda c: c.score, reverse=True)
        return evaluated

    def _evaluate_candidate(
        self,
        candidate: BranchingCandidate,
        current_bound: float,
    ) -> tuple:
        """
        Evaluate LP bounds for a branching candidate.

        Returns:
            Tuple of (left_bound, right_bound)
        """
        if len(candidate.decisions) != 2:
            return (current_bound, current_bound)

        # Solve LP with left decision
        left_bound = self.lp_solver([candidate.decisions[0]])

        # Solve LP with right decision
        right_bound = self.lp_solver([candidate.decisions[1]])

        return (left_bound, right_bound)

    def _can_use_pseudo_cost(self, var_idx: int) -> bool:
        """Check if we have enough data for pseudo-costs."""
        up_data = self._pseudo_costs_up.get(var_idx, (0, 0))
        down_data = self._pseudo_costs_down.get(var_idx, (0, 0))

        return (
            up_data[1] >= self.config.reliability_threshold and
            down_data[1] >= self.config.reliability_threshold
        )

    def _estimate_with_pseudo_cost(self, var_idx: int, frac: float) -> float:
        """Estimate branching score using pseudo-costs."""
        up_sum, up_count = self._pseudo_costs_up.get(var_idx, (0, 1))
        down_sum, down_count = self._pseudo_costs_down.get(var_idx, (0, 1))

        # Average improvement per unit fractionality
        up_cost = up_sum / max(1, up_count)
        down_cost = down_sum / max(1, down_count)

        # Estimate gains
        up_gain = up_cost * (1 - frac)
        down_gain = down_cost * frac

        # Product score
        return (up_gain + 1e-6) * (down_gain + 1e-6)

    def _update_pseudo_cost(
        self,
        var_idx: int,
        frac: float,
        down_gain: float,
        up_gain: float,
    ) -> None:
        """Update pseudo-cost estimates."""
        # Down branch: x <= floor(val), gain per unit = down_gain / frac
        if frac > 1e-6:
            down_sum, down_count = self._pseudo_costs_down.get(var_idx, (0, 0))
            self._pseudo_costs_down[var_idx] = (
                down_sum + down_gain / frac,
                down_count + 1,
            )

        # Up branch: x >= ceil(val), gain per unit = up_gain / (1 - frac)
        if (1 - frac) > 1e-6:
            up_sum, up_count = self._pseudo_costs_up.get(var_idx, (0, 0))
            self._pseudo_costs_up[var_idx] = (
                up_sum + up_gain / (1 - frac),
                up_count + 1,
            )

    def filter_columns(
        self,
        columns,  # List[Column]
        decisions,  # List[BranchingDecision]
    ):
        """Delegate to base strategy."""
        return self.base_strategy.filter_columns(columns, decisions)

    def is_applicable(
        self,
        node,  # BPNode
        columns,  # List[Column]
        column_values: List[float],
    ) -> bool:
        """Delegate to base strategy."""
        return self.base_strategy.is_applicable(node, columns, column_values)

    def set_lp_solver(self, solver: Callable[[List[Any]], float]) -> None:
        """Set the LP solver function."""
        self.lp_solver = solver
