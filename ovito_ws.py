# Vacancy analysis with explicit temporary file control
from ovito.io import import_file
from ovito.modifiers import PolyhedralTemplateMatchingModifier, SelectTypeModifier, DeleteSelectedModifier, WignerSeitzAnalysisModifier
from ovito.pipeline import FileSource
import sys
import paramiko
import getpass
import tempfile
import os
import glob
import ovito
from tqdm import tqdm
import fnmatch

# Enhanced GPU configuration
os.environ['CUDA_VISIBLE_DEVICES'] = '0'  # Use first GPU only
os.environ['OVITO_GPU_ACCELERATION'] = '1'
os.environ['OVITO_DEFAULT_DEVICE'] = 'cuda'
os.environ['OVITO_GPU_BUFFER_SIZE'] = '4096'

def check_gpu_status():
    """Enhanced GPU status check"""
    gpu_enabled = os.environ.get('OVITO_GPU_ACCELERATION') == '1' and \
                  os.environ.get('CUDA_VISIBLE_DEVICES') not in [None, '', '-1']
    print(f"Processing using: {'GPU' if gpu_enabled else 'CPU'}")
    if gpu_enabled:
        print("GPU Configuration:")
        print(f"- Device: {os.environ['OVITO_DEFAULT_DEVICE']}")
        print(f"- Buffer Size: {os.environ['OVITO_GPU_BUFFER_SIZE']}MB")
        print(f"- CUDA Device: {os.environ['CUDA_VISIBLE_DEVICES']}")
    else:
        print("No GPU acceleration enabled")
    return gpu_enabled

# Check command line arguments
if len(sys.argv) != 3:
    print("Usage: python vacancy_controlled.py <sftp_url_pattern> <output_file>")
    print("Example: python vacancy_controlled.py 'u6c204@squidhpc.hpc.cmc.osaka-u.ac.jp:/path/file.*' 'results.csv'")
    sys.exit(1)

sftp_url = sys.argv[1]
output_file = sys.argv[2]

# Parse SFTP URL
if '@' in sftp_url and ':' in sftp_url:
    user_host, remote_path = sftp_url.split(':', 1)
    username, hostname = user_host.split('@', 1)
else:
    print("Error: SFTP URL should be in format 'user@host:/path/pattern'")
    sys.exit(1)

def download_with_progress(sftp, remote_path, local_path, desc="Downloading"):
    """Download file with progress bar and return success status"""
    try:
        filesize = sftp.stat(remote_path).st_size
        downloaded = 0
        with tqdm(total=filesize, unit='B', unit_scale=True, desc=desc) as pbar:
            def callback(bytes_transferred, _):
                nonlocal downloaded
                delta = bytes_transferred - downloaded
                downloaded = bytes_transferred
                pbar.update(delta)
            sftp.get(remote_path, local_path, callback=callback)
        return True
    except Exception as e:
        print(f"Download failed for {remote_path}: {str(e)}")
        return False

def cleanup_temp_files(temp_files):
    """Explicitly clean up temporary files"""
    cleaned_count = 0
    for temp_file in temp_files:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                cleaned_count += 1
                print(f"Cleaned up: {os.path.basename(temp_file)}")
        except Exception as e:
            print(f"Warning: Could not delete {temp_file}: {str(e)}")
    print(f"Cleaned up {cleaned_count} temporary files")

def process_single_file(local_file, frame_number, reference_file=None):
    """Process a single dump file and return results"""
    try:
        # Processing progress bar with multiple steps
        with tqdm(total=100, desc=f"Processing frame {frame_number}", unit="%") as pbar:
            
            # Step 1: Create pipeline and load file
            pbar.set_description(f"Loading frame {frame_number}")
            pipeline = import_file(local_file)
            pbar.update(20)
            
            # Step 2: Add PTM modifier to identify crystal structure (MANDATORY!)
            pbar.set_description(f"Identifying crystal structure for frame {frame_number}")
            ptm_modifier = PolyhedralTemplateMatchingModifier(output_interatomic_distance=True)
            pipeline.modifiers.append(ptm_modifier)
            pbar.update(15)
            
            # Step 3: Select and delete non-crystalline atoms (MANDATORY!)
            pbar.set_description(f"Removing non-crystalline atoms for frame {frame_number}")
            select_modifier = SelectTypeModifier(property='Structure Type', types={0})  # Select "OTHER" type
            pipeline.modifiers.append(select_modifier)
            pbar.update(15)
            
            delete_modifier = DeleteSelectedModifier()
            pipeline.modifiers.append(delete_modifier)
            pbar.update(15)
            
            # Step 4: WignerSeitz analysis with external reference configuration
            pbar.set_description(f"Running vacancy analysis for frame {frame_number}")
            
            ws_modifier = WignerSeitzAnalysisModifier(per_type_occupancies=True)
            
            # CRITICAL FIX: Use external reference file for proper defect detection
            if reference_file and os.path.exists(reference_file):
                print(f"  Using reference file: {os.path.basename(reference_file)}")
                # Create FileSource for reference configuration
                reference_source = FileSource()
                reference_source.load(reference_file)
                ws_modifier.reference = reference_source
            else:
                # Fallback to self-reference (original behavior)
                print("  Warning: No reference file - using self-reference")
                ws_modifier.use_frame_offset = False
                ws_modifier.reference_frame = 0
            
            pipeline.modifiers.append(ws_modifier)
            pbar.update(25)
            
            # Step 5: Compute results
            pbar.set_description(f"Computing results for frame {frame_number}")
            data = pipeline.compute()
            pbar.update(15)
            
            # Step 6: Extract data with better error handling
            pbar.set_description(f"Extracting data for frame {frame_number}")
            frame_number_attr = data.attributes.get('Timestep', frame_number)
            volume = data.cell.volume
            
            # Get vacancy and interstitial counts with fallback
            vacancy_count = data.attributes.get('WignerSeitz.vacancy_count', 0)
            interstitial_count = data.attributes.get('WignerSeitz.interstitial_count', 0)
            
            # Debug output if no defects found
            if vacancy_count == 0 and interstitial_count == 0:
                print(f"INFO: Frame {frame_number} - No defects detected.")
                print(f"  This may indicate a perfect crystal structure.")
                # Show some diagnostic information
                num_particles = len(data.particles.positions)
                print(f"  Analyzed {num_particles} particles, Volume: {volume:.2f}")
            else:
                print(f"  Detected {vacancy_count} vacancies, {interstitial_count} interstitials")
            
            pbar.update(10)
            
            # Clean up pipeline
            pipeline.modifiers.clear()
            pipeline = None
        
        # Print completion message
        print(f"Frame {frame_number_attr} done")
        
        return frame_number_attr, volume, vacancy_count, interstitial_count
        
    except Exception as e:
        print(f"Error processing {local_file}: {str(e)}")
        return None

def interactive_auth(transport, username):
    """Handle keyboard-interactive authentication with 6-digit OTP"""
    def auth_handler(title, instructions, prompt_list):
        responses = []
        if title:
            print(f"\n{title}")
        if instructions:
            print(f"{instructions}")
        
        for i, (prompt, echo) in enumerate(prompt_list):
            # Clean up the prompt for better display
            clean_prompt = prompt.strip()
            
            if echo:
                response = input(f"{clean_prompt}: ")
            else:
                # Check if this looks like an OTP prompt
                if any(keyword in clean_prompt.lower() for keyword in ['verification', 'code', 'token', 'otp', 'authenticator']):
                    print(f"\n📱 Please enter your 6-digit one-time password")
                    response = getpass.getpass(f"{clean_prompt}: ")
                    # Validate OTP format
                    while len(response.strip()) != 6 or not response.strip().isdigit():
                        print("❌ OTP must be exactly 6 digits")
                        response = getpass.getpass(f"{clean_prompt}: ")
                else:
                    response = getpass.getpass(f"{clean_prompt}: ")
            
            responses.append(response.strip())
        
        return responses
    
    try:
        transport.auth_interactive(username, auth_handler)
        print("✅ Authentication successful!")
        return True
    except Exception as e:
        print(f"❌ Interactive authentication failed: {str(e)}")
        return False

def try_authentication(transport, username):
    """Try different authentication methods"""
    # Get available authentication methods
    try:
        auth_methods = transport.auth_none(username)
    except paramiko.BadAuthenticationType as e:
        auth_methods = e.allowed_types
    
    print(f"Available authentication methods: {auth_methods}")
    
    # Try keyboard-interactive first (most common for HPC)
    if 'keyboard-interactive' in auth_methods:
        print("Trying keyboard-interactive authentication...")
        if interactive_auth(transport, username):
            return True
    
    # Try password authentication as fallback
    if 'password' in auth_methods:
        print("Trying password authentication...")
        try:
            password = getpass.getpass(f"Password for {username}: ")
            transport.auth_password(username, password)
            return True
        except Exception as e:
            print(f"Password authentication failed: {str(e)}")
    
    # Try public key authentication
    if 'publickey' in auth_methods:
        print("Trying public key authentication...")
        try:
            transport.auth_publickey(username, paramiko.RSAKey.from_private_key_file(os.path.expanduser('~/.ssh/id_rsa')))
            return True
        except Exception as e:
            print(f"Public key authentication failed: {str(e)}")
    
    return False

def run_analysis():
    """Main analysis with explicit file management"""
    ovito.enable_logging()
    check_gpu_status()
    
    transport = None
    sftp = None
    temp_files = []
    temp_dir = None
    reference_file = None
    
    try:
        print(f"Connecting to {hostname}...")
        transport = paramiko.Transport((hostname, 22))
        transport.connect()
        
        # Try different authentication methods
        print("Authenticating...")
        if not try_authentication(transport, username):
            print("All authentication methods failed")
            return
            
        sftp = paramiko.SFTPClient.from_transport(transport)
        
        print(f"Looking for files matching: {remote_path}")
        
        # Get directory and pattern
        remote_dir = os.path.dirname(remote_path)
        pattern = os.path.basename(remote_path)
        
        # List matching files
        try:
            if sftp is not None:
                file_list = sftp.listdir(remote_dir)
                matching_files = [f for f in file_list if fnmatch.fnmatch(f, pattern)]
                matching_files.sort()
                
                if not matching_files:
                    print(f"No files found matching pattern: {pattern}")
                    return
                    
                print(f"Found {len(matching_files)} matching files")
            else:
                print("Error: SFTP connection not established")
                return
            
        except Exception as e:
            print(f"Error listing remote directory: {str(e)}")
            return
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix="ovito_vacancy_")
        print(f"Using temporary directory: {temp_dir}")
        
        # CRITICAL: Download reference file (.0 file) first
        reference_filename = None
        for filename in matching_files:
            if filename.endswith('.0'):
                reference_filename = filename
                break
        
        if reference_filename:
            print(f"\n🔍 Downloading reference file: {reference_filename}")
            remote_ref_path = f"{remote_dir}/{reference_filename}"
            reference_file = os.path.join(temp_dir, reference_filename)
            
            if download_with_progress(sftp, remote_ref_path, reference_file, f"Downloading reference {reference_filename}"):
                temp_files.append(reference_file)
                print(f"✅ Reference file downloaded: {reference_filename}")
            else:
                print(f"❌ Failed to download reference file: {reference_filename}")
                return
        else:
            print("❌ No .0 reference file found in the file list!")
            print("Available files:", [f for f in matching_files[:5]])  # Show first 5 files
            return
        
        # Open output file
        with open(output_file, 'w') as f:
            # Write header
            f.write("Frame,Volume,Vacancy_Count,Interstitial_Count\n")
            
            # Process each file individually
            for i, filename in enumerate(matching_files):
                remote_file_path = f"{remote_dir}/{filename}"
                local_file_path = os.path.join(temp_dir, filename)
                
                print(f"\nProcessing file {i+1}/{len(matching_files)}: {filename}")
                
                # Skip reference file if we're processing it again
                if filename == reference_filename:
                    print(f"  Skipping reference file {filename} (already downloaded)")
                    # Process the reference file
                    result = process_single_file(reference_file, i, reference_file)
                    
                    if result:
                        frame_number, volume, vacancy_count, interstitial_count = result
                        f.write(f"{frame_number},{volume},{vacancy_count},{interstitial_count}\n")
                        print(f"Frame {frame_number}: Volume={volume:.6f}, Vacancies={vacancy_count}, Interstitials={interstitial_count}")
                    continue
                
                # Download file
                if download_with_progress(sftp, remote_file_path, local_file_path, f"Downloading {filename}"):
                    temp_files.append(local_file_path)
                    
                    # Process file with reference
                    result = process_single_file(local_file_path, i, reference_file)
                    
                    if result:
                        frame_number, volume, vacancy_count, interstitial_count = result
                        f.write(f"{frame_number},{volume},{vacancy_count},{interstitial_count}\n")
                        print(f"Frame {frame_number}: Volume={volume:.6f}, Vacancies={vacancy_count}, Interstitials={interstitial_count}")
                    
                    # Immediately clean up this file to save disk space
                    try:
                        os.remove(local_file_path)
                        temp_files.remove(local_file_path)
                        print(f"Cleaned up: {filename}")
                    except Exception as e:
                        print(f"Warning: Could not immediately delete {local_file_path}: {str(e)}")
                else:
                    print(f"Skipping {filename} due to download failure")
        
        print(f"\nAnalysis completed! Results written to {output_file}")
        
    except Exception as e:
        print(f"Error during execution: {str(e)}")
        raise
    finally:
        # Clean up any remaining temporary files
        if temp_files:
            print(f"\nCleaning up {len(temp_files)} remaining temporary files...")
            cleanup_temp_files(temp_files)
        
        # Clean up temp directory
        try:
            if temp_dir is not None and os.path.exists(temp_dir):
                os.rmdir(temp_dir)
                print(f"Removed temporary directory: {temp_dir}")
        except Exception as e:
            if temp_dir is not None:
                print(f"Warning: Could not remove temp directory {temp_dir}: {str(e)}")
        
        # Close connections
        if sftp:
            sftp.close()
        if transport:
            transport.close()

if __name__ == "__main__":
    print("Starting controlled vacancy analysis with explicit cleanup...")
    run_analysis()
