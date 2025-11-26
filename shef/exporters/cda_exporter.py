import json
import sys
from datetime import datetime, timedelta
from io import BufferedRandom, StringIO
from typing import Any, Optional, TextIO, Union

import cwms  # type: ignore

from shef import loaders
from shef.exporters.abstract_exporter import AbstractExporter
from shef.loaders import abstract_loader, shared


class CdaExporter(AbstractExporter):
    """
    Helper class for using CdaLoader to export SHEF values.

    Like all loaders that support unloading, CdaLoader expects to read a loader-specific time series format from its input when unloading -
    lists of json objects from cda in this case. This class provides high level methods for feeding the desired data to CdaLoader in the
    expected format.
    """

    def __init__(self, cda_url: str, office: str):
        """
        Initializer for CdaExporter class

        Args:
            api_root (str): The CDA API root
            office (str): The office id to use
        """
        super().__init__()
        if not all([cda_url, office]):
            raise shared.LoaderException("Must specifiy api_root, api_key and office")
        self._api_root = cda_url
        self._office = office
        self._cda_loader = loaders.cda_loader.CdaLoader(self.logger, sys.stdout)
        self._cda_loader.set_options(f"[{cda_url}][][{office}]")
        self._cda_loader.make_export_transforms()

    def export(self, timeseries_or_group: str) -> None:
        """
        Exports the specified time series or group for the current time window to the current export output stream

        Args:
            timeseries_or_group (str): If a time series ID, export that time series; If a time series group ID, export each time series in that group
        """
        if len(timeseries_or_group.split(".")) == 6:
            timeseries_ids = [timeseries_or_group]
        elif timeseries_or_group in self._cda_loader._export_groups:
            timeseries_ids = self._cda_loader._export_groups[timeseries_or_group][
                "timeseries"
            ]
        total_value_count: int = 0
        value_count: int = 0
        data = StringIO()
        data.write("[")
        for tsid in timeseries_ids:
            if value_count > 0:
                data.write(",")
            unit = self._cda_loader._transforms[tsid].units
            ts = cwms.get_timeseries(
                ts_id=tsid,
                office_id=self._cda_loader._office_id,
                unit=unit,
                begin=self._start_time,
                end=self._end_time,
            )
            value_count = len(ts.json["values"])
            if value_count > 0:
                data.write(json.dumps(ts.json))
                total_value_count += value_count
        data.write("]")
        to_unload = data.getvalue()
        data.close()
        if (total_value_count) > 0:
            try:
                old_output = self._cda_loader._output
                self._cda_loader._output = self._output
                self._cda_loader.set_input(AbstractExporter.NamedStringIO(to_unload))
                self._cda_loader.unload()
            finally:
                self._cda_loader._output = old_output
                self._cda_loader._input = None

    def get_groups(self) -> dict[str, str]:
        """
        Retrieves time series groups under the "SHEF Export" time series category for the exporter's office

        Returns:
            dict[str, str]: A dictionary of time series group descriptions keyed by time series group IDs
        """
        return {
            group: self._cda_loader._export_groups[group]["description"]
            for group in self._cda_loader._export_groups
        }

    def get_time_series(self, group: str) -> list[str]:
        """
        Retrieves the time series assigned to the specifed time series group under the "SHEF Export" time series category

        Args:
            group (str): The time series group ID

        Returns:
            list[str]: The assigned time series IDs
        """
        return [ts for ts in self._cda_loader._export_groups[group]["timeseries"]]

    def get_unit(self, tsid: str) -> Optional[str]:
        """
        Retrieves the SHEF standard unit as specified in the alias for the specified time series

        Args:
            tsid (str): The time series to specify the SHEF standard unit for

        Returns:
            Optional[str]: The unit as specified in the time series alias
        """
        return self._cda_loader._transforms[tsid].units


exporter_description = "Outputs SHEF text from time series in CWMS database via CDA"
exporter_parameters = "cda_url: str, office: str"
exporter_version = "1.0.0"
exporter_class = CdaExporter
loader_class = loaders.cda_loader.CdaLoader
