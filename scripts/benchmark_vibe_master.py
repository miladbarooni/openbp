#!/usr/bin/env python3
"""
Benchmark: VIBE_opt vs HiGHS as the master-problem LP solver.

Uses the production crew-pairing paths (FastPerSourcePricing) so pricing
cost is identical and realistic; only the master LP solver differs.

Phase 1 — column generation (opencg.applications.crew_pairing).
Phase 2 — branch-and-price (openbp.applications.crew_pairing, Ryan-Foster).

Master LP time is measured by wrapping solve_lp on both backends. The LP
objectives must agree to 1e-5 relative — disagreement fails the run.

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

import opencg.master as master_mod
from opencg.config import get_data_path
from opencg.master import HiGHSMasterProblem, VibeMasterProblem, VIBE_AVAILABLE
from opencg.parsers import KasirzadehParser
from opencg.parsers.base import ParserConfig


class _Timing:
    """Accumulates master solve_lp wall time across a run."""
    lp_time = 0.0
    lp_calls = 0
    lp_iters = 0

    @classmethod
    def reset(cls):
        cls.lp_time, cls.lp_calls, cls.lp_iters = 0.0, 0, 0


def _timed(cls):
    class Timed(cls):
        def solve_lp(self):
            t0 = time.time()
            sol = super().solve_lp()
            _Timing.lp_time += time.time() - t0
            _Timing.lp_calls += 1
            _Timing.lp_iters += sol.iterations or 0
            return sol
    Timed.__name__ = f"Timed{cls.__name__}"
    return Timed


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


def _swap_master(name):
    """Point BOTH registry names at the timed backend under test. The apps
    resolve `HiGHSMasterProblem`/`VibeMasterProblem` from opencg.master at
    call time, so this swaps the master without touching app code."""
    cls = _timed(VibeMasterProblem if name == "vibe" else HiGHSMasterProblem)
    master_mod.HiGHSMasterProblem = cls
    master_mod.VibeMasterProblem = cls
    import opencg.applications.crew_pairing  # ensure module import side effects done
    return cls


def _restore_masters():
    master_mod.HiGHSMasterProblem = HiGHSMasterProblem
    master_mod.VibeMasterProblem = VibeMasterProblem


def run_cg(problem, name, max_iterations):
    from opencg.applications.crew_pairing import CrewPairingConfig, solve_crew_pairing

    _swap_master(name)
    _Timing.reset()
    try:
        t0 = time.time()
        sol = solve_crew_pairing(problem, CrewPairingConfig(
            max_iterations=max_iterations,
            pricing_max_columns=200,
            cols_per_source=5,
            time_per_source=0.1,
            num_threads=0,
            solver="highs",  # name resolved through the swapped registry
            verbose=False,
        ))
        wall = time.time() - t0
    finally:
        _restore_masters()
    return {
        "objective": sol.objective,
        "coverage": sol.coverage_pct,
        "iterations": sol.iterations,
        "columns": sol.num_columns,
        "wall": wall,
        "master_lp_time": _Timing.lp_time,
        "master_lp_calls": _Timing.lp_calls,
        "simplex_iters": _Timing.lp_iters,
    }


def run_bp(problem, name, max_nodes, max_time):
    from openbp.applications.crew_pairing import (
        CrewPairingBPConfig,
        solve_crew_pairing_bp,
    )

    _swap_master(name)
    _Timing.reset()
    try:
        t0 = time.time()
        sol = solve_crew_pairing_bp(problem, CrewPairingBPConfig(
            max_time=max_time,
            max_nodes=max_nodes,
            verbose=False,
        ))
        wall = time.time() - t0
    finally:
        _restore_masters()
    return {
        "status": getattr(sol.status, "name", str(sol.status)),
        "objective": sol.objective,
        "nodes": getattr(sol, "nodes_explored", None),
        "wall": wall,
        "master_lp_time": _Timing.lp_time,
        "master_lp_calls": _Timing.lp_calls,
        "simplex_iters": _Timing.lp_iters,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("instance", nargs="?", default="instance1")
    ap.add_argument("--cg-iterations", type=int, default=50)
    ap.add_argument("--max-nodes", type=int, default=25)
    ap.add_argument("--max-time", type=float, default=900.0)
    ap.add_argument("--skip-bp", action="store_true")
    ap.add_argument("--skip-cg", action="store_true")
    args = ap.parse_args()

    assert VIBE_AVAILABLE, "vibe_opt not installed in this environment"

    print(f"loading {args.instance} ...", flush=True)
    problem = load_instance(args.instance)
    print(f"  flights={len(problem.cover_constraints)} "
          f"arcs={problem.network.num_arcs}", flush=True)

    if not args.skip_cg:
        print("\n=== Phase 1: column generation (production pricing, master swapped) ===",
              flush=True)
        results = {}
        for name in ("highs", "vibe"):
            r = run_cg(problem, name, args.cg_iterations)
            results[name] = r
            print(f"[{name:5s}] lp={r['objective']:.6f} cover={r['coverage']:.1f}% "
                  f"cg_iters={r['iterations']} cols={r['columns']} "
                  f"wall={r['wall']:.1f}s master_lp={r['master_lp_time']:.2f}s "
                  f"({r['master_lp_calls']} solves, {r['simplex_iters']} simplex iters)",
                  flush=True)
        h, v = results["highs"], results["vibe"]
        rel = abs(h["objective"] - v["objective"]) / (1 + abs(h["objective"]))
        print(f"\nLP objective agreement: rel diff = {rel:.2e} "
              f"{'OK' if rel < 1e-5 else '*** DISAGREEMENT ***'}", flush=True)
        print(f"master LP time  highs={h['master_lp_time']:.2f}s  "
              f"vibe={v['master_lp_time']:.2f}s  "
              f"ratio={v['master_lp_time'] / max(h['master_lp_time'], 1e-9):.2f}x",
              flush=True)
        if rel >= 1e-5:
            sys.exit(1)

    if not args.skip_bp:
        print("\n=== Phase 2: branch-and-price (Ryan-Foster, master swapped) ===",
              flush=True)
        for name in ("highs", "vibe"):
            r = run_bp(problem, name, args.max_nodes, args.max_time)
            print(f"[{name:5s}] status={r['status']:<12} obj={r['objective']} "
                  f"nodes={r['nodes']} wall={r['wall']:.1f}s "
                  f"master_lp={r['master_lp_time']:.2f}s "
                  f"({r['master_lp_calls']} solves, {r['simplex_iters']} simplex iters)",
                  flush=True)


if __name__ == "__main__":
    main()
