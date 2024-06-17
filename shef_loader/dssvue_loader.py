import csv, os, re, sys
from .        import base_loader
from .        import shared
from datetime import timedelta
from logging  import Logger
from io       import BufferedRandom
from io       import TextIOWrapper
from typing   import cast
from typing   import Optional
from typing   import TextIO
from typing   import Union

UNDEFINED: float = -3.4028234663852886e+38

class DSSVueLoader(base_loader.BaseLoader) :
    '''
    Loader used by HEC-DSSVue.
    This loader uses ShefDss-style sensor and parameter files and outputs time series for HEC-DSSVue to read and store
    '''
    duration_units = {
        'M' : "Minute",
        'H' : "Hour",
        'D' : "Day",
        'L' : "Month",
        'Y' : "Year"}

    one_day = timedelta(days=1)
    month_interval = timedelta(days=30)
    month_tolerance = (month_interval - 2 * one_day, month_interval + one_day)
    year_interval = timedelta(days=365)
    year_tolerance = (year_interval, year_interval + one_day)

    pathname_line_pattern = re.compile(r"^/(.*?)/(.+?)/(.+?)/(.*?)/(.+?)/(.*?)/$")
    load_info_line_pattern = re.compile(r"^\s+(\{.+?\})$")
    time_value_line_pattern = re.compile(r"^\s+\['(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', ([+-]?\d*(\.(\d*))?)\]$")
    forecast_time_pattern = re.compile("T:(\d{8})-(\d{4})\|")

    def __init__(self, logger: Optional[Logger], output_object: Optional[Union[BufferedRandom, TextIO, str]] = None, append: bool = False) -> None :
        '''
        Constructor
        '''
        super().__init__(logger, output_object, append)
        self._sensors: dict[str, dict[str, str]] = {}
        self._parameters: dict[str, dict[str, str]] = {}
        self._unload_sensors: dict[tuple[str, str, str, str], dict[str, str]] = {}
        self._unload_parameters: dict[tuple[str, str, str], dict[str, str]] = {}
        self._time_series = []
        # following are for unload()
        self._input: Optional[Union[BufferedRandom, TextIOWrapper]] = None
        self._pathname: Optional[str] = None
        self._sensor: Optional[dict[str, str]] = None
        self._parameter: Optional[dict[str, str]] = None
        self._forecast_time: Optional[str] = None
        self._message_count = 0

    def set_options(self, options_str: Optional[str]) -> None :
        '''
        Set the sensor and parameter file names
        '''
        if not options_str :
            raise shared.LoaderException(f"Empty options on {self.loader_name}.set_options()")
        def make_sensor(location: str, pe_code: str, duration_str: str, a_part: str, b_part: str, f_part: str) -> None :
            if not location :
                raise shared.LoaderException("Empty Location")
            if not pe_code :
                raise shared.LoaderException("Empty PE Code")
            if pe_code in shared.SEND_CODES :
                pe_code = shared.SEND_CODES[pe_code][0][:2]
            sensor = f"{location}/{pe_code}"
            if duration_str :
                duration_value = int(duration_str[:-1])
                if duration_value == 0 :
                    e_part = "IR-Month"
                else :
                    duration_unit=DSSVueLoader.duration_units[duration_str[-1]]
                    e_part = f"{duration_value}{duration_unit}"
                    if e_part == "7Day" :
                        e_part = "1Week"
            else :
                e_part = "IR-Month"
            if not b_part :
                b_part = location
            self._sensors[sensor] = {
                "location" : location,
                "a_part" : a_part,
                "b_part" : b_part,
                "e_part" : e_part,
                "f_part" : f_part
            }

        def make_parameter(pe_code, c_part, unit, data_type, transform) :
            if not pe_code.strip() :
                raise shared.LoaderException("Empty PE Code")
            self._parameters[pe_code] = {
                "pe_code"   : pe_code.strip(), # for unload()
                "c_part"    : c_part.strip(),
                "unit"      : unit.strip(),
                "type"      : data_type.strip(),
                "transform" : transform.strip()}

        options = tuple(re.findall("\[(.*?)\]", options_str))
        if len(options) == 2 :
            sensorfile_name, parameterfile_name = options
        else :
            raise shared.LoaderException(f"{self.loader_name} expected 2 options, got [{len(options)}]")
        if not os.path.exists(sensorfile_name) or not os.path.isfile(sensorfile_name):
            raise shared.LoaderException(f"Sensor file [{sensorfile_name}] does not exist")
        if not os.path.exists(parameterfile_name) or not os.path.isfile(parameterfile_name):
            raise shared.LoaderException(f"Parameter file [{parameterfile_name}] does not exist")
        if self._logger :
            self._logger.info(f"{self.loader_name} v{self.loader_version} initialized with:\n\tsensor file    : {sensorfile_name}\n\tparameter file : {parameterfile_name}")

        #----------------------#
        # load the sensor file #
        #----------------------#
        try :
            with open(sensorfile_name) as f :
                line_number = 0
                if sensorfile_name.endswith(".csv") :
                    #------------------#
                    # read as CSV file #
                    #------------------#
                    for fields in csv.reader(f) :
                        line_number += 1
                        for i in range(len(fields)) :
                            fields[i] = fields[i].encode('ascii', errors='ignore').decode('ascii')
                        if len(fields) != 6 or not fields[0] or fields[0][0] == '*' :
                            continue
                        make_sensor(*fields)
                else :
                    #--------------------------------#
                    # read as orininal column format #
                    #--------------------------------#
                    for line in f.readlines() :
                        line_number += 1
                        if not line or line[0] == '*' or not line[:10].strip() :
                            continue
                        location = line[:8].strip()
                        pe_code = line[8:10].strip()
                        duration_str = line[10:15].strip()
                        a_part = line[16:33].strip()
                        b_part = line[33:50].strip()
                        f_part = line[50:67].strip()
                        make_sensor(location, pe_code, duration_str, a_part, b_part, f_part)
        except Exception as e :
            if self._logger :
                self._logger.error(f"{str(e)} on line [{line_number}] in {sensorfile_name}")
                raise
        #-------------------------#
        # load the parameter file #
        #-------------------------#
        try :
            with open(parameterfile_name) as f :
                if parameterfile_name.endswith(".csv") :
                    #------------------#
                    # read as CSV file #
                    #------------------#
                    for fields in csv.reader(f) :
                        line_number += 1
                        for i in range(len(fields)) :
                            fields[i] = fields[i].encode('ascii', errors='ignore').decode('ascii')
                        if len(fields) != 5 or not fields[0] or fields[0][0] == '*' :
                            continue
                        make_parameter(*fields)
                else :
                    #--------------------------------#
                    # read as orininal column format #
                    #--------------------------------#
                    line_number = 0
                    for line in f.readlines() :
                        if not line or line[0] == '*' or not line[:2].strip() :
                            continue
                        pe_code = line[:2].strip()
                        c_part = line[3:27].strip()
                        unit = line[29:36].strip()
                        data_type = line[38:45].strip()
                        transform = line[47:56].strip()
                        make_parameter(pe_code, c_part, unit, data_type, transform)
        except Exception as e :
            raise shared.LoaderException(f"{str(e)} on line [{line_number}] in [{parameterfile_name}]")
        #--------------------------------------------------------------------#
        # verify all the PE codes in the sensors have an entry in parameters #
        #--------------------------------------------------------------------#
        deleted_sensors = []
        for sensor in self._sensors :
            pe_code = sensor.split("/")[1]
            if pe_code not in self._parameters :
                deleted_sensors.append(sensor)
                if self._logger :
                    self._logger.warning(f"Sensor [{sensor}] in [{sensorfile_name}] will not be used, no entry for [{pe_code}] in [{parameterfile_name}]")
        for sensor in deleted_sensors :
            del self._sensors[sensor]

    def set_input(self, input_object: Union[TextIO, str]) -> None :
        '''
        Attach the message unload input stream
        '''
        if self._input :
            raise shared.LoaderException("Input has already been set")
        if isinstance(input_object, TextIOWrapper) :
            self._input = input_object
        elif isinstance(input_object, str) :
            self._input = open(input_object)
        else :
            raise shared.LoaderException(f"Expected TextIOWrapper or str object, got [{input_object.__class__.__name__}]")

    def output_shef_text(self) -> None :
        '''
        Outputs an unloaded time series
        '''
        def h2hm(h: float) -> float :
            whole, fraction = divmod(h/100., 1.)
            return 100 * (whole + fraction * 0.6)

        def h2dur(h: float) -> Optional[float] :
            val = None
            if not self._sensor :
                raise shared.LoaderException("Empty sensor in h2dur()")
            duration_str = self._sensor["e_part"].upper().replace("1WEEK", "7DAYS")
            m = shared.VALUE_UNITS_PATTERN.match(duration_str)
            if m :
                if m.group(2).startswith("SEC") :
                    val = h * 86400
                elif m.group(2).startswith("MIN") :
                    val = h * 1440
                elif m.group(2).startswith("HOUR") :
                    val = h
                elif m.group(2).startswith("DAY") :
                    val = h / 24
                elif m.group(2).startswith("MONTH") :
                    val = h / (30 * 24)
                elif m.group(2).startswith("YEAR") :
                    val = h / (356 * 24)
                elif m.group(2).startswith("DECADE") :
                    val = h / (10 * 365 * 24)
            return val

        def apply_transform(val: Optional[float], transform: str) -> float :
            if val is None :
                raise shared.LoaderException(f"Value is None")
            if transform :
                if transform == "hm2h" :
                    val = h2hm(val)
                    if val is None :
                        raise shared.LoaderException(f"Cannot apply transform for pathname [{self._pathname}]: [{transform}]")
                elif transform == "dur2h" :
                    val = h2dur(val)
                    if val is None :
                        raise shared.LoaderException(f"Cannot apply transform for pathname [{self._pathname}]: [{transform}]")
                else :
                    try :
                        factor = float(transform)
                        val /= factor
                        if val is None :
                            raise shared.LoaderException(f"Cannot apply transform for pathname [{self._pathname}]: [{transform}]")
                    except :
                        raise shared.LoaderException(f"Unexpected transform for pathname [{self._pathname}]: [{transform}]")
            return val

        if not self._time_series :
            msg = f"No time series values for [{self._pathname}]"
            if self._logger :
                self._logger.info(msg)
            self.output(f":     <{msg}>\n")
        else :
            val: Optional[Union[float, str]]
            if not self._sensor :
                raise shared.LoaderException("Empty sensor in output_shef_text()")
            if not self._parameter :
                raise shared.LoaderException("Empty parameter in output_shef_text()")
            if self._sensor["e_part"].upper().startswith("IR-") or self._sensor["e_part"][0] == "~" :
                #-----------------------#
                # irregular time series #
                #-----------------------#
                header = None
            else :
                #---------------------#
                # regular time series #
                #---------------------#
                y,m,d,h,n = self._time_series[0][0].replace(":"," ").replace("-"," ").split()[:5]
                header = f".E {self._sensor['location']} {y}{m}{d} Z DN{h}{n}/"
                if self._forecast_time :
                    header += f"DC{self._forecast_time}/"
                header += f"{self._parameter['pe_code']}"
                duration_str = self._sensor["e_part"].upper().replace("1WEEK", "7DAYS")
                m = shared.VALUE_UNITS_PATTERN.match(duration_str)
                if m :
                    if m.group(2).startswith("SEC") :
                        header += f"/DIS{int(m.group(1)):02d}"
                    elif m.group(2).startswith("MIN") :
                        header += f"/DIN{int(m.group(1)):02d}"
                    elif m.group(2).startswith("HOUR") :
                        header += f"/DIH{int(m.group(1)):02d}"
                    elif m.group(2).startswith("DAY") :
                        header += f"/DID{int(m.group(1)):02d}"
                    elif m.group(2).startswith("MONTH") :
                        header += f"/DIM{int(m.group(1)):02d}"
                    elif m.group(2).startswith("YEAR") :
                        header += f"/DIY{int(m.group(1)):02d}"
                    elif m.group(2).startswith("DECADE") :
                        header += f"/DIY{10*int(m.group(1)):02d}"
                    else :
                        msg = f"Could not determine a valid SHEF interval for [{self._pathname}]"
                        if self._logger :
                            self._logger.error(msg)
                        self.output(f":     <{msg}>\n")
                        self._pathname = None
                        self._sensor = None
                        self._parameter = None
                        self._time_series = []
                        return
            transform = self._parameter["transform"]
            try :
                if header :
                    message = header
                    for tsv in self._time_series :
                        val = float(tsv[1])
                        if val is None or val == UNDEFINED :
                            message += "/m"
                        else :
                            val = apply_transform(val, transform)
                            if val is None :
                                val = "m"
                            message += f"/{val}"
                    self.output(f"{message}\n")
                    self._message_count += 1
                    self._value_count += len(self._time_series)
                else :
                    #-----------------------#
                    # irregular time series #
                    #-----------------------#
                    for i in range(len(self._time_series)) :
                        tsv = self._time_series[i]
                        val = float(tsv[1])
                        if val == UNDEFINED :
                            val = "m"
                        else :
                            val = apply_transform(val, transform)
                            if val is None :
                                val = "m"
                        y,m,d,h,n = tsv[0].replace(":"," ").replace("-"," ").split()[:5]
                        message = f".A {self._sensor['location']} {y}{m}{d} Z DN{h}{n}/"
                        if self._forecast_time :
                            message += f"DC{self._forecast_time}/"
                        message += f"{self._parameter['pe_code']} {val}"
                        self.output(f"{message}\n")
                        self._message_count += 1
                    self._value_count += len(self._time_series)
                self._time_series_count += 1
            except shared.LoaderException as e :
                if self._logger :
                    self._logger.error(str(e))
                self.output(f":     <{str(e)}>\n")
                self._pathname = None
                self._sensor = None
                self._parameter = None
                self._time_series = []
                return
        self._pathname = None
        self._sensor = None
        self._parameter = None
        self._time_series = []

    def unload(self) -> None :
        '''
        Read time series text from HEC-DSSVue and output SHEF
        '''
        if not self._input :
            raise shared.LoaderException("No input file specified before calling unload() method")
        if self._logger :
            self._logger.info(f"Generating SHEF text from HEC-DSSVue via file [{self._input.name}]")
        #------------------------------------------------#
        # populate the sensors and parameters for output #
        #------------------------------------------------#
        for sensor_name in self._sensors :
            sensor = self._sensors[sensor_name]
            a_part = sensor["a_part"]
            b_part = sensor["b_part"]
            e_part = sensor["e_part"]
            f_part = sensor["f_part"]
            self._unload_sensors[(a_part,b_part,e_part,f_part)] = self._sensors[sensor_name]
        for pe_code in self._parameters :
            parameter = self._parameters[pe_code]
            c_part    = parameter["c_part"]
            data_type = parameter["type"]
            unit      = parameter["unit"]
            self._unload_parameters[(c_part, data_type, unit)] = self._parameters[pe_code]
        #--------------------------------------------#
        # read the input stream and output SHEF text #
        #--------------------------------------------#
        line_number = 0
        line_or_bytes = self._input.readline()
        if isinstance(line_or_bytes, bytes) :
            line = line_or_bytes.decode("utf-8")
        line = cast(str, line_or_bytes)
        while line :
            line_number += 1
            line = line[:-1]
            if not line :
                continue
            if DSSVueLoader.pathname_line_pattern.match(line) :
                if all([self._pathname, self._sensor, self._parameter]) :
                    self.output_shef_text()
                self._pathname = line
                self.output(f"\n:--------------------------------------------------------------------------------\n: Pathname = {self._pathname}\n")
            elif DSSVueLoader.load_info_line_pattern.match(line) :
                if self._pathname :
                    A,B,C,E,F = 1,2,3,5,6
                    parts = self._pathname.split("/")
                    try :
                        key = (parts[A],parts[B],parts[E],parts[F])
                        self._sensor = self._unload_sensors[key]
                    except KeyError :
                        try :
                            key = (parts[A],parts[B],parts[E],'*')
                            self._sensor = self._unload_sensors[key]
                        except KeyError :
                            msg = f"No sensor found for [{self._pathname}]"
                            if self._logger :
                                self._logger.info(msg)
                            self.output(f":     <{msg}>\n")
                            self._unload_sensor = None
                            continue
                    loadinfo = eval(line.strip())
                    try :
                        data_type = loadinfo["type"]
                        unit = loadinfo["unit"]
                    except KeyError :
                        msg = f"Invalid loading information in line [{line_number}] of [{self._pathname}]"
                        if self._logger :
                            self._logger.warning(msg)
                        self.output(f":     <{msg}>\n")
                        self._sensor = None
                        continue
                    try :
                        self._parameter = self._unload_parameters[(parts[C], data_type, unit)] # specified data type
                    except KeyError:
                        try :
                            self._parameter = self._unload_parameters[(parts[C], "*", unit)] # inferred data type
                        except KeyError:
                            self._parameter = None
                            msg = f"No parameter found for [{parts[C]}, {data_type}, {unit}]"
                            if self._logger :
                                self._logger.info(msg)
                            self.output(f":     <{msg}>\n")
                            self._parameter = None
                            continue
                    m = DSSVueLoader.forecast_time_pattern.match(parts[F])
                    if m :
                        self._forecast_time = f"{m.group(1)}{m.group(2)}"
                    else :
                        self._forecast_time = None
            elif DSSVueLoader.time_value_line_pattern.match(line) :
                if not(self._sensor and self._parameter) :
                    continue
                tsv = eval(line.strip())
                self._time_series.append([tsv[0], tsv[1]])
            line_or_bytes = self._input.readline()
            if isinstance(line_or_bytes, bytes) :
                line = line_or_bytes.decode("utf-8")
            line = cast(str, line_or_bytes)
        if self._input.name != "<stdin>" :
            self._input.close()
        self.output_shef_text()
        if self._logger :
            self._logger.info("--[Summary]-----------------------------------------------------------")
            self._logger.info(f"{self._value_count} values output in {self._message_count} messages from {self._time_series_count} time series")

    def load_time_series(self) -> None :
        '''
        Output the timeseries for HEC-DSSVue
        '''
        self.assert_value_is_set()
        sv = cast(shared.ShefValue, self._shef_value)
        value_count = time_series_count = 0
        if self._time_series :
            if self._logger :
                self._logger.info(f"Outputting [{len(self._time_series)}] values to be stored to [{self.time_series_name}]")
            time_series = []
            for ts in self._time_series :
                if ts[1] is None or ts[1] == -9999. :
                    if self._logger :
                        self._logger.debug(f"Discarding missing value at [{ts[0]}] for [{self.time_series_name}]")
                else :
                    time_series.append([ts[0], ts[1]])
            if time_series :
                time_series.sort()
                load_individually = False
                dur_intvl = None
                if len(time_series) > 1 :
                    dur_intvl = shared.duration_interval(sv.parameter_code)
                    if dur_intvl :
                        #---------------------------------------------------#
                        # see if we the value times agree with the duration #
                        #---------------------------------------------------#
                        intervals = set()
                        for i in range(1, len(time_series)) :
                            intervals.add(shared.get_datetime(time_series[i][0]) - shared.get_datetime(time_series[i-1][0]))
                        for intvl in sorted(intervals) :
                            if intvl / dur_intvl != intvl // dur_intvl :
                                if dur_intvl == DSSVueLoader.month_interval and DSSVueLoader.month_tolerance[0] <= intvl <= DSSVueLoader.month_tolerance[1] :
                                    pass
                                elif dur_intvl == DSSVueLoader.year_interval and DSSVueLoader.year_tolerance[0] <= intvl <= DSSVueLoader.year_tolerance[1] :
                                    pass
                                else :
                                    if self._logger :
                                        self._logger.warning(
                                            f"Data interval of [{str(intvl)}] does not agree with duration of [{str(dur_intvl)}]"
                                            f"\n\ton [{self.time_series_name}]\n\tWill attempt to load [{len(self._time_series)}] values individually")
                                    load_individually = True
                if load_individually :
                    #------------------------------------------#
                    # load values one at a time, some may fail #
                    #------------------------------------------#
                    for tsv in time_series :
                        self.output(f"{self.time_series_name}\n\t{self.loading_info}\n")
                        self.output(f"\t{list([tsv[0],tsv[1]])}\n")
                    time_series_count = len(time_series)
                else :
                    #---------------------------------------------#
                    # load values in one or more chunks, skipping #
                    # gaps to prevent overriting with missing     #
                    #---------------------------------------------#
                    slices = []
                    start = 0
                    if dur_intvl :
                        for i in range(1, len(time_series)) :
                            interval = shared.get_datetime(time_series[i][0]) - shared.get_datetime(time_series[i-1][0])
                            if interval > dur_intvl * 1.5 :
                                slices.append(slice(start, i, 1))
                                start = i
                    slices.append(slice(start, len(time_series), 1))
                    for i in range(len(slices)) :
                        self.output(f"{self.time_series_name}\n\t{self.loading_info}\n")
                        for tsv in time_series[slices[i]] :
                            self.output(f"\t{list([tsv[0],tsv[1]])}\n")
                    time_series_count = len(slices)
                value_count = len(time_series)
            else :
                if self._logger :
                    self._logger.info(f"No values for [{self.time_series_name}]")
        self._value_count += value_count
        self._time_series_count += time_series_count
        self._time_series = []

    def done(self) -> None :
        '''
        Load any remaining time series and close the output if necessary
        '''
        super().done()
        if self._logger :
            self._logger.info("--[Summary]-----------------------------------------------------------")
            self._logger.info(f"{self._value_count} values output in {self._time_series_count} time series")

    @property
    def loader_version(self) -> str :
        '''
        The class name of the current loader
        '''
        global loader_version
        return loader_version

    @property
    def sensor(self) -> str :
        '''
        The the senor name for the current SHEF value
        '''
        self.assert_value_is_set()
        sv = cast(shared.ShefValue, self._shef_value)
        return f"{sv.location}/{sv.parameter_code[:2]}"

    @property
    def parameter(self) -> str :
        '''
        Get the C Pathname part
        '''
        self.assert_value_is_recognized()
        sv = cast(shared.ShefValue, self._shef_value)
        pe_code = sv.parameter_code[:2]
        param = self._parameters[pe_code]["c_part"]
        if not param :
            raise shared.LoaderException(f"No C Pathname part specified for PE code [{pe_code}]")
        return param

    @property
    def time_series_name(self) -> str :
        '''
        Get the loader-specific time series name for the current SHEF value
        '''
        self.assert_value_is_set()
        sv = cast(shared.ShefValue, self._shef_value)
        return self.get_time_series_name(sv)

    def get_time_series_name(self, shef_value: Optional[shared.ShefValue]) -> str :
        '''
        Get the loader-specific time series name for a specified SHEF value
        '''
        if shef_value is None :
            raise shared.LoaderException(f"Empty SHEF value in get_time_series_name()")
        pe_code = shef_value.parameter_code[:2]
        sensor_name = f"{shef_value.location}/{pe_code}"
        sensor = self._sensors[sensor_name]
        a_part = sensor["a_part"]
        b_part = sensor["b_part"]
        c_part = self._parameters[pe_code]["c_part"]
        if not c_part :
            raise shared.LoaderException(f"No C Pathname part specified for PE code [{pe_code}]")
        c_part = self.parameter
        e_part = sensor["e_part"]
        f_part = sensor["f_part"]
        if f_part == "*" :
            create_date = shef_value.create_date
            if create_date == "0000-00-00" :
                f_part = ""
            else :
                create_time = shef_value.create_time
                y, m, d = create_date.split("-")
                h, n, s = create_time.split(":")
                f_part = f"T:{y}{m}{d}-{h}{n}|"
        return f"/{a_part}/{b_part}/{c_part}//{e_part}/{f_part}/"

    @property
    def use_value(self) -> bool :
        '''
        Get whether the current ShefValue is recognized by the loader
        '''
        self.assert_value_is_set()
        return self.sensor in self._sensors

    @property
    def location(self) -> str :
        '''
        Get the B Pathname part
        '''
        self.assert_value_is_set()
        return cast(dict[str, str], self._sensor)["b_bpart"]

    @property
    def loading_info(self) -> dict :
        '''
        Get the unit and data type
        '''
        self.assert_value_is_set()
        sv = cast(shared.ShefValue, self._shef_value)
        param = self._parameters[self.sensor.split("/")[1]]
        specified_type = param["type"]
        pe_code = sv.parameter_code[:2]
        duration_code = sv.parameter_code[2]
        if specified_type == "*" :
            parameter_code = sv.parameter_code
            if duration_code == 'I' :
                data_type = "INST-CUM" if pe_code == "PC" else "INST-VAL"
            else :
                if pe_code in ("CV") :
                    data_type = "PER-AVER"
                elif parameter_code in ("HGIRZNZ", "QRIRZNZ", "TAIRZNZ") :
                    data_type = "PER-MIN"
                elif parameter_code in ("HGIRZXZ", "QZIRZXZ", "TAIRZXZ"):
                    data_type = "PER-MAX"
                elif pe_code in ("RI", "UC", "UL") :
                    data_type = "PER-CUM"
                else :
                    data_type = "INST-VAL"
        else :
            data_type = specified_type
        return {"unit" : param["unit"], "type" : data_type}

    @property
    def value(self) -> float :
        '''
        Get the loader-specific data value of the current ShefValue
        '''
        expected_pe_codes: tuple[str, ...]
        self.assert_value_is_set()
        sv = cast(shared.ShefValue, self._shef_value)
        val = sv.value
        pe_code = sv.parameter_code[:2]
        transform = self._parameters[pe_code]["transform"]
        if not transform :
            #---------------------------------------------#
            # null transform - set to default for PE code #
            #---------------------------------------------#
            if pe_code in ("AT", "AU", "AW") :
                transform = "hmh2"
            elif pe_code in ("VK", "VL", "VM", "VR") :
                transform = "dur2h"
            else :
                transform = "1"
        if transform == "hm2h" :
            #--------------------------------#
            # hrs/minutes to hours transform #
            #--------------------------------#
            expected_pe_codes = ("AT", "AU", "AW")
            if pe_code not in expected_pe_codes :
                if self._logger :
                    self._logger.warning(f"Transform of [{transform}] used with unexpected PE code [{pe_code}] - normally only for [{','.join(expected_pe_codes)}]")
            hours = val // 100
            minutes = val % 100
            if minutes < 60 :
                val = hours + minutes / 60.
            else :
                if self._logger :
                    self._logger.warning(f"Transform [{transform}] is not valid for value [{val}], value not transformed")
        elif transform == "dur2h" :
            #-----------------------------#
            # duration to hours transform #
            #-----------------------------#
            factor: float
            expected_pe_codes = ("VK", "VL", "VM", "VR")
            duration = self._sensors[self.sensor]["duration"]
            m = shared.VALUE_UNITS_PATTERN.match(duration)
            if not m :
                if self._logger :
                    self._logger.warning(
                        f"Cannot use transform [{transform}] on duration [{duration}] for sensor [{self.sensor}]"
                        f"\n\tUsing data value [{val}] as MWh")
                factor = 1
            else :
                duration_value = float(m.group(1))
                duration_unit  = m.group(2)
                if duration_unit.startswith("Minute") :
                    factor = duration_value / 60
                elif duration_unit.startswith("Hour") :
                    factor = duration_value
                elif duration_unit.startswith("Day") :
                    factor = duration_value * 24
                elif duration_unit.startswith("Month") :
                    factor = duration_value * 24 * 30
                elif duration_unit.startswith("Year") :
                    factor = duration_value * 24 * 65
                else :
                    raise shared.LoaderException(f"Unexpected duration unit [{duration_unit}]")
            if pe_code not in expected_pe_codes :
                if self._logger :
                    self._logger.warning(f"Transform of [{transform}] used with unexpected PE code [{pe_code}] - normally only for [{','.join(expected_pe_codes)}]")
            val *= factor
        else :
            #------------------#
            # scalar transform #
            #------------------#
            val *= float(transform)
        if val == -9999. :
            val = None
        return val

loader_options     = "--loader dssvue[sensor_file_path][parameter_file_path]\n" \
                     "sensor_file_path    = the name of the ShefDss-style sensor file to use \n" \
                     "parameter_file_path = the name of the ShefDss-style parameter file to use \n"
loader_description = "Used by HEC-DSSVue to import/export SHEF data. Uses ShefDss-style configuration.\n" \
                     "As of v1.2 .csv sensor and parameter files can be used to handle long pathname parts."
loader_version     = "1.2"
loader_class       = DSSVueLoader
can_unload         = True
