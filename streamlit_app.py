"""
Streamlit Cloud Entry Point
Redirects to the main dashboard application.
"""
import subprocess
import sys

# For Streamlit Cloud deployment, run the dashboard directly
from dashboard.app import main

if __name__ == "__main__":
    main()
