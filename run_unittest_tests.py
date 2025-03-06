#!/usr/bin/env python3
"""
Script to run the unittest-based tests.
"""
import unittest
import os
import sys

def main():
    """Run the unittest-based tests."""
    # Change to the directory of this script
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Discover and run tests
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover('tests', pattern='test_*.py')
    
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    # Return non-zero exit code if tests failed
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    sys.exit(main()) 