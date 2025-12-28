"""
Variable branching strategy.

Standard branching on fractional LP variable values.
Creates two children: x[j] <= floor(val) and x[j] >= ceil(val).
"""

from dataclasses import dataclass

from openbp.branching.base import BranchingCandidate, BranchingStrategy

# Import from C++ core if available, otherwise from pure Python
try:
    from openbp._core import BranchingDecision, BranchType
except ImportError:
    from openbp.core.node import BranchingDecision


@dataclass
class VariableBranchingConfig:
    """Configuration for variable branching."""
    # Minimum fractionality to consider for branching
    min_fractionality: float = 0.01
    # Prefer variables with fractionality close to 0.5
    prefer_balanced: bool = True
    # Maximum number of candidates to return
    max_candidates: int = 10


class VariableBranching(BranchingStrategy):
    """
    Standard variable branching on fractional LP values.

    For a fractional variable x[j] = v, creates two children:
    - Left: x[j] <= floor(v)
    - Right: x[j] >= ceil(v)

    Variable selection prefers:
    - Fractionality close to 0.5 (most balanced split)
    - Variables with high dual value impact

    This is a fallback strategy when problem-specific branching
    (e.g., Ryan-Foster) is not applicable.
    """

    def __init__(
        self,
        min_fractionality: float = 0.01,
        prefer_balanced: bool = True,
        max_candidates: int = 10,
    ):
        """
        Initialize variable branching.

        Args:
            min_fractionality: Minimum fractionality threshold
            prefer_balanced: Whether to prefer 0.5 fractionality
            max_candidates: Maximum candidates to return
        """
        super().__init__("VariableBranching")
        self.config = VariableBranchingConfig(
            min_fractionality=min_fractionality,
            prefer_balanced=prefer_balanced,
            max_candidates=max_candidates,
        )

    def select_branching_candidates(
        self,
        node,  # BPNode
        columns,  # List[Column]
        column_values: list[float],
        duals: dict[int, float],
    ) -> list[BranchingCandidate]:
        """
        Find fractional variables and create branching candidates.

        Args:
            node: Current B&P node
            columns: Columns in the LP
            column_values: LP solution values
            duals: Dual values (unused here but available)

        Returns:
            List of branching candidates sorted by score
        """
        candidates = []

        for j, val in enumerate(column_values):
            # Check fractionality
            frac = val - int(val)
            if frac < self.config.min_fractionality or frac > (1 - self.config.min_fractionality):
                continue

            # Score based on fractionality
            if self.config.prefer_balanced:
                # Score is highest when frac = 0.5
                score = 1.0 - abs(frac - 0.5) * 2
            else:
                # Just use fractionality as score
                score = min(frac, 1 - frac)

            # Create branching decisions
            floor_val = int(val)
            ceil_val = floor_val + 1

            # Left child: x[j] <= floor(val)
            left_decision = BranchingDecision.variable_branch(j, floor_val, True)

            # Right child: x[j] >= ceil(val)
            right_decision = BranchingDecision.variable_branch(j, ceil_val, False)

            candidate = BranchingCandidate(
                score=score,
                decisions=[left_decision, right_decision],
                description=f"x[{j}] = {val:.4f} -> (<= {floor_val}, >= {ceil_val})",
                metadata={"variable_index": j, "value": val, "fractionality": frac},
            )
            candidates.append(candidate)

        # Sort by score (descending) and limit
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[: self.config.max_candidates]

    def filter_columns(
        self,
        columns,  # List[Column]
        decisions,  # List[BranchingDecision]
    ):
        """
        Filter columns based on variable bound decisions.

        Note: For variable branching on column values, filtering
        is handled by the master problem adding bound constraints.
        This method is a no-op for variable branching.
        """
        return columns

    def configure(self, **kwargs) -> None:
        """Update configuration."""
        if "min_fractionality" in kwargs:
            self.config.min_fractionality = kwargs["min_fractionality"]
        if "prefer_balanced" in kwargs:
            self.config.prefer_balanced = kwargs["prefer_balanced"]
        if "max_candidates" in kwargs:
            self.config.max_candidates = kwargs["max_candidates"]
