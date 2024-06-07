import re
from .        import dummy_loader
from .        import shared
from datetime import timedelta
from logging  import Logger
from io       import BufferedRandom
from io       import TextIOWrapper
from typing   import TextIO
from typing   import Union

class DSSVueLoader(dummy_loader.DummyLoader) :
    '''
    Loader used by HEC-DSSVue.
    This loader uses ShefDss-style sensor and parameter files and outputs time series for HEC-DSSVue to read and store
    '''
    duration_units = {
        'M' : "Minutes",
        'H' : "Hours",
        'D' : "Days",
        'L' : "Months",
        'Y' : "Years"}

    one_day = timedelta(days=1)
    month_interval = timedelta(days=30)
    month_tolerance = (month_interval - 2 * one_day, month_interval + one_day)
    year_interval = timedelta(days=365)
    year_tolerance = (year_interval, year_interval + one_day)

    def __init__(self, logger: Union[None, Logger], output_object: Union[TextIO, str] = None, append: bool = False) -> None :
        '''
        Constructor
        '''
        super().__init__(logger, output_object, append)
        self._sensors = {}
        self._parameters = {}

    def set_options(self, options_str: str) -> None :
        '''
        Set the sensor and parameter file names
        '''
        options = tuple(re.findall("\[(.*?)\]", options_str))
        if len(options) != 2 :
            raise shared.LoaderException(f"{self.loader_name} expected 2 options, got [{len(options)}]")
        sensorFilename, parameterFileName = options
        if self._logger :
            self._logger.info(f"Using:\n\tsensor file    = {sensorFilename}\n\tparameter file = {parameterFileName}")
        #----------------------#
        # load the sensor file #
        #----------------------#
        with open(sensorFilename) as f :
            lines = f.read().strip().split("\n")
        for i in range(len(lines)) :
            line = lines[i]
            if not line or line[0] == '*' or not line[:10].strip() :
                continue
            try :
                location = line[:8].strip()
                pe_code = line[8:10].strip()
                if pe_code in shared.SEND_CODES :
                    pe_code = shared.SEND_CODES[pe_code][0][:2]
                sensor = f"{location}/{pe_code}"
                duration_str = line[10:15].strip()
                if duration_str :
                    duration_value = int(duration_str[:-1])
                    if duration_value == 0 :
                        duration = "IR-Month"
                    else :
                        duration_unit=DSSVueLoader.duration_units[line[14].strip()]
                        if duration_value == 1 :
                            duration_unit = duration_unit[:-1]
                        duration = f"{duration_value}{duration_unit}"
                        if duration == "7Days" :
                            duration = "1Week"
                else :
                    duration = "IR-Month"
                a_part = line[16:33].strip()
                b_part = line[33:50].strip()
                f_part = line[50:67].strip()
                self._sensors[sensor] = {
                    "duration" : duration,
                    "a_part"   : a_part,
                    "b_part"   : b_part if b_part else location,
                    "f_part"   : f_part
                }
            except Exception as e :
                if self._logger :
                    self._logger.error(f"{str(e)} on {sensorFilename}:{i+1}")
        #-------------------------#
        # load the parameter file #
        #-------------------------#
        with open(parameterFileName) as f :
            lines = f.read().strip().split("\n")
        for i in range(len(lines)) :
            line = lines[i]
            if not line or line[0] == '*' or not line[:2].strip() :
                continue
            try :
                pe_code = line[:2].strip()
                c_part = line[3:27].strip()
                unit = line[29:36].strip()
                data_type = line[38:45].strip()
                transform = line[47:56].strip()
                self._parameters[pe_code] = {
                    "c_part"    : c_part,
                    "unit"      : unit,
                    "type"      : data_type,
                    "transform" : transform}
            except Exception as e :
                raise shared.LoaderException(f"{str(e)} on {parameterFileName}:{i+1}")
        #--------------------------------------------------------------------#
        # verify all the PE codes in the sensors have an entry in parameters #
        #--------------------------------------------------------------------#
        deleted_sensors = []
        for sensor in self._sensors :
            pe_code = sensor.split("/")[1]
            if pe_code not in self._parameters :
                deleted_sensors.append(sensor)
                if self._logger :
                    self._logger.warning(f"Sensor [{sensor}] in [{sensorFilename}] will not be used, no entry for [{pe_code}] in [{parameterFileName}]")
        for sensor in deleted_sensors :
            del self._sensors[sensor]

    def load_time_series(self) :
        '''
        Output the timeseries for HEC-DSSVue
        '''
        value_count = time_series_count = 0
        if self._time_series :
            if self._logger :
                self._logger.info(f"Outputting {len(self._time_series)} values to be stored to {self.prev_time_series_name}")
            time_series = []
            for ts in self._time_series :
                if ts[1] is None or ts[1] == -9999. :
                    if self._logger :
                        self._logger.debug(f"Discarding missing value at [{ts[0]}] for [{self.prev_time_series_name}]")
                else :
                    time_series.append([ts[0], ts[1]])
            if time_series :
                time_series.sort()
                load_individually = False
                dur_intvl = None
                if len(time_series) > 1 :
                    dur_intvl = shared.duration_interval(self._prev_shef_value.parameter_code)
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
                                            f"\n\ton [{self.prev_time_series_name}]\n\tWill attempt to load [{len(self._time_series)}] values individually")
                                    load_individually = True
                if load_individually :
                    #------------------------------------------#
                    # load values one at a time, some may fail #
                    #------------------------------------------#
                    for tsv in time_series :
                        self.output(f"{self.prev_time_series_name}\n\t{self.loading_info}\n")
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
                        self.output(f"{self.prev_time_series_name}\n\t{self.loading_info}\n")
                        for tsv in time_series[slices[i]] :
                            self.output(f"\t{list([tsv[0],tsv[1]])}\n")
                    time_series_count = len(slices)
                value_count = len(time_series)
            else :
                if self._logger :
                    self._logger.info(f"No values for [{self.prev_time_series_name}]")
        self._value_count += value_count
        self._time_series_count += time_series_count
        self._time_series = []

    @property
    def sensor(self) -> str :
        '''
        The the senor name for the current SHEF value
        '''
        self.assert_value_is_set()
        return f"{self._shef_value.location}/{self._shef_value.parameter_code[:2]}"

    @property
    def prev_sensor(self) -> str :
        '''
        The the senor name for the current SHEF value
        '''
        return None if self._prev_shef_value is None else f"{self._prev_shef_value.location}/{self._prev_shef_value.parameter_code[:2]}"

    @property
    def parameter(self) -> str :
        '''
        Get the C Pathname part
        '''
        self.assert_value_is_recognized()
        pe_code = self._shef_value.parameter_code[:2]
        param = self._parameters[pe_code]["c_part"]
        if not param :
            raise shared.LoaderException(f"No C Pathname part specified for PE code {pe_code}")
        return param

    @property
    def prev_parameter(self) -> str :
        '''
        Get the C Pathname part
        '''
        if self._prev_shef_value is None :
            return None
        pe_code = self._prev_shef_value.parameter_code[:2]
        param = self._parameters[pe_code]["c_part"]
        if not param :
            raise shared.LoaderException(f"No C Pathname part specified for PE code {pe_code}")
        return param

    @property
    def time_series_name(self) -> str :
        '''
        Get the loader-specific time series name
        '''
        self.assert_value_is_set()
        sensor = self._sensors[self.sensor]
        a_part = sensor["a_part"]
        b_part = sensor["b_part"]
        c_part = self.parameter
        e_part = sensor["duration"]
        f_part = sensor["f_part"]
        if f_part == "*" :
            create_date = self._shef_value.create_date
            if create_date == "0000-00-00" :
                f_part = ""
            else :
                create_time = self._shef_value.create_time
                y, m, d = create_date.split("-")
                h, n, s = create_time.split(":")
                f_part = f"T:{y}{m}{d}-{h}{n}|"
        return f"/{a_part}/{b_part}/{c_part}//{e_part}/{f_part}/"

    @property
    def prev_time_series_name(self) -> str :
        '''
        Get the loader-specific time series name
        '''
        if self._prev_shef_value is None :
            return None
        sensor = self._sensors[self.prev_sensor]
        a_part = sensor["a_part"]
        b_part = sensor["b_part"]
        c_part = self.prev_parameter
        e_part = sensor["duration"]
        f_part = sensor["f_part"]
        if f_part == "*" :
            create_date = self._prev_shef_value.create_date
            if create_date == "0000-00-00" :
                f_part = ""
            else :
                create_time = self._prev_shef_value.create_time
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
    def use_prev_value(self) -> bool :
        '''
        Get whether the current ShefValue is recognized by the loader
        '''
        return self.prev_sensor in self._sensors

    @property
    def location(self) -> str :
        '''
        Get the B Pathname part
        '''
        self.assert_value_is_set()
        return self.sensor["b_bpart"]

    @property
    def loading_info(self) -> dict :
        '''
        Get the unit and data type
        '''
        self.assert_value_is_set()
        param = self._parameters[self.sensor.split("/")[1]]
        specified_type = param["type"]
        pe_code = self._shef_value.parameter_code[:2]
        duration_code = self._shef_value.parameter_code[2]
        if specified_type == "*" :
            parameter_code = self._shef_value.parameter_code
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
        self.assert_value_is_set()
        val = self._shef_value.value
        pe_code = self._shef_value.parameter_code[:2]
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
                    self._logger.warning(f"Transform of {transform} used with unexpected PE code [{pe_code}] - normally only for {','.join(expected_pe_codes)}")
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
            expected_pe_codes = ("VK", "VL", "VM", "VR")
            duration = self._sensors[self.sensor]["duration"]
            m = shared.valueUnitsPattern.match(duration)
            if not m :
                if self._logger :
                    self._logger.warning(
                        f"Cannot use transform [{transform}] on duration [{duration}] for sensor [{self.sensor}]"
                        f"\n\tUsing data value [{val}] as MWh")
                factor = 1
            else :
                duration_value = int(m.group(1))
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
                    self._logger.warning(f"Transform of {transform} used with unexpected PE code [{pe_code}] - normally only for {','.join(expected_pe_codes)}")
            val *= factor
        else :
            #------------------#
            # scalar transform #
            #------------------#
            val *= float(transform)
        if val == -9999. :
            val = None
        return val

loader_options = "--loader dssvue[sensor_file_path][parameter_file_path]"
loader_description = "Used by HEC-DSSVue to import SHEF data. Uses ShefDss-style configuration"
loader_version = "1.0"
loader_class = DSSVueLoader
