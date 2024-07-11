from dataclasses import dataclass, field
from io import BufferedRandom
from logging import Logger
import os
import re
from typing import List, Optional, TextIO, Union, cast

from shef_loader import shared
from . import base_loader
import CWMSpy


@dataclass
class ShefTransform:
    location: str
    parameter_code: str
    timeseries_id: str
    units: Optional[str]
    timezone: Optional[str]
    dl_time: Optional[bool]


class CdaLoader(base_loader.BaseLoader):
    """
    Loader used by cwms-data-api (CDA)
    """

    def __init__(
        self,
        logger: Optional[Logger],
        output_object: Optional[Union[BufferedRandom, TextIO, str]] = None,
        append: bool = False,
    ) -> None:
        """
        Constructor
        """
        super().__init__(logger, output_object, append)
        self._cda_url = "https://cwms-data-test.cwbi.us/cwms-data/"
        self._transforms: List[ShefTransform] = []

    def set_options(self, options_str: str | None) -> None:
        """
        Set the crit file name
        """
        if not options_str:
            raise shared.LoaderException(
                f"Empty options on {self.loader_name}.set_options()"
            )

        def make_shef_transform(crit: str) -> ShefTransform:
            base, *options = crit.split(";")
            shef, timeseries_id = base.split("=")
            location, pe_code, type_code, duration_value = shef.split(".")
            duration_code = shared.DURATION_CODES[int(duration_value)]
            parameter_code = pe_code + duration_code + type_code
            timezone = dl_time = units = None
            for option in options:
                param, value = option.split("=")
                if param == "TZ":
                    timezone = value
                elif param == "DLTime":
                    if value == "true":
                        dl_time = True
                    else:
                        dl_time = False
                elif param == "Units":
                    units = value
                else:
                    if self._logger:
                        self._logger.warning("Unhandled option for {shef}: {option}")
            return ShefTransform(
                location, parameter_code, timeseries_id, units, timezone, dl_time
            )

        options = tuple(re.findall("\[(.*?)\]", options_str))
        if len(options) == 1:
            (critfile_name,) = options
        else:
            raise shared.LoaderException(
                f"{self.loader_name} expected 1 option, got [{len(options)}]"
            )
        if not os.path.exists(critfile_name) or not os.path.isfile(critfile_name):
            raise shared.LoaderException(f"Crit file [{critfile_name}] does not exist")

        try:
            with open(critfile_name) as f:
                for line_number, line in enumerate(f):
                    line = line.strip()
                    if line == "" or line[0] == "#":
                        continue
                    self._transforms.append(make_shef_transform(line))
        except Exception as e:
            if self._logger:
                self._logger.error(
                    f"{str(e)} on line [{line_number}] in {critfile_name}"
                )
                raise

    def load_time_series(self) -> None:
        """
        Output the timeseries for CDA
        """
        self.assert_value_is_set()
        sv = cast(shared.ShefValue, self._shef_value)
        if self._logger:
            self._logger.debug(f"ts_name: {self.get_time_series_name(sv)}")
            self._logger.debug(f"shef_value: {sv}")
            self._logger.debug(f"time_series: {self._time_series}")
        value_count = time_series_count = 0
        if self._time_series:
            time_series = []
            for ts in self._time_series:
                time_series.append([ts[0], ts[1]])
            time_series_count += 1
        value_count = len(time_series)
        self._value_count += value_count
        self._time_series_count += time_series_count
        self._time_series = []

    def done(self) -> None:
        """
        Load any remaining time series and close the output if necessary
        """
        super().done()
        if self._logger:
            self._logger.info(
                "--[Summary]-----------------------------------------------------------"
            )
            self._logger.info(
                f"{self._value_count} values output in {self._time_series_count} time series"
            )

    @property
    def loader_version(self) -> str:
        """
        The version string for the current loader
        """
        global loader_version
        return loader_version

    @property
    def use_value(self) -> bool:
        self.assert_value_is_set()
        # TODO: Check if critfile assignment exists
        return True


loader_options = "--loader cda[crit_file_path]\n"
loader_description = "Used by CDA to import SHEF data."
loader_version = "0.1"
loader_class = CdaLoader
can_unload = False
