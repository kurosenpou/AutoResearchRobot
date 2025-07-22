# Simulation Manager - Complete MD Workflow Documentation

## Overview

The Simulation Manager provides a complete end-to-end workflow for running molecular dynamics simulations on remote HPC servers. It automates the entire process from uploading input files to downloading and analyzing results.

## Features

### 🚀 Complete Workflow Automation
- **File Upload**: Automatically uploads required input files to remote HPC server
- **Job Submission**: Submits simulation job using `qsub` command
- **Progress Monitoring**: Checks for simulation completion every hour by looking for `restart.relax` file
- **Results Download**: Downloads simulation results including output files and shear directory
- **Automatic Analysis**: Runs NVE/NVT, WS, and DXA analyses on the results

### 📁 Required Input Files
The local directory must contain these files:
- **`*.lmp`**: LAMMPS structure file
- **`in.*.lammps`**: LAMMPS input script
- **`run.*.sh`**: Job submission script for HPC scheduler
- **`dbg.*.sh`**: Debug script

### 🔬 Automatic Analyses
After simulation completion, the following analyses are performed:
1. **NVE/NVT Analysis**: Uses `*d2-*.txt` files from simulation output
2. **Wigner-Seitz (WS) Analysis**: Uses `shear/3.dump.shear-II.*` files for vacancy analysis
3. **DXA Analysis**: Uses `shear/3.dump.shear-II.*` files for dislocation analysis

## Usage

### Command Line Interface

```bash
python main.py simulate LOCAL_PATH REMOTE_PATH NVE_OUTPUT WS_OUTPUT DXA_OUTPUT [--config CONFIG]
```

**Arguments:**
- `LOCAL_PATH`: Local directory containing input files
- `REMOTE_PATH`: Remote directory to upload files to
- `NVE_OUTPUT`: Output file for NVE/NVT analysis results
- `WS_OUTPUT`: Output file for WS vacancy analysis results  
- `DXA_OUTPUT`: Output file for DXA dislocation analysis results
- `--config`: Optional SFTP configuration file (JSON format)

### Examples

#### Basic Usage
```bash
python main.py simulate ./simulation_input/ /home/user/simulation001/ nve_results.csv ws_results.csv dxa_results.csv
```

#### With Configuration File
```bash
python main.py simulate ./local_files/ /hpc/user/sim001/ nve.csv ws.csv dxa.csv --config sftp_config.json
```

### SFTP Configuration

#### Interactive Configuration
If no config file is provided, the system will prompt for:
- Hostname (e.g., `squid.hpc.cmc.osaka-u.ac.jp`)
- Username
- Authentication method (SSH key or password)

#### Configuration File Format
Create a JSON file with SFTP connection details:

```json
{
    "hostname": "squid.hpc.cmc.osaka-u.ac.jp",
    "username": "your_username",
    "key_filename": "/path/to/ssh/key"
}
```

Or for password authentication:
```json
{
    "hostname": "squid.hpc.cmc.osaka-u.ac.jp", 
    "username": "your_username",
    "password": "your_password"
}
```

## Workflow Details

### 1. File Upload Phase
- Connects to remote HPC server via SSH/SFTP
- Creates remote directory structure
- Uploads all required input files:
  - `*.lmp` - LAMMPS structure file
  - `in.*.lammps` - LAMMPS input script  
  - `run.*.sh` - Job submission script
  - `dbg.*.sh` - Debug script

### 2. Job Submission Phase
- Locates `run.*.sh` file in remote directory
- Executes `qsub run.*.sh` command to submit job
- Captures and reports job ID for monitoring

### 3. Monitoring Phase
- Checks for `restart.relax` file every hour (3600 seconds)
- Provides progress updates with check count
- Continues until simulation completes

### 4. Results Download Phase
- Downloads `restart.relax` file (completion indicator)
- Downloads all `*d2-*.txt` files (simulation output data)
- Recursively downloads `shear/` directory with all contents
- Creates local `simulation_results/` directory

### 5. Analysis Phase
- **NVE/NVT Analysis**: Processes first `*d2-*.txt` file found
- **WS Analysis**: Analyzes `shear/3.dump.shear-II.*` files for vacancies
- **DXA Analysis**: Analyzes `shear/3.dump.shear-II.*` files for dislocations
- Generates CSV output files and summary reports

## Output Files

### Simulation Results Directory Structure
```
simulation_results/
├── restart.relax                    # Completion indicator
├── output1_d2-data.txt             # Simulation output data
├── output2_d2-data.txt             # Additional output files
└── shear/                          # Shear analysis directory
    ├── 3.dump.shear-II.0           # Trajectory files
    ├── 3.dump.shear-II.1000        # for OVITO analysis
    └── ...
```

### Analysis Output Files
- **`nve_results.csv`**: NVE/NVT thermomechanical analysis results
- **`ws_results.csv`**: Vacancy concentration and structural analysis
- **`dxa_results.csv`**: Dislocation density and evolution data
- **`*_summary.txt`**: Summary statistics for each analysis

## HPC Server Integration

### Osaka University HPC (Squid)
Based on the manual: https://www.hpc.cmc.osaka-u.ac.jp/system/manual/squid-use/transfer/

**Connection Example:**
```bash
# Manual connection for reference
sftp username@squid.hpc.cmc.osaka-u.ac.jp
```

**Job Submission:**
```bash
# The system automatically runs this command
qsub run.*.sh
```

### Job Script Requirements
Your `run.*.sh` file should be compatible with the HPC scheduler and include:
- Proper resource allocation directives
- LAMMPS execution commands
- Output file generation instructions

## Error Handling

### Connection Issues
- Automatic retry for transient network errors
- Clear error messages for authentication failures
- Graceful handling of SSH key and password authentication

### File Transfer Issues  
- Validation of required input files before upload
- Detailed logging of upload/download progress
- Error reporting for missing or corrupted files

### Simulation Monitoring
- Timeout handling for long-running simulations
- Clear progress indicators with check counts
- Automatic detection of simulation completion

### Analysis Issues
- Graceful degradation if individual analyses fail
- Detailed error reporting for missing dependencies
- Continuation of workflow even if some analyses fail

## Dependencies

### Required Packages
```bash
pip install paramiko pandas numpy scipy tqdm
```

### Optional Packages (for OVITO analysis)
```bash
pip install ovito
```

### System Requirements
- Python 3.7+
- SSH client access to remote HPC server
- Sufficient local storage for results download

## Troubleshooting

### Common Issues

**Authentication Failures:**
- Verify SSH key permissions (`chmod 600 ~/.ssh/id_rsa`)
- Check hostname and username spelling
- Ensure 2FA/OTP codes are entered correctly

**File Upload Failures:**
- Verify input files exist and have correct naming patterns
- Check remote directory permissions
- Ensure sufficient disk space on remote server

**Job Submission Issues:**
- Verify `run.*.sh` script has execute permissions
- Check HPC queue status and resource availability
- Validate job script syntax for target scheduler

**Analysis Failures:**
- Install OVITO for DXA and WS analyses: `pip install ovito`
- Verify output file formats match expected structure
- Check for sufficient local disk space

### Monitoring Tips

**Check Simulation Status:**
- Log into HPC server manually to check job queue: `qstat`
- Verify simulation is progressing by checking output files
- Monitor resource usage to ensure job isn't stalled

**Performance Optimization:**
- Use SSH key authentication for faster connections
- Enable GPU acceleration for OVITO analyses (default)
- Consider adjusting monitoring interval for shorter simulations

## Example Workflow

### 1. Prepare Input Files
```bash
# Create local directory with required files
mkdir simulation_input
cd simulation_input

# Create or copy required files:
# - structure.lmp (LAMMPS structure)
# - in.simulation.lammps (LAMMPS input script)
# - run.simulation.sh (HPC job script)
# - dbg.simulation.sh (Debug script)
```

### 2. Create SFTP Configuration
```bash
# sftp_config.json
{
    "hostname": "squid.hpc.cmc.osaka-u.ac.jp",
    "username": "your_username",
    "key_filename": "~/.ssh/id_rsa"
}
```

### 3. Run Complete Workflow
```bash
python main.py simulate \
    ./simulation_input/ \
    /home/username/simulation_001/ \
    nve_analysis.csv \
    vacancy_analysis.csv \
    dislocation_analysis.csv \
    --config sftp_config.json
```

### 4. Monitor Progress
The system will display:
- Upload progress for each file
- Job submission confirmation with job ID
- Hourly monitoring updates
- Download progress for results
- Analysis completion status

### 5. Review Results
Check output files:
- `nve_analysis.csv` - Thermomechanical properties
- `vacancy_analysis.csv` - Vacancy concentrations
- `dislocation_analysis.csv` - Dislocation densities
- `simulation_results/` - Complete downloaded results

This automated workflow eliminates manual file management and provides comprehensive analysis of MD simulation results with minimal user intervention.
