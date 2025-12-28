# OpenBP: Open-Source Branch-and-Price Framework

A research-grade framework for solving optimization problems using Branch-and-Price, built on top of [OpenCG](https://github.com/miladbarooni/opencg).

## When Do You Need Branch-and-Price?

### Use [OpenCG](https://github.com/miladbarooni/opencg) (Direct Column Generation) When:
- ✅ LP-IP gap < 1% (LP solutions are near-integral)
- ✅ Coverage > 99%
- ✅ **Fast solve times** (seconds to minutes)
- ✅ Heuristic optimality sufficient

**→ This covers ~80-90% of practical applications!**

### Use OpenBP (Branch-and-Price) When:
- ❌ LP-IP gap > 1-2% (many fractional variables)
- ❌ Direct IP solve too slow or fails
- ✅ Need **provable optimality**
- ✅ Have time for longer solves (minutes to hours)

### Performance Comparison

**Benchmark**: Crew Pairing (Kasirzadeh Instance 1, 1013 flights)

| Method | Approach | Time | Gap | Coverage |
|--------|----------|------|-----|----------|
| **OpenCG** (Direct IP) | CG + IP | **40s** | 0.3% | **99.9%** ✅ |
| **OpenBP** (B&P) | Branch-and-Price | 3min | 0.0% | 100.0% |

**Conclusion**: For most problems, OpenCG is faster. Use OpenBP only when you need guaranteed optimality.

---

## Features

### Core Functionality
- **High-Performance C++ Core**: Tree management, node selection
- **Seamless OpenCG Integration**: Automatic column generation at each node
- **Flexible Python API**: Easy to customize for researchers

### Branching Strategies
- **Ryan-Foster**: For set partitioning (crew pairing, vehicle routing)
- **Arc Branching**: For routing with arc flow
- **Variable Branching**: Generic LP branching
- **Strong Branching**: With pseudocost caching

### Node Selection Policies
- **Best-First**: Explore best bound first (prove optimality fast)
- **Depth-First**: Dive deep (find feasible solutions fast)
- **Best-Estimate**: Hybrid using pseudocosts

---

## Installation

### Prerequisites
- **[OpenCG](https://github.com/miladbarooni/opencg)** - Must be installed first!
- Python 3.9+
- C++ compiler with C++17 support
- CMake 3.15+

### Step 1: Install OpenCG

```bash
git clone https://github.com/miladbarooni/opencg.git
cd opencg
pip install -e ".[dev]"
cd ..
```

### Step 2: Install OpenBP

```bash
git clone https://github.com/miladbarooni/openbp.git
cd openbp
pip install -e ".[dev]"
```

### Verify Installation

```python
from openbp._core import HAS_CPP_BACKEND
from opencg._core import HAS_CPP_BACKEND as OPENCG_CPP

print(f"OpenCG C++ backend: {OPENCG_CPP}")
print(f"OpenBP C++ backend: {HAS_CPP_BACKEND}")
```

Expected: Both should be `True` ✅

---

## Quick Start

### Step 1: Try OpenCG First (Recommended!)

Before using Branch-and-Price, **always try direct column generation**:

```python
from opencg.solver import ColumnGeneration, CGConfig
from opencg.parsers import KasirzadehParser

# Parse problem
parser = KasirzadehParser()
problem = parser.parse("data/instance1")

# Try direct CG + IP
cg_config = CGConfig(
    max_iterations=50,
    solve_ip=True,  # Solve IP after CG
    verbose=True,
)

cg = ColumnGeneration(problem, cg_config)
solution = cg.solve()

print(f"LP Objective: {solution.lp_objective}")
print(f"IP Objective: {solution.ip_objective}")
print(f"Gap: {solution.gap * 100:.2f}%")

# Decision point
if solution.gap < 0.01:
    print("✅ Direct IP worked! No need for Branch-and-Price")
else:
    print(f"⚠️  Gap = {solution.gap*100:.2f}% - consider Branch-and-Price")
```

### Step 2: Use Branch-and-Price (When Needed)

Only if direct IP doesn't work well:

```python
from openbp import BranchAndPrice
from openbp.branching import RyanFosterBranching
from openbp.node_selection import BestFirstSelection

# Configure B&P solver
solver = BranchAndPrice(
    problem,
    branching_strategy=RyanFosterBranching(),
    node_selection=BestFirstSelection(),
    time_limit=3600,  # 1 hour
    gap_tolerance=0.01,  # Stop at 1% gap
    verbose=True,
)

# Solve with optimality guarantee
solution = solver.solve()

print(f"Status: {solution.status}")
print(f"Objective: {solution.objective}")
print(f"Gap: {solution.gap * 100:.2f}%")
print(f"Nodes Explored: {solution.nodes_explored}")
print(f"Time: {solution.solve_time:.2f}s")
```

**See [QUICKSTART.md](QUICKSTART.md) for detailed tutorial!**

---

## Architecture

### How OpenBP Builds on OpenCG

```
┌──────────────────────────────────────────────────────────┐
│  OpenBP Layer                                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Branch-and-Price Tree (C++)                       │  │
│  │  • Node creation and management                    │  │
│  │  • Best-first / Depth-first selection              │  │
│  │  • Bound tracking and pruning                      │  │
│  └───────────────┬──────────────────────────────────────┘  │
│  ┌───────────────▼──────────────────────────────────────┐  │
│  │  Branching Strategies (Python + C++)               │  │
│  │  • Ryan-Foster, Arc, Variable branching            │  │
│  │  • Modifies network for child nodes                │  │
│  └───────────────┬──────────────────────────────────────┘  │
└──────────────────┼──────────────────────────────────────────┘
                   │ Uses OpenCG at each node
                   ▼
┌──────────────────────────────────────────────────────────┐
│  OpenCG Layer (Column Generation)                        │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Column Generation Loop                            │  │
│  │  • Master problem (HiGHS LP/IP)                    │  │
│  │  • Pricing subproblem (C++ labeling)               │  │
│  │  • Dual values & reduced costs                     │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### Key Integration Points

1. **Problem Definition**: OpenBP uses OpenCG's `Problem`, `Network`, `Arc`, `Resource` classes
2. **Column Generation**: Each B&P node runs `ColumnGeneration` from OpenCG
3. **Branching Modifies Network**: Child nodes have modified networks (forbidden arcs, merged nodes)
4. **Column Inheritance**: Child nodes can reuse parent's column pool for warm starting

### Example: Ryan-Foster Branching

When LP solution has fractional columns:

```python
# Find two items (i, j) that appear together in fractional columns
# Create two child nodes:
#   Left:  i and j must be in SAME pairing
#   Right: i and j must be in DIFFERENT pairings

# OpenCG's network makes this easy:
#   Left:  Merge nodes i and j → single super-node
#   Right: Add (i,j) to forbidden pairs in pricing
```

---

## Documentation

- **[Quick Start Guide](QUICKSTART.md)** - 20-minute tutorial with examples
- **[OpenCG Documentation](https://github.com/miladbarooni/opencg)** - Required dependency
- **[Examples](examples/notebooks/)** - Jupyter notebooks with interactive tutorials

---

## Applications

OpenBP works with any problem that OpenCG can model:

- **Airline Crew Scheduling**: Assign pairings to cover all flights
- **Vehicle Routing**: CVRP, VRPTW with optimal routes
- **Bin Packing**: Minimize bins while covering all items
- **Any Set Covering Problem**: Where you need provable optimality

---

## Research & Citations

If you use OpenBP in your research, please cite:

```bibtex
@software{openbp2024,
  title={OpenBP: An Open-Source Branch-and-Price Framework},
  author={Barooni, Milad and Contributors},
  year={2024},
  url={https://github.com/miladbarooni/openbp}
}

@software{opencg2024,
  title={OpenCG: An Open-Source Column Generation Framework},
  author={Barooni, Milad and Contributors},
  year={2024},
  url={https://github.com/miladbarooni/opencg}
}
```

### Related Papers
- Barnhart et al. (1998): "Branch-and-Price: Column generation for solving huge integer programs"
- Desaulniers et al. (2005): "Column Generation" (comprehensive textbook)
- Vanderbeck & Wolsey (2010): "Reformulation and Decomposition of Integer Programs"

---

## Contributing

We welcome contributions!

- 🐛 Report bugs via [Issues](https://github.com/miladbarooni/openbp/issues)
- 💡 Suggest features via [Discussions](https://github.com/miladbarooni/openbp/discussions)
- 📝 Improve documentation
- 🔬 Add new branching strategies
- 🧪 Add test cases

---

## License

OpenBP is released under the **MIT License**. See [LICENSE](LICENSE) for details.

---

## Acknowledgments

- Built on **[OpenCG](https://github.com/miladbarooni/opencg)** - our column generation framework
- Uses **[HiGHS](https://github.com/ERGO-Code/HiGHS)** - excellent open-source LP/MIP solver
- Inspired by BaPCod, SCIP, and academic B&P literature
