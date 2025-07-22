#!/usr/bin/env python3
"""
Simulation Manager Processor
Manages complete MD simulation workflow from upload to analysis on remote HPC servers
"""

import os
import sys
import time
import glob
import subprocess
from typing import List, Optional, Dict, Tuple, Union
from pathlib import Path
import paramiko
from paramiko import SSHClient, SFTPClient
import logging

# Add parent directory for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from ..core.ovito_analysis import OVITO_AVAILABLE
    from ..utils.sftp_utils import SFTPManager
    from ..utils.ensemble_detector import detect_simulation_ensemble
    from .nve_processor import process_nve_simulation
    from .nvt_processor import process_nvt_simulation
    from .ws_processor import process_ws_analysis
    from .dxa_processor import process_dxa_analysis
except ImportError:
    try:
        from core.ovito_analysis import OVITO_AVAILABLE
        from utils.sftp_utils import SFTPManager
        from utils.ensemble_detector import detect_simulation_ensemble
        from nve_processor import process_nve_simulation
        from nvt_processor import process_nvt_simulation
        from ws_processor import process_ws_analysis
        from dxa_processor import process_dxa_analysis
    except ImportError:
        from backend.core.ovito_analysis import OVITO_AVAILABLE
        from backend.utils.sftp_utils import SFTPManager
        from backend.utils.ensemble_detector import detect_simulation_ensemble
        from backend.processors.nve_processor import process_nve_simulation
        from backend.processors.nvt_processor import process_nvt_simulation
        from backend.processors.ws_processor import process_ws_analysis
        from backend.processors.dxa_processor import process_dxa_analysis

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimulationManager:
    """
    Manages complete MD simulation workflow on remote HPC servers
    """
    
    def __init__(self, sftp_config: Dict):
        """
        Initialize simulation manager
        
        Args:
            sftp_config: SFTP configuration for remote server connection
        """
        self.sftp_config = sftp_config
        self.ssh_client: Optional[SSHClient] = None
        self.sftp_client: Optional[SFTPClient] = None
        self.connected = False
        
    def connect(self) -> bool:
        """
        Establish SSH/SFTP connection to remote server
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Extract connection parameters
            hostname = self.sftp_config['hostname']
            username = self.sftp_config['username']
            port = self.sftp_config.get('port', 22)
            
            # Connect with key or password
            if 'key_filename' in self.sftp_config:
                self.ssh_client.connect(
                    hostname=hostname,
                    username=username,
                    port=port,
                    key_filename=self.sftp_config['key_filename']
                )
            elif 'password' in self.sftp_config:
                self.ssh_client.connect(
                    hostname=hostname,
                    username=username,
                    port=port,
                    password=self.sftp_config['password']
                )
            else:
                # Try with agent or default keys
                self.ssh_client.connect(
                    hostname=hostname,
                    username=username,
                    port=port
                )
            
            self.sftp_client = self.ssh_client.open_sftp()
            self.connected = True
            logger.info(f"✅ Connected to {hostname}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to remote server: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Close SSH/SFTP connections"""
        if self.sftp_client:
            self.sftp_client.close()
        if self.ssh_client:
            self.ssh_client.close()
        self.connected = False
        logger.info("🔌 Disconnected from remote server")
    
    def upload_simulation_files(self, local_path: str, remote_path: str) -> bool:
        """
        Upload simulation files to remote server
        
        Args:
            local_path: Local directory containing simulation files
            remote_path: Remote directory to create and upload files to
            
        Returns:
            True if upload successful, False otherwise
        """
        if not self.connected or not self.sftp_client:
            logger.error("❌ Not connected to remote server")
            return False
        
        try:
            logger.info(f"📤 Uploading files from {local_path} to {remote_path}")
            
            # Create remote directory
            self._create_remote_directory(remote_path)
            
            # Find required files
            required_patterns = ['*.lmp', 'in.*.lammps', 'run.*.sh', 'dbg.*.sh']
            uploaded_files = []
            
            for pattern in required_patterns:
                files = glob.glob(os.path.join(local_path, pattern))
                if not files:
                    logger.warning(f"⚠️ No files found matching pattern: {pattern}")
                    continue
                
                for local_file in files:
                    filename = os.path.basename(local_file)
                    remote_file = f"{remote_path}/{filename}"
                    
                    logger.info(f"📁 Uploading {filename}...")
                    self.sftp_client.put(local_file, remote_file)
                    uploaded_files.append(filename)
            
            if not uploaded_files:
                logger.error("❌ No files were uploaded")
                return False
            
            logger.info(f"✅ Successfully uploaded {len(uploaded_files)} files:")
            for filename in uploaded_files:
                logger.info(f"  📄 {filename}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to upload files: {e}")
            return False
    
    def _create_remote_directory(self, remote_path: str):
        """Create remote directory recursively"""
        if not self.sftp_client:
            return
        
        try:
            self.sftp_client.mkdir(remote_path)
        except IOError:
            # Directory might already exist or parent doesn't exist
            parent = os.path.dirname(remote_path)
            if parent and parent != remote_path:
                self._create_remote_directory(parent)
                try:
                    self.sftp_client.mkdir(remote_path)
                except IOError:
                    pass  # Directory might already exist
    
    def submit_job(self, remote_path: str) -> Optional[str]:
        """
        Submit simulation job using qsub
        
        Args:
            remote_path: Remote directory containing job files
            
        Returns:
            Job ID if submission successful, None otherwise
        """
        if not self.connected or not self.ssh_client:
            logger.error("❌ Not connected to remote server")
            return None
        
        try:
            # Find run.*.sh file
            stdin, stdout, stderr = self.ssh_client.exec_command(f"ls {remote_path}/run.*.sh")
            run_files = stdout.read().decode().strip().split('\n')
            
            if not run_files or not run_files[0]:
                logger.error("❌ No run.*.sh file found")
                return None
            
            run_script = run_files[0]
            logger.info(f"🚀 Submitting job: {run_script}")
            
            # Change to remote directory and submit job
            command = f"cd {remote_path} && qsub {os.path.basename(run_script)}"
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            
            job_output = stdout.read().decode().strip()
            error_output = stderr.read().decode().strip()
            
            if error_output:
                logger.error(f"❌ Job submission error: {error_output}")
                return None
            
            # Extract job ID (typically format: job_id.hostname)
            job_id = job_output.split('.')[0] if job_output else None
            
            if job_id:
                logger.info(f"✅ Job submitted successfully. Job ID: {job_id}")
                return job_id
            else:
                logger.error(f"❌ Failed to extract job ID from: {job_output}")
                return None
            
        except Exception as e:
            logger.error(f"❌ Failed to submit job: {e}")
            return None
    
    def check_simulation_completion(self, remote_path: str) -> bool:
        """
        Check if simulation is completed by looking for restart.relax file
        
        Args:
            remote_path: Remote directory to check
            
        Returns:
            True if simulation completed, False otherwise
        """
        if not self.connected or not self.sftp_client:
            return False
        
        try:
            restart_file = f"{remote_path}/restart.relax"
            self.sftp_client.stat(restart_file)
            return True
        except IOError:
            return False
    
    def monitor_simulation(self, remote_path: str, job_id: str, check_interval: int = 3600) -> bool:
        """
        Monitor simulation progress by checking for completion file
        
        Args:
            remote_path: Remote directory to monitor
            job_id: Job ID for reference
            check_interval: Check interval in seconds (default: 1 hour)
            
        Returns:
            True when simulation completes, False if monitoring fails
        """
        logger.info(f"👁️ Monitoring simulation (Job ID: {job_id})")
        logger.info(f"🕐 Checking every {check_interval//60} minutes for restart.relax file")
        
        check_count = 0
        while True:
            check_count += 1
            logger.info(f"🔍 Check #{check_count}: Looking for restart.relax...")
            
            if self.check_simulation_completion(remote_path):
                logger.info("✅ Simulation completed! restart.relax file found")
                return True
            
            logger.info(f"⏳ Simulation still running. Next check in {check_interval//60} minutes")
            time.sleep(check_interval)
    
    def download_results(self, remote_path: str, local_download_path: str) -> bool:
        """
        Download simulation results from remote server
        
        Args:
            remote_path: Remote directory containing results
            local_download_path: Local directory to download results to
            
        Returns:
            True if download successful, False otherwise
        """
        if not self.connected or not self.sftp_client or not self.ssh_client:
            logger.error("❌ Not connected to remote server")
            return False
        
        try:
            logger.info(f"📥 Downloading results from {remote_path}")
            
            # Create local download directory
            os.makedirs(local_download_path, exist_ok=True)
            
            # Download restart.relax file
            restart_file = f"{remote_path}/restart.relax"
            local_restart = os.path.join(local_download_path, "restart.relax")
            self.sftp_client.get(restart_file, local_restart)
            logger.info("📄 Downloaded restart.relax")
            
            # Download *d2-*.txt files
            stdin, stdout, stderr = self.ssh_client.exec_command(f"ls {remote_path}/*d2-*.txt")
            d2_files = stdout.read().decode().strip().split('\n')
            
            for d2_file in d2_files:
                if d2_file:
                    filename = os.path.basename(d2_file)
                    local_file = os.path.join(local_download_path, filename)
                    self.sftp_client.get(d2_file, local_file)
                    logger.info(f"📄 Downloaded {filename}")
            
            # Download shear directory
            shear_remote = f"{remote_path}/shear"
            shear_local = os.path.join(local_download_path, "shear")
            self._download_directory_recursive(shear_remote, shear_local)
            
            logger.info("✅ Results downloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to download results: {e}")
            return False
    
    def _download_directory_recursive(self, remote_dir: str, local_dir: str):
        """Recursively download directory contents"""
        if not self.sftp_client:
            return
            
        try:
            os.makedirs(local_dir, exist_ok=True)
            
            for item in self.sftp_client.listdir_attr(remote_dir):
                remote_item = f"{remote_dir}/{item.filename}"
                local_item = os.path.join(local_dir, item.filename)
                
                if hasattr(item, 'st_mode') and item.st_mode and (item.st_mode & 0o040000):  # Directory
                    self._download_directory_recursive(remote_item, local_item)
                else:  # File
                    self.sftp_client.get(remote_item, local_item)
                    logger.info(f"📄 Downloaded {item.filename}")
                    
        except Exception as e:
            logger.warning(f"⚠️ Error downloading directory {remote_dir}: {e}")


def detect_ensemble_type(data_file: str) -> str:
    """
    Detect ensemble type (NVE or NVT) based on presence of etally column
    
    Args:
        data_file: Path to simulation data file
        
    Returns:
        'nve' if no etally column found, 'nvt' if etally column present
    """
    return detect_simulation_ensemble(data_file, verbose=True)


def run_complete_simulation_workflow(local_path: str, remote_path: str, 
                                   nve_output: str, ws_output: str, dxa_output: str,
                                   sftp_config: Dict) -> bool:
    """
    Run complete simulation workflow from upload to analysis
    
    Args:
        local_path: Local directory containing input files
        remote_path: Remote directory to upload files to
        nve_output: Output file for NVE/NVT analysis
        ws_output: Output file for WS analysis
        dxa_output: Output file for DXA analysis
        sftp_config: SFTP configuration for remote connection
        
    Returns:
        True if workflow completed successfully, False otherwise
    """
    
    print("🎯 Starting Complete Simulation Workflow")
    print("=" * 60)
    
    # Validate input files
    if not validate_input_files(local_path):
        return False
    
    # Initialize simulation manager
    sim_manager = SimulationManager(sftp_config)
    
    try:
        # Step 1: Connect to remote server
        print("\n📡 Step 1: Connecting to remote server...")
        if not sim_manager.connect():
            return False
        
        # Step 2: Upload simulation files
        print("\n📤 Step 2: Uploading simulation files...")
        if not sim_manager.upload_simulation_files(local_path, remote_path):
            return False
        
        # Step 3: Submit job
        print("\n🚀 Step 3: Submitting simulation job...")
        job_id = sim_manager.submit_job(remote_path)
        if not job_id:
            return False
        
        # Step 4: Monitor simulation
        print("\n👁️ Step 4: Monitoring simulation progress...")
        if not sim_manager.monitor_simulation(remote_path, job_id):
            return False
        
        # Step 5: Download results
        print("\n📥 Step 5: Downloading simulation results...")
        download_path = os.path.join(os.path.dirname(local_path), "simulation_results")
        if not sim_manager.download_results(remote_path, download_path):
            return False
        
        # Step 6: Run NVE/NVT analysis
        print("\n🔬 Step 6: Running NVE/NVT analysis...")
        d2_files = glob.glob(os.path.join(download_path, "*d2-*.txt"))
        if d2_files:
            # Use first d2 file found
            d2_file = d2_files[0]
            
            # Detect ensemble type based on data format
            ensemble_type = detect_ensemble_type(d2_file)
            
            if ensemble_type == 'nvt':
                print("🌡️ Using NVT processor for analysis...")
                analysis_success = process_nvt_simulation(
                    simulation_file=d2_file,
                    output_file=nve_output
                )
            else:
                print("⚙️ Using NVE processor for analysis...")
                analysis_success = process_nve_simulation(
                    simulation_file=d2_file,
                    output_file=nve_output
                )
            
            if not analysis_success:
                logger.warning(f"⚠️ {ensemble_type.upper()} analysis failed")
        else:
            logger.warning("⚠️ No *d2-*.txt files found for NVE/NVT analysis")
        
        # Step 7: Run WS analysis
        print("\n🔬 Step 7: Running Wigner-Seitz analysis...")
        shear_files = glob.glob(os.path.join(download_path, "shear", "3.dump.shear-II.*"))
        if shear_files:
            # Use pattern for WS analysis
            shear_pattern = os.path.join(download_path, "shear", "3.dump.shear-II.*")
            # Need reference file - could be the initial structure
            reference_file = d2_files[0] if d2_files else shear_files[0]
            
            ws_success = process_ws_analysis(
                input_pattern=shear_pattern,
                reference_file=reference_file,
                output_file=ws_output,
                remote=False
            )
            if not ws_success:
                logger.warning("⚠️ WS analysis failed")
        else:
            logger.warning("⚠️ No shear files found for WS analysis")
            shear_pattern = None
            reference_file = d2_files[0] if d2_files else None
        
        # Step 8: Run DXA analysis
        print("\n🔬 Step 8: Running DXA analysis...")
        if shear_files and shear_pattern and reference_file:
            dxa_success = process_dxa_analysis(
                input_pattern=shear_pattern,
                reference_file=reference_file,
                output_file=dxa_output,
                remote=False
            )
            if not dxa_success:
                logger.warning("⚠️ DXA analysis failed")
        else:
            logger.warning("⚠️ No shear files found for DXA analysis")
        
        print("\n✅ Complete simulation workflow finished!")
        print(f"📊 Results available in: {download_path}")
        print(f"📄 NVE/NVT output: {nve_output}")
        print(f"📄 WS output: {ws_output}")
        print(f"📄 DXA output: {dxa_output}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Workflow failed: {e}")
        return False
        
    finally:
        sim_manager.disconnect()


def validate_input_files(local_path: str) -> bool:
    """
    Validate that required input files are present
    
    Args:
        local_path: Local directory to check
        
    Returns:
        True if all required files present, False otherwise
    """
    required_patterns = ['*.lmp', 'in.*.lammps', 'run.*.sh', 'dbg.*.sh']
    
    print(f"🔍 Validating input files in {local_path}...")
    
    for pattern in required_patterns:
        files = glob.glob(os.path.join(local_path, pattern))
        if not files:
            print(f"❌ Missing required file matching pattern: {pattern}")
            return False
        else:
            print(f"✅ Found {len(files)} file(s) matching {pattern}")
    
    return True


def create_sftp_config_interactive() -> Dict:
    """
    Create SFTP configuration interactively
    
    Returns:
        SFTP configuration dictionary
    """
    print("🔐 HPC Server Connection Configuration")
    print("=" * 40)
    
    hostname = input("Hostname (e.g., squid.hpc.cmc.osaka-u.ac.jp): ").strip()
    username = input("Username: ").strip()
    
    auth_method = input("Authentication method (1: SSH key, 2: Password): ").strip()
    
    config = {
        'hostname': hostname,
        'username': username
    }
    
    if auth_method == "1":
        key_path = input("SSH key file path (press Enter for default): ").strip()
        if key_path:
            config['key_filename'] = key_path
    elif auth_method == "2":
        import getpass
        password = getpass.getpass("Password: ")
        config['password'] = password
    
    return config


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Complete MD Simulation Workflow Manager")
    parser.add_argument("local_path", help="Local directory containing input files")
    parser.add_argument("remote_path", help="Remote directory to upload files to")
    parser.add_argument("nve_output", help="Output file for NVE/NVT analysis")
    parser.add_argument("ws_output", help="Output file for WS analysis")
    parser.add_argument("dxa_output", help="Output file for DXA analysis")
    parser.add_argument("--config", help="SFTP config file (JSON format)")
    
    args = parser.parse_args()
    
    # Get SFTP configuration
    if args.config and os.path.exists(args.config):
        import json
        with open(args.config, 'r') as f:
            sftp_config = json.load(f)
    else:
        sftp_config = create_sftp_config_interactive()
    
    # Run workflow
    success = run_complete_simulation_workflow(
        local_path=args.local_path,
        remote_path=args.remote_path,
        nve_output=args.nve_output,
        ws_output=args.ws_output,
        dxa_output=args.dxa_output,
        sftp_config=sftp_config
    )
    
    sys.exit(0 if success else 1)
