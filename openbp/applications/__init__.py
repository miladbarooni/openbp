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

from openbp.applications.cutting_stock import (
    solve_cutting_stock_bp,
    CuttingStockBPConfig,
)
from openbp.applications.vrptw import (
    solve_vrptw_bp,
    VRPTWBPConfig,
)
from openbp.applications.vrptw_bpc import (
    solve_vrptw_bpc,
    VRPTWBPCConfig,
)
from openbp.applications.crew_pairing import (
    solve_crew_pairing_bp,
    CrewPairingBPConfig,
)
from openbp.applications.set_partitioning import (
    solve_set_partitioning,
    SetPartitioningConfig,
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
