import re
from loaders  import shared
from datetime import timedelta
from logging  import Logger
from io       import BufferedRandom
from io       import TextIOWrapper
from typing   import cast
from typing   import Optional
from typing   import TextIO
from typing   import Union

class BaseLoader :
    '''
    Base class for all SHEF data loaders.
    This class simply writes the SHEF information to the output for "loading"
    '''
    def __init__(self, logger: Optional[Logger], output_object: Optional[Union[BufferedRandom, TextIO, str]] = None, append: bool = False) -> None :
        '''
        Constructor
        '''
        self._logger: Optional[Logger] = logger
        self._append: bool = append
        self._shef_value: Optional[shared.ShefValue] = None
        self._time_series: list[list] = []
        self._value_count: int = 0
        self._time_series_count: int = 0
        self._output: Optional[Union[BufferedRandom, TextIO]]
        if output_object is None :
            self._output = None
            self._output_name = None
            self._output_opened = False
        elif isinstance(output_object, (BufferedRandom, TextIOWrapper)) :
            self._output = output_object
            self._output_name = output_object.name
            self._output_opened = False
        elif isinstance(output_object, str) :
            self._output = open(output_object, "a+b" if append else "w+b")
            self._output_name = output_object
            self._output_opened = True
        else :
            raise shared.LoaderException(f"Unexpected object type for output device: [{output_object.__class__.__name__}]")
        if self._logger :
            self._logger.info(f"{self.loader_name} v{self.loader_version} instatiated")

    def set_options(self, options_str: Optional[str]) -> None :
        '''
        Set the loader-specific options. This loader takes none, but other loaders should take option strings
        in the format of [option_1][option_2]... with the options in square brackts. Use the parse_options
        method to extract the actual positional options. If key/value options are required, encode those into
        positional options (e.g., [key1=val2][key2=val2]) and the process into a dictionary
        '''
        if options_str :
            options = tuple(re.findall("\[(.*?)\]", options_str))
            if self._logger :
                self._logger.info(f"{self.loader_name} initialized with {str(options)}")

    def get_additional_pe_codes(self, parser_recognized_pe_code: set) -> set :
        '''
        Return any PE codes recognized by this loader that aren't otherwised recognized by the parser
        '''
        return set()

    def assert_value_is_set(self) -> None :
        '''
        Called from methods that require a ShefValue to be set
        '''
        if not self._shef_value :
            raise shared.LoaderException("setvalue() has not been called on loader")

    def assert_value_is_recognized(self) -> None :
        '''
        Called from methods that require the current ShefValue to be recognized by the loader
        '''
        if not self.use_value :
            raise shared.LoaderException(f"Loader does not use value {self.time_series_name}")

    def output(self, s: str) -> None :
        '''
        Write a string to the loader output device
        '''
        if self._output is not None :
            if isinstance(self._output, TextIOWrapper) :
                self._output.write(s)
            elif isinstance(self._output, BufferedRandom) :
                self._output.write(s.encode("utf-8"))

    def set_shef_value(self, value_str: str) -> None :
        '''
        Sets the current ShefValue for the loader loading any data accumulated if the time series name has changed
        '''
        try :
            shef_value = shared.make_shef_value(value_str)
            if self._shef_value is None :
                #-------------#
                # first value #
                #-------------#
                self._shef_value = shef_value
                try:
                    self.time_series_name  # Test for valid time_series_name property
                    if self.use_value :
                        self._time_series.append([self.date_time, self.value, self.data_qualifier, self.forecast_date_time])
                except (KeyError, shared.LoaderException) as e:
                    if self._logger:
                        self._logger.error(shared.exc_info(e))
                    self._shef_value = None  # Reset _shef_value until valid value found
            else :
                #-------------------#
                # subsequent values #
                #-------------------#
                if self.get_time_series_name(shef_value) == self.time_series_name :
                    #------------------#
                    # same time series #
                    #------------------#
                    self._shef_value = shef_value
                    if self.use_value :
                        self._time_series.append([self.date_time, self.value, self.data_qualifier, self.forecast_date_time])
                else :
                    #-----------------#
                    # new time series #
                    #-----------------#
                    self.load_time_series()
                    self._shef_value = shef_value
                    if self.use_value :
                        self._time_series.append([self.date_time, self.value, self.data_qualifier, self.forecast_date_time])
        except Exception as e :
            if self._logger :
                self._logger.error(shared.exc_info(e))

    def load_time_series(self) -> None :
        '''
        Load or output the timeseries in a loader-specific manner
        '''
        if self._logger :
            self._logger.info(f"Storing {len(self._time_series)} values to {self.time_series_name}")
        if self._time_series :
            self.output(f"{self.time_series_name}\n")
            for ts in sorted(self._time_series) :
                output_str = ", ".join(map(str, ts))
                self.output(f"\t{output_str}\n")
        self._time_series = []

    def done(self) -> None :
        '''
        Load any remaining time series and close the output if necessary
        '''
        self.load_time_series()
        if self._output and self._output_opened :
            self._output.close()
            self._output = None
            self._output_name = None

    def get_time_series_name(self, shef_value: Optional[shared.ShefValue]) -> str :
        '''
        Get the loader-specific time series name for a specified SHEF value
        '''
        if not shef_value :
            raise shared.LoaderException("shef_value is None")
        return f"{shef_value.location}.{shef_value.parameter_code}"

    @property
    def loader_name(self) -> str :
        '''
        The class name of the current loader
        '''
        return self.__class__.__name__

    @property
    def loader_version(self) -> str :
        '''
        The class name of the current loader
        '''
        global loader_version
        return loader_version

    @property
    def output_name(self) -> Optional[str] :
        '''
        The name of the output device, if any
        '''
        return self._output_name

    @property
    def time_series_name(self) -> str :
        '''
        Get the loader-specific time series name for the current SHEF value
        '''
        self.assert_value_is_set()
        return self.get_time_series_name(self._shef_value)

    @property
    def use_value(self) -> bool :
        '''
        Get whether the current ShefValue is recognized by the loader
        '''
        self.assert_value_is_set()
        return True

    @property
    def location(self) -> str :
        '''
        Get the loader-specific location name
        '''
        self.assert_value_is_set()
        return f"{cast(shared.ShefValue, self._shef_value).location}"

    @property
    def loading_info(self) -> dict :
        '''
        Get the loader-specific metadata required to load the time series
        '''
        self.assert_value_is_set()
        return {}

    @property
    def date_time(self) -> str :
        '''
        Get the observation date/time of the current ShefValue
        '''
        self.assert_value_is_set()
        sv: shared.ShefValue = cast(shared.ShefValue, self._shef_value)
        return f"{sv.obs_date} {sv.obs_time}"

    @property
    def forecast_date_time(self) -> str :
        '''
        Get the creation date/time, if any, of the current ShefValue
        '''
        self.assert_value_is_set()
        sv: shared.ShefValue = cast(shared.ShefValue, self._shef_value)
        return "" if sv.create_date == "0000-00-00" else f"{sv.create_date} {sv.create_time}"

    @property
    def parameter(self) -> str :
        '''
        Get the loader-specific parameter name of the current ShefValue
        '''
        self.assert_value_is_set()
        sv: shared.ShefValue = cast(shared.ShefValue, self._shef_value)
        return f"{sv.parameter_code}"

    @property
    def value(self) -> float :
        '''
        Get the loader-specific data value of the current ShefValue
        '''
        self.assert_value_is_set()
        sv: shared.ShefValue = cast(shared.ShefValue, self._shef_value)
        return sv.value

    @property
    def data_qualifier(self) -> str :
        '''
        Get the loader-specific data value qualifier of the current ShefValue
        '''
        self.assert_value_is_set()
        sv: shared.ShefValue = cast(shared.ShefValue, self._shef_value)
        return f"{sv.data_qualifier}"

    @property
    def duration_interval(self) -> timedelta :
        '''
        Get the SHEF duration of the current ShefValue as a timedelta object
        '''
        self.assert_value_is_set()
        sv: shared.ShefValue = cast(shared.ShefValue, self._shef_value)
        return shared.duration_interval(sv.parameter_code)

loader_options = "--loader dummy"
loader_description = "Base class for other SHEF data loaders. Writes SHEF information to output"
loader_version = "1.1"
loader_class = BaseLoader
can_unload = False
