"""
Ryan-Foster branching strategy for set partitioning/covering problems.

Ryan-Foster branching branches on pairs of items (i, j) that appear
together in some columns but not in others. It creates:
- Same branch: Items i and j must be in the same column
- Different branch: Items i and j must be in different columns

This is the standard branching strategy for crew scheduling, bin packing,
and other set partitioning problems.

Reference:
    Ryan, D.M. and Foster, B.A. (1981). An Integer Programming Approach
    to Scheduling. Computer Scheduling of Public Transport, 269-280.
"""

from typing import List, Dict, Set, Tuple, FrozenSet
from dataclasses import dataclass
from collections import defaultdict

from openbp.branching.base import BranchingStrategy, BranchingCandidate

try:
    from openbp._core import BranchingDecision, BranchType
except ImportError:
    from openbp.core.node import BranchingDecision, BranchType


@dataclass
class RyanFosterConfig:
    """Configuration for Ryan-Foster branching."""
    # Minimum sum of column values for a pair to be considered
    min_pair_value: float = 0.01
    # Maximum number of candidates to evaluate
    max_candidates: int = 20
    # Prefer pairs with fractional overlap
    prefer_fractional: bool = True


class RyanFosterBranching(BranchingStrategy):
    """
    Ryan-Foster branching for set partitioning problems.

    For each pair of items (i, j), let:
    - together = sum of column values where both i and j are covered
    - apart = sum of column values where exactly one of i, j is covered

    If 0 < together < 1 (fractional overlap), we can branch:
    - Same branch: i and j must appear in the same column
    - Different branch: i and j must appear in different columns

    The score prioritizes pairs where branching is most balanced:
    - Higher score for pairs with together close to 0.5

    Implementation Notes:
    -------------------
    - For each active Ryan-Foster decision, we filter columns during
      pricing: columns violating "same" or "different" constraints
      are excluded.
    - The master problem also gets additional constraints linking
      the coverage of i and j.
    """

    def __init__(
        self,
        min_pair_value: float = 0.01,
        max_candidates: int = 20,
        prefer_fractional: bool = True,
    ):
        """
        Initialize Ryan-Foster branching.

        Args:
            min_pair_value: Minimum pair value to consider
            max_candidates: Maximum candidates to return
            prefer_fractional: Prefer pairs with fractional overlap
        """
        super().__init__("RyanFosterBranching")
        self.config = RyanFosterConfig(
            min_pair_value=min_pair_value,
            max_candidates=max_candidates,
            prefer_fractional=prefer_fractional,
        )

    def select_branching_candidates(
        self,
        node,  # BPNode
        columns,  # List[Column]
        column_values: List[float],
        duals: Dict[int, float],
    ) -> List[BranchingCandidate]:
        """
        Find item pairs with fractional overlap.

        Args:
            node: Current B&P node
            columns: Columns in the LP
            column_values: LP solution values
            duals: Dual values (unused here)

        Returns:
            List of branching candidates sorted by score
        """
        # Compute pair overlap values
        pair_together: Dict[Tuple[int, int], float] = defaultdict(float)
        pair_apart: Dict[Tuple[int, int], float] = defaultdict(float)
        all_items: Set[int] = set()

        for col, val in zip(columns, column_values):
            if val < 1e-9:
                continue

            items = list(col.covered_items)
            all_items.update(items)

            # Items in this column are "together"
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    pair = (min(items[i], items[j]), max(items[i], items[j]))
                    pair_together[pair] += val

        # For "apart", we need items that appear separately
        # Item i appears in column c but j doesn't
        item_to_columns: Dict[int, List[Tuple[int, float]]] = defaultdict(list)
        for idx, (col, val) in enumerate(zip(columns, column_values)):
            if val < 1e-9:
                continue
            for item in col.covered_items:
                item_to_columns[item].append((idx, val))

        # Compute apart values
        all_items_list = sorted(all_items)
        for i in range(len(all_items_list)):
            for j in range(i + 1, len(all_items_list)):
                item_i, item_j = all_items_list[i], all_items_list[j]
                pair = (item_i, item_j)

                # Columns containing i but not j, and vice versa
                cols_i = {idx for idx, _ in item_to_columns[item_i]}
                cols_j = {idx for idx, _ in item_to_columns[item_j]}

                # i without j
                for idx, val in item_to_columns[item_i]:
                    if idx not in cols_j:
                        pair_apart[pair] += val

                # j without i
                for idx, val in item_to_columns[item_j]:
                    if idx not in cols_i:
                        pair_apart[pair] += val

        # Find fractional pairs
        candidates = []
        for pair, together in pair_together.items():
            apart = pair_apart.get(pair, 0.0)
            total = together + apart

            # Skip if no fractional overlap
            if together < self.config.min_pair_value:
                continue
            if together > 1.0 - self.config.min_pair_value:
                continue

            # Score: prefer balanced splits (together close to 0.5)
            if self.config.prefer_fractional:
                score = 1.0 - abs(together - 0.5) * 2
            else:
                score = min(together, 1.0 - together)

            # Create branching decisions
            item_i, item_j = pair

            # Same branch: i and j must be together
            same_decision = BranchingDecision.ryan_foster(item_i, item_j, True)

            # Different branch: i and j must be apart
            diff_decision = BranchingDecision.ryan_foster(item_i, item_j, False)

            candidate = BranchingCandidate(
                score=score,
                decisions=[same_decision, diff_decision],
                description=f"({item_i}, {item_j}): together={together:.3f}, apart={apart:.3f}",
                metadata={
                    "item_i": item_i,
                    "item_j": item_j,
                    "together": together,
                    "apart": apart,
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
        Filter columns violating Ryan-Foster decisions.

        For each decision:
        - If same_column=True: keep only columns where both i,j or neither
        - If same_column=False: keep only columns where at most one of i,j
        """
        result = columns

        for decision in decisions:
            if decision.type != BranchType.RYAN_FOSTER:
                continue

            i, j = decision.item_i, decision.item_j
            same = decision.same_column

            filtered = []
            for col in result:
                items = col.covered_items
                has_i = i in items
                has_j = j in items

                if same:
                    # Must have both or neither
                    if has_i == has_j:
                        filtered.append(col)
                else:
                    # Must not have both
                    if not (has_i and has_j):
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
        Check if Ryan-Foster can be applied.

        Requires columns with covered_items (set partitioning structure).
        """
        if not columns:
            return False

        # Check if columns have covered_items
        for col in columns:
            if hasattr(col, "covered_items") and col.covered_items:
                return True

        return False
