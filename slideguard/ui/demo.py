#!/usr/bin/env python3
"""
Demo script for SlideGuard UI.
This script demonstrates how to use the UI programmatically.
"""

import sys
import os

# Add the parent directory to the path so we can import slideguard modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from slideguard.ui.app import SlideGuardUI


def demo_ui():
    """Demonstrate the UI functionality."""
    print("🎯 SlideGuard UI Demo")
    print("=" * 50)
    
    # Create UI instance
    ui = SlideGuardUI()
    
    # Check if evaluator was initialized
    if ui.evaluator is None:
        print("❌ Evaluator not initialized. Please check your configuration.")
        print("💡 Make sure you have set up your environment variables or .env file")
        return
    
    print("✅ Evaluator initialized successfully")
    print("🚀 UI is ready to use!")
    print()
    print("To launch the UI, run one of the following commands:")
    print("  poetry run slideguard ui run")
    print("  python slideguard/ui/launch.py")
    print("  python -c \"from slideguard.ui.app import create_app; create_app().launch()\"")
    print()
    print("The UI will be available at http://localhost:7860?__theme=light")


if __name__ == "__main__":
    demo_ui()
