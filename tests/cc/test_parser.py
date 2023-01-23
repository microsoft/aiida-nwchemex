"""Tests for the NWChemEx CC output parser."""
import re

import pytest

from aiida_nwchemex_cc.parsers import _getNum


def test_parse_cholesky(data_dir):
    """Test parsing output of cholesky decomposition."""
    with open(data_dir / "nwchemex-cholesky.log", encoding="utf8") as handle:
        log = handle.read()

    patFP = r"([+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?)"

    reTimeCholesky = re.compile(r"Time taken for CD \(\+SVD\):\s+" + patFP)
    timeCholesky = _getNum(reTimeCholesky.findall(log), wantMin=False)
    assert pytest.approx(timeCholesky.value, 0.1) == 0.5
