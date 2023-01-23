"""
Calculations provided by aiida-nwchem

Register calculations via the "aiida.calculations" entry point in setup.json.
"""
from aiida_nwchem.calculations import NwchemBaseCalculation

######################### Start of calculations plugin ===================
# class nwchemCalc(CalcJob):
#     """
#     AiiDA calculation plugin wrapping nwchem

#     Simple AiiDA plugin wrapper for running qms modules on an input file.
#     """

#     @classmethod
#     def define(cls, spec):
#         """Define inputs and outputs of the calculation."""
#         super().define(spec)

#         # set default values for AiiDA options
#         spec.inputs["metadata"]["options"]["resources"].default = {
#             "num_machines": 1,
#             "num_mpiprocs_per_machine": 4,
#         }
#         spec.inputs["metadata"]["options"]["parser_name"].default = "nwchemex_cc.nwchem"

#         spec.input("problem", valid_type=Str, help="base name of problem")
#         spec.input("inpFile", valid_type=Str, help="NWChem input file location")
#         spec.input("outFile", valid_type=Str, help="NWChem stdout file location")
#         spec.input("errFile", valid_type=Str, help="NWChem stderr file location")
#         spec.input(
#             "restore", help="Files to restore from previous run (retrieved objects)"
#         )

#         # parsed outputs
#         spec.output("SCF", valid_type=Float, help="float, Total SCF energy")
#         spec.output(
#             "CCSD", valid_type=Float, help="float, correlation energy / hartree"
#         )
#         spec.output(
#             "CCSDT", valid_type=Float, help="float, correlation energy (T) / hartree"
#         )
#         spec.output(
#             "LRCCSDT",
#             valid_type=Float,
#             help="float, correlation energy (LR-T) / hartree",
#         )
#         spec.output("timeWall", valid_type=Float, help="wall clock time in seconds")
#         spec.output("timeCPU", valid_type=Float, help="CPU time in seconds")
#         spec.output("Contrib1", valid_type=List, help="1e contributions (top 10)")
#         spec.output("Contrib2", valid_type=List, help="2e contributions (top 10)")
#         spec.output("Library", valid_type=Str, help="Library of basis functions used")
#         spec.output("FuncCnt", valid_type=Int, help="Number of basis functions used")
#         spec.output("WaveType", valid_type=Str, help="restricted or unrestricted")
#         spec.output("Program", valid_type=Str, help="Name of program run")
#         spec.output("Version", valid_type=Str, help="Version of program")
#         # spec.output('dirFiles',valid_type=SinglefileData, help='TGZ of all the directory files after a run')

#         spec.exit_code(
#             100,
#             "ERROR_MISSING_OUTPUT_FILE",
#             message="Calculation did not produce all expected output file.",
#         )

#     def prepare_for_submission(self, folder):
#         """
#         Create input file.

#         :param folder: an `aiida.common.folders.Folder` where the plugin should temporarily place all files needed by
#             the calculation.
#         :return: `aiida.common.datastructures.CalcInfo` instance
#         """
#         codeinfo = datastructures.CodeInfo()

#         restore = self.inputs["restore"]
#         if restore is not None:
#             for nam in restore.list_object_names():
#                 with restore.open(nam, "rb") as inp:
#                     with folder.open(nam, "wb") as out:
#                         out.write(inp.read())

#         inpPth = self.inputs["inpFile"].value
#         inpNam = os.path.split(inpPth)[1]
#         with folder.open(inpNam, "w", encoding="utf8") as out:
#             with open(inpPth, encoding="utf8") as inp:
#                 out.write(inp.read(), encoding="utf8")
#         codeinfo.cmdline_params = [inpNam]
#         codeinfo.code_uuid = self.inputs.code.uuid
#         codeinfo.stdinp_name = None  # self.inputs.inpFile
#         codeinfo.stdout_name = None  # self.inputs.outFile
#         codeinfo.stderr_name = None  # self.inputs.errFile

#         # Prepare a `CalcInfo` to be returned to the engine
#         calcinfo = datastructures.CalcInfo()
#         calcinfo.codes_info = [codeinfo]

#         calcinfo.retrieve_list = [
#             "*.nw",
#             "*.std*",
#             "*.db",
#             "*.movecs",
#             "*.f1*",
#             "*.v2*",
#             "*.t1amp*",
#             "*.t2amp*",
#         ]
#         calcinfo.retrieve_temporary_list = []

#         return calcinfo


class NwchemCalculation(NwchemBaseCalculation):
    """
    Calculation plugin for NWChem that adds port for outputs produced by nwchemex_cc parser.
    """

    @classmethod
    def define(cls, spec):
        """Define inputs and outputs of the calculation."""
        super().define(spec)

        # set default values for AiiDA options
        spec.inputs["metadata"]["options"]["resources"].default = {
            "num_machines": 1,
            "num_mpiprocs_per_machine": 4,
        }
        spec.inputs["metadata"]["options"]["parser_name"].default = "nwchemex_cc.nwchem"

        # parsed outputs
        spec.output_namespace(
            "results",
            dynamic=True,
            required=False,
            help="Specific results provided by specialized parsers.",
        )
