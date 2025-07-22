#!/usr/bin/env python3
"""
SFTP utilities for remote file operations
Handles authentication, downloading, and connection management
"""

import paramiko
import getpass
import tempfile
import os
from typing import Optional, Tuple
from ..config.constants import DEFAULT_SFTP_PORT, OTP_LENGTH


class SFTPManager:
    """Manages SFTP connections and file operations"""
    
    def __init__(self):
        self.transport: Optional[paramiko.Transport] = None
        self.sftp: Optional[paramiko.SFTPClient] = None
        
    def parse_sftp_url(self, sftp_url: str) -> Tuple[str, str, str]:
        """
        Parse SFTP URL into components
        
        Args:
            sftp_url: URL in format 'user@host:/path/file'
            
        Returns:
            Tuple of (username, hostname, remote_path)
        """
        if '@' not in sftp_url or ':' not in sftp_url:
            raise ValueError("SFTP URL should be in format 'user@host:/path/file'")
        
        user_host, remote_path = sftp_url.split(':', 1)
        username, hostname = user_host.split('@', 1)
        
        return username, hostname, remote_path
    
    def authenticate(self, hostname: str, username: str) -> bool:
        """
        Establish authenticated SFTP connection
        
        Args:
            hostname: Server hostname
            username: Username for authentication
            
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            print(f"Connecting to {hostname}...")
            self.transport = paramiko.Transport((hostname, DEFAULT_SFTP_PORT))
            self.transport.connect()
            
            # Interactive authentication handler
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
                        if any(keyword in clean_prompt.lower() 
                              for keyword in ['verification', 'code', 'token', 'otp', 'authenticator']):
                            print(f"\n📱 Please enter your {OTP_LENGTH}-digit one-time password")
                            response = getpass.getpass(f"{clean_prompt}: ")
                            while (len(response.strip()) != OTP_LENGTH or 
                                   not response.strip().isdigit()):
                                print(f"❌ OTP must be exactly {OTP_LENGTH} digits")
                                response = getpass.getpass(f"{clean_prompt}: ")
                        else:
                            response = getpass.getpass(f"{clean_prompt}: ")
                    responses.append(response.strip())
                return responses
            
            self.transport.auth_interactive(username, auth_handler)
            self.sftp = paramiko.SFTPClient.from_transport(self.transport)
            
            if self.sftp is None:
                raise Exception("Failed to create SFTP client")
                
            print("✅ Authentication successful!")
            return True
            
        except Exception as e:
            print(f"❌ Authentication failed: {str(e)}")
            self.close()
            return False
    
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """
        Download file from remote server
        
        Args:
            remote_path: Path to file on remote server
            local_path: Local path to save the file
            
        Returns:
            True if download successful, False otherwise
        """
        if self.sftp is None:
            print("❌ SFTP connection not established")
            return False
        
        try:
            print(f"Downloading {remote_path}...")
            self.sftp.get(remote_path, local_path)
            print(f"✅ Downloaded to {local_path}")
            return True
            
        except Exception as e:
            print(f"❌ Download failed: {str(e)}")
            return False
    
    def download_from_url(self, sftp_url: str, local_path: str) -> bool:
        """
        Download file directly from SFTP URL
        
        Args:
            sftp_url: Complete SFTP URL
            local_path: Local path to save the file
            
        Returns:
            True if download successful, False otherwise
        """
        try:
            username, hostname, remote_path = self.parse_sftp_url(sftp_url)
            
            if not self.authenticate(hostname, username):
                return False
            
            return self.download_file(remote_path, local_path)
            
        except Exception as e:
            print(f"❌ Error downloading from URL: {str(e)}")
            return False
        finally:
            self.close()
    
    def close(self):
        """Close SFTP and transport connections"""
        if self.sftp:
            self.sftp.close()
            self.sftp = None
        if self.transport:
            self.transport.close()
            self.transport = None


def is_remote_path(path: str) -> bool:
    """
    Check if the path is a remote SFTP URL
    
    Args:
        path: File path or URL to check
        
    Returns:
        True if path is a remote SFTP URL, False otherwise
    """
    return '@' in path and ':' in path


def download_remote_file(sftp_url: str) -> Optional[str]:
    """
    Download remote file and return temporary file path
    
    Args:
        sftp_url: SFTP URL to download from
        
    Returns:
        Path to temporary file, or None if download failed
    """
    try:
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.close()
        
        sftp_manager = SFTPManager()
        if sftp_manager.download_from_url(sftp_url, temp_file.name):
            return temp_file.name
        else:
            # Clean up on failure
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            return None
            
    except Exception as e:
        print(f"❌ Error in download_remote_file: {str(e)}")
        return None


def download_file_sftp(remote_path: str, local_path: str, sftp_config: dict) -> bool:
    """
    Download file using SFTP configuration
    
    Args:
        remote_path: Remote file path
        local_path: Local destination path
        sftp_config: SFTP configuration with hostname and username
        
    Returns:
        True if download successful, False otherwise
    """
    try:
        sftp_manager = SFTPManager()
        if sftp_manager.authenticate(sftp_config['hostname'], sftp_config['username']):
            return sftp_manager.download_file(remote_path, local_path)
        return False
    except Exception as e:
        print(f"❌ Error downloading file: {e}")
        return False


def list_remote_files(pattern: str, sftp_config: dict) -> list:
    """
    List remote files matching pattern
    
    Args:
        pattern: File pattern to match
        sftp_config: SFTP configuration
        
    Returns:
        List of matching remote file paths
    """
    try:
        sftp_manager = SFTPManager()
        if sftp_manager.authenticate(sftp_config['hostname'], sftp_config['username']):
            # For now, return a simple list - this would need proper implementation
            # based on the pattern and remote directory listing
            import fnmatch
            
            # Extract directory and pattern
            if '/' in pattern:
                remote_dir = '/'.join(pattern.split('/')[:-1])
                file_pattern = pattern.split('/')[-1]
            else:
                remote_dir = '.'
                file_pattern = pattern
            
            try:
                # List files in remote directory
                if sftp_manager.sftp is not None:
                    files = sftp_manager.sftp.listdir(remote_dir)
                    matching_files = []
                    
                    for file in files:
                        if fnmatch.fnmatch(file, file_pattern):
                            if remote_dir == '.':
                                matching_files.append(file)
                            else:
                                matching_files.append(f"{remote_dir}/{file}")
                    
                    return matching_files
                else:
                    print("❌ SFTP connection not established")
                    return []
            except Exception as e:
                print(f"❌ Error listing remote files: {e}")
                return []
        return []
    except Exception as e:
        print(f"❌ Error in list_remote_files: {e}")
        return []
