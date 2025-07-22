#!/usr/bin/env python3
"""
Post processor for NVT simulations - Python version
Processes LAMMPS output data for NVT ensemble simulations
Supports both local files and remote SFTP access
Supports both CSV and TXT input files

Usage Examples:
  Local TXT file:
    python post_processor_nvt.py data.txt output.csv
  
  Local CSV file:
    python post_processor_nvt.py data.csv output.csv
  
  Remote SFTP file:
    python post_processor_nvt.py user@server:/path/data.txt output.csv
    python post_processor_nvt.py user@server:/path/data.csv output.csv

Requirements:
  - For remote access: paramiko library (pip install paramiko)
  - For local elastic constants: c1144.txt, c2255.txt, c3366.txt, c1144r.txt, c2255r.txt, c3366r.txt
  - For remote elastic constants: python elastic_constant.py user@server:/path/to/elastic/files/
"""

import sys
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
import paramiko
import getpass
import tempfile
import os
from urllib.parse import urlparse

# Import elastic constants
import elastic_constant
S11 = elastic_constant.S11
S12 = elastic_constant.S12
S44 = elastic_constant.S44
C11 = elastic_constant.C11
C12 = elastic_constant.C12
C44_val = elastic_constant.C44

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

def read_input_file(input_path, headers):
    """Read input file, supporting both local and remote paths, CSV and TXT formats"""
    temp_file = None
    
    try:
        if is_remote_path(input_path):
            # Download from remote server
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_file.close()
            
            if not download_file_from_sftp(input_path, temp_file.name):
                raise Exception("Failed to download remote file")
            
            file_path = temp_file.name
        else:
            # Use local file
            file_path = input_path
        
        # Determine file format and read accordingly
        if file_path.lower().endswith('.csv'):
            # CSV format
            outputdata = pd.read_csv(file_path, comment="#", names=headers)
        else:
            # TXT format (space-delimited)
            outputdata = pd.read_csv(file_path, delim_whitespace=True, comment="#", names=headers)
        
        return outputdata
        
    finally:
        # Clean up temporary file if it was created
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except Exception as e:
                print(f"Warning: Could not delete temporary file: {e}")

# Check command line arguments
if len(sys.argv) != 3:
    print("Usage: python post_processor_nvt.py <input_file_or_url> <output_file>")
    print("Examples:")
    print("  python post_processor_nvt.py data.txt output.csv")
    print("  python post_processor_nvt.py user@server:/path/data.txt output.csv")
    sys.exit(1)

input_file = sys.argv[1]
output_file = sys.argv[2]

# Read data
headers = ["step", "l_1", "l_2", "l_3", "l_4", "l_5", "l_6", "p_1", "p_2", "p_3", "p_4", "p_5", "p_6", 
           "vol", "ep", "ek", "u", "t", "rho", "entropy", "etally"]
outputdata = read_input_file(input_file, headers)

# Calculate time step
dt = outputdata.iloc[1]['step'] - outputdata.iloc[0]['step']
print(f"Time step: {dt}")

# Transform output data - strain calculations
for i in range(1, 4):  # 1, 2, 3
    col_name = f"l_{i}"
    d_strain_col_name = f"de_{i}"
    d_strain_dt_name = f"de_dt_{i}"
    
    col_vals = outputdata[col_name].to_numpy()
    strain_increments = np.log(col_vals[1:] / col_vals[:-1])
    outputdata[d_strain_col_name] = np.concatenate([[0], strain_increments])
    outputdata[d_strain_dt_name] = outputdata[d_strain_col_name].to_numpy() / dt

for i in range(4, 7):  # 4, 5, 6
    col_name = f"l_{i}"
    d_strain_col_name = f"de_{i}"
    d_strain_dt_name = f"de_dt_{i}"
    
    col_vals = outputdata[col_name].to_numpy()
    outputdata[d_strain_col_name] = np.concatenate([[0], np.diff(col_vals)])
    outputdata[d_strain_dt_name] = outputdata[d_strain_col_name].to_numpy() / dt

# Stress calculations
for i in range(1, 7):  # 1 to 6
    col_name = f"p_{i}"
    stress_col_name = f"s_{i}"
    d_stress_col_name = f"ds_{i}"
    d_stress_dt_name = f"ds_dt_{i}"
    
    col_vals = outputdata[col_name].to_numpy()
    outputdata[stress_col_name] = col_vals
    outputdata[d_stress_col_name] = np.concatenate([[0], np.diff(col_vals)])
    outputdata[d_stress_dt_name] = outputdata[d_stress_col_name].to_numpy() / dt

# Von Mises strain
de_1 = outputdata['de_1'].to_numpy()
de_2 = outputdata['de_2'].to_numpy()
de_3 = outputdata['de_3'].to_numpy()
de_4 = outputdata['de_4'].to_numpy()
de_5 = outputdata['de_5'].to_numpy()
de_6 = outputdata['de_6'].to_numpy()

outputdata['de_mises'] = (np.sqrt(2)/3 * 
                          np.sqrt((de_1 - de_2)**2 + (de_2 - de_3)**2 + (de_1 - de_3)**2 + 
                                  3/2 * (de_4**2 + de_5**2 + de_6**2)))

# Cumulative strains
for i in range(1, 7):
    strain_col_name = f"de_{i}"
    cum_strain_col_name = f"e_{i}"
    outputdata[cum_strain_col_name] = np.cumsum(outputdata[strain_col_name].to_numpy())

outputdata['e_mises'] = np.cumsum(outputdata['de_mises'].to_numpy())

# Elastic strain rate calculations
ds_dt_1 = outputdata['ds_dt_1'].to_numpy()
ds_dt_2 = outputdata['ds_dt_2'].to_numpy()
ds_dt_3 = outputdata['ds_dt_3'].to_numpy()
ds_dt_4 = outputdata['ds_dt_4'].to_numpy()
ds_dt_5 = outputdata['ds_dt_5'].to_numpy()
ds_dt_6 = outputdata['ds_dt_6'].to_numpy()

outputdata['dee_dt_1'] = S11 * ds_dt_1 + S12 * (ds_dt_2 + ds_dt_3)
outputdata['dee_dt_2'] = S11 * ds_dt_2 + S12 * (ds_dt_1 + ds_dt_3)
outputdata['dee_dt_3'] = S11 * ds_dt_3 + S12 * (ds_dt_1 + ds_dt_2)
outputdata['dee_dt_4'] = S44 * ds_dt_4
outputdata['dee_dt_5'] = S44 * ds_dt_5
outputdata['dee_dt_6'] = S44 * ds_dt_6

# Plastic strain rate calculations
for i in range(1, 7):
    de_dt_col = f"de_dt_{i}"
    dee_dt_col = f"dee_dt_{i}"
    dep_dt_col = f"dep_dt_{i}"
    outputdata[dep_dt_col] = outputdata[de_dt_col].to_numpy() - outputdata[dee_dt_col].to_numpy()

# Convert rates back to increments
for i in range(1, 7):
    dee_dt_col = f"dee_dt_{i}"
    dep_dt_col = f"dep_dt_{i}"
    dee_col = f"dee_{i}"
    dep_col = f"dep_{i}"
    
    outputdata[dee_col] = outputdata[dee_dt_col].to_numpy() * dt
    outputdata[dep_col] = outputdata[dep_dt_col].to_numpy() * dt

# Cumulative plastic strains
for i in range(1, 7):
    dep_col = f"dep_{i}"
    ep_col = f"ep_{i}"
    outputdata[ep_col] = np.cumsum(outputdata[dep_col].to_numpy())

# Von Mises stress
s_1 = outputdata['s_1'].to_numpy()
s_2 = outputdata['s_2'].to_numpy()
s_3 = outputdata['s_3'].to_numpy()
s_4 = outputdata['s_4'].to_numpy()
s_5 = outputdata['s_5'].to_numpy()
s_6 = outputdata['s_6'].to_numpy()

outputdata['s_mises'] = np.sqrt(0.5 * ((s_1 - s_2)**2 + (s_2 - s_3)**2 + (s_1 - s_3)**2 + 
                                       6 * (s_4**2 + s_5**2 + s_6**2)))

# Work calculations
for i in range(1, 7):
    stress_col = f"s_{i}"
    de_col = f"de_{i}"
    dee_col = f"dee_{i}"
    dep_col = f"dep_{i}"
    
    work_col = f"dw_{i}"
    elastic_work_col = f"dwe_{i}"
    plastic_work_col = f"dwp_{i}"
    
    stress_vals = outputdata[stress_col].to_numpy()
    de_vals = outputdata[de_col].to_numpy()
    dee_vals = outputdata[dee_col].to_numpy()
    dep_vals = outputdata[dep_col].to_numpy()
    
    outputdata[work_col] = (1.0e9) * (stress_vals * de_vals)
    outputdata[elastic_work_col] = (1.0e9) * (stress_vals * dee_vals)
    outputdata[plastic_work_col] = (1.0e9) * (stress_vals * dep_vals)

# Total work calculations
dw_cols = [outputdata[f'dw_{i}'].to_numpy() for i in range(1, 7)]
dwe_cols = [outputdata[f'dwe_{i}'].to_numpy() for i in range(1, 7)]
dwp_cols = [outputdata[f'dwp_{i}'].to_numpy() for i in range(1, 7)]

outputdata['dW'] = sum(dw_cols)
outputdata['dWe'] = sum(dwe_cols)
outputdata['dWp'] = sum(dwp_cols)

# Cumulative work
outputdata['W'] = np.cumsum(outputdata['dW'].to_numpy())
outputdata['We'] = np.cumsum(outputdata['dWe'].to_numpy())
outputdata['Wp'] = np.cumsum(outputdata['dWp'].to_numpy())

# Recalculate differential work
Wp_vals = outputdata['Wp'].to_numpy()
We_vals = outputdata['We'].to_numpy()
outputdata['dWp'] = np.concatenate([[0], np.diff(Wp_vals)])
outputdata['dWe'] = np.concatenate([[0], np.diff(We_vals)])

# Energy calculations
vol = outputdata['vol'].to_numpy()
ep = outputdata['ep'].to_numpy()
ek = outputdata['ek'].to_numpy()
u = outputdata['u'].to_numpy()
t = outputdata['t'].to_numpy()
etally = outputdata['etally'].to_numpy()
rho = outputdata['rho'].to_numpy()

# Convert energy units (eV to J/m³)
conversion_factor = 1.602e-19  # eV to J
volume_factor = 1e-30  # Å³ to m³

outputdata['Delta_Ep'] = ((ep - ep[0]) * conversion_factor) / (vol * volume_factor)
outputdata['Delta_Ek'] = ((ek - ek[0]) * conversion_factor) / (vol * volume_factor)
outputdata['Delta_U'] = ((u - u[0]) * conversion_factor) / (vol * volume_factor)
outputdata['Delta_T'] = t - t[0]
outputdata['Delta_Q'] = ((etally - etally[0]) * conversion_factor) / (vol * volume_factor)

# Energy calculations
outputdata['Delta_Etot'] = outputdata['Delta_U'].to_numpy() + outputdata['Delta_Q'].to_numpy()
outputdata['Delta_Ttally'] = outputdata['Delta_Q'].to_numpy() / (rho * (1000 * 903))
outputdata['dQ'] = np.concatenate([[0], np.diff(outputdata['Delta_Q'].to_numpy())])
outputdata['dU'] = np.concatenate([[0], np.diff(outputdata['Delta_U'].to_numpy())])

# TQC calculations
dWp = outputdata['dWp'].to_numpy()
dQ = outputdata['dQ'].to_numpy()
Wp = outputdata['Wp'].to_numpy()
Delta_Q = outputdata['Delta_Q'].to_numpy()
dU = outputdata['dU'].to_numpy()
dWe = outputdata['dWe'].to_numpy()
We = outputdata['We'].to_numpy()
Delta_U = outputdata['Delta_U'].to_numpy()

outputdata['Beta_0_diff'] = dQ / (dWp + 1e-25)
outputdata['Beta_0_int'] = Delta_Q / (Wp + 1e-25)
outputdata['Beta_1_diff'] = 1 - ((dU - dWe) / (dWp + 1e-25))
outputdata['Beta_1_int'] = 1 - ((Delta_U - We) / (Wp + 1e-25))

print(outputdata.describe())

# Select and rename columns for output
df_tqc = outputdata[['step', 'e_6', 's_6', 'dW', 'W', 'We', 'Wp', 'dWp', 'dWe', 'Delta_Ep', 'Delta_Ek', 
                     'Delta_U', 'Delta_T', 'Delta_Q', 'Delta_Etot', 'Delta_Ttally', 'dQ', 'dU', 
                     'Beta_0_diff', 'Beta_0_int', 'Beta_1_diff', 'Beta_1_int']].copy()

df_headers = ["#step", "#e_xz", "#s_xz", "#dW", "#W", "#We", "#Wp", "#dWp", "#dWe", "#Delta_Ep", "#Delta_Ek", 
              "#Delta_U", "#Delta_T", "#Delta_Q", "#Delta_Etot", "#Delta_Ttally", "#dQ", "#dU", 
              "#Beta_0_diff", "#Beta_0_int", "#Beta_1_diff", "#Beta_1_int"]

df_tqc.columns = df_headers

def calculate_beta_averages(df, threshold):
    """Calculate and print averages of Beta parameters for e_xz > threshold"""
    filtered_df = df[df["#e_xz"] > threshold]
    
    if len(filtered_df) > 0:
        beta0_diff_avg = filtered_df["#Beta_0_diff"].mean()
        beta0_int_avg = filtered_df["#Beta_0_int"].mean()
        beta1_diff_avg = filtered_df["#Beta_1_diff"].mean()
        beta1_int_avg = filtered_df["#Beta_1_int"].mean()
        
        print(f"\nAverages for #e_xz > {threshold}:")
        print(f"Average Beta_0_diff: {beta0_diff_avg}")
        print(f"Average Beta_0_int: {beta0_int_avg}")
        print(f"Average Beta_1_diff: {beta1_diff_avg}")
        print(f"Average Beta_1_int: {beta1_int_avg}")
        
        return (beta0_diff_avg, beta0_int_avg, beta1_diff_avg, beta1_int_avg)
    else:
        print(f"\nNo data points with #e_xz > {threshold}")
        return None

# Find the row where e_xz is closest to 0.002
closest_idx = np.argmin(np.abs(df_tqc["#e_xz"] - 0.002))
closest_strain = df_tqc.iloc[closest_idx]["#e_xz"]
corresponding_stress = df_tqc.iloc[closest_idx]["#s_xz"]

print("Elastic constants:")
print(f"C11 = {C11}")
print(f"C12 = {C12}")
print(f"C44 = {C44_val}")

print(f"Closest e_xz value to 0.002: {closest_strain}")
print(f"Corresponding s_xz value: {corresponding_stress}")

# Calculate average Beta values for e_xz > 0.2
calculate_beta_averages(df_tqc, 0.2)

# Write output file
df_tqc.to_csv(output_file, sep='\t', index=False)
print(df_tqc.describe())
