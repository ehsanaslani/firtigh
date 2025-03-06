#!/usr/bin/env python3
"""
Convenience script to run the tests.
"""
import subprocess
import sys
import os

def main():
    """Run the tests."""
    # Change to the directory of this script
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Install dependencies if needed
    print("Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
    
    # Run the tests
    print("\nRunning tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "-v"], check=False)
    
    # Return the exit code
    return result.returncode

if __name__ == "__main__":
    sys.exit(main()) 