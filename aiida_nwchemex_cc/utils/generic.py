"""Generic utilities for creating nwchem/nwchemex input files."""
import re

from ase.data import chemical_symbols
import numpy as np

PTABLE = {symbol: i for i, symbol in enumerate(chemical_symbols)}


# override basis specified by the user for specific elements
# because nwchemex lacks support for effective core potentials in certain basis sets
BASIS_SET_OVERRIDES = {"Sn": "3-21G"}


def calc_basis(basis_set):
    """Calculate basis set functions for the atom
    :param basis_set: basis set returned by bse.get_basis
    :type basis_set: str
    :return: number of basis functions of the atom
    :rtype: int
    """
    ob = "d*[spdfgh]"
    parsed_basis = re.findall(
        f"-> \\[(\\{ob},*\\{ob}*,*\\{ob}*,*\\{ob}*,*\\{ob}*,*\\{ob}*)\\]", basis_set
    )
    pattern = "(\\d)*s*,*(\\d)*p*,*(\\d)*d*,*(\\d)*f*,*(\\d)*g*,*(\\d)*h*"
    primitive = list(re.findall(pattern, parsed_basis[0])[0])
    plist = [int(p) for p in primitive if p != ""]

    orbital_fillings = [1, 3, 5, 7, 9, 11]
    nlen = min(len(plist), len(orbital_fillings))
    a1 = np.array(plist, dtype=int)
    a2 = np.array(orbital_fillings)
    product = a1[:nlen] * a2[:nlen]
    nbf = np.sum(product)
    return nbf
