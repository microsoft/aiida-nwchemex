"""
Parsers provided by aiida-nwchem.

Register parsers via the "aiida.parsers" entry point in setup.json.
"""

# pylint: disable=too-many-locals,too-many-statements,too-many-branches,broad-except
import re

from aiida_nwchem.parsers import NwchemBaseParser

from aiida import orm
from aiida.engine import ExitCode
from aiida.orm import Float, Int, List, Str
from aiida.plugins import CalculationFactory

from aiida_nwchemex.parsers import NwchemexParser

nwchemCalc = CalculationFactory("nwchemex_cc.nwchem")


def _getNum(lst, isFloat=True, wantMin=True):
    """Find the best match to use and save it as a node"""
    if len(lst) == 0:
        lst = ["0"]
    else:
        lst = [max(x, key=len) for x in lst]  # Pick off longest match
    if isFloat:
        lst = [float(x) for x in lst]
        if wantMin:
            node = Float(min(lst))
        else:
            node = Float(max(lst))
    else:
        lst = [int(x) for x in lst]
        if wantMin:
            node = Int(min(lst))
        else:
            node = Int(max(lst))
    return node


def _getContrib(doNWChem, contents, reCtrbHead, reCtrbVal, count=10):
    # Now need to get the single and double contributions
    gather = 0
    singles = []
    doubles = []
    reBlank = re.compile(r"^\s*\n")
    if doNWChem:
        tst1 = "Singles"
        tst2 = "Doubles"
    else:
        tst1 = "1"
        tst2 = "2"
    for line in contents.split("\n"):
        m1 = reCtrbHead.match(line)
        m2 = reCtrbVal.match(line)
        m3 = reBlank.match(line)
        if gather == 0 and m1 is not None:
            if m1.group(1) == tst1:
                gather = 1
            elif m1.group(1) == tst2:
                gather = 2
            else:
                raise Exception("Bad contributions header")

        elif gather in [1, 2] and m2 is not None:
            if gather == 1:
                singles.append(float(m2.group(1)))
            elif gather == 2:
                doubles.append(float(m2.group(1)))
            else:
                raise Exception("Bad contributions value")

        elif m3 is not None:
            pass
        elif gather == 2:
            break

    # Keep the top n by abs magnitude
    singles.sort(key=lambda num: -abs(num))
    doubles.sort(key=lambda num: -abs(num))
    singles = [x for x in singles[:count] if x >= 0.1]
    doubles = [x for x in doubles[:count] if x >= 0.1]
    return (singles, doubles)


class CCNwchemParser(NwchemBaseParser):
    """Parses CCNwchemCalculation."""

    def parse(self, **kwargs):
        """
        Reuses nwchem.parse() and adds specific 'results' for the CCNwchemCalculation.

        :returns: an exit code, if parsing fails (or nothing if parsing succeeds)
        """
        exit_code = super().parse(**kwargs)
        if exit_code != ExitCode(0):
            return exit_code

        patFP = r"([+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?)"
        reSCF = re.compile(r"Total SCF energy =\s*" + patFP)
        reCCSD = re.compile(r"CCSD total energy / hartree\s+=\s*" + patFP)
        reCCSDT = re.compile(r"CCSD\(T\) total energy / hartree\s+=\s*" + patFP)
        reLRCCSDT = re.compile(r"LR-CCSD\(T\)IIB total energy / hartree\s+=\s*" + patFP)
        reCtrbHead = re.compile(r"\s*([a-zA-Z]+) contributions")
        reCtrbVal = re.compile(r"^\s+\d+.*\)\s+" + patFP)
        reTime = re.compile(r"Total times  cpu:\s+([0-9.]+)s\s+wall:\s+([0-9.]+)s")
        # reLabel = re.compile(r"# Label: (\S+)")
        reLibrary = re.compile(r"\* library (\S+)")
        reFuncCnt = re.compile(r"# This job contains (\d+)")
        reGAoffset = re.compile(r"\d+ ga offset\s+\d+ size_xx_perproc\s+\d+mx\s+\d+\s+")
        reWave = re.compile(r"Wavefunction.*[:=].*(UHF|Unrestricted)")
        reNwChem = re.compile(r"\(NWChem\) ([0-9.]+)")

        # Parse the output file
        # pylint: disable=protected-access
        with self.retrieved.open(
            self.node.process_class._DEFAULT_OUTPUT_FILE, "r"
        ) as handle:
            contents = handle.read().replace("\00", "")

        # Kludge becuase GA can write on top of other output
        contents = reGAoffset.sub("", contents)

        # Need to parse the outFile (do this last in case it blows up)
        SCF = 0.0
        CCSD = 0.0
        CCSDT = 0.0
        LRCCSDT = 0.0
        timeCPU = 0.0
        timeWall = 0.0
        singles = []
        doubles = []
        library = ""
        funcCnt = 0
        program = ""
        version = ""

        SCF = _getNum(reSCF.findall(contents))
        CCSD = _getNum(reCCSD.findall(contents))
        CCSDT = _getNum(reCCSDT.findall(contents))
        LRCCSDT = _getNum(reLRCCSDT.findall(contents))
        m = reTime.search(contents)
        if m:
            timeCPU = float(m.group(1))
            timeWall = float(m.group(2))
        m = reLibrary.search(contents)
        if m:
            library = m.group(1)
        m = reFuncCnt.search(contents)
        if m:
            funcCnt = int(m.group(1))
        m = reWave.search(contents)
        if m:
            waveType = "unrestricted"
        else:
            waveType = "restricted"
        m = reNwChem.search(contents)
        if m:
            program = "NwChem"
            version = m.group(1)

        # Now need to get the single and double contributions
        singles, doubles = _getContrib(True, contents, reCtrbHead, reCtrbVal, 10)

        # Save away parsed items
        self.out("results.SCF", SCF)
        self.out("results.CCSD", CCSD)
        self.out("results.CCSDT", CCSDT)
        self.out("results.LRCCSDT", LRCCSDT)
        # note: this is the "Total times" wall/cpu, while the aiida-nwchem parser parses the "Task times"
        self.out("results.timeWall", Float(timeWall))
        self.out("results.timeCPU", Float(timeCPU))
        self.out("results.Contrib1", List(list=singles))
        self.out("results.Contrib2", List(list=doubles))
        self.out("results.Library", Str(library))
        self.out("results.FuncCnt", Int(funcCnt))
        self.out("results.WaveType", Str(waveType))
        self.out("results.Program", Str(program))
        self.out("results.Version", Str(version))

        return ExitCode(0)


class CCNwchemexParser(NwchemexParser):
    """Parses CCNwchemexCalculation."""

    def parse(self, **kwargs):
        """
        Reuses NwchemexParser.parse() and adds specific 'results' for the CCNwchemexCalculation.

        :returns: an exit code, if parsing fails (or nothing if parsing succeeds)
        """
        exit_code = super().parse(**kwargs)
        if exit_code != ExitCode(0):
            return exit_code

        code = self.node.inputs["code"].get_executable().stem
        outputs = self.outputs
        self.logger.info(f"Parsing output of '{code}' calculation.")

        if code == "HartreeFock":
            hf_dict = outputs.json["scf"].get_dict()
            self.out("results.Basis", orm.Str(hf_dict["input"]["molecule"]["basisset"]))
            self.out("results.HF", orm.Float(hf_dict["output"]["SCF"]["final_energy"]))

            ortho_dict = outputs.json["orthogonalizer"].get_dict()
            self.out("results.BasisCnt", orm.Int(ortho_dict["ortho_dims"][0]))
        elif code == "CholeskyDecomp":
            pass
        elif code == "CD_CCSD":
            ccsd_dict = outputs.json["ccsd"].get_dict()
            self.out(
                "results.CCSD",
                orm.Float(ccsd_dict["output"]["CCSD"]["final_energy"]["total"]),
            )
        elif code == "CCSD_T":
            pass
        else:
            raise ValueError(f"Unknown code {code}")

        # log-file-based parsing (not yet provided via JSON files)
        contents = outputs.log_file.get_content()

        patFP = r"([+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?)"

        if code == "HartreeFock":
            reTimeHF = re.compile(r"Time taken for Hartree-Fock:\s+" + patFP)
            timeHF = _getNum(reTimeHF.findall(contents), wantMin=False)
            self.out("results.timeHF", timeHF)
        elif code == "CholeskyDecomp":
            reTimeCholesky = re.compile(r"Time taken for CD \(\+SVD\):\s+" + patFP)
            timeCholesky = _getNum(reTimeCholesky.findall(contents), wantMin=False)
            self.out("results.timeChol", timeCholesky)

        elif code == "CD_CCSD":
            reTimeCSCc = re.compile(
                r"Time taken for Closed Shell Cholesky CCSD:\s+" + patFP
            )
            reTimeCSCo = re.compile(
                r"Time taken for Open Shell Cholesky CCSD:\s+" + patFP
            )
            timeCSCc = _getNum(reTimeCSCc.findall(contents), wantMin=False)
            timeCSCo = _getNum(reTimeCSCo.findall(contents), wantMin=False)
            timeCSC = max(timeCSCc, timeCSCo)
            self.out("results.timeCSC", timeCSC)
        elif code == "CCSD_T":
            reCCSDTb = re.compile(r"CCSD\[T\] total energy / hartree\s+=\s+" + patFP)
            reCCSDTp = re.compile(r"CCSD\(T\) total energy / hartree\s+=\s+" + patFP)
            reCtrbHead = re.compile(r"T([12]) amplitudes")
            reCtrbVal = re.compile(r"^" + patFP)
            reTimeCCSD = re.compile(r"Total CCSD\(T\) Time:\s+" + patFP)
            CCSDTb = _getNum(reCCSDTb.findall(contents))
            CCSDTp = _getNum(reCCSDTp.findall(contents))
            singles, doubles = _getContrib(False, contents, reCtrbHead, reCtrbVal, 5)
            timeCCSD = _getNum(reTimeCCSD.findall(contents), wantMin=False)
            self.out("results.CCSDTb", CCSDTb)
            self.out("results.CCSDTp", CCSDTp)
            self.out("results.Contrib1", orm.List(list=singles))
            self.out("results.Contrib2", orm.List(list=doubles))
            self.out("results.timeCCSD", timeCCSD)

        else:
            raise ValueError(f"Unknown code {code}")

        return ExitCode(0)
