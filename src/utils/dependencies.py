#!/usr/bin/env python3
"""Dependency management utilities."""

import subprocess
import sys


def verify_and_install_dependencies():
    """Verify and install required dependencies."""
    print("🔍 Checking dependencies...")
    
    required_packages = {
        'slack_bolt': 'slack-bolt>=1.15.0',
        'dotenv': 'python-dotenv>=0.19.0'
    }
    
    missing_packages = []
    
    for package, pip_name in required_packages.items():
        try:
            __import__(package)
            print(f"✅ {package}: Available")
        except ImportError:
            print(f"❌ {package}: Missing")
            missing_packages.append(pip_name)
    
    if missing_packages:
        print(f"\n📦 Installing missing packages: {', '.join(missing_packages)}")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing_packages)
            print("✅ All packages installed successfully!")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install packages: {e}")
            print("Please run: pip install slack-bolt python-dotenv")
            sys.exit(1)