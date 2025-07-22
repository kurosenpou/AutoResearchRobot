#!/usr/bin/env python3
"""
Elastic constant calculations - Python version
Importing elastic constant data and calculating elastic constants
Supports both local files and remote SFTP access
Supports both CSV and TXT input files

Usage Examples:
  Local files (default):
    python elastic_constant.py
    (requires c1144.txt, c2255.txt, c3366.txt, c1144r.txt, c2255r.txt, c3366r.txt in current directory)
  
  Remote SFTP files:
    python elastic_constant.py user@server:/path/to/elastic/files/
    (will download and process remote files with the same names)

Requirements:
  - For remote access: paramiko library (pip install paramiko)
  - Elastic constant data files: c1144.txt, c2255.txt, c3366.txt, c1144r.txt, c2255r.txt, c3366r.txt
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
import paramiko
import getpass
import tempfile
import os
import sys
import argparse

def is_remote_path(path):
    """Check if the path is a remote SFTP URL"""
    return '@' in path and ':' in path

def download_file_from_sftp(sftp_url, local_path):
    """Download file from SFTP server"""
    # Parse SFTP URL (user@host:/path/file)
    if '@' in sftp_url and ':' in sftp_url:
        user_host, remote_path = sftp_url.split(':', 1)
        username, hostname = user_host.split('@', 1)
    else:
        raise ValueError("SFTP URL should be in format 'user@host:/path/file'")
    
    transport = None
    try:
        print(f"Connecting to {hostname}...")
        transport = paramiko.Transport((hostname, 22))
        transport.connect()
        
        # Interactive authentication
        def auth_handler(title, instructions, prompt_list):
            responses = []
            if title:
                print(f"\n{title}")
            if instructions:
                print(f"{instructions}")
            
            for prompt, echo in prompt_list:
                clean_prompt = prompt.strip()
                if echo:
                    response = input(f"{clean_prompt}: ")
                else:
                    if any(keyword in clean_prompt.lower() for keyword in ['verification', 'code', 'token', 'otp', 'authenticator']):
                        print(f"\n📱 Please enter your 6-digit one-time password")
                        response = getpass.getpass(f"{clean_prompt}: ")
                        while len(response.strip()) != 6 or not response.strip().isdigit():
                            print("❌ OTP must be exactly 6 digits")
                            response = getpass.getpass(f"{clean_prompt}: ")
                    else:
                        response = getpass.getpass(f"{clean_prompt}: ")
                responses.append(response.strip())
            return responses
        
        transport.auth_interactive(username, auth_handler)
        sftp = paramiko.SFTPClient.from_transport(transport)
        
        print(f"Downloading {remote_path}...")
        if sftp is not None:
            sftp.get(remote_path, local_path)
            print(f"Downloaded to {local_path}")
            sftp.close()
        else:
            raise Exception("Failed to create SFTP client")
        
        return True
        
    except Exception as e:
        print(f"Error downloading file: {str(e)}")
        return False
    finally:
        if transport:
            transport.close()

def read_elastic_file(file_path, headers):
    """Read elastic constant file, supporting both local and remote paths, CSV and TXT formats"""
    temp_file = None
    
    try:
        if is_remote_path(file_path):
            # Download from remote server
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_file.close()
            
            if not download_file_from_sftp(file_path, temp_file.name):
                raise Exception(f"Failed to download remote file: {file_path}")
            
            local_path = temp_file.name
        else:
            # Use local file
            local_path = file_path
        
        # Determine file format and read accordingly
        if local_path.lower().endswith('.csv'):
            # CSV format
            data = pd.read_csv(local_path, comment="#", names=headers)
        else:
            # TXT format (space-delimited)
            data = pd.read_csv(local_path, delim_whitespace=True, comment="#", names=headers)
        
        return data
        
    finally:
        # Clean up temporary file if it was created
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except Exception as e:
                print(f"Warning: Could not delete temporary file: {e}")

# Check if running as main script with arguments for remote files
def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Elastic Constant Calculations - Python Version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Local files (default):
    python elastic_constant.py
    (requires c1144.txt, c2255.txt, c3366.txt, c1144r.txt, c2255r.txt, c3366r.txt in current directory)
  
  Remote SFTP files:
    python elastic_constant.py user@server:/path/to/elastic/files/
    (will download and process remote files with the same names)
  
  With custom strain threshold:
    python elastic_constant.py --threshold 0.001
  
  Remote files with custom threshold:
    python elastic_constant.py user@server:/path/files/ --threshold 0.0015

File Requirements:
  The following elastic constant data files are required:
  - c1144.txt, c2255.txt, c3366.txt (forward loading)
  - c1144r.txt, c2255r.txt, c3366r.txt (reverse loading)
  
  Files can be in CSV or TXT format with the following columns:
  delta_exx, delta_eyy, delta_ezz, delta_exy, delta_eyz, delta_exz,
  delta_pxx, delta_pyy, delta_pzz, delta_pxy, delta_pyz, delta_pxz

Dependencies:
  - pandas, numpy, scikit-learn (always required)
  - paramiko (required for remote SFTP access: pip install paramiko)
        """
    )
    
    parser.add_argument(
        'path', 
        nargs='?', 
        default='',
        help='Base path for elastic constant files. For remote files, use format: user@server:/path/to/files/ (default: current directory)'
    )
    
    parser.add_argument(
        '--threshold', 
        type=float, 
        default=0.002,
        help='Strain threshold for filtering data (default: 0.002)'
    )
    
    parser.add_argument(
        '--output',
        help='Output file for results (default: print to console)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output with detailed statistics'
    )
    
    args = parser.parse_args()
    
    # Process elastic constants with parsed arguments
    process_elastic_constants(args.path, args.threshold, args.verbose, args.output)


def process_elastic_constants(file_prefix="", strain_threshold=0.002, verbose_output=False, output_file=None):
    """Process elastic constants with given parameters"""
    
    print("🔧 Elastic Constant Analysis")
    print("=" * 50)
    if file_prefix:
        if is_remote_path(file_prefix):
            print(f"📡 Remote SFTP source: {file_prefix}")
        else:
            print(f"📁 Local source: {file_prefix}")
    else:
        print("📁 Local source: current directory")
    print(f"🎯 Strain threshold: {strain_threshold}")
    print()

    # Helper function to get file path
    def get_file_path(filename):
        if file_prefix and not file_prefix.endswith('/'):
            return f"{file_prefix}/{filename}"
        return f"{file_prefix}{filename}"

    # Importing elastic constant data
    headers_e_constant = ["delta_exx", "delta_eyy", "delta_ezz", "delta_exy", "delta_eyz", "delta_exz", 
                          "delta_pxx", "delta_pyy", "delta_pzz", "delta_pxy", "delta_pyz", "delta_pxz"]

    try:
        c1144_original_data = read_elastic_file(get_file_path("c1144.txt"), headers_e_constant)
        c2255_original_data = read_elastic_file(get_file_path("c2255.txt"), headers_e_constant)
        c3366_original_data = read_elastic_file(get_file_path("c3366.txt"), headers_e_constant)
        c1144r_original_data = read_elastic_file(get_file_path("c1144r.txt"), headers_e_constant)
        c2255r_original_data = read_elastic_file(get_file_path("c2255r.txt"), headers_e_constant)
        c3366r_original_data = read_elastic_file(get_file_path("c3366r.txt"), headers_e_constant)

        # Filter data using the specified threshold
        c1144_data = c1144_original_data[c1144_original_data.delta_exx <= strain_threshold]
        c2255_data = c2255_original_data[c2255_original_data.delta_eyy <= strain_threshold]
        c3366_data = c3366_original_data[c3366_original_data.delta_ezz <= strain_threshold]
        c1144r_data = c1144r_original_data[c1144r_original_data.delta_exx <= strain_threshold]
        c2255r_data = c2255r_original_data[c2255r_original_data.delta_eyy <= strain_threshold]
        c3366r_data = c3366r_original_data[c3366r_original_data.delta_ezz <= strain_threshold]

    except Exception as e:
        print(f"❌ Error reading elastic constant files: {e}")
        print("Make sure all elastic constant files (c1144.txt, c2255.txt, etc.) are available")
        if file_prefix:
            print(f"Looking for files with prefix: {file_prefix}")
        sys.exit(1)

    if verbose_output:
        print("📊 Data Statistics:")
        print("c1144_data:", c1144_data.describe())
        print("c2255_data:", c2255_data.describe())
        print("c3366_data:", c3366_data.describe())
        print("c1144r_data:", c1144r_data.describe())
        print("c2255r_data:", c2255r_data.describe())
        print("c3366r_data:", c3366r_data.describe())
        print()

    # Calculating elastic constants
    def fit_linear_model(X, y):
        """Fit linear regression model and return coefficients"""
        model = LinearRegression()
        model.fit(X.reshape(-1, 1), y)
        return model.coef_[0], model.intercept_

    # Fit linear regression models
    coef_c1111, _ = fit_linear_model(c1144_data.delta_exx.values, c1144_data.delta_pxx.values)
    coef_c2211, _ = fit_linear_model(c1144_data.delta_exx.values, c1144_data.delta_pyy.values)
    coef_c3311, _ = fit_linear_model(c1144_data.delta_exx.values, c1144_data.delta_pzz.values)

    coef_c1111r, _ = fit_linear_model(c1144r_data.delta_exx.values, c1144r_data.delta_pxx.values)
    coef_c2211r, _ = fit_linear_model(c1144r_data.delta_exx.values, c1144r_data.delta_pyy.values)
    coef_c3311r, _ = fit_linear_model(c1144r_data.delta_exx.values, c1144r_data.delta_pzz.values)

    coef_c1122, _ = fit_linear_model(c2255_data.delta_eyy.values, c2255_data.delta_pxx.values)
    coef_c2222, _ = fit_linear_model(c2255_data.delta_eyy.values, c2255_data.delta_pyy.values)
    coef_c3322, _ = fit_linear_model(c2255_data.delta_eyy.values, c2255_data.delta_pzz.values)

    coef_c1122r, _ = fit_linear_model(c2255r_data.delta_eyy.values, c2255r_data.delta_pxx.values)
    coef_c2222r, _ = fit_linear_model(c2255r_data.delta_eyy.values, c2255r_data.delta_pyy.values)
    coef_c3322r, _ = fit_linear_model(c2255r_data.delta_eyy.values, c2255r_data.delta_pzz.values)

    coef_c1133, _ = fit_linear_model(c3366_data.delta_ezz.values, c3366_data.delta_pxx.values)
    coef_c2233, _ = fit_linear_model(c3366_data.delta_ezz.values, c3366_data.delta_pyy.values)
    coef_c3333, _ = fit_linear_model(c3366_data.delta_ezz.values, c3366_data.delta_pzz.values)

    coef_c1133r, _ = fit_linear_model(c3366r_data.delta_ezz.values, c3366r_data.delta_pxx.values)
    coef_c2233r, _ = fit_linear_model(c3366r_data.delta_ezz.values, c3366r_data.delta_pyy.values)
    coef_c3333r, _ = fit_linear_model(c3366r_data.delta_ezz.values, c3366r_data.delta_pzz.values)

    coef_c4444, _ = fit_linear_model(c1144_data.delta_exy.values, c1144_data.delta_pxy.values)
    coef_c5555, _ = fit_linear_model(c2255_data.delta_eyz.values, c2255_data.delta_pyz.values)
    coef_c6666, _ = fit_linear_model(c3366_data.delta_exz.values, c3366_data.delta_pxz.values)

    coef_c4444r, _ = fit_linear_model(c1144r_data.delta_exy.values, c1144r_data.delta_pxy.values)
    coef_c5555r, _ = fit_linear_model(c2255r_data.delta_eyz.values, c2255r_data.delta_pyz.values)
    coef_c6666r, _ = fit_linear_model(c3366r_data.delta_exz.values, c3366r_data.delta_pxz.values)

    # Calculate mean elastic constants
    C1111 = abs(np.mean([coef_c1111, coef_c1111r]))
    C2211 = abs(np.mean([coef_c2211, coef_c2211r]))
    C3311 = abs(np.mean([coef_c3311, coef_c3311r]))

    C1122 = abs(np.mean([coef_c1122, coef_c1122r]))
    C2222 = abs(np.mean([coef_c2222, coef_c2222r]))
    C3322 = abs(np.mean([coef_c3322, coef_c3322r]))

    C1133 = abs(np.mean([coef_c1133, coef_c1133r]))
    C2233 = abs(np.mean([coef_c2233, coef_c2233r]))
    C3333 = abs(np.mean([coef_c3333, coef_c3333r]))

    C4444 = abs(np.mean([coef_c4444, coef_c4444r]))
    C5555 = abs(np.mean([coef_c5555, coef_c5555r]))
    C6666 = abs(np.mean([coef_c6666, coef_c6666r]))

    # Define the 6x6 rigidity matrix (in Voigt notation for simplicity)
    C = np.array([[C1111, C1122, C1133, 0.0, 0.0, 0.0],
                  [C2211, C2222, C2233, 0.0, 0.0, 0.0],
                  [C3311, C3322, C3333, 0.0, 0.0, 0.0],
                  [0.0, 0.0, 0.0, C4444, 0.0, 0.0],
                  [0.0, 0.0, 0.0, 0.0, C5555, 0.0],
                  [0.0, 0.0, 0.0, 0.0, 0.0, C6666]])

    # Calculate the inverse to get the compliance matrix S (6x6 matrix)
    S = np.linalg.inv(C)

    # Calculate averaged constants
    C11 = np.mean([C[0, 0], C[1, 1], C[2, 2]])
    C12 = np.mean([C[0, 1], C[0, 2], C[1, 0], C[1, 2], C[2, 0], C[2, 1]])
    C44 = np.mean([C[3, 3], C[4, 4], C[5, 5]])

    S11 = np.mean([S[0, 0], S[1, 1], S[2, 2]])
    S12 = np.mean([S[0, 1], S[0, 2], S[1, 0], S[1, 2], S[2, 0], S[2, 1]])
    S44 = np.mean([S[3, 3], S[4, 4], S[5, 5]])

    # Prepare output
    results = []
    results.append("🔧 Elastic Constants Results")
    results.append("=" * 50)
    results.append("\n📋 Rigidity Matrix (Pa):")
    results.append(f"{C1111:.2e} {C1122:.2e} {C1133:.2e} 0.0 0.0 0.0")
    results.append(f"{C2211:.2e} {C2222:.2e} {C2233:.2e} 0.0 0.0 0.0") 
    results.append(f"{C3311:.2e} {C3322:.2e} {C3333:.2e} 0.0 0.0 0.0")
    results.append(f"0.0 0.0 0.0 {C4444:.2e} 0.0 0.0")
    results.append(f"0.0 0.0 0.0 0.0 {C5555:.2e} 0.0")
    results.append(f"0.0 0.0 0.0 0.0 0.0 {C6666:.2e}")
    
    results.append(f"\n📊 Averaged Elastic Constants:")
    results.append(f"C11 = {C11:.2e} Pa")
    results.append(f"C12 = {C12:.2e} Pa")
    results.append(f"C44 = {C44:.2e} Pa")
    
    results.append(f"\n📊 Compliance Constants:")
    results.append(f"S11 = {S11:.2e} Pa⁻¹")
    results.append(f"S12 = {S12:.2e} Pa⁻¹")
    results.append(f"S44 = {S44:.2e} Pa⁻¹")

    # Output results
    if output_file:
        try:
            with open(output_file, 'w') as f:
                for line in results:
                    f.write(line + '\n')
                # Also write raw values for programmatic use
                f.write(f"\n# Raw values for programmatic use:\n")
                f.write(f"C11={C11}\n")
                f.write(f"C12={C12}\n")
                f.write(f"C44={C44}\n")
                f.write(f"S11={S11}\n")
                f.write(f"S12={S12}\n")
                f.write(f"S44={S44}\n")
            print(f"✅ Results written to {output_file}")
        except Exception as e:
            print(f"❌ Error writing to output file: {e}")
    else:
        for line in results:
            print(line)

    # Return values for programmatic use
    return {
        'C11': C11, 'C12': C12, 'C44': C44,
        'S11': S11, 'S12': S12, 'S44': S44,
        'rigidity_matrix': C,
        'compliance_matrix': S
    }


if __name__ == "__main__":
    main()
else:
    # For backward compatibility when imported
    def run_elastic_analysis(file_prefix="", strain_threshold=0.002):
        """Backward compatibility function"""
        return process_elastic_constants(file_prefix, strain_threshold)
