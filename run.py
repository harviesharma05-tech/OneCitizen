#!/usr/bin/env python3
"""Entry point: generate data if missing, run the pipeline, serve the dashboard."""
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from ubdp import app as ubdp_app  # noqa: E402
from ubdp.generate_data import build  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

if __name__ == "__main__":
    if not glob.glob(os.path.join(DATA, "dept_*.csv")):
        print("No department data found. Generating synthetic sources...")
        build()
    ubdp_app.main()
