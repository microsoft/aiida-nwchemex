"""
Parsers provided by aiida-nwchemex.

Register parsers via the "aiida.parsers" entry point in setup.json.
"""

import json
from pathlib import Path
import re

from aiida import orm
from aiida.common import exceptions
from aiida.engine import ExitCode
from aiida.parsers.parser import Parser
from aiida.plugins import CalculationFactory

nwchemexCalc = CalculationFactory("nwchemex.nwchemexCalc")


def remove_prefix(text, prefix):
    """Remove prefix from text."""
    return text[text.startswith(prefix) and len(prefix) :]


class NwchemexParser(Parser):
    """
    Parser class for parsing output of calculation.
    """

    def __init__(self, node):
        """
        Initialize Parser instance

        Checks that the ProcessNode being passed was produced by a nwchemexCalculation.

        :param node: ProcessNode of calculation
        :param type node: :class:`aiida.orm.ProcessNode`
        """
        super().__init__(node)
        if not issubclass(node.process_class, nwchemexCalc):
            raise exceptions.ParsingError("Can only parse Nwchemex calculations")

    def parse(self, **kwargs):
        """
        Parse outputs, store results in database.

        :returns: an exit code, if parsing fails (or nothing if parsing succeeds)
        """
        # pylint: disable=too-many-locals,too-many-return-statements

        # Check that folder content is as expected
        output_filename = self.node.get_option("output_filename")
        files_retrieved = self.retrieved.base.repository.list_object_names()
        files_expected = [output_filename]
        # Note: set(A) <= set(B) checks whether A is a subset of B
        if not set(files_expected) <= set(files_retrieved):
            self.logger.error(
                f"Found files '{files_retrieved}', expected to find '{files_expected}'"
            )
            return self.exit_codes.ERROR_MISSING_OUTPUT_FILES

        stderr_content = self.node.get_scheduler_stderr()
        if stderr_content and "error:" in stderr_content.lower():
            self.logger.error(f"Error(s) occurred during execution:\n{stderr_content}")
            return self.exit_codes.ERROR_EXECUTION

        # add output file
        # stdout_content = self.node.get_scheduler_stdout()
        # add output file
        self.logger.info(f"Adding '{output_filename}'")
        with self.retrieved.base.repository.open(output_filename, "rb") as handle:
            output_node = orm.SinglefileData(file=handle)
        self.out("log_file", output_node)

        log_content = output_node.get_content()
        # Note: this could be a restart handler that resubmits the calculation with the
        # right number of ranks. If this problem arises because of a hardware failure,
        # however, such a handler would only work if the job is resubmitted to the same
        # (problematic) machine.
        if re.findall(
            "#ranks per node(.+) > #gpus(.+) per node ... terminating program.",
            log_content,
        ):
            self.logger.error(log_content)
            return self.exit_codes.ERROR_RANK_GPU_MISMATCH

        if re.findall(
            "#ERROR(.+)Left tensor dims H2D copy failed. invalid device symbol",
            log_content,
        ):
            self.logger.error(log_content)
            return self.exit_codes.ERROR_UNSUPPORTED_CUDA_ARCHITECTURE

        if not "time taken" in log_content.lower():
            self.logger.error(
                f"Time taken not reported, suspected failure:\n{log_content}"
            )
            return self.exit_codes.ERROR_RUNTIME_MISSING

        # get JSON files
        retrieve_temporary_list = self.node.get_attribute(
            "retrieve_temporary_list", None
        )

        # If temporary files were specified, check that we have them
        if retrieve_temporary_list:
            try:
                retrieved_temporary_folder = kwargs["retrieved_temporary_folder"]
            except KeyError:
                return self.exit_codes.ERROR_NO_RETRIEVED_TEMPORARY_FOLDER

        input_dict = self.node.inputs.parameters.get_dict()
        json_files = Path(retrieved_temporary_folder).glob("*.json")

        PREFIX = f"{nwchemexCalc.DEFAULT_PROBLEM_NAME}.{input_dict['basis']['basisset']}."  #  pylint:disable=protected-access

        json_dict = {}
        for json_file in json_files:
            method = remove_prefix(json_file.stem, PREFIX)
            self.logger.info(f"Adding output dictionary for method {method}")
            with json_file.open("r", encoding="utf8") as handle:
                json_dict[method] = orm.Dict(dict=json.load(handle))
            # self.out(f"json.{method}", json_dict[method])
        self.out("json", json_dict)

        return ExitCode(0)
