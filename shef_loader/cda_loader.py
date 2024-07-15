import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BufferedRandom
import json
from logging import Logger
import os
import re
import time
from typing import Coroutine, NamedTuple, Optional, TextIO, TypedDict, Union, cast

from requests import Response

from shef_loader import shared
from . import base_loader
import CWMSpy


class ShefTransform(NamedTuple):
    location: str
    parameter_code: str
    timeseries_id: str
    units: Optional[str]
    timezone: Optional[str]
    dl_time: Optional[bool]


class CdaValue(NamedTuple):
    timestamp: str
    value: float
    quality: int


TimeseriesPayload = TypedDict(
    "TimeseriesPayload",
    {"name": str, "office-id": str, "units": str, "values": list[CdaValue]},
)


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
        self._cwms = CWMSpy.CWMS()
        self._transforms: dict[str, ShefTransform] = {}
        self._write_tasks: list[Coroutine] = []

    def set_options(self, options_str: str | None) -> None:
        """
        Set the crit file name and CDA apiKey
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
        if len(options) == 2:
            (critfile_name, cda_api_key) = options
        else:
            raise shared.LoaderException(
                f"{self.loader_name} expected 2 options, got [{len(options)}]"
            )
        if not os.path.exists(critfile_name) or not os.path.isfile(critfile_name):
            raise shared.LoaderException(f"Crit file [{critfile_name}] does not exist")

        try:
            with open(critfile_name) as f:
                for line_number, line in enumerate(f):
                    line = line.strip()
                    if line == "" or line[0] == "#":
                        continue
                    transform = make_shef_transform(line)
                    transform_key = f"{transform.location}.{transform.parameter_code}"
                    self._transforms[transform_key] = transform
        except Exception as e:
            if self._logger:
                self._logger.error(
                    f"{str(e)} on line [{line_number}] in {critfile_name}"
                )
                raise
        self._cwms.connect(self._cda_url, f"apikey {cda_api_key}")

    @property
    def transform_key(self) -> str:
        """
        The transform key for the current SHEF value
        """
        self.assert_value_is_set()
        return f"{self._shef_value.location}.{self._shef_value.parameter_code[:-1]}"

    @property
    def transform(self) -> ShefTransform:
        """
        The ShefTransform object for the current SHEF value
        """
        return self._transforms[self.transform_key]

    def get_time_series_name(self, shef_value: Optional[shared.ShefValue]) -> str:
        if shef_value is None:
            raise shared.LoaderException(f"Empty SHEF value in get_time_series_name()")
        transform_key = f"{shef_value.location}.{shef_value.parameter_code[:-1]}"
        return self._transforms[transform_key].timeseries_id

    @staticmethod
    def get_unix_timestamp(timestamp: str) -> int:
        dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
        return int(dt.timestamp() * 1000)

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
            time_series: list[CdaValue] = []
            for ts in self._time_series:
                time = self.get_unix_timestamp(ts[0])
                time_series.append([time, ts[1], 0])
            post_data: TimeseriesPayload = {}
            post_data["name"] = self.get_time_series_name(sv)
            post_data["office-id"] = "LRL"
            post_data["units"] = self.transform.units
            post_data["values"] = time_series
            task = self.create_write_task(post_data)
            self._write_tasks.append(task)
            time_series_count = 1
        value_count = len(time_series)
        self._value_count += value_count
        self._time_series_count += time_series_count
        self._time_series = []

    def create_write_task(self, post_data: str) -> Coroutine:
        return asyncio.to_thread(self._cwms.write_ts, post_data)

    async def process_write_tasks(self) -> None:
        if self._logger:
            self._logger.info("Beginning CWMS-Data-API POST tasks...")
        start_time = time.time()
        results: list[Response] = await asyncio.gather(*self._write_tasks)
        process_time = time.time() - start_time
        for response in [x for x in results if x.status_code >= 400]:
            if self._logger:
                payload = json.loads(response.request.body)
                tsid = payload["name"]
                self._logger.error(
                    f"HTTP {response.status_code}: {tsid} - {response.content}"
                )
        if self._logger:
            self._logger.info(
                f"CWMS-Data-API POST tasks complete ({process_time:.2f} seconds)"
            )

    def done(self) -> None:
        """
        Load any remaining time series and close the output if necessary
        """
        super().done()
        if self._logger:
            asyncio.run(self.process_write_tasks())
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
        return self.transform_key in self._transforms


loader_options = "--loader cda[crit_file_path][cda_api_key]\n"
loader_description = "Used by CDA to import SHEF data."
loader_version = "0.1"
loader_class = CdaLoader
can_unload = False
