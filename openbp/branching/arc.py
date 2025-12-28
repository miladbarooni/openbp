"""
Arc branching strategy for routing and scheduling problems.

Arc branching branches on whether a specific arc is used in the solution.
It creates:
- Required branch: The arc must be in the solution
- Forbidden branch: The arc cannot be in the solution

This is commonly used for CVRP, crew scheduling, and other problems
where routes/pairings are represented as paths in a network.
"""

from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict

from openbp.branching.base import BranchingStrategy, BranchingCandidate

try:
    from openbp._core import BranchingDecision, BranchType
except ImportError:
    from openbp.core.node import BranchingDecision, BranchType


@dataclass
class ArcBranchingConfig:
    """Configuration for arc branching."""
    # Minimum arc usage value to consider for branching
    min_arc_value: float = 0.01
    # Maximum number of candidates to return
    max_candidates: int = 20
    # Consider arcs from a specific source (e.g., depot)
    source_filter: int = -1  # -1 means no filter


class ArcBranching(BranchingStrategy):
    """
    Arc branching for vehicle routing and scheduling.

    For each arc in the network, compute its usage across all columns
    weighted by column values. If the usage is fractional, we can branch:
    - Required branch: Arc must be used (at least once)
    - Forbidden branch: Arc cannot be used

    This is effective for:
    - CVRP: Branch on customer-to-customer arcs
    - Crew scheduling: Branch on flight connections
    - Any problem with path-based columns

    Implementation Notes:
    -------------------
    - Arc usage is computed as sum of column values containing the arc
    - For forbidden arcs, pricing must skip these arcs
    - For required arcs, columns not using the arc have penalty
    """

    def __init__(
        self,
        min_arc_value: float = 0.01,
        max_candidates: int = 20,
        source_filter: int = -1,
    ):
        """
        Initialize arc branching.

        Args:
            min_arc_value: Minimum arc value to consider
            max_candidates: Maximum candidates to return
            source_filter: Only consider arcs from this source (-1 = all)
        """
        super().__init__("ArcBranching")
        self.config = ArcBranchingConfig(
            min_arc_value=min_arc_value,
            max_candidates=max_candidates,
            source_filter=source_filter,
        )

    def select_branching_candidates(
        self,
        node,  # BPNode
        columns,  # List[Column]
        column_values: List[float],
        duals: Dict[int, float],
    ) -> List[BranchingCandidate]:
        """
        Find arcs with fractional usage.

        Args:
            node: Current B&P node
            columns: Columns in the LP
            column_values: LP solution values
            duals: Dual values (unused here)

        Returns:
            List of branching candidates sorted by score
        """
        # Compute arc usage
        # arc_key = (source_node, arc_index) to handle per-source pricing
        arc_usage: Dict[Tuple[int, int], float] = defaultdict(float)

        for col, val in zip(columns, column_values):
            if val < 1e-9:
                continue

            arc_indices = col.arc_indices
            if not arc_indices:
                continue

            # Get source node (first arc's source or from column metadata)
            source_node = getattr(col, "source_node", 0)

            for arc_idx in arc_indices:
                key = (source_node, arc_idx)
                arc_usage[key] += val

        # Find fractional arcs
        candidates = []
        for (source, arc_idx), usage in arc_usage.items():
            # Apply source filter if set
            if self.config.source_filter >= 0 and source != self.config.source_filter:
                continue

            # Check fractionality
            frac = usage - int(usage)
            if frac < self.config.min_arc_value:
                continue
            if frac > 1.0 - self.config.min_arc_value:
                continue

            # Score: prefer balanced splits
            score = 1.0 - abs(frac - 0.5) * 2

            # Create branching decisions
            # Required: arc must be used
            required = BranchingDecision.arc_branch(arc_idx, source, True)

            # Forbidden: arc cannot be used
            forbidden = BranchingDecision.arc_branch(arc_idx, source, False)

            candidate = BranchingCandidate(
                score=score,
                decisions=[forbidden, required],  # Forbidden first (usually tighter)
                description=f"arc[{arc_idx}] from {source}: usage={usage:.3f}",
                metadata={
                    "arc_index": arc_idx,
                    "source_node": source,
                    "usage": usage,
                    "fractionality": frac,
                },
            )
            candidates.append(candidate)

        # Sort by score and limit
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[: self.config.max_candidates]

    def filter_columns(
        self,
        columns,  # List[Column]
        decisions,  # List[BranchingDecision]
    ):
        """
        Filter columns violating arc decisions.

        For each decision:
        - If arc_required=True: keep columns using the arc
        - If arc_required=False: keep columns NOT using the arc
        """
        result = columns

        for decision in decisions:
            if decision.type != BranchType.ARC:
                continue

            arc_idx = decision.arc_index
            source = decision.source_node
            required = decision.arc_required

            filtered = []
            for col in result:
                # Check source match (if source is specified)
                col_source = getattr(col, "source_node", 0)
                if source >= 0 and col_source != source:
                    # Different source - decision doesn't apply
                    filtered.append(col)
                    continue

                has_arc = arc_idx in col.arc_indices

                if required:
                    # Arc must be in column
                    if has_arc:
                        filtered.append(col)
                else:
                    # Arc must NOT be in column
                    if not has_arc:
                        filtered.append(col)

            result = filtered

        return result

    def is_applicable(
        self,
        node,  # BPNode
        columns,  # List[Column]
        column_values: List[float],
    ) -> bool:
        """
        Check if arc branching can be applied.

        Requires columns with arc_indices (path representation).
        """
        if not columns:
            return False

        for col in columns:
            if hasattr(col, "arc_indices") and col.arc_indices:
                return True

        return False
