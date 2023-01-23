"""Utility functions for generating NWCHEM input files."""
import json
import math
from typing import List, Tuple

import basis_set_exchange as bse

from .generic import PTABLE, calc_basis

# pylint: disable=too-many-locals,too-many-arguments

# Template for generating an NWChem input deck
NWCHEM_TEMPLATE = """
{start} {name}

# Label: {label}
# This job contains {nbasis} basis functions.
# MPI suggestion: {nodes} nodes, {processes} processes

echo
{memory}

geometry units {geometry_units}
symmetry c1
{geometry}
end

basis spherical
* library {basis}
end
{ecp}
{charge}
scf
thresh {scf_thresh:.1e}
tol2e {scf_tol2e}
{scf_type}
maxiter 200
nopen {spin}
end
{method}
{readwrite}
task {task} energy

{append_text}
"""


def write_nw(
    start: str,
    mol_name: str,
    label: str,
    geometry: str = None,
    nbasis: int = 0,
    nodes: int = 1,
    processes: int = None,
    memory: str = "memory stack 1700 mb heap 100 mb global 5000 mb noverify",
    geometry_units: str = "au",
    basis: str = "sto-3g",
    charge: int = 0,
    scf_thresh: float = 1.0e-8,
    scf_tol2e: float = 1.0e-9,
    scf_type: str = "",
    spin: int = 0,
    method: str = "",
    readwrite: str = "",
    tilesize: int = 20,
    attilesize: int = 40,
    tce_thresh: float = 1.0e-6,
    task: str = "scf",
    append_text: str = "",
    ecp: str = "",
) -> str:
    """Generate an NWChem input deck
    :param start: Start/Restart a job
    :type start: str
    :param mol_name: Molecule name
    :type mol_name: str
    :param geometry: Molecule geometry in the following format (each atom on
        a new line) : [Atom] [X] [Y] [Z]
    :type geometry: str
    :param memory: Memory specification, defaults to "memory stack 1000 mb
        heap 100 mb global 1000 mb noverify"
    :type memory: str, optional
    :param geometry_units: Units used for geometry ("au"|"angstrom"), defaults
        to "au"
    :type geometry_units: str, optional
    :param basis: Basis to use for atoms, defaults to "sto-3g"
    :type basis: str, optional
    :param charge: Molecule charge, defaults to 0
    :type charge: int, optional
    :param scf_thresh: Threshold for SCF solver with one-decimal precision,
        defaults to 1.0e-10
    :type scf_thresh: float, optional
    :param scf_tol2e: 2-electron tolerance for SCF solver, defaults to 1.0e-10
    :type scf_tol2e: float, optional
    :param rhf: Restricted (Open-shell) Hartree Fock method. Either "rhf" or
        "rohf", defaults to "rhf"
    :type rhf: str, optional
    :param spin: number of singly occupied orbitals, defaults to "0"
    :type spin: str, optional
    :param method: Post-HF Calculation method, defaults to "" (not doing any)
    :type method: str, optional
    :param readwrite: store integrals and amplitudes for post-HF calcualtions, defaults to "" (not doing any)
    :type readwrite: str, optional
    :param tilesize: spin-orbital tilesize for local integrals in tce,
        defaults to 20
    :type tilesize: int, optional
    :param attilesize: orbital tilesize for local integrals in tce,
        defaults to 40
    :type attilesize: int, optional
    :param tce_thresh: Threshold for TCE solver with one-decimal precision,
        defaults to 1.0e-6
    :type tce_thresh: float, optional
    :param task: task energy to calculate, defaults to "scf"
    :type task: str, optional
    :param ecp: effective core potential section
    :type task: str, optional


    :raises ValueError: If neither Mol or num_active_el|geometry are specified.
    :return: NWChem input deck formatted string
    :rtype: str
    """

    if scf_type in ("unrestricted", "uhf"):
        scf_type = "uhf"
        tce_tricks = ""
    else:
        # no need to specify scf_type if it is restricted
        # (it is the default behavior + there is rhf/rohf depending on spin)
        scf_type = ""
        tce_tricks = "2eorb\n2emet"

    charge_text = f"charge {charge}" if charge else ""
    tce_text = (
        f"tce \n{method}\ntilesize {tilesize}\n{tce_tricks}\nattilesize {attilesize}"
        f"\nthresh {tce_thresh}\nend\nset tce:printtol 1e-2\nset tce:nts T"
        if method
        else ""
    )
    readwrite_text = (
        f"set tce:readint {readwrite}\nset tce:readt {readwrite}\nset tce:writeint T\nset tce:writet T"
        if readwrite
        else ""
    )

    nw_chem = NWCHEM_TEMPLATE.format(
        start=start,
        name=f"{mol_name}",
        label=label,
        memory=memory,
        nodes=nodes,
        nbasis=nbasis,
        processes=processes,
        geometry_units=geometry_units,
        geometry=geometry,
        basis=basis,
        charge=charge_text,
        scf_thresh=scf_thresh,
        scf_tol2e=scf_tol2e,
        scf_type=scf_type,
        spin=spin,
        tilesize=tilesize,
        attilesize=attilesize,
        tce_thresh=tce_thresh,
        method=tce_text,
        readwrite=readwrite_text,
        task=task,
        append_text=append_text,
        ecp=ecp,
    )

    return nw_chem


def _get_geometry_dict(struct: dict, basis: str, processes: int):
    """Get NWChem geometry string from a structure."""
    nbasis = 0
    geometry = ""
    ecp = ""

    elements = []
    for i in range(0, struct["nAtoms"]):
        element = struct["atoms"][i]["element"]
        elements.append(element)
        Z = PTABLE[element]

        if Z > 36:  # for elements beyond Kr, we can't use cc-pvdz
            if basis == "cc-pvdz":
                raise ValueError(
                    f"{element} is not supported in cc-pvdz basis."
                    + "Consider switching to def2-svp."
                )
            if basis != "def2-svp":
                print(
                    f"Warning: Detected element {element} in geometry."
                    + "but basis is not def2-svp."
                )

        bf = bse.get_basis(basis, elements=[Z], fmt="nwchem")
        nbasis = nbasis + calc_basis(bf)
        x, y, z = struct["atoms"][i]
        if i == struct["nAtoms"] - 1:
            geometry = geometry + f"{element} {x:12.8f} {y:12.8f} {z:12.8f}"
        else:
            geometry = geometry + f"{element} {x:12.8f} {y:12.8f} {z:12.8f} \n"
    # print("This molecule has %s basis functions under %s basis"%(nbasis,basis))

    ecp_elements = {element for element in elements if PTABLE[element] > 36}
    if basis == "def2-svp" and ecp_elements:
        ecp = "ecp\n"
        for element in ecp_elements:
            ecp += f"{element} library {basis}\n"
        ecp += "end"
    else:
        ecp = ""

    if nbasis < 20:
        processes = 2

    nodes = 1
    if nbasis > 300:
        # Factor 1.5 just as a buffer
        # 8=bytes per 64bit floating point number
        # nbasis**4 = number of integrals
        memory_required = 1.5 * 8 * nbasis**4
        # On our VM types, we can typically give 5 GB of memory per process
        process_memory = 1e9 * 5
        nodes = math.ceil(memory_required / (process_memory * processes))
    return dict(
        geometry=geometry, ecp=ecp, nbasis=nbasis, nodes=nodes, processes=processes
    )


def generate_nwchem_steps(
    struct, workflow_json: dict, n_steps: int = 2
) -> List[Tuple[int, str]]:
    """Create NWChem input files for 2- and 4-step algorithm.

    2-step:
        Step 1: run scf
        Step 2: run ccsd(t)

    4-step:
        Step 1: run scf
        Step 2: run ccsd
        Step 3: run lr-ccsd(t)
        Step 4: run ccsd(t)

    """
    assert n_steps in (2, 4), "Number of steps must be 2 or 4"

    # basis to operate under
    basis = workflow_json["basis"] or "cc-pvdz"
    scf_type = workflow_json["scfType"] or "rhf"
    processes = workflow_json["procs"]

    nwfiles = []
    machines = []
    geo = _get_geometry_dict(struct, basis, processes)
    for step_id in range(n_steps):
        kwargs = {}
        if step_id == 0:
            # hartree-fock
            start_text = "start"
            method_text = ""
            kwargs[
                "memory"
            ] = "memory stack 2500 mb heap 100 mb global 1100 mb noverify"
        else:
            # ccsd
            start_text = "restart"
            kwargs["task"] = "tce"

            if n_steps == 2:
                method_text = "ccsd(t)"
            else:
                if step_id == 1:
                    method_text = "ccsd"
                    io_setting = "F"
                elif step_id == 2:
                    method_text = "lr-ccsd(t)"
                    io_setting = "T"
                else:
                    method_text = "ccsd(t)"
                    io_setting = "T"
                kwargs["readwrite"] = (io_setting,)

        kwargs.update(
            dict(
                label=struct["label"],
                mol_name=struct["_id"]["$oid"] + "-" + basis,
                spin=struct["multiplicity"] - 1,
                charge=struct["charge"],
                geometry=geo["geometry"],
                ecp=geo["ecp"],
                nbasis=geo["nbasis"],
                processes=geo["processes"],
                nodes=geo["nodes"],
                start=start_text,
                basis=basis,
                method=method_text,
                scf_type=scf_type,
            )
        )
        nwfiles.append(write_nw(**kwargs))
        machines.append(geo["nodes"])

    return machines, nwfiles


def nwchem_input_multi(gblDefs, nstep=4) -> List[Tuple[str, str]]:
    """
    :param nstep: number of steps of workflow (4 or 2)

    output will be a list of tuples of molecular id and nwchem input files
    """
    # all the molecules we want to work on
    structures_file = gblDefs["struct"] or "pull.py"
    # substring to match filter IDs on
    match = gblDefs["filter"]
    # max count to process
    count = gblDefs["count"] or 999999

    input_files = []
    with open(structures_file, encoding="utf8") as inp:
        for line in inp:
            if count == 0:
                break
            count -= 1

            structure = json.loads(line)
            if structure["label"] == "duplicate":
                print("Skipping this duplicated structure...")
                continue

            if match is None or match in structure["_id"]["$oid"]:
                # (molid, (nmachines, input file))
                line = (
                    structure["_id"]["$oid"],
                    generate_nwchem_steps(
                        structure, workflow_json=gblDefs, n_steps=nstep
                    ),
                )
                input_files.append(line)
    return input_files
