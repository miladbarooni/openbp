"""
Application-specific B&P solvers.

This module provides ready-to-use branch-and-price solvers for
common optimization problems.

Available Applications:
----------------------
- Cutting Stock: 1D bin packing with column generation
- VRPTW: Vehicle Routing Problem with Time Windows
- Crew Pairing: Airline crew scheduling
- Set Partitioning: Generic set partitioning solver
"""

from openbp.applications.crew_pairing import (
    CrewPairingBPConfig,
    solve_crew_pairing_bp,
)
from openbp.applications.cutting_stock import (
    CuttingStockBPConfig,
    solve_cutting_stock_bp,
)
from openbp.applications.set_partitioning import (
    SetPartitioningConfig,
    solve_set_partitioning,
)
from openbp.applications.vrptw import (
    VRPTWBPConfig,
    solve_vrptw_bp,
)
from openbp.applications.vrptw_bpc import (
    VRPTWBPCConfig,
    solve_vrptw_bpc,
)

__all__ = [
    "solve_cutting_stock_bp",
    "CuttingStockBPConfig",
    "solve_vrptw_bp",
    "VRPTWBPConfig",
    "solve_vrptw_bpc",
    "VRPTWBPCConfig",
    "solve_crew_pairing_bp",
    "CrewPairingBPConfig",
    "solve_set_partitioning",
    "SetPartitioningConfig",
]
