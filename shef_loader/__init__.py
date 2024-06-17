'''
# Package shef_loader

This package includes modules to be used for loading (storing) SHEF data (as parsed by the `shefParser` program) to specific data stores, and optionally unloading (generating SHEF text) from specific data stores. Each module is responsible for one data store type. Note that depending on the purpose of the loader, loading may consist only of outputting parsed SHEF data to an output stream in a loader-specific format to be used by a non-Python program to perform the actual loading. If a loader supports unloading, the inverse may be true (i.e., a non-Python program unloads the data store into a data stream which the loader then reads to generate the SHEF text).

### Contents:

- [How It Works](#how-it-works)
- [Module Requirements](#module-requirements)
- [The Shared Module](#the-shared-module)
- [Base Class Members](#base-class-members)

## How It Works
Normally, `shefLoader` parses SHEF text and outputs each value on a single line in one of two text formats also output by the NOAA/NWS `shefit` program. Specifying the `--loader` option to `shefParser` changes the behavior as follows:

1. Instantiates the loader via `__init__(self, logger: Optional[Logger], output_object: Optional[Union[BufferedRandom, TextIO, str]] = None, append: bool = False) -> None`, where:
    - `logger` is a `logging.Logger` object or `None`
    - `output_object` is a file-like object, file name, or `None`
    - `append` controls whether the output is overwritten or appended to (if applicable)
2. Initializes the loader via `set_options(self, options_str: Optional[str]) -> None`, where `options_str` is a loader-specific string used to set all options necessary to perform loading and, optionally, unloading
3. For each value, calls the loader method `set_shef_value(self, value_str: str) -> None` where `value_str` is the value as a `shefParser -f1 (or --format 1)` string. This method then:
    - Compares the loader-specific time series name of the value to that of the previous value, if any.
    - If there was a previous value and the the time series name is different, calls the loader method `load_time_series(self) -> None`.
    - Accumulates the value into the loader variable `_time_series`
4. Terminates by calling the loader method `done(self) -> None`. This calls the loader `load_time_series(self) -> None` to load the last accumlated time series

Specifying the `--unload` option to `shefParser` changes the behavior so that instead of items 3 and 4 above, `shefParser` calls the loader method `unload(self) -> None` once.

## Module Requirements
Each loader module must have several module-level variables and one module-level class that extends class `dummy_loader.DummyLoader`.

|variable|description|
|--|--|
|`loader_options: str`|Specifies how the user specifies the module to `shefParser`. This should be `--loader <module_name><options>`. <*module_name*> may the the full module name or *xxx* if the module is named *xxx*_loader. <*options*> is loader-specific, but <*module_name*><*options*> must be passed as a single string. `loader_options` may be a multi-line string.|
|`loader_description: str`|Describes the loader. May be a multi-line string.|
|`loader_version: str`|The version identifier of the loader module.|
|`loader_class: class`|The class in the module that extends `dummy_loader.DummyLoader`.|
|`can_unload: bool`|Specifies whether the loader class has an `unload()` method.|

These variables are typically defined at the bottom of the module since the loader class must be defined before the `loader_class` variable.

## The Shared Module
The packages contains a module name `shared` which provides the following items:
#### Types
|type|description|
|--|--|
|`ShefValue: namedtuple("ShefValue")`|Holds all information for a single SHEF value|

#### Variables
|variable|description|
|--|--|
|`DURATION_CODES: dict[int, str]`|SHEF duration character by numeric value|
|`DURATION_VALUES: dict[str, int]`|SHEF duration numeric value by character|
|`PROBABILITY_CODES: dict[float, str]`|SHEF probability numeric value by character|
|`PROBABILITY_VALUES: dict[str, float]`|SHEF probability character by numberic value|
|`SEND_CODES: dict[str, tuple[str, bool]]`|(<*parameter_code*>, <*value_time_is_prev_0700*>) by send code|
|`VALUE_UNITS_PATTERN: re.Pattern`|matches pattern `([0-9]+)([a-z]+)` case insensitive|

#### Functions
|function|description|
|--|--|
|`make_shef_value(format_1_line: str) -> ShefValue`|Creates a `ShefValue` object from a shefParser -f 1 (shefit -1) line.|
|`get_datetime(datetime_str: str) -> datetime`|Creates a `datetime.datetime` object from a string like "yyyy-mm-dd hh:nn:ss".|
|`duration_interval(parameter_code: str) -> timedelta`|Creates a `datetime.timedelta` object that represents the duration in a SHEF parameter code.|

#### Exceptions
|exception|description|
|--|--|
|`LoaderException(Exception)`|Used to partition loader exceptions from other exceptions.|

## Base Class Members

The class `dummy_loader.DummyLoader` provides the following fields and methods:

#### Fields
|field|description|
|--|--|
|`_logger: Optional[Logger]`|The logger. Populated from constructor|
|`_output: Optional[Union[BufferedRandom, TextIO]]`|The output device. Populated by constructor.|
|`_append: bool`|Whether to `_output` was opened for append. Populated by constructor.|
|`_shef_value: Optional[shared.ShefValue]`|The current `ShefValue` object. Populated by `set_shef_value()`|
|`_time_series: list[list]`|The current accumulated time series. Populated by `set_shef_value()`. Depopulated by `load_time_series()`|
|`_value_count: int = 0`|The number of values processed so far. Initialized by constructor. Updated by `load_time_series()` in subclass.|
|`_time_series_count: int = 0`|The number of time series processed so far. Initialized by constructor. Updated by `load_time_series()` in subclass.|

#### Methods
|method|description|
|--|--|
|`__init__(self, logger: Optional[Logger], output_object: Optional[Union[BufferedRandom, TextIO, str]] = None, append: bool = False) -> None`|Constructor. **Must be overridden, but be sure to call `super()__init__()` at beginning of subclass constructor.**|
|`set_options(self, options_str: Optional[str]) -> None`|Initializer. **Override if loader takes any configuration options.**|
|`assert_value_is_set(self) -> None`|Raises `shared.LoaderException` if there is no current `ShefValue` object. **Should not need to override.**|
|`assert_value_is_recognized(self) -> None`|Raises `shared.LoaderException` if the current `ShefValue` object is not recognized as a time series. **Should not need to override.**|
|`output(self, s: str) -> None`|Sends a string to the output. No exception is raised if `_output is None`. **Should not need to override unless the subclass uses `_output` as a non-stream file output (e.g., HDF5, HEC-DSS).**|
|`get_time_series_name(self, shef_value: Optional[shared.ShefValue]) -> str`|Returns the loader-specific time series name for a specified `shefValue` object. Raises `shared.LoaderException` if the `shef_value` parameter is empty or None. **Override if loader requires something other than <*shef_location*>.<*shef_parameter_code*> for a time series name.**|
|`set_shef_value(self, value_str: str) -> None`|Sets the current `ShefValue` object, after calling `load_time_series()` if necessary. Appends properties [`date_time`, `value`, `data_qualifier`, `forecast_date_time`] to `_time_series`. **Override only if loader requires additional items**.|
|`load_time_series(self) -> None`|Loads accumulated time series to data store. **Must be overridden**.|
|`done(self) -> None`|Calls `load_time_series()` and closes `_output` if open. **Should not need to override unless the subclass uses `_output` as a non-stream file output (e.g., HDF5, HEC-DSS).**|

#### Read-Only Properties
|property|description|
|--|--|
|`loader_name: str`|The class name of the loader. **Should not need to be overridden.**|
|`loader_version: str`|The version ID string of the loader module. **Must be overridden.**|
|`output_name: str`|The name of the output device (`_output`), if any. **Should not need to be overridden.**|
|`time_series_name: str`|The time series name of the current `shefValue` object as returned by `get_time_series_name()`. Calls `assert_value_is_set()` **Should not need to be overridden.**|
|`use_value: bool`|Whether the time series represented by the current `ShefValue` object is recognized by the loader. Calls `assert_value_is_set()`. Used by `assert_value_is recognized`. **Must be overridden.**|
|`location: str`|The location name of the current `ShefValue` object. Calls `assert_value_is_set()`. **Override if the loader requires anything other than the SHEF location identifier.***|
|`loading_info: dict`|A dictionary of information generated from the current `ShefValue` object and/or the loader configuration options that is required to load the time series to the data store. Calls `assert_value_is_set()`. **Override only if such a dictionary is necessary.**|
|`date_time: str`|The observation time of the current `ShefValue` object in `"yyyy-mm-dd hh:nn:ss"` format. Calls `assert_value_is_set()`. **Override if another format for the observation time is required.**|
|`forecast_date_time: str`|The forecast time (creation time) of the current `ShefValue` object in `"yyyy-mm-dd hh:nn:ss"` format. If the value has no forecast time, the value is `"0000-00-00 00:00:00"`. Calls `assert_value_is_set()`. **Override if another format for the forecast time is required.**|
|`parameter: str`|The parameter name of the current `ShefValue` object. Calls `assert_value_is_set()`. **Override if the loader requires anything other than the SHEF parameter code.**|
|`value: float`|The data value of the current `ShefValue` object. Calls `assert_value_is_set()`. **Override if the loader requires anything other than the value in SHEF English units.**|
|`data_qualifier: str`|The data value qualifier of the current `ShefValue` object. Calls `assert_value_is_set()`. **Override if the loader requires anything other than the SHEF data qualifier.**|
|`duration_interval: datetime.timedelta`|The duration of the current `ShefValue` object as a `datetime.timedelta` object. Calls `assert_value_is_set()`. Calls `shared.durtion_interval()`. **Should not need to override.**|__all__: list = []

See https://github.com/HydrologicEngineeringCenter/SHEF_processing/blob/master/shef_loader/Readme.md for formatted version
'''
__all__ : list = []
from . import dummy_loader
from . import dssvue_loader

