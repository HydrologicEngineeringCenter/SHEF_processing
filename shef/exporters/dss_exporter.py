import os
import platform
import sys
from datetime import datetime
from io import StringIO
from typing import Any, Optional

from hecdss import Catalog, HecDss  # type: ignore
from hecdss.record_type import RecordType  # type: ignore

from shef import loaders
from shef.exporters.abstract_exporter import AbstractExporter
from shef.loaders import shared

valid_e_parts = [
    "IR-Day",
    "IR-Month",
    "IR-Year",
    "IR-Decade",
    "IR-Century",
    "~1Minute",
    "~2Minute",
    "~3Minute",
    "~4Minute",
    "~5Minute",
    "~6Minute",
    "~10Minute",
    "~12Minute",
    "~15Minute",
    "~20Minute",
    "~30Minute",
    "~1Hour",
    "~2Hour",
    "~3Hour",
    "~4Hour",
    "~6Hour",
    "~8Hour",
    "~12Hour",
    "~1Day",
    "~2Day",
    "~3Day",
    "~4Day",
    "~5Day",
    "~6Day",
    "~1Week",
    "~1Month",
    "~1Year",
    "1Minute",
    "2Minute",
    "3Minute",
    "4Minute",
    "5Minute",
    "6Minute",
    "10Minute",
    "12Minute",
    "15Minute",
    "20Minute",
    "30Minute",
    "1Hour",
    "2Hour",
    "3Hour",
    "4Hour",
    "6Hour",
    "8Hour",
    "12Hour",
    "1Day",
    "2Day",
    "3Day",
    "4Day",
    "5Day",
    "6Day",
    "1Week",
    "Tri-Month",
    "Semi-Month",
    "1Month",
    "1Year",
]


class DssExporter(AbstractExporter):
    """
    Helper class for using DssLoader to export SHEF values.

    Like all loaders that support unloading, DssLoader expects to read a loader-specific time series format from its input when unloading.
    This class provides high level methods for feeding the desired data to CdaLoader in the expected format.
    """

    def __init__(
        self, dss_filename: str, sensor_filename: str, parameter_filename: str
    ):
        """
        Initializer for DssExporter class

        Args:
            api_root (str): The CDA API root
            office (str): The office id to use
        """
        super().__init__()
        if not all([dss_filename, sensor_filename, parameter_filename]):
            raise shared.LoaderException(
                "Must specifiy dss_filename, sensor_filename, and parameter_filename"
            )
        if not os.path.exists(dss_filename) and not os.path.exists(
            f"{dss_filename}.dss"
        ):
            raise shared.LoaderException(
                f"Specified HEC-DSS file does not exist: {dss_filename}"
            )
        self._dss_filename = dss_filename
        HecDss.set_global_debug_level(int(os.getenv("DSS_MESSAGE_LEVEL", "4")))
        self._dss_file: HecDss = HecDss(dss_filename)
        self._catalog: Catalog = self._dss_file.get_catalog()
        self._dss_loader: loaders.dss_loader.DssLoader = loaders.dss_loader.DssLoader(
            self.logger, sys.stdout
        )
        self._dss_loader.set_options(
            f"[{dss_filename}][{sensor_filename}][{parameter_filename}]"
        )
        basedir: str = (
            os.path.join(os.getenv("USERPROFILE", ""), "Application Data")
            if platform.system() == "Windows"
            else "~"
        )
        self._groups_filename: str = os.path.join(
            basedir, "HEC", "HEC-DSSVue", "groups.txt"
        )

    def __del__(self) -> None:
        if self._dss_file:
            self._dss_file.close()

    def export(self, identifier: str) -> None:
        """
        Exports one of the following to the current export output stream:
        * The specified time series in the current HEC-DSS file for the current time window
        * The group as configured using HEC-DSSVue

        Args:
            identifier (str): Must be a time series pathname in the HEC-DSS file or the name of a group as configured using HEC-DSSVue
        """
        if len(identifier.split("/")) == 8:
            # ----------------- #
            # export a pathname #
            # ----------------- #
            if self._catalog.get_record_type(identifier) not in (
                RecordType.RegularTimeSeries,
                RecordType.IrregularTimeSeries,
            ):
                self.logger.warning(
                    f"Cannot export {identifier}: No such record or record is not time series"
                )
                return
            ts = self._dss_file.get(
                identifier, startdatetime=self._start_time, enddatetime=self._end_time
            )
            data = StringIO()
            data.write(f"{identifier}\n")
            data.write(f"\t{{'unit': '{ts.units}', 'type': '{ts.data_type}'}}\n")
            for i in range(len(ts.values)):
                data.write(
                    f"\t['{ts.times[i].strftime('%Y-%m-%d %H:%M')}:00', {ts.values[i]}]\n"
                )
            self._dss_loader.set_input(AbstractExporter.NamedStringIO(data.getvalue()))
            data.close()
            try:
                old_output = self._dss_loader._output
                self._dss_loader._output = self._output
                self._dss_loader.unload()
            finally:
                self._dss_loader._output = old_output
                self._dss_loader._input = None
        else:
            # -------------- #
            # export a group #
            # -------------- #
            groups: dict[str, dict[str, Any]] = self.get_groups()
            try:
                group = groups[identifier]
            except KeyError:
                self.logger.warning(
                    f"Cannot export {identifier}: No such group defined in {self._groups_filename}"
                )
                return
            # -------------------------------------- #
            # save original DSS file and time window #
            # -------------------------------------- #
            orig_time_window = (self._start_time, self._end_time)
            orig_dss_file = self._dss_file
            if group["timewindow"]:
                # -------------------------------------------------- #
                # set the time window to that specified in the group #
                # -------------------------------------------------- #
                try:
                    from hec import hectime  # type: ignore
                    from hec.hectime import HecTime  # type: ignore
                except ImportError:
                    self.logger.warning(
                        f"Cannot export {identifier}: package hec is not installed. (pip install hec-python-library)"
                    )
                    return
                start_time = HecTime()
                end_time = HecTime()
                if hectime.get_time_window(group["timewindow"], start_time, end_time):
                    self.logger.warning(
                        f"Cannot export {identifier}: invalid time window: {group['timewindow']}"
                    )
                    return
                self._start_time = start_time.datetime()
                self._end_time = end_time.datetime()
            last_filename = None
            opened_dss_files: list[list[Any]] = []
            for filename, pathname in group["datasets"]:
                # ---------------------------------------------------------- #
                # open the DSS file for the dataset if it's not already open #
                # ---------------------------------------------------------- #
                if filename != last_filename and not os.path.samefile(
                    filename, self._dss_filename
                ):
                    for i in range(len(opened_dss_files)):
                        if os.path.samefile(filename, opened_dss_files[i][0]):
                            last_filename = opened_dss_files[i][0]
                            self._dss_file = opened_dss_files[i][1]
                            break
                    else:
                        last_filename = filename
                        opened_dss_files.append([filename, HecDss(filename)])
                    self._dss_file = opened_dss_files[-1][1]
                # ------------------ #
                # export the dataset #
                # ------------------ #
                self.export(pathname)
            # -------------------------------------------------------------------------------------- #
            # close any DSS files opened for the group and restore original DSS file and time window #
            # -------------------------------------------------------------------------------------- #
            for filename, dssfile in opened_dss_files:
                dssfile.close()
            self._dss_file = orig_dss_file
            self._start_time, self._end_time = orig_time_window

    def get_groups(self) -> dict[str, dict[str, Any]]:
        """
        Retrieves groups defined in HEC-DSSVue

        Returns:
            list: A list of groups as defined in HEC-DSSVue
        """
        groups: dict[str, dict[str, Any]] = {}
        group: str
        if os.path.exists(self._groups_filename):
            with open(self._groups_filename) as f:
                for line in f:
                    if line.startswith("Group:"):
                        group = line.strip().split(" ", 1)[1]
                        groups[group] = {"timewindow": None, "datasets": []}
                    elif line.startswith("TimeWindow:"):
                        groups[group]["timewindow"] = line.strip().split(" ", 1)[1]
                    elif line.startswith("Name:"):
                        groups[group]["datasets"].append(
                            [None, line.strip().split(" ", 1)[1]]
                        )
                    elif line.startswith("File:"):
                        groups[group]["datasets"][-1][0] = line.strip().split(" ", 1)[1]
                    else:  # End or blank line
                        pass
            for group in groups:
                for i in range(len(groups[group]["datasets"]))[::-1]:
                    e_part = groups[group]["datasets"][i][1].split("/")[5]
                    if e_part not in valid_e_parts:
                        del groups[group]["datasets"][i]
        else:
            self.logger.warning(f"Groups file does not exist: {self._groups_filename}")
        return groups

    def get_time_window_str(self, group: str) -> Optional[str]:
        """
        Retrieves the time window string, if any, for the specified time series group

        Args:
            group (str): The time series group ID

        Returns:
            Optonal[str]: The time window string or None if no time window is specified for the group
        """
        try:
            twstr: Optional[str] = self.get_groups()[group]["timewindow"]
        except KeyError:
            self.logger.error(f"No such group: {group}")
        return twstr

    def get_time_window(self, group: str) -> Optional[list[datetime]]:
        """
        Retrieves the time window, if any, for the specified time series group as a list of datetime objects

        Args:
            group (str): The time series group ID

        Returns:
            Optional[list[datetime]]: A list comprising the start time and end time of the time window or None if no time window is specified for the groupa
        """
        try:
            twstr: Optional[str] = self.get_groups()[group]["timewindow"]
        except KeyError:
            self.logger.error(f"No such group: {group}")
            return None
        if not twstr:
            return None
        try:
            from hec import hectime
            from hec.hectime import HecTime
        except ImportError:
            self.logger.warning(
                f"Cannot parse time window: module hec is does not exist. (Run 'pip install hec-python-library' to fix)"
            )
            return None
        start_time = HecTime()
        end_time = HecTime()
        if hectime.get_time_window(twstr, start_time, end_time):
            self.logger.warning(f"Invalid time window: {twstr}")
            return None
        return [start_time.datetime(), end_time.datetime()]

    def get_time_series(self, group: str) -> list[list[str]]:
        """
        Retrieves the time in the specifed time series group

        Args:
            group (str): The time series group ID

        Returns:
            list[list[str]]: The time series in the group. Each time series is a list of two items: the HEC-DSS file name, and the pathname
        """
        try:
            datasets: list[list[str]] = self.get_groups()[group]["datasets"]
        except KeyError:
            self.logger.error(f"No such group: {group}")
        return datasets


exporter_description = "Outputs SHEF text from time series in HEC-DSS Files"
exporter_parameters = "dss_filename: str, sensor_filename: str, parameter_filename: str"
exporter_version = "1.0.0"
exporter_class = DssExporter
loader_class = loaders.dss_loader.DssLoader
