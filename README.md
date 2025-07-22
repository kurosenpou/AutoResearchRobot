# OVITO Workflow - Automated Materials Analysis System

A comprehensive Python backend system for automated thermomechanical analysis and dislocation/vacancy analysis in molecular dynamics simulations using OVITO.

## 🚀 Features

### Core Analysis Capabilities
- **Elastic Constants Calculation** - Automated stress-strain analysis with linear regression
- **NVE/NVT Simulation Processing** - Microcanonical and canonical ensemble analysis
- **Dislocation Analysis (DXA)** - OVITO-based dislocation tracking and density analysis
- **Vacancy Analysis (WS)** - Wigner-Seitz vacancy detection and evolution tracking
- **Elastic-Plastic Decomposition** - Advanced strain analysis with statistical filtering

### Advanced Features
- **GPU Acceleration** - OVITO processing with CUDA support
- **Remote File Access** - SFTP integration for distributed computing
- **Modular Architecture** - Extensible processor-based design
- **CLI Interface** - Comprehensive command-line tool with detailed help
- **Progress Tracking** - Real-time analysis progress with tqdm
- **Export Formats** - CSV output with comprehensive metrics

## 📦 Installation

### Prerequisites
- Python 3.8+
- OVITO Pro (for DXA/WS analysis)
- CUDA toolkit (optional, for GPU acceleration)

### Setup
```bash
# Clone the repository
git clone https://github.com/yourusername/AutoResearchRobot.git
cd AutoResearchRobot

# Install dependencies
pip install ovito pandas tqdm numpy scipy paramiko

# Verify installation
python -m backend.main --help
```

## 🔧 Usage

### Command Line Interface

#### Elastic Constants Analysis
```bash
# Local files
python -m backend.main elastic ./elastic_data/

# Remote SFTP files
python -m backend.main elastic user@server:/path/to/elastic/ --remote
```

#### NVE Simulation Processing
```bash
# With automatic elastic constants calculation
python -m backend.main nve simulation.txt results.csv --elastic-dir ./elastic_data/

# With pre-calculated compliance parameters
python -m backend.main nve simulation.txt results.csv --compliance "1e-11,-2e-12,3e-11"

# Remote processing
python -m backend.main nve user@server:/sim.txt output.csv --remote
```

#### NVT Simulation Processing
```bash
# Local NVT ensemble analysis
python -m backend.main nvt nvt_simulation.txt nvt_results.csv --elastic-dir ./elastic_data/

# Remote NVT with compliance
python -m backend.main nvt user@server:/nvt.txt output.csv --remote --compliance "1.2e-11,-1.8e-12,2.9e-11"
```

#### Dislocation Analysis (DXA)
```bash
# Local trajectory analysis
python -m backend.main dxa "trajectory*.dump" reference.dump dislocation_results.csv

# Remote analysis with specific frames
python -m backend.main dxa user@server:/path/traj* reference.dump results.csv --remote --frames 0 100 200

# GPU-accelerated processing
python -m backend.main dxa trajectory.dump reference.dump results.csv

# CPU-only processing
python -m backend.main dxa trajectory.dump reference.dump results.csv --no-gpu
```

#### Vacancy Analysis (WS)
```bash
# Local vacancy evolution analysis
python -m backend.main ws "simulation*.dump" perfect_crystal.dump vacancy_results.csv

# Remote analysis with frame selection
python -m backend.main ws user@server:/path/sim* reference.dump vacancies.csv --remote --frames 0 50 100
```

### Python API

```python
from backend.core.ovito_analysis import DislocationAnalysis, WignerSeitzAnalysis
from backend.processors import process_nve_simulation, process_dxa_analysis

# Dislocation analysis
dxa = DislocationAnalysis(gpu_enabled=True)
results = dxa.analyze_trajectory("trajectory*.dump", "reference.dump")

# NVE processing
process_nve_simulation(
    input_file="simulation.txt",
    output_file="results.csv",
    elastic_dir="./elastic_data/",
    threshold=0.002
)
```

## 📊 Output Formats

### NVE/NVT Analysis Output
- **Elastic Properties**: Young's modulus, Poisson's ratio, bulk/shear modulus
- **Strain Decomposition**: Elastic and plastic strain components
- **Stress Analysis**: Von Mises equivalent stress and strain
- **Energy Analysis**: Work, heat, and energy balance
- **Statistical Metrics**: Averages, standard deviations, filtering

### DXA Analysis Output
- **Dislocation Metrics**: Total length, segment count, density
- **Segment Details**: Individual dislocation segments with Burgers vectors
- **Evolution Tracking**: Frame-by-frame dislocation evolution
- **Volume Analysis**: Cell volume and density calculations

### WS Analysis Output
- **Vacancy Metrics**: Total sites, occupied/vacant counts, concentration
- **Structure Analysis**: Crystal structure type identification
- **Evolution Tracking**: Vacancy formation and evolution over time

## 🏗️ Architecture

```
backend/
├── core/
│   ├── elastic_constants.py     # Elastic property calculations
│   ├── ovito_analysis.py        # OVITO DXA/WS integration
│   └── statistical_analysis.py  # Statistical filtering and analysis
├── processors/
│   ├── nve_processor.py         # NVE ensemble processing
│   ├── nvt_processor.py         # NVT ensemble processing
│   ├── dxa_processor.py         # DXA analysis processor
│   └── ws_processor.py          # WS analysis processor
├── utils/
│   └── sftp_utils.py            # Remote file access utilities
└── main.py                      # CLI interface
```

## 🔬 Scientific Background

### Elastic Constants Calculation
Implements linear regression analysis of stress-strain relationships to determine:
- Compliance matrix components (S11, S12, S44)
- Elastic constants (C11, C12, C44)
- Engineering properties (E, ν, K, G)

### Dislocation Analysis (DXA)
Uses OVITO's Dislocation Analysis Modifier to:
- Identify dislocation lines and networks
- Calculate Burgers vectors and line directions
- Track dislocation evolution and density changes
- Support FCC, BCC, and HCP crystal structures

### Vacancy Analysis (WS)
Implements Wigner-Seitz analysis for:
- Vacancy detection in crystal lattices
- Structural defect identification
- Vacancy concentration calculations
- Evolution tracking over simulation time

## 🚨 Requirements

### File Formats
- **Simulation Data**: LAMMPS log format with stress/strain components
- **OVITO Files**: LAMMPS dump files, XYZ, CFG, or any OVITO-supported format
- **Elastic Data**: Stress-strain data with specific column requirements

### Data Columns
#### Simulation Files
```
step, l_1, l_2, l_3, l_4, l_5, l_6, p_1, p_2, p_3, p_4, p_5, p_6, vol, ep, ek, u, t, rho, entropy[, etally]
```

#### Elastic Data Files
```
delta_exx, delta_eyy, delta_ezz, delta_exy, delta_eyz, delta_exz, delta_pxx, delta_pyy, delta_pzz, delta_pxy, delta_pyz, delta_pxz
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- OVITO team for the powerful analysis framework
- Materials science community for theoretical foundations
- Contributors and testers

## 📞 Support

For questions, issues, or contributions:
- Open an issue on GitHub
- Contact: [Your contact information]
- Documentation: [Link to detailed docs]

---

**Note**: This system requires OVITO Pro for dislocation and vacancy analysis features. Basic thermomechanical analysis works without OVITO.
