#!/usr/bin/env python3
"""
Benchmark: VIBE_opt vs HiGHS as the master-problem LP solver.

Phase 1 — column generation (OpenCG) on Kasirzadeh crew pairing:
    identical problem, identical pricing; only the master LP solver differs.
Phase 2 — branch-and-price (OpenBP): full B&P tree, LP relaxation at every
    node solved by the chosen master.

Correctness gate: LP objectives must agree to 1e-5 relative between the two
masters; disagreement is reported loudly and fails the run.

Usage:
    python scripts/benchmark_vibe_master.py [instance1|instance2|instance3]
        [--cg-iterations N] [--max-nodes N] [--max-time S] [--skip-bp]
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "opencg"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from opencg.config import get_data_path
from opencg.master import HiGHSMasterProblem, VibeMasterProblem, VIBE_AVAILABLE
from opencg.parsers import KasirzadehParser
from opencg.parsers.base import ParserConfig
from opencg.solver import CGConfig, ColumnGeneration

MASTERS = {"highs": HiGHSMasterProblem, "vibe": VibeMasterProblem}


def load_instance(name: str):
    instance_path = get_data_path() / "kasirzadeh" / name
    nested = instance_path / name
    if nested.exists():
        instance_path = nested
    parser = KasirzadehParser(ParserConfig(
        verbose=False,
        validate=True,
        options={
            "min_connection_time": 0.5,
            "max_connection_time": 4.0,
            "min_layover_time": 4.0,
            "max_layover_time": 24.0,
            "max_duty_time": 14.0,
            "max_flight_time": 10.0,
            "max_pairing_days": 7,
        },
    ))
    return parser.parse(instance_path)


def run_cg(problem, master_cls, max_iterations: int):
    cg = ColumnGeneration(problem, CGConfig(
        max_iterations=max_iterations,
        verbose=False,
    ))
    cg.set_master(master_cls(problem))
    t0 = time.time()
    sol = cg.solve()
    wall = time.time() - t0
    return {
        "status": sol.status.name,
        "lp_objective": sol.lp_objective,
        "iterations": sol.iterations,
        "columns": sol.total_columns,
        "wall": wall,
        "master_time": sol.master_time,
        "pricing_time": sol.pricing_time,
    }


def run_bp(problem, master_cls, max_nodes: int, max_time: float):
    from openbp.solver.branch_and_price import BPConfig, BranchAndPrice
    from openbp.branching import RyanFosterBranching
    from openbp.node_selection import BestFirstSelection

    solver = BranchAndPrice(
        problem,
        branching_strategy=RyanFosterBranching(),
        node_selection=BestFirstSelection(),
        master_class=master_cls,
        config=BPConfig(max_nodes=max_nodes, max_time=max_time),
    )
    t0 = time.time()
    sol = solver.solve()
    wall = time.time() - t0
    return {
        "status": sol.status.name,
        "objective": sol.objective,
        "nodes": sol.nodes_explored,
        "wall": wall,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("instance", nargs="?", default="instance1")
    ap.add_argument("--cg-iterations", type=int, default=50)
    ap.add_argument("--max-nodes", type=int, default=25)
    ap.add_argument("--max-time", type=float, default=900.0)
    ap.add_argument("--skip-bp", action="store_true")
    args = ap.parse_args()

    assert VIBE_AVAILABLE, "vibe_opt not installed in this environment"

    print(f"loading {args.instance} ...")
    problem = load_instance(args.instance)
    print(f"  flights={len(problem.cover_constraints)} "
          f"arcs={problem.network.num_arcs}")

    print("\n=== Phase 1: column generation (identical pricing, master swapped) ===")
    cg_results = {}
    for name, cls in MASTERS.items():
        r = run_cg(problem, cls, args.cg_iterations)
        cg_results[name] = r
        print(f"[{name:5s}] status={r['status']:<15} lp={r['lp_objective']:.6f} "
              f"iters={r['iterations']:3d} cols={r['columns']:5d} "
              f"wall={r['wall']:.2f}s master={r['master_time']:.2f}s "
              f"pricing={r['pricing_time']:.2f}s")

    h, v = cg_results["highs"], cg_results["vibe"]
    rel = abs(h["lp_objective"] - v["lp_objective"]) / (1 + abs(h["lp_objective"]))
    print(f"\nLP objective agreement: rel diff = {rel:.2e} "
          f"{'OK' if rel < 1e-5 else '*** DISAGREEMENT ***'}")
    if h["master_time"] > 0:
        print(f"master-time ratio (vibe/highs): "
              f"{v['master_time'] / h['master_time']:.2f}x")
    if rel >= 1e-5:
        sys.exit(1)

    if args.skip_bp:
        return

    print("\n=== Phase 2: branch-and-price (LP at every node by the master) ===")
    for name, cls in MASTERS.items():
        r = run_bp(problem, cls, args.max_nodes, args.max_time)
        print(f"[{name:5s}] status={r['status']:<12} obj={r['objective']} "
              f"nodes={r['nodes']} wall={r['wall']:.2f}s")


if __name__ == "__main__":
    main()
