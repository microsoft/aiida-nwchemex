"""
Calculations provided by aiida-nwchemex

Register calculations via the "aiida.calculations" entry point in setup.json.
"""
import json

from jsonschema import validate

from aiida import orm
from aiida.common import datastructures
from aiida.engine import CalcJob

from . import SCHEMA_DIR

with open(SCHEMA_DIR / "input_schema.json", encoding="utf8") as _handle:
    NWCHEMEX_INPUT_SCHEMA = json.load(_handle)


def _is_valid_nwchemex_input(input_dict, _port):
    """Validate NWCHEMEX input dictionary."""
    return validate(instance=input_dict.get_dict(), schema=NWCHEMEX_INPUT_SCHEMA)


class NwchemexCalculation(CalcJob):
    """
    AiiDA calculation plugin wrapping nwchemex

    Takes input files and can restore files from a previous calculation.
    """

    DEFAULT_PROBLEM_NAME = "problem"
    _DEFAULT_INPUT_FILE_NAME = f"{DEFAULT_PROBLEM_NAME}.json"
    _DEFAULT_LOG_FILE_NAME = f"{DEFAULT_PROBLEM_NAME}.log"

    @classmethod
    def define(cls, spec):
        """Define inputs and outputs of the calculation."""
        super().define(spec)

        # set default values for AiiDA options
        spec.inputs["metadata"]["options"]["resources"].default = {
            "num_machines": 1,
            "num_mpiprocs_per_machine": 5,
        }
        spec.inputs["metadata"]["options"]["withmpi"].default = True
        spec.inputs["metadata"]["options"]["parser_name"].default = "nwchemex.nwchemex"
        spec.input(
            "metadata.options.output_filename",
            valid_type=str,
            default=cls._DEFAULT_LOG_FILE_NAME,
        )

        # input ports
        spec.input(
            "parameters",
            valid_type=orm.Dict,
            validator=_is_valid_nwchemex_input,
            help="NWChemEx input dictionary",
        )
        spec.input(
            "restart_folder",
            valid_type=orm.RemoteData,
            help="Working directory of a previous calculation to restart from",
            required=False,
        )

        # parsed outputs
        spec.output("log_file", valid_type=orm.SinglefileData, help="NWChemEx output")
        spec.output_namespace(
            "json",
            dynamic=True,
            required=False,
            help="JSON output of NWChemEx",
            valid_type=orm.Dict,
        )
        spec.output_namespace(
            "results",
            dynamic=True,
            required=False,
            help="Specific results provided by specialized parsers.",
        )

        spec.exit_code(
            100,
            "ERROR_MISSING_OUTPUT_FILES",
            message="Calculation did not produce all expected output files.",
        )
        spec.exit_code(
            301,
            "ERROR_NO_RETRIEVED_TEMPORARY_FOLDER",
            message="The retrieved temporary folder could not be accessed.",
        )
        spec.exit_code(
            302,
            "ERROR_RUNTIME_MISSING",
            message="NWChemEx output did not include runtime (calculation likely did not terminate successfully).",
        )
        spec.exit_code(
            303,
            "ERROR_RANK_GPU_MISMATCH",
            message="Number of MPI ranks did not match number of GPUs plus one.",
        )
        spec.exit_code(
            304,
            "ERROR_UNSUPPORTED_CUDA_ARCHITECTURE",
            message="The architecture of your CUDA device may not be supported by this version of NWChemEx."
            + " Consider rebuilding with '-DGPU_ARCH=all'.",
        )
        spec.exit_code(
            305,
            "ERROR_EXECUTION",
            message="Error during execution (stderr contains 'error:').",
        )

    def prepare_for_submission(self, folder):
        """
        Create input file.

        :param folder: an `aiida.common.folders.Folder` where the plugin should temporarily place all files needed by
            the calculation.
        :return: `aiida.common.datastructures.CalcInfo` instance
        """
        input_dict = self.inputs.parameters.get_dict()
        with folder.open(self._DEFAULT_INPUT_FILE_NAME, "w", encoding="utf8") as handle:
            json.dump(input_dict, handle)

        codeinfo = datastructures.CodeInfo()
        codeinfo.cmdline_params = [self._DEFAULT_INPUT_FILE_NAME]
        codeinfo.stdout_name = self.metadata.options.output_filename
        codeinfo.code_uuid = self.inputs.code.uuid

        # Prepare a `CalcInfo` to be returned to the engine
        calcinfo = datastructures.CalcInfo()
        calcinfo.codes_info = [codeinfo]

        output_folder = (
            f"{self.DEFAULT_PROBLEM_NAME}.{input_dict['basis']['basisset']}_files/"
        )
        calcinfo.retrieve_list = [
            codeinfo.stdout_name,
            # "_scheduler-stderr.txt",
            # "_scheduler_stdout.txt",
        ]
        # Typical folder structure
        #   problem.cc-pvdz_files/unrestricted/         <= scf json here
        #   problem.cc-pvdz_files/unrestricted/scf/     <= orthogonalizer json here
        # No need to store the JSON files since they will be fully stored in dictionary form
        calcinfo.retrieve_temporary_list = [
            (output_folder + "*/*.json", "", 0),
            (output_folder + "*/*/*.json", "", 0),
        ]

        # Symlinks.
        calcinfo.remote_symlink_list = []
        calcinfo.remote_copy_list = []
        if "restart_folder" in self.inputs:
            comp_uuid = self.inputs.restart_folder.computer.uuid
            remote_path = self.inputs.restart_folder.get_remote_path()
            copy_info = (comp_uuid, remote_path + f"/{output_folder}", output_folder)

            # If running on the same computer - make a symlink.
            if self.inputs.code.computer.uuid == comp_uuid:
                calcinfo.remote_symlink_list.append(copy_info)
            # If not - copy the folder.
            else:
                calcinfo.remote_copy_list.append(copy_info)

        return calcinfo
