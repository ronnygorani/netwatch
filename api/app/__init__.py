# This file makes the "app" folder a PACKAGE — a collection of modules
# you can import (from app.config import settings, etc.).
#
# It also holds the single source of truth for the application version:
# main.py (FastAPI metadata) and the /health response both read it from
# here, so the number can never drift between the two.

__version__ = "0.2.0"
