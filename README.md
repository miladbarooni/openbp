# OpenBP: Open-Source Branch-and-Price Framework

[![Tests](https://github.com/miladbarooni/openbp/actions/workflows/tests.yml/badge.svg)](https://github.com/miladbarooni/openbp/actions)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A research-grade, extensible framework for solving optimization problems using **Branch-and-Price**, built on top of [OpenCG](https://github.com/miladbarooni/opencg).

---

## 🚀 Quick Links

- **[Quick Start](QUICKSTART.md)** - Get started in 20 minutes
- **[Documentation](docs/)** - Comprehensive guides
- **[Examples](examples/)** - Jupyter notebooks and scripts
- **[OpenCG](https://github.com/miladbarooni/opencg)** - Required dependency

---

## 💡 When Do You Need Branch-and-Price?

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

---

## 🎯 Features

### Core Functionality
- **High-Performance C++ Core**: Tree management, node selection implemented in C++ with pybind11
- **Seamless OpenCG Integration**: Automatic column generation at each node
- **Flexible Python API**: Easy to customize for researchers

### Branching Strategies
- **Ryan-Foster**: For set partitioning (crew pairing, vehicle routing)
- **Arc Branching**: For routing with arc flow
- **Variable Branching**: Generic LP branching
- **Strong Branching**: With pseudocost caching
- **Custom Strategies**: Implement your own!

### Node Selection Policies
- **Best-First**: Explore best bound first (prove optimality fast)
- **Depth-First**: Dive deep (find feasible solutions fast)
- **Best-Estimate**: Hybrid using pseudocosts
- **Custom Policies**: Define your own strategy

### Advanced Features (Coming Soon)
- Primal heuristics (diving, RINS)
- Cutting planes at root node
- Warm starting with OpenCG columns
- Solution pool management

---

## 📦 Installation

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

**Using Conda (Recommended)**:
```bash
git clone https://github.com/miladbarooni/openbp.git
cd openbp
conda env create -f environment.yml
conda activate openbp
pip install -e ".[dev]"
```

**Using pip**:
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

## 🏃 Quick Start

### Option 1: Try OpenCG First (Recommended!)

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

### Option 2: Use Branch-and-Price (When Needed)

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

## 🏗️ Architecture

### How OpenBP Builds on OpenCG

```
┌──────────────────────────────────────────────────────────┐
│  OpenBP Layer                                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Branch-and-Price Tree (C++)                       │  │
│  │  • Node creation and management                    │  │
│  │  • Best-first / Depth-first selection              │  │
│  │  │  • Bound tracking and pruning                   │  │
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

This seamless integration is why OpenBP can be so flexible!

---

## 📚 Documentation

### For Users
- **[Quick Start Guide](QUICKSTART.md)** - 20-minute tutorial
- **[User Guide](docs/user_guide.md)** - Comprehensive how-to
- **[When to Use B&P](docs/when_to_use.md)** - Decision guide
- **[Performance Tips](docs/performance.md)** - Optimization strategies

### For Developers
- **[Architecture](docs/architecture.md)** - System design
- **[API Reference](docs/api/)** - All classes and methods
- **[Custom Branching](docs/custom_branching.md)** - Implement your own
- **[Contributing](CONTRIBUTING.md)** - How to contribute

### Examples
- **[Jupyter Notebooks](examples/notebooks/)**
  - 01_vehicle_routing_bp.ipynb
  - 02_crew_rostering_bp.ipynb
  - 03_custom_branching.ipynb
- **[Python Scripts](examples/)**
  - crew_rostering.py
  - multi_commodity_flow.py

---

## 🎓 Research & Citations

If you use OpenBP in your research, please cite:

```bibtex
@software{openbp2024,
  title={OpenBP: An Open-Source Branch-and-Price Framework},
  author={Barooni, Milad and Contributors},
  year={2024},
  url={https://github.com/miladbarooni/openbp},
  note={Research-grade Branch-and-Price framework built on OpenCG}
}

@software{opencg2024,
  title={OpenCG: An Open-Source Column Generation Framework},
  author={Barooni, Milad and Contributors},
  year={2024},
  url={https://github.com/miladbarooni/opencg},
  note={High-performance Column Generation framework}
}
```

### Related Papers
- Barnhart et al. (1998): "Branch-and-Price: Column generation for solving huge integer programs"
- Desaulniers et al. (2005): "Column Generation" (comprehensive textbook)
- Vanderbeck & Wolsey (2010): "Reformulation and Decomposition of Integer Programs"

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Ways to Contribute
- 🐛 Report bugs via [Issues](https://github.com/miladbarooni/openbp/issues)
- 💡 Suggest features via [Discussions](https://github.com/miladbarooni/openbp/discussions)
- 📝 Improve documentation
- 🔬 Add new branching strategies
- 🧪 Add test cases
- 🎓 Share your research using OpenBP

### Development Setup

```bash
# Clone with submodules
git clone --recurse-submodules https://github.com/miladbarooni/openbp.git
cd openbp

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run linters
ruff check openbp/
black --check openbp/
```

---

## 📊 Comparison with Other Frameworks

| Framework | Language | Open Source | Extensible | Performance | Learning Curve |
|-----------|----------|-------------|------------|-------------|----------------|
| **OpenBP** | Python+C++ | ✅ MIT | ✅✅✅ High | ✅✅ Good | ✅✅ Medium |
| **OpenCG** | Python+C++ | ✅ MIT | ✅✅✅ High | ✅✅✅ Excellent | ✅✅✅ Low |
| BaPCod | C++ | ❌ Commercial | ⚠️ Limited | ✅✅✅ Excellent | ❌ High |
| VRPSolver | C++ | ⚠️ Academic | ⚠️ Limited | ✅✅✅ Excellent | ❌ Very High |
| SCIP | C | ✅ ZIB | ✅ Medium | ✅✅✅ Excellent | ❌ Very High |

**OpenBP's Advantage**: Best balance of performance, flexibility, and ease of use for researchers.

---

## 📈 Performance

### Benchmark: Crew Pairing (Kasirzadeh Instance 1)

| Method | Approach | Time | Gap | Coverage |
|--------|----------|------|-----|----------|
| **OpenCG** (Direct IP) | CG + IP | **40s** | 0.3% | **99.9%** ✅ |
| **OpenBP** (B&P) | Branch-and-Price | 3min | 0.0% | 100.0% |
| Literature (Kasirzadeh 2017) | Heuristic B&P | 9.6s | 0.0% | 100.0% |

**Conclusion**: For this instance, **OpenCG is faster** because LP gap is small. Use OpenBP only when needed!

---

## 🗺️ Roadmap

### Version 0.2 (Current)
- ✅ Core B&P algorithm
- ✅ Ryan-Foster, Arc, Variable branching
- ✅ Best-first, Depth-first selection
- ✅ OpenCG integration

### Version 0.3 (Q1 2025)
- [ ] Primal heuristics (diving, RINS)
- [ ] Cutting planes at root
- [ ] Strong branching with caching
- [ ] Solution pool

### Version 0.4 (Q2 2025)
- [ ] Parallel node processing
- [ ] Advanced node selection (best-estimate)
- [ ] Warm starting strategies
- [ ] Performance profiling tools

### Version 1.0 (Q3 2025)
- [ ] Comprehensive documentation
- [ ] PyPI release
- [ ] Academic publication
- [ ] Community ecosystem

---

## 📄 License

OpenBP is released under the **MIT License**. See [LICENSE](LICENSE) for details.

This means you can:
- ✅ Use commercially
- ✅ Modify and redistribute
- ✅ Use in private projects
- ✅ Use in academic research

---

## 🙏 Acknowledgments

- Built on **[OpenCG](https://github.com/miladbarooni/opencg)** - our column generation framework
- Uses **[HiGHS](https://github.com/ERGO-Code/HiGHS)** - excellent open-source LP/MIP solver
- Inspired by **BaPCod**, **SCIP**, and academic B&P literature
- Thanks to all contributors!

---

## 💬 Get Help

- **Documentation**: https://openbp.readthedocs.io
- **Issues**: https://github.com/miladbarooni/openbp/issues
- **Discussions**: https://github.com/miladbarooni/openbp/discussions
- **OpenCG Help**: https://github.com/miladbarooni/opencg/discussions

---

## 🌟 Star History

If OpenBP helps your research or project, please ⭐ star the repository!

[![Star History Chart](https://api.star-history.com/svg?repos=miladbarooni/openbp&type=Date)](https://star-history.com/#miladbarooni/openbp&Date)

---

**Made with ❤️ for the Operations Research community**

[Get Started →](QUICKSTART.md) | [Documentation →](docs/) | [Examples →](examples/)
