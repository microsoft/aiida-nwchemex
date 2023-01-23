"""
AiiDA plugin for multi-configurational quantum chemistry.

Supported codes:
 - NWChem
 - NWChemEx
"""

__version__ = "1.0.0"

__all__ = []

from pathlib import Path

THIS_DIR = Path(__file__).parent.absolute()
SCHEMA_DIR = THIS_DIR / "schemas"
