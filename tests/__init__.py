""" Tests for the plugin.

Includes both tests written in unittest style (test_cli.py) and tests written
in pytest style (test_calculations.py).
"""
import pathlib

TEST_DIR = pathlib.Path(__file__).parent.resolve()
DATA_DIR = TEST_DIR / "data"
