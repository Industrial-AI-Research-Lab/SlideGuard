#!/usr/bin/env python3
"""
Launcher script for SlideGuard Gradio UI.
"""

import sys
import os

# Add the parent directory to the path so we can import slideguard modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from slideguard.ui.app import create_app
from slideguard.ui.auth import verify_user_db


def main():
    """Launch the SlideGuard Gradio UI."""
    print("🚀 Starting SlideGuard UI...")
    print("📝 Make sure you have configured your environment variables or .env file")
    print("🔗 The UI will be available at http://localhost:7860?__theme=light")
    print()
    
    try:
        app = create_app()
        app.launch(
            server_name="127.0.0.1",
            server_port=7860,
            share=False,
            debug=True,
            show_error=True,
            quiet=True,
            show_api=False,
            auth=verify_user_db
        )
    except Exception as e:
        print(f"❌ Failed to start UI: {e}")
        print("💡 Make sure you have installed all dependencies: pip install gradio PyMuPDF")
        sys.exit(1)


if __name__ == "__main__":
    main()
