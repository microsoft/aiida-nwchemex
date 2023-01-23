"""Tests for calculation classes provided by aiida_nwchemex_cc."""

import pytest

from aiida import engine, orm, plugins


def test_h2o_base(nwchem_code, data_dir):
    """Test running NWChem on H2O using plain input file."""
    builder = plugins.CalculationFactory("nwchemex_cc.nwchem").get_builder()
    builder.code = nwchem_code
    builder.metadata.options.resources = {"num_machines": 1}
    with open(data_dir / "cc-h2o.inp", "rb") as handle:
        builder.input_file = orm.SinglefileData(handle, filename="h2o.inp")

    result, node = engine.run_get_node(builder)

    assert node.is_finished_ok, node.exit_message

    with result["retrieved"].open("aiida.out") as handle:
        log = handle.read()

    assert "output_parameters" in result, log
    parameters = result["output_parameters"].get_dict()
    pytest.approx(parameters["total_dft_energy"], 0.1, -74.38)

    # test stuff added by aiida_nwchemex_cc parser
    assert "results" in result, log
    assert result["results"]["timeWall"].value >= 0.1
