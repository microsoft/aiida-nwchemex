#!/usr/bin/env python3
"""Adapter for scine database.
"""
# pylint: disable=no-member,import-outside-toplevel,too-many-branches,too-many-locals
# pylint: disable=too-many-statements,too-many-arguments,missing-function-docstring,redefined-builtin

from json import dump, dumps, loads


def _store_property(
    properties,
    property_name: str,
    property_type: str,
    data,
    model,
    calculation,
    structure,
) -> object:
    """
    Adds a single property into the database, connecting it with a given
    structure and calculation (it's results section)

    Parameters
    ----------
    properties :: db.Collection (Scine::Database::Collection)
        The collection housing all properties.
    property_name :: str
        The name (key) of the new property, e.g. ``electronic_energy``.
    property_type :: str
        The type of property to be added, e.g. ``NumberProperty``.
    data :: object (According to 'property_type')
        The data to be stored in the property, the type of this object is
        dependent on the type of property requested. A ``NumberProperty``
        will require a ``float``, a ``VectorProperty`` will require a
        ``List[float]``, etc.
    model :: db.Model (Scine::Database::Model)
        The model used in the calculation that resulted in this property.
    calculation :: db.Calculation (Scine::Database::Calculation)
        The calculation that resulted in this property.
        The calculation has to be linked to its collection.
    structure :: db.Structure (Scine::Database::Structure)
        The structure for which the property is to be added. The properties
        field of the structure will receive an additional entry, or have
        an entry replaced, based on the options given to this function.
        The structure has to be linked to its collection.

    Returns
    -------
    property :: Derived of db.Property (Scine::Database::Property)
        The property, a dervied class of db.Property, linked to the
        properties' collection, or ``None`` if no property was generated due
        to duplication.
    """
    import scine_database as db

    class_ = getattr(db, property_type)
    db_property = class_()
    db_property.link(properties)
    db_property.create(model, property_name, structure.id(), calculation.id(), data)
    structure.add_property(property_name, db_property.id())
    results = calculation.get_results()
    results.add_property(db_property.id())
    calculation.set_results(results)
    return db_property


def doPull(fName="pull.json", dbName="test_db_dave", doAll=False):
    import scine_database as db

    manager = db.Manager()
    credentials = db.Credentials("localhost", 27017, dbName)
    manager.set_credentials(credentials)
    manager.connect()

    # Get collections
    structures = manager.get_collection("structures")
    calculations = manager.get_collection("calculations")
    # properties      = manager.get_collection('properties')

    # Get all relevant jobs
    selection = {
        "$and": [
            {"status": "new"},
            {"job.order": "ms_cc_calculation"},
        ]
    }

    # keepOn = True
    # update = {'$set': {'status': 'pending', 'executor': 'I_am_in_the_clouds'}}

    with open(fName, "w", encoding="utf8") as out:

        # Grab all structures
        if doAll:
            structure_ids = structures.query_structures(dumps({}))
            for structure in structure_ids:
                structure.link(structures)

                # Get structure(s)
                data = loads(structure.json())
                data["struID"] = str(structure)
                dump(data, out)
                out.write("\n")

        # Grab relevant calculations
        else:
            calculation_ids = calculations.query_calculations(dumps(selection))
            for cid in calculation_ids:
                calculation = db.Calculation(cid.id())
                calcID = str(cid.id())
                calculation.link(calculations)
                # calculation.set_status(db.Status.PENDING)

                # Get structure(s)
                structure_ids = calculation.get_structures()
                structure = db.Structure(structure_ids[0])
                strID = str(structure_ids[0])
                structure.link(structures)
                data = loads(structure.json())
                data["struID"] = strID
                data["calcID"] = calcID
                dump(data, out)
                out.write("\n")

    # Check that we wrote it OK
    count = 0
    with open(fName, encoding="utf8") as inp:
        for line in inp:
            input = loads(line)
            count += 1
            atomCount = {}
            for atom in input["atoms"]:
                elem = str(atom["element"])
                atomCount[elem] = atomCount.get(elem, 0) + 1
            print(f"{input['_id']['$oid']}: {atomCount}")
    print(f" ==== Created: {fName}, Count: {count}")


def doUpdate(fName, dbName, rslts):
    import scine_database as db

    def _getReq(struct, k):
        if not k in struct:
            raise Exception(f'{k} not parsed for structure node {struct["Node"]}')
        return struct[k]

    def _getE(struct, k):
        return float(struct[k])

    # Get a db connection
    manager = db.Manager()
    credentials = db.Credentials("localhost", 27017, dbName)
    manager.set_credentials(credentials)
    manager.connect()

    # Get collections
    structures = manager.get_collection("structures")
    calculations = manager.get_collection("calculations")
    properties = manager.get_collection("properties")

    # Get database IDs
    pulled = {}
    with open(fName, encoding="utf8") as inp:
        for line in inp:
            input = loads(line)
            oid = input["_id"]["$oid"]
            pulled[oid] = [input["struID"], input["calcID"]]

    for struct in rslts:
        summary = {}
        try:
            summary["oid"] = _getReq(struct, "OID")
            print(f'    Doing: {summary["oid"]}')
            summary["program"] = _getReq(struct, "Program")
            if summary["program"] == "NWChemEx":
                summary["version"] = "0.0"
                summary["wave"] = "UHF"
                summary["lib"] = _getReq(struct, "Basis")
                summary["nfncs"] = int(_getReq(struct, "BasisCnt"))
                summary["scf"] = _getE(struct, "HF")
                summary["ccsd"] = _getE(struct, "CCSD")
                summary["ccsd(t)"] = _getE(struct, "CCSDTp")
                summary["lrccsd(t)"] = 0.0
                summary["timeCPU"] = (
                    _getE(struct, "timeHF")
                    + _getE(struct, "timeCCSD")
                    + _getE(struct, "timeCSC")
                )
            else:
                summary["version"] = _getReq(struct, "Version")
                summary["wave"] = _getReq(struct, "WaveType")
                summary["lib"] = _getReq(struct, "Library")
                summary["nfncs"] = int(_getReq(struct, "FuncCnt"))
                summary["scf"] = _getE(struct, "SCF")
                summary["ccsd"] = _getE(struct, "CCSD")
                summary["ccsd(t)"] = _getE(struct, "CCSDT")
                summary["lrccsd(t)"] = _getE(struct, "LRCCSDT")
                summary["timeCPU"] = _getE(struct, "timeCPU")
        except Exception as exc:  # pylint: disable=broad-except
            print(f"!!!! {exc} !!!!")
            continue

        if summary["oid"] not in pulled:
            print(f"!!!! Can't find {summary['oid']} in {fName} !!!!")
            continue

        struID, calcID = pulled[summary["oid"]]

        # Look for various bad run flags
        bad = None

        def app(string):
            nonlocal bad
            if bad is None:
                bad = string
            else:
                bad += "," + string

        # Check for Aiida/SLURM status as well as run time
        if not struct["OK"]:
            app("NotFinished")
        if float(summary["timeCPU"]) < 0.2:
            app("NotRun")
        if summary["scf"] == 0.0:
            app("NoSCF")
        if summary["ccsd"] == 0.0:
            app("NoCCSD")
        if summary["ccsd(t)"] == 0.0 and summary["lrccsd(t)"] == 0.0:
            app("NoCCSD(T)")
        summary["bad"] = bad
        if bad is not None:
            print(f"!!!! Bad result for {summary['oid']} {bad} !!!!")

        # Get our desired entry back from the database
        structure = structures.get_structure(db.ID(struID))
        structure.link(structures)
        calculation = calculations.get_calculation(db.ID(calcID))
        calculation.link(calculations)

        energies = {}
        for typ in ["scf", "ccsd", "ccsd(t)", "lrccsd(t)"]:
            if summary[typ] < 0.0:
                energies[typ] = summary[typ]

        # make sure we update the smallest energy found last (so it sticks)
        for typ, energy in sorted(energies.items(), key=lambda x: x[1], reverse=True):
            model = calculation.get_model()
            model.basis_set = summary["lib"]
            if typ == "scf":
                model.method = "hf"
                model.method_family = "hf"
            else:
                model.method = typ
                model.method_family = "cc"
            model.spin_mode = summary["wave"]
            model.program = summary["program"]
            model.version = summary["version"]
            model.electronic_temperature = "0.0"
            calculation.set_model(model)

            prop = _store_property(
                properties,
                "electronic_energy",
                "NumberProperty",
                energy,
                model,
                calculation,
                structure,
            )
            prop.set_comment("updated")

        if summary["bad"] is not None:
            calculation.set_status(db.Status.FAILED)
            calculation.set_comment(f"BAD:{summary['bad']}")
        else:
            calculation.set_status(db.Status.COMPLETE)
            calculation.set_comment("Good run")
