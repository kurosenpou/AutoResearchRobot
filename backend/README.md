# OVITO Workflow Backend

A modular backend system for thermomechanical analysis of LAMMPS simulation data, supporting both NVE and NVT ensembles with remote SFTP access capabilities.

## 🏗️ Architecture

```
backend/
├── main.py                 # Command-line interface
├── __init__.py            # Main package exports
├── config/                # Configuration and constants
│   ├── __init__.py
│   └── constants.py       # Physical constants, headers, thresholds
├── core/                  # Core scientific modules
│   ├── __init__.py
│   ├── elastic_constants.py    # Elastic constants calculation
│   └── thermomechanical.py     # Thermomechanical analysis
├── processors/            # High-level processors
│   ├── __init__.py
│   ├── nve_processor.py   # NVE ensemble processor
│   └── nvt_processor.py   # NVT ensemble processor
└── utils/                 # Utility modules
    ├── __init__.py
    ├── sftp_utils.py      # SFTP connection management
    ├── file_utils.py      # File I/O with format detection
    └── math_utils.py      # Mathematical calculations
```

## 🚀 Features

### Core Capabilities
- **Elastic Constants Calculation**: Linear regression analysis of stress-strain data
- **Thermomechanical Analysis**: Complete NVE/NVT ensemble post-processing
- **Taylor-Quinney Coefficient (TQC)**: Plastic work to heat conversion analysis
- **Von Mises Calculations**: Equivalent stress and strain analysis
- **Elastic-Plastic Decomposition**: Strain partitioning using compliance matrix

### Technical Features
- **Remote SFTP Access**: Interactive authentication with OTP support
- **Multi-format Support**: Automatic CSV/TXT format detection
- **Modular Design**: Clean separation of concerns for maintainability
- **Type Safety**: Full Python type annotations
- **Error Handling**: Robust error handling and cleanup
- **Progress Reporting**: Detailed console output with emojis

## 📦 Dependencies

### Core Dependencies
```python
numpy>=1.20.0
pandas>=1.3.0
scikit-learn>=1.0.0
paramiko>=2.7.0  # For SFTP
```

### Optional Dependencies (for OVITO analysis)
```python
ovito>=3.8.0  # For DXA and WS analysis
tqdm>=4.60.0  # Progress bars (included with ovito)
```

### Installation
```bash
# Basic installation
pip install numpy pandas scikit-learn paramiko

# With OVITO support (for DXA and WS analysis)
pip install ovito

# Note: OVITO installation may require specific Python versions
# Check OVITO documentation for compatibility
```

## 🔧 Usage

### Command Line Interface

```bash
# Process NVE simulation with remote files
python main.py nve simulation.txt output.csv --remote --elastic-dir /path/to/elastic

# Process NVT simulation with known compliance parameters
python main.py nvt simulation.txt output.csv --compliance "1e-11,2e-11,3e-11"

# Calculate elastic constants only
python main.py elastic /path/to/elastic --elastic-files "c1144.txt,c2255.txt,c3366.txt"

# DXA dislocation analysis (requires OVITO)
python main.py dxa "trajectory*.dump" reference.dump dislocation_results.csv

# WS vacancy analysis with specific frames (requires OVITO)
python main.py ws simulation.dump perfect_crystal.dump vacancy_results.csv --frames 0 100 200

# Remote OVITO analysis with GPU acceleration
python main.py dxa user@server:/path/traj* reference.dump results.csv --remote

# CPU-only OVITO processing
python main.py ws trajectory.dump reference.dump results.csv --no-gpu
```

### Python API

```python
from backend import process_nve_simulation, process_nvt_simulation

# NVE analysis
success = process_nve_simulation(
    simulation_file="simulation_data.txt",
    output_file="results.csv",
    elastic_constants_dir="/path/to/elastic",
    remote=False,
    strain_threshold=0.002
)

# NVT analysis with remote files
success = process_nvt_simulation(
    simulation_file="user@server:/path/simulation.txt",
    output_file="nvt_results.csv",
    remote=True,
    sftp_config={'hostname': 'server', 'username': 'user'},
    compliance_params=(1e-11, 2e-11, 3e-11)
)
```

### Advanced Usage

```python
from backend.core import ElasticConstantsProcessor, ThermomechanicalProcessor

# Elastic constants calculation
elastic_proc = ElasticConstantsProcessor()
results = elastic_proc.process_complete_elastic_analysis(
    ["c1144.txt", "c2255.txt", "c3366.txt"]
)

# Custom thermomechanical analysis
thermo_proc = ThermomechanicalProcessor()
thermo_proc.set_compliance_parameters(1e-11, 2e-11, 3e-11)
data = thermo_proc.load_simulation_data("simulation.txt")
processed = thermo_proc.process_complete_analysis(data, "nve")
```

### OVITO Analysis API

```python
from backend.processors import process_dxa_analysis, process_ws_analysis

# DXA dislocation analysis
dxa_success = process_dxa_analysis(
    input_pattern="trajectory*.dump",
    reference_file="perfect_crystal.dump", 
    output_file="dislocation_results.csv",
    frames=[0, 100, 200, 300],  # Specific frames
    gpu_enabled=True
)

# WS vacancy analysis with remote files
ws_success = process_ws_analysis(
    input_pattern="user@server:/path/simulation*.dump",
    reference_file="reference.dump",
    output_file="vacancy_results.csv",
    remote=True,
    sftp_config={'hostname': 'server', 'username': 'user'},
    frames=None  # All frames
)

# GPU configuration for OVITO
from backend.core.ovito_analysis import OvitoGPUConfig
gpu_available = OvitoGPUConfig.setup_gpu(gpu_id=0, buffer_size=4096)
```

## 📊 Input/Output Formats

### Input Files

**Simulation Data (NVE):**
```
step, l_1, l_2, l_3, l_4, l_5, l_6, p_1, p_2, p_3, p_4, p_5, p_6, vol, ep, ek, u, t, rho, entropy
```

**Simulation Data (NVT):**
```
step, l_1, l_2, l_3, l_4, l_5, l_6, p_1, p_2, p_3, p_4, p_5, p_6, vol, ep, ek, u, t, rho, entropy, etally
```

**Elastic Constants:**
```
delta_exx, delta_pxx  # Strain vs stress data
```

### Output Files

**Main Results:** Complete analysis with all calculated quantities
**Summary:** Filtered statistics above strain threshold

## 🔬 Scientific Background

### Elastic Constants
- Calculates 6x6 rigidity matrix from stress-strain relationships
- Inverts to compliance matrix for elastic-plastic decomposition
- Supports cubic crystal symmetry

### Thermomechanical Analysis
- Logarithmic strains for normal components
- Engineering strains for shear components  
- Von Mises equivalent stress/strain
- Work decomposition (elastic vs plastic)
- Energy balance analysis

### Taylor-Quinney Coefficient
- β₀: Heat generation efficiency (differential and integral)
- β₁: Energy storage efficiency (differential and integral)
- Accounts for ensemble differences (NVE vs NVT)

## 🔬 OVITO Integration

The backend now includes complete integration with OVITO for advanced structural analysis:

### DXA (Dislocation Analysis)
- **Dislocation density calculations** with segment tracking
- **Burgers vector analysis** for dislocation characterization
- **Multi-frame trajectory support** for evolution studies
- **GPU acceleration** for high-performance processing

### WS (Wigner-Seitz) Vacancy Analysis
- **Vacancy concentration tracking** over simulation time
- **Structure type identification** using polyhedral template matching
- **Site occupancy analysis** with reference structure comparison
- **Statistical summaries** for vacancy evolution

### OVITO Features
- **Remote SFTP support** for large trajectory files
- **Pattern-based file matching** for batch processing
- **Interactive GPU configuration** with automatic detection
- **Comprehensive result summaries** with frame-by-frame analysis

## 🛠️ Development

### Code Organization
- **config/**: Physical constants, file headers, analysis thresholds
- **core/**: Scientific calculation modules (elastic constants, thermomechanics)
- **processors/**: High-level analysis workflows (NVE/NVT)
- **utils/**: Infrastructure (SFTP, file I/O, mathematical utilities)

### Design Principles
- **Modularity**: Each module has a single responsibility
- **Extensibility**: Easy to add new ensemble types or analysis methods
- **Testability**: Clean interfaces for unit testing
- **Performance**: Vectorized operations using NumPy/Pandas
- **Reliability**: Comprehensive error handling and resource cleanup

## 🔐 Remote Access

### SFTP Configuration
- Interactive authentication with password/OTP support
- Automatic file download and cleanup
- Secure connection management
- URL format: `user@hostname:/path/to/file`

### Security Features
- No password storage
- Temporary file cleanup
- Connection timeout handling
- Authentication retry logic

## 📈 Performance Considerations

- **Memory Efficient**: Streaming file processing where possible
- **Vectorized**: NumPy operations for mathematical calculations
- **Lazy Loading**: Data loaded only when needed
- **Resource Management**: Automatic cleanup of temporary files and connections

## 🧪 Testing

```python
# Unit tests for individual modules
python -m pytest backend/tests/

# Integration tests
python -m pytest backend/tests/integration/

# Performance benchmarks
python -m pytest backend/tests/performance/
```

## 📝 License

This project is part of the OVITO workflow for materials science simulation analysis.

## 🤝 Contributing

1. Follow the modular architecture patterns
2. Add type annotations for all functions
3. Include docstrings with Args/Returns sections  
4. Add unit tests for new functionality
5. Update this README for new features
