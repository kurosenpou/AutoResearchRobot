import sys
import ovito
from ovito.io import import_file, export_file
from ovito.modifiers import DislocationAnalysisModifier
from ovito.data import DislocationNetwork
import paramiko
import getpass
import tempfile
import os
from tqdm import tqdm

# Configuration for path to input files
ARGS = sys.argv[1:3]
if len(ARGS) != 2:  # Check for exactly 2 args
    print("Usage: python3 perform_dxa.py <base_path> <output_file>")
    sys.exit(1)

# Global configuration variables
username = 'u6c204'
password = None
otp = None
base_path = ARGS[0]
reference_remote = f"{base_path}0"  # Append '0' to base path for reference
frames = list(range(0, 500001, 5000))
output_file = ARGS[1]
progress_callback = None

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

def download_with_progress(sftp, remote_path, local_path, desc="Downloading"):
    """Download file with progress bar"""
    try:
        filesize = sftp.stat(remote_path).st_size
        downloaded = 0
        with tqdm(total=filesize, unit='B', unit_scale=True, desc=desc) as pbar:
            def callback(bytes_transferred, _):
                nonlocal downloaded
                delta = bytes_transferred - downloaded
                downloaded = bytes_transferred
                pbar.update(delta)
                if progress_callback:
                    progress_callback(download=(downloaded / filesize) * 100)
            sftp.get(remote_path, local_path, callback=callback)
    except Exception as e:
        raise Exception(f"Download failed: {str(e)}")

def process_dump_file(pipeline, output_index):
    """Process a single dump file with GPU acceleration"""
    if progress_callback:
        progress_callback(processing=0)

    # Force GPU settings through modifier
    dxa_modifier = DislocationAnalysisModifier()
    dxa_modifier.input_crystal_structure = DislocationAnalysisModifier.Lattice.FCC
    pipeline.modifiers.append(dxa_modifier)
    
    if progress_callback:
        progress_callback(processing=50)

    # Compute results
    data = pipeline.compute()
    
    # Get analysis results
    total_line_length = data.attributes['DislocationAnalysis.total_line_length']
    cell_volume = data.attributes['DislocationAnalysis.cell_volume']
    length_12_110 = data.attributes['DislocationAnalysis.length.1/2<110>']
    length_13_100 = data.attributes['DislocationAnalysis.length.1/3<100>']
    length_13_111 = data.attributes['DislocationAnalysis.length.1/3<111>']
    length_16_110 = data.attributes['DislocationAnalysis.length.1/6<110>']
    length_16_112 = data.attributes['DislocationAnalysis.length.1/6<112>']
    length_other = data.attributes['DislocationAnalysis.length.other']
    count_BCC = data.attributes['DislocationAnalysis.counts.BCC']
    count_FCC = data.attributes['DislocationAnalysis.counts.FCC']
    count_HCP = data.attributes['DislocationAnalysis.counts.HCP']
    count_CubicDiamond = data.attributes['DislocationAnalysis.counts.CubicDiamond']
    count_HexagonalDiamond = data.attributes['DislocationAnalysis.counts.HexagonalDiamond']
    count_Other = data.attributes['DislocationAnalysis.counts.OTHER']
    
    if progress_callback:
        progress_callback(processing=100)

    print(f"Frame {output_index} - Dislocation density: {total_line_length / cell_volume}")
    print(f"Frame {output_index} - Found {len(data.dislocations.lines)} dislocation lines")

    return (total_line_length, cell_volume, length_12_110, length_13_100, length_13_111, 
            length_16_110, length_16_112, length_other, count_BCC, count_FCC, count_HCP, 
            count_CubicDiamond, count_HexagonalDiamond, count_Other, len(data.dislocations.lines))
            
def close_file_handles(pipeline):
    """Ensure all file handles are closed"""
    if pipeline:
        pipeline.modifiers.clear()
        pipeline = None

def run_analysis():
    """Main function to run the analysis"""
    ovito.enable_logging()
    check_gpu_status()

    transport = None
    try:
        transport = paramiko.Transport(('squidhpc.hpc.cmc.osaka-u.ac.jp', 22))
        transport.start_client()

        def handler(title, instructions, prompt_list):
            answers = []
            for prompt in prompt_list:
                if any(keyword in prompt[0].lower() for keyword in ['password', 'pass']):
                    answers.append(password)
                elif any(keyword in prompt[0].lower() for keyword in ['verification', 'token', 'otp']):
                    answers.append(otp)
            return answers

        transport.auth_interactive(username, handler)
        sftp = paramiko.SFTPClient.from_transport(transport)
        
        results = []
        progress_bar = tqdm(frames, desc="Processing frames", unit="frame")
        
        for frame in progress_bar:
            remote_path = f"{base_path}{frame}"
            progress_bar.set_description(f"Processing frame {frame}")
            temp_file = None
            
            try:
                temp_file = tempfile.NamedTemporaryFile(delete=False)
                download_with_progress(sftp, remote_path, temp_file.name,
                                    f"Downloading frame {frame}")
                temp_file.close()
                
                pipeline = import_file(temp_file.name, multiple_frames=False)
                result = process_dump_file(pipeline, frame)
                results.append((frame, *result))
                
                close_file_handles(pipeline)
                os.unlink(temp_file.name)
                
            except Exception as frame_error:
                print(f"Error processing frame {frame}: {str(frame_error)}")
                if temp_file and os.path.exists(temp_file.name):
                    try:
                        os.unlink(temp_file.name)
                    except:
                        print(f"Warning: Could not delete temporary file for frame {frame}")
                continue
        
        with open(output_file, 'w') as f:
            f.write("Frame,Total_Length,Volume,Length_1/2<110>,"
            "Length_1/3<100>,Length_1/3<111>,Length_1/6<110>,Length_1/6<112>,"
            "Length_other,Counts_BCC,Counts_FCC,Counts_HCP,Counts_CubicDiamond,"
            "Counts_HexagonalDiamond,Counts_OTHER,Dislocation_Count\n")
            for frame, length, volume, length_perfect, length_loop, length_frank, length_stair_rod, length_shockley, length_other, count_bcc, count_fcc, count_hcp, count_cubicdiamond, count_hexagonaldiamond, count_other, count_dislocation in results:
                f.write(f"{frame},{length},{volume},{length_perfect},{length_loop},{length_frank},{length_stair_rod},{length_shockley},{length_other},{count_bcc},{count_fcc},{count_hcp},{count_cubicdiamond},{count_hexagonaldiamond},{count_other},{count_dislocation}\n")

    except Exception as e:
        print(f"Error during execution: {str(e)}")
        raise
    finally:
        if transport is not None:
            transport.close()
        print("Analysis completed")

if __name__ == "__main__":
    password = getpass.getpass('Enter your password: ')
    otp = input('Enter your one-time password: ')
    run_analysis()