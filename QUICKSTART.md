# Quick Start Guide - OpenBP

**Goal**: Understand when to use Branch-and-Price and solve your first problem in 20 minutes.

> **New to Column Generation?** Start with [OpenCG Quick Start](https://github.com/miladbarooni/opencg/blob/main/QUICKSTART.md) first!

---

## When Do You Need Branch-and-Price?

### Use **OpenCG** (Direct Column Generation + IP) When:
- ✅ LP-IP gap < 1%
- ✅ Coverage > 99%
- ✅ LP solutions are mostly integral
- ✅ **Faster solve times** (seconds to minutes)

**Examples**: Crew pairing, cutting stock, most vehicle routing instances

### Use **OpenBP** (Branch-and-Price) When:
- ❌ LP-IP gap > 1-2%
- ❌ Many fractional variables (>10% in range [0.3, 0.7])
- ❌ Direct IP solve fails or too slow
- ✅ Need **provable optimality**

**Examples**: Crew rostering with complex constraints, bin packing with conflicts, some multi-commodity flow problems

---

## Prerequisites (5 minutes)

### Required
- **OpenCG installed** - OpenBP builds on OpenCG
- **Python 3.9+**
- **C++ compiler** with C++17 support
- **CMake 3.15+**

### Install OpenCG First

If you haven't already:

```bash
git clone https://github.com/miladbarooni/opencg.git
cd opencg
pip install -e ".[dev]"

# Verify
python -c "from opencg._core import HAS_CPP_BACKEND; print(f'OpenCG C++ backend: {HAS_CPP_BACKEND}')"
```

---

## Installation (5 minutes)

### Option 1: Using Conda (Recommended)

```bash
# Clone OpenBP repository
git clone https://github.com/miladbarooni/openbp.git
cd openbp

# Create environment (includes OpenCG)
conda env create -f environment.yml
conda activate openbp

# Install in development mode
pip install -e ".[dev]"

# Verify installation
python -c "from openbp._core import HAS_CPP_BACKEND; print(f'OpenBP C++ backend: {HAS_CPP_BACKEND}')"
```

Expected output: `OpenBP C++ backend: True` ✅

### Option 2: Pip Install (if OpenCG already installed)

```bash
# Clone repository
git clone https://github.com/miladbarooni/openbp.git
cd openbp

# Install
pip install -e ".[dev]"
```

---

## Your First Branch-and-Price Solve (10 minutes)

### Problem: Set Partitioning with Fractional LP

Create a file `my_first_bp.py`:

```python
from opencg import Problem
from opencg.parsers import KasirzadehParser
from opencg.parsers.base import ParserConfig
from openbp import BranchAndPrice
from openbp.branching import RyanFosterBranching
from openbp.node_selection import BestFirstSelection

# Parse a crew pairing instance
# (This is an example - you'd use an instance where B&P is actually needed)
parser_config = ParserConfig(
    verbose=False,
    options={
        'min_connection_time': 0.5,
        'max_connection_time': 4.0,
        'min_layover_time': 4.0,
        'max_layover_time': 24.0,
        'max_duty_time': 14.0,
        'max_flight_time': 8.0,
        'max_pairing_days': 5,
    }
)

parser = KasirzadehParser(parser_config)
problem = parser.parse("path/to/instance")

print(f"Problem: {len(problem.cover_constraints)} flights")

# Configure Branch-and-Price solver
solver = BranchAndPrice(
    problem,
    branching_strategy=RyanFosterBranching(),
    node_selection=BestFirstSelection(),
    time_limit=3600,  # 1 hour
    verbose=True,
)

# Solve with optimality guarantee
print("\nSolving with Branch-and-Price...")
solution = solver.solve()

# Print results
print("\n" + "="*60)
print("SOLUTION")
print("="*60)
print(f"Status: {solution.status}")
print(f"Objective: {solution.objective}")
print(f"Best Bound: {solution.best_bound}")
print(f"Gap: {solution.gap * 100:.2f}%")
print(f"Nodes Explored: {solution.nodes_explored}")
print(f"Solve Time: {solution.solve_time:.2f}s")

if solution.gap < 0.01:
    print("\n✅ OPTIMAL SOLUTION (gap < 1%)")
elif solution.gap < 0.05:
    print("\n✅ NEAR-OPTIMAL (gap < 5%)")
else:
    print(f"\n⚠️  Gap = {solution.gap*100:.2f}% - may need more time")
```

### What Just Happened?

1. **Root Node**: Solved column generation to get LP relaxation
2. **Branching**: When LP fractional, created two child nodes with Ryan-Foster branching
3. **Node Selection**: Used best-first to explore most promising nodes
4. **Bounding**: Pruned nodes where bound worse than current best
5. **Convergence**: Stopped when gap < tolerance or time limit

**Key Difference from OpenCG**: Explores a tree of nodes, guarantees optimality (if solved to completion).

---

## How OpenBP Integrates with OpenCG

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  OpenBP (Branch-and-Price Framework)                    │
│  ┌───────────────────────────────────────────────────┐  │
│  │  B&P Tree (C++)                                   │  │
│  │  - Node management                                │  │
│  │  - Best-first / Depth-first selection             │  │
│  │  - Bound tracking                                 │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Branching Strategies (Python + C++)              │  │
│  │  - Ryan-Foster (set partitioning)                 │  │
│  │  - Arc branching (routing)                        │  │
│  │  - Variable branching (generic)                   │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                         ↓
           Uses OpenCG for each node
                         ↓
┌─────────────────────────────────────────────────────────┐
│  OpenCG (Column Generation Framework)                   │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Column Generation                                │  │
│  │  - Master problem (LP/IP)                         │  │
│  │  - Pricing subproblem (SPPRC)                     │  │
│  │  - Dual values and reduced costs                  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Key Integration Points

1. **Problem Definition**: OpenBP uses OpenCG's `Problem` class
2. **Column Generation**: Each B&P node runs OpenCG's `ColumnGeneration`
3. **Branching Modifies Network**: Branching decisions update OpenCG's network
4. **Columns Inherited**: Child nodes can reuse parent's column pool

### Example: Ryan-Foster Branching

When LP has fractional solution, Ryan-Foster branching:

```python
# Finds two items (i, j) covered by fractional columns
# Creates two branches:
#   Left:  Force items i and j in SAME column
#   Right: Force items i and j in DIFFERENT columns

# This is implemented by modifying the OpenCG network:
#   Left:  Merge nodes i and j
#   Right: Add forbidden arc pairs
```

OpenCG's flexible network structure makes this seamless!

---

## Choosing the Right Branching Strategy

### Ryan-Foster Branching

**Best for**: Set partitioning problems (crew pairing, vehicle routing)

```python
from openbp.branching import RyanFosterBranching

solver = BranchAndPrice(
    problem,
    branching_strategy=RyanFosterBranching(),
)
```

**How it works**: Branches on pairs of items that appear together fractionally

### Arc Branching

**Best for**: Routing problems with arc flow variables

```python
from openbp.branching import ArcBranching

solver = BranchAndPrice(
    problem,
    branching_strategy=ArcBranching(),
)
```

**How it works**: Branches on arcs that have fractional flow

### Variable Branching

**Best for**: Generic problems or when others don't apply

```python
from openbp.branching import VariableBranching

solver = BranchAndPrice(
    problem,
    branching_strategy=VariableBranching(),
)
```

**How it works**: Standard branch on fractional column variables

---

## Node Selection Strategies

### Best-First (Default)

**Best for**: Finding optimal quickly, proving optimality

```python
from openbp.node_selection import BestFirstSelection

solver = BranchAndPrice(
    problem,
    node_selection=BestFirstSelection(),
)
```

**Behavior**: Explores nodes with best LP bound first

### Depth-First

**Best for**: Finding good feasible solutions fast

```python
from openbp.node_selection import DepthFirstSelection

solver = BranchAndPrice(
    problem,
    node_selection=DepthFirstSelection(),
)
```

**Behavior**: Dives deep to find integer solutions quickly

### Best-Estimate (Hybrid)

**Best for**: Balancing feasibility and optimality

```python
from openbp.node_selection import BestEstimateSelection

solver = BranchAndPrice(
    problem,
    node_selection=BestEstimateSelection(),
)
```

**Behavior**: Uses pseudocosts to estimate both bound and feasibility

---

## Performance Tips

### 1. Try OpenCG First!

Before using Branch-and-Price, always try direct IP with OpenCG:

```python
from opencg.solver import ColumnGeneration, CGConfig

cg_config = CGConfig(
    max_iterations=50,
    solve_ip=True,  # Solve IP after CG
    verbose=True,
)

cg = ColumnGeneration(problem, cg_config)
solution = cg.solve()

# Check if you actually need B&P
if solution.gap < 0.01:
    print("✅ Direct IP worked! No need for B&P")
else:
    print(f"⚠️  Gap = {solution.gap*100:.2f}% - consider B&P")
```

### 2. Warm Start from OpenCG

Use OpenCG's column pool to warm start B&P:

```python
# Run OpenCG first
cg = ColumnGeneration(problem, cg_config)
cg_solution = cg.solve()

# Use its columns in B&P
solver = BranchAndPrice(
    problem,
    initial_columns=cg._column_pool.get_all_columns(),
    branching_strategy=RyanFosterBranching(),
)

solution = solver.solve()
```

### 3. Set Time Limits

```python
solver = BranchAndPrice(
    problem,
    time_limit=3600,  # 1 hour
    gap_tolerance=0.01,  # Stop at 1% gap
)
```

### 4. Use Primal Heuristics (if available)

```python
from openbp.heuristics import DivingHeuristic

solver = BranchAndPrice(
    problem,
    branching_strategy=RyanFosterBranching(),
    primal_heuristic=DivingHeuristic(),  # Find good solutions fast
)
```

---

## Troubleshooting

### "OpenCG not found"

**Fix**:
```bash
# Install OpenCG first
pip install -e /path/to/opencg

# Then install OpenBP
pip install -e .
```

### "B&P is very slow"

**Diagnosis**: Check if you actually need B&P:
```python
# Run OpenCG first, check gap
cg_solution = cg.solve()
print(f"Gap: {cg_solution.gap * 100:.2f}%")

# If gap < 1%, use direct IP instead
if cg_solution.gap < 0.01:
    print("Use OpenCG with solve_ip=True instead!")
```

### "Tree exploding (too many nodes)"

**Fix**: Use stronger branching or add cutting planes
```python
from openbp.branching import StrongBranching

solver = BranchAndPrice(
    problem,
    branching_strategy=StrongBranching(num_candidates=5),
    # Stronger branching = fewer nodes but more time per node
)
```

---

## What's Next?

### Learn More
- **[OpenBP Documentation](docs/)** - Comprehensive guide
- **[Branching Strategies](docs/branching.md)** - When to use which
- **[Integration Guide](docs/integration.md)** - Deep dive on OpenCG integration

### Examples
- **[examples/notebooks/](examples/notebooks/)** - Jupyter tutorials
- **[examples/crew_rostering.py](examples/)** - Full example with B&P

### Advanced Topics
- **Custom Branching Rules** - Implement problem-specific branching
- **Cutting Planes** - Strengthen LP bounds
- **Primal Heuristics** - Find good solutions faster

---

## Comparison: OpenCG vs OpenBP

| Aspect | OpenCG | OpenBP |
|--------|--------|--------|
| **Method** | Column Generation + Direct IP | Branch-and-Price |
| **Optimality** | Heuristic (if LP fractional) | Guaranteed (if complete) |
| **Speed** | Fast (seconds to minutes) | Slower (minutes to hours) |
| **Use When** | LP near-integral (<1% gap) | LP fractional (>1% gap) |
| **Complexity** | Simpler (no tree) | More complex (tree + branching) |
| **Best For** | Most practical problems | Problems needing provable optimality |

---

## Getting Help

- **OpenBP Documentation**: https://openbp.readthedocs.io
- **OpenCG Documentation**: https://opencg.readthedocs.io
- **Issues**: https://github.com/miladbarooni/openbp/issues
- **Discussions**: https://github.com/miladbarooni/openbp/discussions

---

**Congratulations!** 🎉 You now understand when and how to use Branch-and-Price.

**Remember**: Always try OpenCG first! Only use OpenBP when you really need it.

**Total time**: ~20 minutes
- Understanding when to use B&P: 5 min
- Installation: 5 min
- First solve: 10 min
