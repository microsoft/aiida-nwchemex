"""Utilities for writing NWChemEx input files."""
import json
from typing import List, Tuple

import basis_set_exchange as bse  # pip install basis_set_exchange
import numpy as np

from .nwchem import calc_basis
from .generic import BASIS_SET_OVERRIDES, PTABLE


def nwchemex_input(struct, basis, wf, scf_type):
    """Generate nwchemex json input file for given structure, basis set, and workflow definition."""
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements

    multiplicity = struct["multiplicity"]
    charge = struct["charge"]
    # label = struct["label"]
    # name = struct["_id"]["$oid"]
    nbasis = 0
    nocc = 0
    nvirt = 0
    nelec = 0
    geometry_key = {"coordinates": [], "units": "au"}
    symbols = []
    for i in range(0, struct["nAtoms"]):
        atom = struct["atoms"][i]
        symbol = atom["element"]
        symbols.append(symbol)
        Z = PTABLE[atom["element"]]

        element_basis = BASIS_SET_OVERRIDES.get(symbol, basis)

        bf = bse.get_basis(element_basis, elements=[Z], fmt="nwchem")
        nbasis = nbasis + calc_basis(bf)
        nelec = nelec + Z
        atom_coord_string = (
            str(symbol)
            + " "
            + str(atom["x"])
            + " "
            + str(atom["y"])
            + " "
            + str(atom["z"])
        )
        geometry_key["coordinates"].append(atom_coord_string)

    nelec = nelec + charge
    nocc = int(nelec / 2)
    nvirt = nbasis - nocc
    inputDicts = []
    stepMachines = []

    if scf_type in ("unrestricted", "uhf"):
        scf_type = "unrestricted"
    else:
        scf_type = "restricted"

    for step in [1, 2, 3, 4]:
        stepNam = f"step{step}"
        shMem = wf[stepNam]["shMem"]
        nGPU = wf[stepNam]["nGPU"]

        if step in (1, 2):
            machines = 1
        elif step == 3:
            machines = (
                (3 * nvirt**4 + 13 * (nvirt**2) * (nocc**2) + 5 * nocc**4)
                * 8
                / 1e9
                / shMem
            )

            if scf_type == "restricted":
                machines /= 2
            else:
                machines *= 4

            machines = int(np.ceil(machines))
        else:
            machines = int(28 * 8 * nbasis**4 / 1e9 / shMem) + 1

        if step == 1:
            noscf = False
            restart = False
            readt = False
            writev = False
            writet = True
        else:
            noscf = True
            restart = True
            readt = True
            writev = False
            writet = True

        basis_key = {"basisset": basis, "gaussian_type": "spherical"}
        special_elements = set(symbols).intersection(set(BASIS_SET_OVERRIDES.keys()))
        if special_elements:
            atom_basis = {}
            for element in special_elements:
                element_basis = BASIS_SET_OVERRIDES[element]
                atom_basis[element] = element_basis
                print(
                    f"Warning: overriding basis '{basis}' to '{element_basis}' for element '{element}'."
                )

            basis_key["atom_basis"] = atom_basis

        dictionary = {
            "geometry": geometry_key,
            "basis": basis_key,
            "common": {"maxiter": 50},
            "SCF": {
                "noscf": noscf,
                "restart": restart,
                "charge": charge,
                "multiplicity": multiplicity,
                "scf_type": scf_type,
                "tol_int": 1e-20,
                "tol_lindep": 1e-5,
                "conve": 1e-08,
                "convd": 1e-07,
                "diis_hist": 10,
            },
            "CD": {"diagtol": 1e-06},
            "CC": {
                "threshold": 1e-06,
                "ccsd_maxiter": 100,
                "readt": readt,
                "writev": writev,
                "writet": writet,
                "CCSD(T)": {"ngpu": nGPU, "ccsdt_tilesize": 40},
            },
        }
        stepMachines.append(machines)
        inputDicts.append(dictionary)

    return stepMachines, inputDicts


def nwchemex_input_multi(gblDefs, wf) -> List[Tuple[str, dict]]:
    """
    Return list of NWChemEx inputs (one for each molecule)

    gblDefs         = workflow global defaults
    wf              = workflow individual steps
    """

    structures_file = gblDefs["struct"]
    match = gblDefs["filter"]
    count = gblDefs["count"]
    basis = gblDefs["basis"]
    scf_type = gblDefs["scfType"] or "rhf"

    inputDicts = []
    with open(structures_file, encoding="utf8") as inp:
        for line in inp:
            if count == 0:
                break
            count -= 1

            structure = json.loads(line)
            if match is None or match in structure["_id"]["$oid"]:
                inputDicts.append(
                    (
                        structure["_id"]["$oid"],
                        nwchemex_input(structure, basis, wf, scf_type),
                    )
                )
    return inputDicts
