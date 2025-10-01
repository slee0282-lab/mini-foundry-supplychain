"""
Mini Foundry Supply Chain Control Tower

Entry point for the supply chain analytics dashboard.
Redirects to the full dashboard application.
"""

import subprocess
import sys
import os

def main():
    """Launch the Streamlit dashboard."""
    print("🚀 Launching Mini Foundry Supply Chain Control Tower...")

    # Path to the dashboard app
    dashboard_path = os.path.join(os.path.dirname(__file__), 'dashboard', 'app.py')

    # Launch Streamlit
    try:
        subprocess.run([
            sys.executable, '-m', 'streamlit', 'run', dashboard_path,
            '--server.port=8501',
            '--server.address=localhost'
        ])
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped by user")
    except Exception as e:
        print(f"❌ Error launching dashboard: {str(e)}")
        print("\nTry running directly with:")
        print(f"streamlit run {dashboard_path}")

if __name__ == "__main__":
    main()
