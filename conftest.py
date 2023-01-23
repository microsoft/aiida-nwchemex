"""pytest fixtures for simplified testing."""
# pylint: disable=redefined-outer-name

import pytest
from aiida import orm
from tests import DATA_DIR


pytest_plugins = [
    "aiida.manage.tests.pytest_fixtures",
]  # pylint: disable=invalid-name


@pytest.fixture(scope="function", autouse=True)
def clear_database_auto(clear_database):  # pylint: disable=unused-argument
    """Automatically clear database in between tests."""


@pytest.fixture(scope="function")
def data_dir():  # pylint: disable=unused-argument
    """Directory for tests data."""
    return DATA_DIR


# @pytest.fixture(scope="function")
# def nwchem_code(aiida_local_code_factory):
#     """Get a nwchem code."""
#     code = aiida_local_code_factory(executable="nwchem", entry_point="nwchem.base")
#     return code


@pytest.fixture(scope="function")
def nwchem_code(mock_code_factory):
    """Create mocked "nwchem" code."""
    return mock_code_factory(
        label="nwchem-7.1",
        data_dir_abspath=DATA_DIR,
        entry_point="nwchem.base",
        # hasher=CustomInputHasher,
        # files *not* to copy into the data directory
        ignore_paths=("_aiidasubmit.sh", "*.movecs", "*.gridpts.*", "*.db"),
    )


@pytest.fixture(scope="function")
def h2o_structure_data():
    """Get a H2O structuredata."""
    alat = 4.0  # angstrom
    cell = [
        [
            alat,
            0.0,
            0.0,
        ],
        [
            0.0,
            alat,
            0.0,
        ],
        [
            0.0,
            0.0,
            alat,
        ],
    ]

    s = orm.StructureData(cell=cell)
    s.append_atom(position=(0.0, 0.0, 0.0), symbols=["O"])
    s.append_atom(position=(0.0, 1.43042809, -1.10715266), symbols=["H"])
    s.append_atom(position=(0.0, -1.43042809, -1.10715266), symbols=["H"])
    return s
