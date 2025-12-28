#!/usr/bin/env python3
"""
Unified diagnostic tool for Branch-and-Price problems.

This consolidates various diagnostic scripts into a single tool with subcommands.

Usage:
    python scripts/diagnose.py crew_pairing [instance_path]
    python scripts/diagnose.py vrptw [instance_path]
    python scripts/diagnose.py tree --help
"""

import argparse
import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "opencg"))
sys.path.insert(0, str(Path(__file__).parent.parent))


def diagnose_crew_pairing(args):
    """Run crew pairing diagnostics using OpenCG's diagnostic script."""
    # Import OpenCG diagnostic
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "opencg" / "scripts"))

    try:
        from diagnose_crew_pairing import CrewPairingDiagnostics
    except ImportError:
        print("Error: Cannot import diagnose_crew_pairing from opencg/scripts/")
        print("Make sure opencg is installed and the diagnostic script exists.")
        return 1

    instance_path = Path(args.instance) if args.instance else None
    if instance_path is None:
        # Try default path
        opencg_path = Path(__file__).parent.parent.parent / "opencg"
        instance_path = opencg_path / "data" / "kasirzadeh" / "instance1"

    if not instance_path.exists():
        print(f"Error: Instance not found: {instance_path}")
        return 1

    config_options = {}
    if args.fix:
        config_options = {
            'max_connection_time': 4.0,
            'min_layover_time': 4.0,  # Close the gap
        }

    diag = CrewPairingDiagnostics(instance_path, config_options)
    results = diag.run_all()

    errors = [r for r in results if r.severity == "error"]
    return 1 if errors else 0


def diagnose_tree(args):
    """Diagnose B&P tree state."""
    print("Tree diagnostics not yet implemented.")
    print("This will analyze:")
    print("  - Number of open/closed nodes")
    print("  - Current bounds (lower/upper)")
    print("  - Branching decisions")
    print("  - Node selection patterns")
    return 0


def diagnose_vrptw(args):
    """Diagnose VRPTW instance."""
    print("VRPTW diagnostics not yet implemented.")
    print("This will analyze:")
    print("  - Customer reachability")
    print("  - Time window feasibility")
    print("  - Capacity constraints")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Unified diagnostic tool for Branch-and-Price",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/diagnose.py crew_pairing
  python scripts/diagnose.py crew_pairing --fix
  python scripts/diagnose.py crew_pairing /path/to/instance
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Diagnostic type')

    # Crew pairing subcommand
    crew_parser = subparsers.add_parser('crew_pairing', aliases=['crew'],
                                        help='Crew pairing diagnostics')
    crew_parser.add_argument('instance', nargs='?', help='Instance path')
    crew_parser.add_argument('--fix', action='store_true',
                            help='Apply recommended fixes')

    # VRPTW subcommand
    vrptw_parser = subparsers.add_parser('vrptw', help='VRPTW diagnostics')
    vrptw_parser.add_argument('instance', nargs='?', help='Instance path')

    # Tree subcommand
    tree_parser = subparsers.add_parser('tree', help='B&P tree diagnostics')
    tree_parser.add_argument('--nodes', type=int, help='Limit nodes to analyze')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command in ['crew_pairing', 'crew']:
        return diagnose_crew_pairing(args)
    elif args.command == 'vrptw':
        return diagnose_vrptw(args)
    elif args.command == 'tree':
        return diagnose_tree(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
