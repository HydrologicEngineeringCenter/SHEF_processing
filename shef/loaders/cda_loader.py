import asyncio
from datetime import datetime, timezone
from io import BufferedRandom
from itertools import groupby
from logging import Logger
import re
import time
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
from shef.loaders import base_loader, shared
import cwms  # type: ignore


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

MAX_CONNECTIONS = 10


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
        self._cda_url: str = ""
        self._office_code: str = ""
        self._parsed_payloads: list[TimeseriesPayload] = []
        self._payloads: list[TimeseriesPayload] = []
        self._time_series_error_count: int = 0
        self._transforms: dict[str, ShefTransform] = {}
        self._value_error_count: int = 0
        self._write_tasks: list[Coroutine] = []

    def set_options(self, options_str: Union[str, None]) -> None:
        """
        Set the office code, CDA URL, and CDA apikey
        """
        if not options_str:
            raise shared.LoaderException(
                f"Empty options on {self.loader_name}.set_options()"
            )

        def make_shef_transform(crit: dict) -> ShefTransform:
            """
            Create a ShefTransform object based on the provided SHEF time series group item
            """
            office = crit["office-id"]
            time_series_id = crit["timeseries-id"]
            shef, options_str = crit["alias-id"].split(":")
            options = options_str.split(";")
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
                office,
                location,
                parameter_code,
                time_series_id,
                units,
                timezone,
                dl_time,
            )

        options = tuple(re.findall(r"\[(.*?)\]", options_str))
        if len(options) == 2:
            self._cda_url = options[0]
            cda_api_key = options[1]
        else:
            raise shared.LoaderException(
                f"{self.loader_name} expected 2 options, got [{len(options)}]"
            )

        cwms.init_session(api_root=self._cda_url, api_key=f"apikey {cda_api_key}")

        shef_group = cwms.get_timeseries_group(
            group_office_id="CWMS",
            category_office_id="CWMS",
            group_id="SHEF Data Acquisition",
            category_id="Data Acquisition",
        ).json
        try:
            for time_series in shef_group["assigned-time-series"]:
                transform = make_shef_transform(time_series)
                transform_key = f"{transform.location}.{transform.parameter_code}"
                self._transforms[transform_key] = transform
        except Exception as e:
            if self._logger:
                self._logger.error(
                    f"{str(e)} occurred while processing SHEF criteria for {time_series['timeseries-id']}"
                )
                raise

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

    def get_time_series_name(self, shef_value: Optional[shared.ShefValue]) -> str:
        """
        Get the time series ID for the current SHEF value
        """
        if shef_value is None:
            raise shared.LoaderException("Empty SHEF value in get_time_series_name()")
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

    def load_time_series(self) -> None:
        """
        Store SHEF values as CDA POST payloads grouped by time series ID
        """
        if self._shef_value and self._time_series:
            sv = cast(shared.ShefValue, self._shef_value)
            if self._logger:
                self._logger.debug(f"ts_name: {self.get_time_series_name(sv)}")
                self._logger.debug(f"shef_value: {sv}")
                self._logger.debug(f"time_series: {self._time_series}")
            if self._time_series:
                time_series: list[CdaValue] = []
                for ts in self._time_series:
                    time = self.get_unix_timestamp(ts[0])
                    time_series.append(CdaValue(time, ts[1], 0))
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

    def create_write_task(self, post_data: TimeseriesPayload) -> Coroutine:
        """
        Create an async CDA POST request coroutine for provided post_data
        """
        post_data_dict = cast(dict[str, Any], post_data)

        async def limited_task():
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

    async def store_cda_data(self):
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

    @property
    def loader_version(self) -> str:
        """
        The version string for the current loader
        """
        global loader_version
        return loader_version

    @property
    def use_value(self) -> bool:
        """
        Returns true if criteria exist for the current ShefValue
        """
        self.assert_value_is_set()
        return self.transform_key in self._transforms


loader_options = (
    "--loader cda[cda_url][cda_api_key]\n"
    "cda_url     = the url of the CDA instance to be used, e.g. https://cwms-data.usace.army.mil/cwms-data/\n"
    "cda_api_key = the api_key to use for CDA POST requests\n"
)
loader_description = "Used to import SHEF data through cwms-data-api.  Requires cwms-python v0.6.0 or greater."
loader_version = "0.3"
loader_class = CdaLoader
can_unload = False
