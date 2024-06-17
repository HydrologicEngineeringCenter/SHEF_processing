import re
from .        import shared
from datetime import timedelta
from logging  import Logger
from io       import BufferedRandom
from io       import TextIOWrapper
<<<<<<< HEAD
from typing   import cast
from typing   import Optional
=======
>>>>>>> master
from typing   import TextIO
from typing   import Union

class DummyLoader :
    '''
    Base class for all SHEF data loaders.
    This class simply writes the SHEF information to the output for "loading"
    '''
<<<<<<< HEAD
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
=======
    def __init__(self, logger: Union[None, Logger], output_object: Union[TextIO, str] = None, append: bool = False) -> None :
        '''
        Constructor
        '''
        global loader_version
        self._logger = logger
        self._append = append
        self._shef_value = None
        self._prev_shef_value = None
        self._time_series = []
        self._value_count = 0
        self._time_series_count = 0
>>>>>>> master
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
<<<<<<< HEAD
            self._logger.info(f"{self.loader_name} v{self.loader_version} instatiated")

    def set_options(self, options_str: Optional[str]) -> None :
=======
            self._logger.info(f"{self.loader_name} v {loader_version} instatiated")

    def set_options(self, options_str: str) -> None :
>>>>>>> master
        '''
        Set the loader-specific options. This loader takes none, but other loaders should take option strings 
        in the format of [option_1][option_2]... with the options in square brackts. Use the parse_options
        method to extract the actual positional options. If key/value options are required, encode those into
        positional options (e.g., [key1=val2][key2=val2]) and the process into a dictionary
        '''
<<<<<<< HEAD
        if options_str :
            options = tuple(re.findall("\[(.*?)\]", options_str))
            if self._logger :
                self._logger.info(f"{self.loader_name} initialized with {str(options)}")
=======
        options = tuple(re.findall("\[(.*?)\]", options_str))
        if self._logger :
            self._logger.info(f"{self.loader_name} initialized with {str(options)}")
        pass
>>>>>>> master

    def assert_value_is_set(self) -> None :
        '''
        Called from methods that require a ShefValue to be set
        '''
        if not self._shef_value :
            raise shared.LoaderException("setvalue() has not been called on transformer")

    def assert_value_is_recognized(self) -> None :
        '''
        Called from methods that require the current ShefValue to be recognized by the loader
        '''
        if not self.use_value :
<<<<<<< HEAD
            raise shared.LoaderException(f"Loader does not use value {self.time_series_name}")
=======
            raise shared.LoaderException(f"Loader does not use value {self.time_series_name()}")
>>>>>>> master

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
        shef_value = shared.make_shef_value(value_str)
        if self._shef_value is None :
<<<<<<< HEAD
            #-------------#
            # first value #
            #-------------#
            self._shef_value = shef_value
            if self.use_value :
                self._time_series.append([self.date_time, self.value, self.data_qualifier, self.forecast_date_time])
        else :
            #-------------------#
            # subsequent values #
            #-------------------#
            if self.get_time_series_name(shef_value) == self.time_series_name :
                #------------------#
                # same time series #
                #------------------#
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

    def load_time_series(self) -> None :
=======
            self._shef_value = shef_value
        else :
            if self.use_value :
                self._time_series.append([self.date_time, self.value, self.data_qualifier, self.forecast_date_time])
            self._prev_shef_value = self._shef_value
            self._shef_value = shef_value
            if self.time_series_name != self.prev_time_series_name:
                self.load_time_series()

    def load_time_series(self) :
>>>>>>> master
        '''
        Load or output the timeseries in a loader-specific manner
        '''
        if self._logger :
            self._logger.info(f"Storing {len(self._time_series)} values to {self.time_series_name}")
        if self._time_series :
<<<<<<< HEAD
            self.output(f"{self.time_series_name}\n")
=======
            self.output(f"{self.prev_time_series_name}\n")
>>>>>>> master
            for ts in sorted(self._time_series) :
                output_str = ", ".join(map(str, ts))
                self.output(f"\t{output_str}\n")
        self._time_series = []

<<<<<<< HEAD
    def done(self) -> None :
=======
    def done(self) :
>>>>>>> master
        '''
        Load any remaining time series and close the output if necessary
        '''
        self.load_time_series()
<<<<<<< HEAD
        if self._output and self._output_opened :
=======
        if self._output_opened :
>>>>>>> master
            self._output.close()
            self._output = None
            self._output_name = None

<<<<<<< HEAD
    def get_time_series_name(self, shef_value: Optional[shared.ShefValue]) -> str :
        '''
        Get the loader-specific time series name for a specified SHEF value
        '''
        if not shef_value :
            raise shared.LoaderException("shef_value is None")
        return f"{shef_value.location}.{shef_value.parameter_code}"

    @property
    def loader_name(self) -> str :
=======
    @property
    def loader_name(self) :
>>>>>>> master
        '''
        The class name of the current loader
        '''
        return self.__class__.__name__

    @property
<<<<<<< HEAD
    def loader_version(self) -> str :
        '''
        The class name of the current loader
        '''
        global loader_version
        return loader_version

    @property
    def output_name(self) -> Optional[str] :
=======
    def output_name(self) :
>>>>>>> master
        '''
        The name of the output device, if any
        '''
        return self._output_name

    @property
    def time_series_name(self) -> str :
        '''
<<<<<<< HEAD
        Get the loader-specific time series name for the current SHEF value
        '''
        self.assert_value_is_set()
        return self.get_time_series_name(self._shef_value)
=======
        Get the loader-specific time series name
        '''
        self.assert_value_is_set()
        return f"{self._shef_value.location}.{self._shef_value.parameter_code}"

    @property
    def prev_time_series_name(self) -> str :
        '''
        Get the loader-specific time series name
        '''
        return None if self._prev_shef_value is None else f"{self._prev_shef_value.location}.{self._prev_shef_value.parameter_code}"
>>>>>>> master

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
<<<<<<< HEAD
        return f"{cast(shared.ShefValue, self._shef_value).location}"
=======
        return f"{self._shef_value.location}"
>>>>>>> master

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
<<<<<<< HEAD
        sv: shared.ShefValue = cast(shared.ShefValue, self._shef_value)
        return f"{sv.obs_date} {sv.obs_time}"
=======
        return f"{self._shef_value.obs_date} {self._shef_value.obs_time}"
>>>>>>> master

    @property
    def forecast_date_time(self) -> str :
        '''
        Get the creation date/time, if any, of the current ShefValue
        '''
        self.assert_value_is_set()
<<<<<<< HEAD
        sv: shared.ShefValue = cast(shared.ShefValue, self._shef_value)
        return "" if sv.create_date == "0000-00-00" else f"{sv.create_date} {sv.create_time}"
=======
        return None  if self._shef_value.create_date == "0000-00-00" else f"{self._shef_value.create_date} {self._shef_value.create_time}"
>>>>>>> master

    @property
    def parameter(self) -> str :
        '''
        Get the loader-specific parameter name of the current ShefValue
        '''
        self.assert_value_is_set()
<<<<<<< HEAD
        sv: shared.ShefValue = cast(shared.ShefValue, self._shef_value)
        return f"{sv.parameter_code}"
=======
        return f"{self._shef_value.parameter_code}"
>>>>>>> master

    @property
    def value(self) -> float :
        '''
        Get the loader-specific data value of the current ShefValue
        '''
        self.assert_value_is_set()
<<<<<<< HEAD
        sv: shared.ShefValue = cast(shared.ShefValue, self._shef_value)
        return sv.value
=======
        return f"{self._shef_value.value}"
>>>>>>> master

    @property
    def data_qualifier(self) -> str :
        '''
        Get the loader-specific data value qualifier of the current ShefValue
        '''
        self.assert_value_is_set()
<<<<<<< HEAD
        sv: shared.ShefValue = cast(shared.ShefValue, self._shef_value)
        return f"{sv.data_qualifier}"
=======
        return f"{self._shef_value.data_qualifier}"
>>>>>>> master

    @property
    def duration_interval(self) -> timedelta :
        '''
        Get the SHEF duration of the current ShefValue as a timedelta object
        '''
        self.assert_value_is_set()
<<<<<<< HEAD
        sv: shared.ShefValue = cast(shared.ShefValue, self._shef_value)
        return shared.duration_interval(sv.parameter_code)
=======
        return shared.duration_interval(self.shef_value.parameter_code)
>>>>>>> master

loader_options = "--loader dummy"
loader_description = "Base class for other SHEF data loaders. Writes SHEF information to output"
loader_version = "1.0"
loader_class = DummyLoader
<<<<<<< HEAD
can_unload = False
=======
>>>>>>> master
