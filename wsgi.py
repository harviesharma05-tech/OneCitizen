"""
WSGI entry point for production servers (gunicorn, etc.).

`run.py` is for local development — it calls app.run() directly. Render/
Railway/Heroku-style platforms instead run a WSGI server (gunicorn) that
imports an `app` object from this file, so the two entry points are kept
separate.

Start command on Render:   gunicorn wsgi:app
"""
import glob
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "src"))

from ubdp.generate_data import build  # noqa: E402

DATA = os.path.join(BASE, "data")
if not glob.glob(os.path.join(DATA, "dept_*.csv")):
    build()

from ubdp.app import app  # noqa: E402
from ubdp import pipeline  # noqa: E402

# Warm the entity-resolution pipeline once at boot instead of on the first
# request, so the first visitor isn't the one waiting on it.
pipeline.run(verbose=True)
