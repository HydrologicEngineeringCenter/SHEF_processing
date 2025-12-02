import asyncio
import json
import math
import re
import time
from datetime import datetime, timezone
from io import BufferedRandom, StringIO, TextIOWrapper
from itertools import groupby
from logging import Logger
from typing import (
    Any,
    Callable,
    Coroutine,
    NamedTuple,
    Optional,
    TextIO,
    Tuple,
    TypedDict,
    Union,
    cast,
)

import cwms  # type: ignore

from shef.loaders import abstract_loader, shared

MS_DAY = 86400 * 1000
MS_HOUR = 3600 * 1000
MS_MINUTE = 60 * 1000
MS_SECOND = 1 * 1000


class ShefTransform(NamedTuple):
    office: str
    location: str
    parameter_code: str
    timeseries_id: str
    units: Optional[str]
    timezone: Optional[str]
    dl_time: Optional[bool]


class CdaValue(NamedTuple):
    timestamp: int
    value: float
    quality: int


class TimeSeriesResponse(TypedDict):
    name: str
    values: list[CdaValue]


TimeseriesPayload = TypedDict(
    "TimeseriesPayload",
    {"name": str, "office-id": str, "units": Optional[str], "values": list[CdaValue]},
)

CWMS_INTERVAL_PATTERN: str = r"([0-9]+)(\w+)"

CWMS_INTERVAL_SECONDS: dict[str, int] = {
    "Second": 1,
    "Seconds": 1,
    "Minute": 60,
    "Minutes": 60,
    "Hour": 3600,
    "Hours": 3600,
    "Day": 86400,
    "Days": 86400,
}

SHEF_INTERVAL_MS: dict[str, int] = {
    "DID": 86400 * 1000,
    "DIH": 3600 * 1000,
    "DIN": 60 * 1000,
    "DIS": 1 * 1000,
}

MAX_CONNECTIONS = 10


class CdaLoader(abstract_loader.AbstractLoader):
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
        self._cda_url: str = ""
        self._export_groups: dict[str, dict[str, Any]] = {}
        self._input: Optional[Union[BufferedRandom, TextIOWrapper]] = None
        self._message_count: int = 0
        self._office_id: str = ""
        self._parsed_payloads: list[TimeseriesPayload] = []
        self._payloads: list[TimeseriesPayload] = []
        self._time_series_error_count: int = 0
        self._transforms: dict[str, ShefTransform] = {}
        self._value_error_count: int = 0
        self._write_tasks: list[Coroutine[Any, Any, Any]] = []
        self._configured_pe_codes = set()

    def make_shef_transform(self, crit: dict[str, Any]) -> ShefTransform:
        """
        Create a ShefTransform object based on the provided SHEF time series group item
        """
        office = crit["office-id"]
        time_series_id = crit["timeseries-id"]
        try:
            shef, options_str = crit["alias-id"].split(":")
            options = options_str.split(";")
        except:
            shef, options = crit["alias-id"], []
        location, pe_code, type_code, duration_value = shef.split(".")
        self._configured_pe_codes.add(pe_code)
        duration_code = shared.DURATION_CODES[int(duration_value)]
        parameter_code = pe_code + duration_code + type_code
        timezone = dl_time = units = None
        for option in options:
            if len(option.split("=")) == 2:
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
                        self._logger.warning(f"Unhandled option for {shef}: {option}")
            else:
                if self._logger:
                    self._logger.warning(f"Unhandled option for {shef}: {option}")
        return ShefTransform(
            office,
            location,
            parameter_code,
            time_series_id,
            units,
            timezone,
            dl_time,
        )

    def set_options(self, options_str: Union[str, None]) -> None:
        """
        Set the office code, CDA URL, and CDA apikey
        """
        if not options_str:
            raise shared.LoaderException(
                f"Empty options on {self.loader_name}.set_options()"
            )

        options = self.get_options(options_str)
        if len(options) > 2:
            self._office_id = options[2]
        if len(options) > 1:
            self._cda_url = options[0]
            cda_api_key = options[1]
        else:
            raise shared.LoaderException(
                f"{self.loader_name} expected 2 or 3 options, got [{len(options)}]"
            )

        if cda_api_key:
            cwms.init_session(api_root=self._cda_url, api_key=f"apikey {cda_api_key}")
        else:
            cwms.init_session(
                api_root=self._cda_url, api_key=None
            )  # don't need api key if unloading

    @property
    def transform_key(self) -> str:
        """
        The transform key for the current SHEF value
        """
        self.assert_value_is_set()
        sv = cast(shared.ShefValue, self._shef_value)
        return f"{sv.location}.{sv.parameter_code[:-1]}"

    @property
    def transform(self) -> ShefTransform:
        """
        The ShefTransform object for the current SHEF value
        """
        return self._transforms[self.transform_key]

    def make_transforms(self) -> None:
        """
        Makes the loading transforms
        """
        shef_group = cwms.get_timeseries_group(
            group_office_id="CWMS",
            category_office_id="CWMS",
            group_id="SHEF Data Acquisition",
            category_id="Data Acquisition",
        ).json
        try:
            for assigned_ts in shef_group["assigned-time-series"]:
                transform = self.make_shef_transform(assigned_ts)
                transform_key = f"{transform.location}.{transform.parameter_code}"
                self._transforms[transform_key] = transform
        except Exception as e:
            if self._logger:
                self._logger.warning(
                    f"{str(e)} occurred while processing SHEF criteria for {assigned_ts['timeseries-id']}"
                )

    def get_additional_pe_codes(self, parser_recognized_pe_codes: set[str]) -> set[str]:
        """
        Return any PE codes recognized by this loader that aren't otherwised recognized by the parser
        """
        if not self._transforms:
            self.make_transforms()
        return self._configured_pe_codes - parser_recognized_pe_codes

    def get_time_series_name(self, shef_value: Optional[shared.ShefValue]) -> str:
        """
        Get the time series ID for the current SHEF value
        """
        if shef_value is None:
            raise shared.LoaderException("Empty SHEF value in get_time_series_name()")
        if not self._transforms:
            self.make_transforms()
        transform_key = f"{shef_value.location}.{shef_value.parameter_code[:-1]}"
        return self._transforms[transform_key].timeseries_id

    @staticmethod
    def get_unix_timestamp(timestamp: str) -> int:
        """
        Convert a SHEFIT timestamp string to a Unix timestamp in milliseconds
        """
        dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
        return int(dt.timestamp() * 1000)

    @staticmethod
    def get_python_datetime(unix_time: int) -> datetime:
        return datetime.fromtimestamp(unix_time / 1000, tz=timezone.utc)

    def load_time_series(self) -> None:
        """
        Store SHEF values as CDA POST payloads grouped by time series ID
        """

        if self._shef_value and self._time_series:
            sv = self._shef_value
            if self._logger:
                self._logger.debug(f"ts_name: {self.get_time_series_name(sv)}")
                self._logger.debug(f"shef_value: {sv}")
                self._logger.debug(f"time_series: {self._time_series}")
            if self._time_series:
                time_series: list[CdaValue] = []
                for ts in self._time_series:
                    time = self.get_unix_timestamp(ts[0])
                    time_series.append(CdaValue(time, float(ts[1]), 0))
                post_data: TimeseriesPayload = {
                    "name": self.get_time_series_name(sv),
                    "office-id": self.transform.office,
                    "units": self.transform.units,
                    "values": time_series,
                }
                match_index = self.find_matching_payload_index(post_data)
                if not match_index:
                    self._payloads.append(post_data)
                else:
                    match_payload = self._payloads[match_index]
                    match_payload["values"].extend(time_series)
            self._time_series = []

    def create_write_task(
        self, post_data: TimeseriesPayload
    ) -> Coroutine[Any, Any, Any]:
        """
        Create an async CDA POST request coroutine for provided post_data
        """
        post_data_dict = cast(dict[str, Any], post_data)

        async def limited_task() -> Coroutine[Any, Any, Any]:
            async with self._semaphore:
                return await asyncio.to_thread(
                    cwms.store_timeseries,
                    data=post_data_dict,
                    store_rule="REPLACE WITH NON MISSING",
                )

        return limited_task()

    async def process_write_tasks(self) -> None:
        """
        Submit CDA POST requests and report results
        """
        if self._logger:
            self._logger.info("Beginning CWMS-Data-API POST tasks...")
        start_time = time.time()
        results = await asyncio.gather(*self._write_tasks, return_exceptions=True)
        for i, result in enumerate(results):
            payload = self._parsed_payloads[i]
            tsid = payload["name"]
            value_count = len(payload["values"])
            if isinstance(result, BaseException):
                self._value_error_count += value_count
                self._time_series_error_count += 1
                if self._logger:
                    self._logger.error(
                        f"Failed to store {value_count} values in {tsid}",
                        exc_info=result,
                    )
            else:
                self._value_count += value_count
                self._time_series_count += 1
                if self._logger:
                    self._logger.info(f"Stored {value_count} values in {tsid}")
        process_time = time.time() - start_time
        if self._logger:
            self._logger.info(
                f"CWMS-Data-API POST tasks complete ({process_time:.2f} seconds)"
            )

    def find_matching_payload_index(
        self, payload: TimeseriesPayload
    ) -> Union[int, None]:
        """
        Get index of matching payload for tsid, office, and units
        """
        for i, this_payload in enumerate(self._payloads):
            if (
                payload["name"] == this_payload["name"]
                and payload["office-id"] == this_payload["office-id"]
                and payload["units"] == this_payload["units"]
            ):
                return i
        return None

    def parse_payload_tasks(self) -> None:
        """
        Prepare POST request payloads and create an async coroutine for each

        Payloads are grouped based on the corresponding time series interval.
        Irregular and pseudo-irregular intervals are always combined.  Regular
        intervals are combined when no gaps are present.
        """

        def get_cwms_interval_ms(cwms_interval: str) -> int:
            """
            Return the integer-equivalent to a CWMS interval string (in milliseconds)
            """
            match = re.match(CWMS_INTERVAL_PATTERN, cwms_interval)
            if match:
                quantity = int(match.group(1))
                unit = match.group(2)
                multiplier = CWMS_INTERVAL_SECONDS[unit] * 1000
                return quantity * multiplier
            else:
                raise shared.LoaderException(
                    f"Could not parse CWMS interval string: {cwms_interval}"
                )

        def group_by_interval(interval: int) -> Callable[[Tuple[int, CdaValue]], float]:
            """
            Return a group_values function for the specified interval (in milliseconds)
            """

            def group_values(enum_tuple: Tuple[int, CdaValue]) -> float:
                """
                Group continuous series of timestamps based on a chosen interval
                """
                index, cda_value = enum_tuple
                timestamp = cda_value.timestamp
                group_key = (timestamp / interval) - index
                return group_key

            return group_values

        def remove_duplicate_timestamps(
            tsid: str, values: list[CdaValue]
        ) -> list[CdaValue]:
            """
            Return a list of CdaValues with no duplicate timestamps
            """
            cleaned_values: list[CdaValue] = []
            used_timestamps: list[int] = []
            for value in values:
                if value.timestamp in used_timestamps:
                    if self._logger:
                        self._logger.warning(
                            f"Removing duplicate timestamp {value.timestamp} for {tsid}"
                        )
                else:
                    used_timestamps.append(value.timestamp)
                    cleaned_values.append(value)
            return cleaned_values

        for payload in self._payloads:
            payload["values"].sort(key=lambda x: x.timestamp)
            payload["values"] = remove_duplicate_timestamps(
                payload["name"], payload["values"]
            )
            cwms_interval_str = payload["name"].split(".")[3]
            if cwms_interval_str == "0" or cwms_interval_str[0] == "~":
                self._parsed_payloads.append(payload)
                task = self.create_write_task(payload)
                self._write_tasks.append(task)
                continue
            interval = get_cwms_interval_ms(cwms_interval_str)
            for _, group in groupby(
                enumerate(payload["values"]), group_by_interval(interval)
            ):
                values = [x[1] for x in group]
                this_payload = payload.copy()
                this_payload["values"] = values
                self._parsed_payloads.append(this_payload)
                task = self.create_write_task(this_payload)
                self._write_tasks.append(task)

    async def store_cda_data(self) -> None:
        self._semaphore = asyncio.Semaphore(MAX_CONNECTIONS)
        self.parse_payload_tasks()
        await self.process_write_tasks()

    def done(self) -> None:
        """
        Submit all collected CDA POST requests
        """
        super().done()
        asyncio.run(self.store_cda_data())
        if self._logger:
            self._logger.info(
                "--[Summary]-----------------------------------------------------------"
            )
            self._logger.info(
                f"{self._value_count} values posted in {self._time_series_count} time series"
            )
            if self._value_error_count > 0:
                self._logger.info(
                    f"Errors occurred for {self._value_error_count} values in {self._time_series_error_count} time series"
                )

    def set_input(self, input_object: Union[StringIO, TextIO, str]) -> None:
        """
        Attach the message unload input stream
        """
        if self._input:
            raise shared.LoaderException("Input has already been set")
        if isinstance(input_object, (StringIO, TextIOWrapper)):
            self._input = input_object  # type: ignore
        elif isinstance(input_object, str):
            self._input = open(input_object)
        else:
            raise shared.LoaderException(
                f"Expected TextIOWrapper or str object, got [{input_object.__class__.__name__}]"
            )

    def make_export_transforms(self) -> None:
        if not self._office_id:
            raise shared.LoaderException(
                f"Cannot unload without office specified, use options [api_root][api_key][office]"
            )
        if not self._transforms:
            tsids_used: dict[str, list[str]] = {}
            group_list = cwms.get_timeseries_groups(
                office_id=self._office_id,
                include_assigned=True,
                timeseries_category_like="SHEF Export",
                timeseries_group_like="^.+$",
                category_office_id="CWMS",
            ).json
            for shef_group in group_list:
                group_id = shef_group["id"]
                self._export_groups[group_id] = {
                    "description": shef_group["description"],
                    "timeseries": [],
                }
                try:
                    for time_series in shef_group["assigned-time-series"]:
                        transform = self.make_shef_transform(time_series)
                        transform_key = (
                            f"{transform.location}.{transform.parameter_code}"
                        )
                        self._transforms[transform_key] = transform
                        if transform.timeseries_id in tsids_used:
                            if self._logger:
                                self._logger.warning(
                                    f"Tranform for time seires {transform.timeseries_id} specified in group(s) "
                                    f"{','.join(tsids_used[transform.timeseries_id])} is/are overriden by transform specified in group {group_id}"
                                )
                        self._export_groups[group_id]["timeseries"].append(
                            transform.timeseries_id
                        )
                        tsids_used.setdefault(transform.timeseries_id, []).append(
                            group_id
                        )
                        self._transforms[transform.timeseries_id] = (
                            transform  # to be able to retrieve by time series ID
                        )
                except Exception as e:
                    if self._logger:
                        self._logger.warning(
                            f"{str(e)} occurred while processing SHEF criteria for {time_series['timeseries-id']}"
                        )

    def unload(self) -> None:
        """
        Read a list of CDA time series response objects in JSON format and output SHEF
        """
        self.make_export_transforms()
        if not self._input:
            raise shared.LoaderException(
                "No input file specified before calling unload() method"
            )
        if self._logger:
            self._logger.info(
                f"Generating SHEF text from CDA Time Series responses via file [{self._input.name}]"
            )

        # -------------------------------------------#
        # read the input stream and output SHEF text #
        # -------------------------------------------#
        input_data = self._input.read()
        try:
            input_json = json.loads(input_data)
        except json.JSONDecodeError as e:
            if self._logger:
                self._logger.error(
                    "Error encountered while parsing CDA Time Series response JSON object:"
                )
                raise e

        cda_data = cast(list[TimeSeriesResponse], input_json)
        for ts_response in cda_data:
            self.output_time_series_as_shef(ts_response)

        if self._input.name != "<stdin>":
            self._input.close()

        if self._logger:
            self._logger.info(
                "--[Summary]-----------------------------------------------------------"
            )
            self._logger.info(
                f"{self._value_count} values output in {self._message_count} messages from {self._time_series_count} time series"
            )

    def output_time_series_as_shef(self, time_series: TimeSeriesResponse) -> None:
        """
        Output all time series values in SHEF format

        Uses .E format if the time series has multiple values with a consistent
        interval. Otherwise uses .A format.
        """
        try:
            transform = self.get_transform_for_tsid(time_series["name"])
        except TypeError as e:
            if self._logger:
                self._logger.error(
                    "Input must be a list of CDA Time Series response objects"
                )
            raise e
        if not transform:
            if self._logger:
                self._logger.warning(
                    f"No transform found for {time_series['name']} -- skipping..."
                )
            return
        values = time_series["values"]
        intervals = self.get_timestamp_differences(values)
        if len(values) == 1 or len(intervals) > 1:
            shef_messages = self.build_shef_a_from_time_series(time_series, transform)
        else:
            shef_messages = self.build_shef_e_from_time_series(time_series, transform)
        self._time_series_count += 1
        self.output(shef_messages + "\n")

    def build_shef_a_from_time_series(
        self, time_series: TimeSeriesResponse, transform: ShefTransform
    ) -> str:
        """
        Return a SHEF .A string for a time series
        """
        shef_lines = []
        for value in time_series["values"]:
            timestamp = self.get_python_datetime(value[0])
            date_str = timestamp.strftime("%Y%m%d")
            time_str = timestamp.strftime("%H%M%S")
            message = [".A"]
            message.append(transform.location)
            message.append(date_str)
            message.append("Z")
            message.append("DH" + time_str + "/" + transform.parameter_code)
            message.append("%.10g\n" % value[1])
            shef_lines.append(" ".join(message))
            self._value_count += 1
            self._message_count += 1
        return "".join(shef_lines)

    def build_shef_e_from_time_series(
        self, time_series: TimeSeriesResponse, transform: ShefTransform
    ) -> str:
        """
        Return a SHEF .E string for a time series
        """
        max_message_len = 132
        shef_lines: list[str] = []
        interval_ms = self.get_timestamp_differences(time_series["values"]).pop()
        interval_str = self.get_shef_interval_from_ms(interval_ms)
        timestamp = self.get_python_datetime(time_series["values"][0][0])
        date_str = timestamp.strftime("%Y%m%d")
        time_str = timestamp.strftime("%H%M%S")
        header = [".E"]
        header.append(transform.location)
        header.append(date_str)
        header.append("Z")
        header.append(f"DH{time_str}/{transform.parameter_code}/{interval_str}")
        shef_lines.append(" ".join(header))

        line_num = 1
        line = self.start_continuation_line("E", line_num)
        for value in time_series["values"]:
            value_str = (
                "-/" if value[1] is None or math.isnan(value[1]) else f"{value[1]:.6g}/"
            )
            if len(line + value_str) > max_message_len:
                shef_lines.append(line)
                line_num += 1
                line = self.start_continuation_line("E", line_num)
            line += value_str
            self._value_count += 1
        shef_lines.append(line)

        self._message_count += 1
        return "\n".join(shef_lines) + "\n"

    @staticmethod
    def start_continuation_line(format: str, number: int) -> str:
        """
        Return the beginning of a SHEF continuation line, e.g. ".E1 "
        """
        return f".{format}{number:.3g} "

    @staticmethod
    def get_shef_interval_from_ms(time_series_ms: int) -> Optional[str]:
        """
        Return SHEF interval code (e.g. DIH01) for an interval in ms
        """
        for interval_code, interval_ms in SHEF_INTERVAL_MS.items():
            if time_series_ms % interval_ms == 0:
                num_units = time_series_ms / interval_ms
                return f"{interval_code}{int(num_units):02}"
        return None

    def get_transform_for_tsid(self, tsid: str) -> Optional[ShefTransform]:
        """
        Return the ShefTransform for a given time series id (or None)
        """
        matching_transforms = [
            x for x in self._transforms.values() if x.timeseries_id == tsid
        ]
        return matching_transforms[0] if matching_transforms else None

    @staticmethod
    def get_timestamp_differences(values: list[CdaValue]) -> set[int]:
        """
        For a list of time series values, return all unique timestamp deltas
        """
        diff = []
        for i in range(1, len(values)):
            diff.append(values[i][0] - values[i - 1][0])
        return set(diff)

    @property
    def use_value(self) -> bool:
        """
        Returns true if criteria exist for the current ShefValue
        """
        self.assert_value_is_set()
        return self.transform_key in self._transforms


loader_options = (
    "--loader cda[cda_url][cda_api_key]\n"
    "* cda_url = the url of the CDA instance to be used, e.g. https://cwms-data.usace.army.mil/cwms-data/\n"
    "* cda_api_key = the api_key to use for CDA POST requests\n"
)
loader_description = (
    "Used to import and export SHEF data through cwms-data-api.\n"
    "For unloading, input a list of CDA /timeseries responses.\n"
    "Requires cwms-python v0.6.3 or greater."
)
loader_version = "0.5"
loader_class = CdaLoader
can_unload = True
