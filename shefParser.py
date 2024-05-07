import copy, io, logging, os, re, sys
from argparse    import ArgumentParser
from collections import deque
from datetime    import datetime
from datetime    import timedelta
from datetime    import timezone
from pathlib     import Path
from typing      import Union
from zoneinfo    import ZoneInfo

'''
COMMENTS FROM MOST RECENT SHEFPARM FILE FROM NOAA

$   6/19/91   'HYD.RFS.SYSTEM(SHEFPARM)'
$
$  DEFINE SHEF PARAMETER INORMATION
$
$   910619     ADD E AND F EXTREMUM CODES
$   910114     ADD Y CODES
$   960322     This file includes the following that are not in the
$              Feb 1996 documentation:
$                PE codes (*1) .... YD,YG,YH,YI,YJ
$                TS codes (*3) .... MA,MC,MH,MK,MS,MT,MW
$                Qualifiers (*7) .. E,F,R,Q,T,S,V
$   980309     For SHEF Version1.3 added Duration Code of  N
$                Added PE codes PD, PE, PL, and UG for METAR Decoder
$                Added PE codes CZ for CBRFC and HU for MARFC
$                Added PE codes BA thru BQ for Snow Model states
$                Added PE codes CA thru CY for Soil Moisture Model states
$                Added TS codes MA, MC, MH, MK, MS, MT, and MW for model type
$                Deleted PE codes YD,YG,YH,YI,YJ
$   001121     Added Qualifier codes B,G,M,P
$   010720     Added PE codes for ST, TE; modified factors for HQ, MS
$              Changed factor for PA, PD
$              Treat PL English as mb, so use 10.0 for metric to KPA
$              (Note that the -1.0 conversion factor is for temperature C to F)
$   020112     Added 8 TS codes (R2-R9);
$              added 6 PE codes (MD, MN, MV,RN, RW, WD)
$   031124     Added SF SFD to instantaneous duration list
$              added TS codes #A-D, #2-9, as in 1A..1D..12..19..99
$   041221     Added PE codes for SB,SE,SM,SP,SU
$   041216     PE codes: added SP; changed SB,SM,SU
$   050128     TS codes: ARCHIVE DATABASE updates back in the fall of 2002
$                        #[FGMPRSTVWXZ] for #=1 to 9
$   050324     Added FL type source code
$   011906     Added PE codes for GP, GW, TJ, PJ,WS, WX,WY and UE
$   101106     Added E and G Duration Codes for 5 and 10 Minutes respectively
$              Added FR Type Source for Persistence Forecasts
$              Added PE code YI for SERFC
$              Added PE codes GC, GL, HV, TR, and TZ for Utah DOT
$
'''
versions = '''
+-------+-----------+-----+-------------------------------------------------------------------------+
| 0.1.0 | 23Apr2024 | MDP | Initializes program defaults (optionally modifing using SHEFPARM file), |
|       |           |     | and retrieves complete SHEF messages from input with error logging.     |
+-------+-----------+-----+-------------------------------------------------------------------------+
| 0.1.1 | 24Apr2024 | MDP | Proceses command line, parses .A and .E headers, and converts to UTC    |
+-------+-----------+-----+-------------------------------------------------------------------------+
| 0.4.0 | 26Apr2024 | MDP | Parses .A messages and generates "shefit -2" style output               |
+-------+-----------+-----+-------------------------------------------------------------------------+
| 0.6.0 | 29Apr2024 | MDP | Parses .A and .E messages and generates "shefit -2" style output        |
+-------+-----------+-----+-------------------------------------------------------------------------+
| 0.8.0 | 29Apr2024 | MDP | Parses .A, .E, and .B messages and generates "shefit -2" style output   |
+-------+-----------+-----+-------------------------------------------------------------------------+

Authors:
    MDP  Mike Perryman, USACE IWR-HEC
'''
version      = "0.6.0"
version_date = "29Apr2024"
logger       = None

class ShefParserException(Exception) :
    pass

class MonthsDelta :
    '''
    Class to hold information about months to increment a time by
    '''
    def __init__(self, months: int, eom: bool = False) :
        self._months = months
        self._eom    = eom

    @property
    def months(self) :
        return self._months

    @property
    def eom(self) :
        return self._eom

    def __repr__(self) :
        return f"months={self._months}, eom={self._eom}"

class Dt24 :
    '''
    Datetime class for use with SHEF
    * accepts and produces 2400 for midnight
    * can be incremented by MonthsDelta
    * can replicate time zone adjustments in NOAA Fortran SHEF parsing code
    '''

    DST_DATES = (
        #
        # DOM of transition for winter->summer and summer->winter for years 1976-2040.
        # Before 2007, months are April/October, afterward months are March/November
        #
        (26,31), (24,30), (30,29), (29,28), (27,26), (26,25),
        (25,31), (24,30), (29,28), (28,27), (27,26), ( 5,25),
        ( 3,30), ( 2,29), ( 1,28), ( 7,27), ( 5,25), ( 4,31),
        ( 3,30), ( 2,29), ( 7,27), ( 6,26), ( 5,25), ( 4,31),
        ( 2,29), ( 1,28), ( 7,27), ( 6,26), ( 4,31), ( 3,30),
        ( 2,29), (11, 4), ( 9, 2), ( 8, 1), (14, 7), (13, 6),
        (11, 4), (10, 3), ( 9, 2), ( 8, 1), (13, 6), (12, 5),
        (11, 4), (10, 3), ( 8, 1), (14, 7), (13, 6), (12, 5),
        (10, 3), ( 9, 2), ( 8, 1), (14, 7), (12, 5), (11, 4),
        (10, 3), ( 9, 2), (14, 7), (13, 6), (12, 5), (11, 4),
        ( 9, 2), ( 8, 1), (14, 7), (13, 6), (11, 4))

    TZ_OFFSETS = {
        "Z" :  0,
        "N" :  210, "NS" : 210, "ND" : 210,
        "A" :  240, "AS" : 240, "AD" : 180,
        "E" :  300, "ES" : 300, "ED" : 240,
        "C" :  360, "CS" : 360, "CD" : 300,
        "M" :  420, "MS" : 420, "MD" : 360,
        "P" :  480, "PS" : 480, "PD" : 420,
        "Y" :  540, "YS" : 540, "YD" : 480,
        "L" :  540, "LS" : 540, "LD" : 480,
        "H" :  600, "HS" : 600, "HD" : 600,
        "B" :  660, "BS" : 660, "BD" : 600,
        "J" : -480}

    @staticmethod
    def is_leap(y: int) :
        return (not bool(y % 4) and bool(y % 100)) or (not bool(y % 400))

    @staticmethod
    def last_day(y: int, m: int) :
        return m if m in (1,3,5,7,8,10,12) else 30 if m in (4,6,9,11) else 29 if Dt24.is_leap(y) else 28

    @staticmethod
    def now() :
        t = datetime.now()
        return Dt24(t.year, t.month, t.day, t.hour, t.minute, t.second, tzinfo=ZoneInfo("UTC"))

    @staticmethod
    def clone(other) :
        '''
        Create a (distinct) copy of this object
        '''
        y, m, d, h, n, s, z = other.year, other.month, other.day, other.hour, other.minute, other.second, other.tzinfo
        if isinstance(other._tzinfo, str) :
            z = other._tzinfo
        return Dt24(y, m, d, h, n, s, tzinfo=z)

    def __init__(self, *args, **kwargs) :
        '''
        Constructor
        '''
        args2   = args[:]
        kwargs2 = copy.deepcopy(kwargs)
        if "tzinfo" in kwargs2 :
            tzinfo = kwargs2["tzinfo"]
        else :
            raise ShefParserException(f"Cannot instantiate {self.__class__.__name__} object without tzinfo")
        adjust = False
        length = len(args2)
        if length > 3 :
            if args2[3] == 24 :
                adjust = True
                args2 = args2[:3]+(23,)+args2[4:]
        if isinstance(tzinfo, str) :
            del kwargs2["tzinfo"]
            tzinfo = tzinfo.upper()
            if tzinfo not in Dt24.TZ_OFFSETS :
                raise ShefParserException(f"Invalid SHEF time zone: {tzinfo}")
        elif isinstance(tzinfo, (timezone, ZoneInfo)) :
            pass
        else :
            raise ShefParserException(f"Invalid type for tzinfo: {tzinfo.__class__.__name__}")
        self._dt       = datetime(*args2, **kwargs2)
        self._tzinfo   = tzinfo
        self._adjusted = adjust
        if self._adjusted :
            self._dt += timedelta(hours=1)

    def to_timezone(self, tz) :
        '''
        Create a new object translated to the specified time zone
        '''
        def is_shef_summer_time(tz, y, m, d, h) :
            '''
            Determine whether a date is in summer time as defined by the SHEF Fortran parses
            '''
            summer_time = False
            if len(tz) == 1 and tz not in "ZJHN" :
                if 10 >= dt.month >= 3 :
                    if not (1976 <= dt.year <= 2040) :
                        raise ShefParserException("Can only perform SHEF time zone DST operations for years 1976-2040")
                    dom = Dt24.DST_DATES[dt.year-1976]
                    if dt.year < 2007 :
                        months = (4, 10)
                    else :
                        months = (3, 11)
                    if months[0] < dt.month < months[1] :
                        summer_time = True
                    elif dt.month == months[0] and (dt.day > dom[0] or dt.day == dom[0] and dt.hour >= 2) :
                        summer_time = True
                    elif dt.month == months[1] and (dt.day < dom[1] or dt.day == dom[1] and dt.hour < 2) :
                        summer_time = True
            return summer_time

        dt = self
        if not isinstance(tz, (ZoneInfo, str)) :
            raise ShefParserException(f"Invalid time zone type: {tz.__class__.__name__}")
        if isinstance(self._tzinfo, (timezone, ZoneInfo)) and isinstance(tz, (timezone, ZoneInfo)) :
            #-------------------------------#
            # move directly to specified TZ #
            #-------------------------------#
            dt = self._dt.astimezone(tz)
        elif isinstance(self._tzinfo, str) and isinstance(tz, str) :
            tz = tz.upper()
            if tz == "UTC" : tz = "Z"
            if tz not in Dt24.TZ_OFFSETS :
                raise ShefParserException(f"Invalid SHEF time zone: {tz}")
            #-------------------#
            # first move to UTC #
            #-------------------#
            adjusted = False
            if is_shef_summer_time(self._tzinfo, dt.year, dt.month, dt.day, dt.hour) :
                dt -= timedelta(hours=1)
                adjusted = True
            dt += timedelta(minutes=Dt24.TZ_OFFSETS[self._tzinfo])
            #---------------------------#
            # next move to specified TZ #
            #---------------------------#
            dt -= timedelta(minutes=Dt24.TZ_OFFSETS[tz])
            if not adjusted and is_shef_summer_time(self._tzinfo, dt.year, dt.month, dt.day, dt.hour) :
                dt += timedelta(hours=1)
        elif isinstance(self._tzinfo, str) and isinstance(tz, (timezone, ZoneInfo)) :
            #-------------------#
            # first move to UTC #
            #-------------------#
            if is_shef_summer_time(self._tzinfo, dt.year, dt.month, dt.day, dt.hour) :
                dt -= timedelta(hours=1)
            dt += timedelta(minutes=Dt24.TZ_OFFSETS[self._tzinfo])
            self._dt = datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, tzinfo=ShefParser.UTC)
            self._tzinfo = tzinfo=ShefParser.UTC
            #---------------------------#
            # next move to specified TZ #
            #---------------------------#
            dt = self._dt.astimezone(tz)
        else :
            raise ShefParserException(f"Invalid time zone combination: {self._tzinfo.__class__.__name__}, {tz.__class__.__name__}")
        dt = Dt24(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, tzinfo=tz)
        return dt

    def add_months(self, months: int, end_of_month: bool = False) :
        '''
        Add a number of months this object and return result
        '''
        dt = self._dt
        y, m, d, h, n, s, z = dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.tzinfo
        m += months
        while m > 12 :
            y += 1
            m -= 12
        while m < 1 :
            y -= 1
            m += 12
        if end_of_month :
            da = Dt24.last_day(y, m)
        else :
            da = min(d, Dt24.last_day(y, m))
        return Dt24(y, m, d, h, n, s, tzinfo=z)

    def __add__(self, other : Union[timedelta, MonthsDelta]) :
        if isinstance(other, timedelta) :
            dt = self._dt.__add__(other)
        if isinstance(other, MonthsDelta) :
            dt = self.add_months(other.months, other.eom)
        return Dt24(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, tzinfo=self._tzinfo)

    def __sub__(self, other : Union[timedelta, MonthsDelta]) :
        if isinstance(other, timedelta) :
            dt = self._dt.__sub__(other)
        if isinstance(other, MonthsDelta) :
            dt = self.add_months(-other.months, other.eom)
        if isinstance(other, Dt24) :
            return self._dt - other._dt
        return Dt24(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, tzinfo=self._tzinfo)

    def __repr__(self) :
        dt = self._dt
        if dt.hour == dt.minute == dt.second == 0 :
            s = (dt - timedelta(hours=1)).__repr__()
            return s[:11] + "24" + s[13:] + f" tzinfo={self._tzinfo}"
        return self._dt.__repr__() + f" tzinfo={self._tzinfo}"

    def __getattribute__(self, name) :
        if name in ("_dt", "_adjusted", "to_timezone", "add_months", "_tzinfo", "__class__") :
            return super().__getattribute__(name)
        elif name == "year" :
            if self._adjusted :
                y, h, n, s = self._dt.year, self._dt.hour, self._dt.minute, self._dt.second
                if h == n == s == 0 :
                    return (self._dt - timedelta(hours=1)).year
                return y
            else :
                return self._dt.year
        elif name == "month" :
            if self._adjusted :
                m, h, n, s = self._dt.month, self._dt.hour, self._dt.minute, self._dt.second
                if h == n == s == 0 :
                    return (self._dt - timedelta(hours=1)).month
                return m
            else :
                return self._dt.month
        elif name == "day" :
            if self._adjusted :
                d, h, n, s = self._dt.day, self._dt.hour, self._dt.minute, self._dt.second
                if h == n == s == 0 :
                    return (self._dt - timedelta(hours=1)).day
                return d
            else :
                return self._dt.day

        elif name == "hour" :
            if self._adjusted :
                h, n, s = self._dt.hour, self._dt.minute, self._dt.second
                if h == n == s == 0 :
                    return 24
                return h
            else :
                return self._dt.hour

        elif name == "tzinfo" :
            return self._tzinfo

        elif name == "astimezone" :
            return self.to_timezone

        else :
            return super().__getattribute__("_dt").__getattribute__(name)

    def __repr__(self) :
        return f"{self.year:04d}/{self.month:02d}/{self.day:02d}T{self.hour:02d}:{self.minute:02d}:{self.second:02d}{self.tzinfo}"

class OutputRecord :
    '''
    Parsed value
    '''
    SHEFIT_TEXT_V1 = "SHEFIT-TEXT1"
    SHEFIT_TEXT_V2 = "SHEFIT-TEXT2"
    SHEFIT_BINARY  = "SHEFIT-BINARY"

    OUTPUT_FORMATS = [SHEFIT_TEXT_V1, SHEFIT_TEXT_V2, SHEFIT_BINARY]

    def __init__(
            self,
            location:         str,
            parameter_code:   str,
            utc_obstime:      Dt24,
            utc_create_time:  Dt24 = None,
            en_value:         float = -9999.,
            qualifier:        str = 'Z',
            revised:          bool = False,
            duration_unit:    str  = 'Z',
            duration_value:   int  = None,
            message_source:   str = None,
            time_series_code: int = 0,
            comment:          str = None) :
        '''
        Constuctor
        '''
        if not location :
            raise ShefParserException("Location must not be empty")
        if not 3 <= len(location) <= 8 :
            raise ShefParserException(f"Location {location} must be 3 to 8 characters in length")
        if not parameter_code :
            raise ShefParserException("Parameter code must not be empty")
        if len(parameter_code) != 7 :
            raise ShefParserException(f"Parameter code {parameter_code} must be 7 characters in length")
        if not utc_obstime :
            raise ShefParserException("Observed time must not be empty")

        self._location             = location
        self._observation_time     = utc_obstime
        self._creation_time        = utc_create_time
        self._parameter_code       = parameter_code
        self._value                = en_value
        self._qualifier            = qualifier
        self._revised              = revised
        self._duration_unit        = duration_unit,
        self._duration_value       = duration_value,
        self._message_source       = message_source
        self._time_series_code     = time_series_code
        self._comment              = comment

    def format(self, fmt: str) :
        if fmt == OutputRecord.SHEFIT_TEXT_V2 :
            buf = io.StringIO()
            buf.write(self.location.ljust(8))
            buf.write(f"{self._observation_time.year:4d}")
            buf.write(f"{self._observation_time.month:2d}")
            buf.write(f"{self._observation_time.day:2d}")
            buf.write(f"{self._observation_time.hour:2d}")
            buf.write(f"{self._observation_time.minute:2d}")
            buf.write(f"{self._observation_time.second:2d}")
            buf.write(' ')
            if self._creation_time :
                buf.write(f"{self._creation_time.year:4d}")
                buf.write(f"{self._creation_time.month:2d}")
                buf.write(f"{self._creation_time.day:2d}")
                buf.write(f"{self._creation_time.hour:2d}")
                buf.write(f"{self._creation_time.minute:2d}")
                buf.write(f"{self._creation_time.second:2d}")
            else :
                buf.write("   0 0 0 0 0 0")
            buf.write(self.physical_element_code.rjust(3))
            buf.write(self.type_code.rjust(2))
            buf.write(self.source_code)
            buf.write(self.extremum_code)
            buf.write(f"{self.value:10.3f}")
            buf.write(self.qualifier.rjust(2))
            buf.write(f"{self.probability_code_number:6.2f}")
            buf.write(f"{self.duration_code_number:5d}")
            buf.write(f"{self.revised:2d}")
            buf.write(' ')
            buf.write(self.message_source.ljust(8) if self.message_source else "        ")
            buf.write(f"{self.time_series_code:4d}")
            if self.comment :
                buf.write(f"\n{self.comment}")
            rec = buf.getvalue()
            buf.close()
        else :
            raise ShefParserException(f'Invalid output format: "{fmt}"')
        return rec

    @property
    def location(self) :
        return self._location
    @property
    def obstime(self) :
        t = self._observation_time
        return (t.year, t.month, t.day, t.hour, t.minute, t.second)
    @property
    def create_time(self) :
        t = self._create_time
        if not t : return (0, 0, 0, 0, 0, 0)
        return (t.year, t.month, t.day, t.hour, t.minute, t.second)
    @property
    def physical_element_code(self) :
        return self._parameter_code[:2]
    @property
    def duration_code(self) :
        return self._parameter_code[2]
    @property
    def duration_code_number(self) :
        if self.duration_code == 'V' :
            if self._duration_unit == 'Z' or self._duration_value is None :
                raise ShefParserException(f"No duration specified for parameter code {self._parametet_code}")
            return ShefParser.DURATION_VARIABLE_CODES[self._duration_unit] + self._duration_value
        else :
            return ShefParser.DURATION_CODES[self.duration_code]
    @property
    def type_code(self) :
        return self._parameter_code[3]
    @property
    def source_code(self) :
        return self._parameter_code[4]
    @property
    def extremum_code(self) :
        return self._parameter_code[5]
    @property
    def probability_code(self) :
        return self._parameter_code[6]
    @property
    def probability_code_number(self) :
        return float(ShefParser.PROBABILITY_CODES[self._parameter_code[6]])
    @property
    def value(self) :
        return self._value
    @property
    def qualifier(self) :
        return self._qualifier
    @property
    def revised(self) :
        return self._revised
    @property
    def message_source(self) :
        return self._message_source
    @property
    def time_series_code(self) :
        return self._time_series_code
    @property
    def comment(self) :
        return self._comment


class ShefParser :
    '''
    The parser
    '''
    PE_DESCRIPTIONS = {
        #
        # From SHEF Manual (shef_2.2.pdf)
        #
        "AF" : {"description" :"Surface frost intensity", "units" : "(coded, see Table 20)"},
        "AG" : {"description" :"Percent of green vegetation", "units" : "(%)"},
        "AM" : {"description" :"Surface dew intensity", "units" : "(coded, see Table 21)"},
        "AT" : {"description" :"Time below critical temperature, 25 DF or -3.9 DC", "units" : "(HRS and MIN)"},
        "AU" : {"description" :"Time below critical temperature, 32 DF or 0 DC", "units" : "(HRS and MIN)"},
        "AW" : {"description" :"Leaf wetness", "units" : "(HRS and MIN)"},
        "BA" : {"description" :"Solid portion of water equivalent", "units" : "(in, mm)"},
        "BB" : {"description" :"Heat deficit", "units" : "(in, mm)"},
        "BC" : {"description" :"Liquid water storage", "units" : "(in, mm)"},
        "BD" : {"description" :"Temperature index", "units" : "(DF, DC)"},
        "BE" : {"description" :"Maximum water equivalent since snow began to accumulate", "units" : "(in, mm)"},
        "BF" : {"description" :"Areal water equivalent just prior to the new snowfall", "units" : "(in, mm)"},
        "BG" : {"description" :"Areal extent of snow cover from the areal depletion curve just prior to the new snowfall", "units" : "(%)"},
        "BH" : {"description" :"Amount of water equivalent above which 100 % areal snow cover temporarily exists", "units" : "(in, mm)"},
        "BI" : {"description" :"Excess liquid water in storage", "units" : "(in, mm)"},
        "BJ" : {"description" :"Areal extent of snow cover adjustment", "units" : "(in, mm)"},
        "BK" : {"description" :"Lagged excess liquid water for interval 1", "units" : "(in, mm)"},
        "BL" : {"description" :"Lagged excess liquid water for interval 2", "units" : "(in, mm)"},
        "BM" : {"description" :"Lagged excess liquid water for interval 3", "units" : "(in, mm)"},
        "BN" : {"description" :"Lagged excess liquid water for interval 4", "units" : "(in, mm)"},
        "BO" : {"description" :"Lagged excess liquid water for interval 5", "units" : "(in, mm)"},
        "BP" : {"description" :"Lagged excess liquid water for interval 6", "units" : "(in, mm)"},
        "BQ" : {"description" :"Lagged excess liquid water for interval 7", "units" : "(in, mm)"},
        "CA" : {"description" :"Upper zone tension water contents", "units" : "(in, mm)"},
        "CB" : {"description" :"Upper zone free water contents", "units" : "(in, mm)"},
        "CC" : {"description" :"Lower zone tension water contents", "units" : "(in, mm)"},
        "CD" : {"description" :"Lower zone free water supplementary storage contents", "units" : "(in, mm)"},
        "CE" : {"description" :"Lower zone free water primary storage contents", "units" : "(in, mm)"},
        "CF" : {"description" :"Additional impervious area contents", "units" : "(in, mm)"},
        "CG" : {"description" :"Antecedent precipitation index", "units" : "(in, mm)"},
        "CH" : {"description" :"Soil moisture index deficit", "units" : "(in, mm)"},
        "CI" : {"description" :"Base flow storage contents", "units" : "(in, mm)"},
        "CJ" : {"description" :"Base flow index", "units" : "(in, mm)"},
        "CK" : {"description" :"First quadrant index Antecedent Evaporation Index (AEI)", "units" : "(in, mm)"},
        "CL" : {"description" :"First quadrant index Antecedent Temperature Index (ATI)", "units" : "(DF, DC)"},
        "CM" : {"description" :"Frost index", "units" : "(DF, DC)"},
        "CN" : {"description" :"Frost efficiency index", "units" : "(%)"},
        "CO" : {"description" :"Indicator of first quadrant index", "units" : "(AEI or ATI)"},
        "CP" : {"description" :"Storm total rainfall", "units" : "(in, mm)"},
        "CQ" : {"description" :"Storm total runoff", "units" : "(in, mm)"},
        "CR" : {"description" :"Storm antecedent index", "units" : "(in, mm)"},
        "CS" : {"description" :"Current antecedent index", "units" : "(in, mm)"},
        "CT" : {"description" :"Storm period counter", "units" : "(integer)"},
        "CU" : {"description" :"Average air temperature", "units" : "(DF, DC)"},
        "CV" : {"description" :"Current corrected synthetic temperature", "units" : "(DF, DC)"},
        "CW" : {"description" :"Storm antecedent evaporation index, AEI", "units" : "(in, mm)"},
        "CX" : {"description" :"Current AEI", "units" : "(in, mm)"},
        "CY" : {"description" :"Current API", "units" : "(in, mm)"},
        "CZ" : {"description" :"Climate Index", "units" : ""},
        "EA" : {"description" :"Evapotranspiration potential amount", "units" : "(IN, MM)"},
        "ED" : {"description" :"Evaporation, pan depth", "units" : "(IN, MM)"},
        "EM" : {"description" :"Evapotranspiration amount", "units" : "(IN, MM)"},
        "EP" : {"description" :"Evaporation, pan increment", "units" : "(IN, MM)"},
        "ER" : {"description" :"Evaporation rate", "units" : "(IN/day, MM/day)"},
        "ET" : {"description" :"Evapotranspiration total", "units" : "(IN, MM)"},
        "EV" : {"description" :"Evaporation, lake computed", "units" : "(IN, MM)"},
        "FA" : {"description" :"Fish - shad", "units" : ""},
        "FB" : {"description" :"Fish - sockeye", "units" : ""},
        "FC" : {"description" :"Fish - chinook", "units" : ""},
        "FE" : {"description" :"Fish - chum", "units" : ""},
        "FK" : {"description" :"Fish - coho", "units" : ""},
        "FL" : {"description" :"Fish - ladder", "units" : "(1=left, 2=right, 3=total)"},
        "FP" : {"description" :"Fish - pink", "units" : ""},
        "FS" : {"description" :"Fish – steelhead", "units" : ""},
        "FT" : {"description" :"Fish type - type", "units" : "(1=adult, 2=jacks, 3=fingerlings)"},
        "FZ" : {"description" :"Fish - count of all types combined", "units" : ""},
        "GC" : {"description" :"Condition, road surface", "units" : "(coded, see Table 1)"},
        "GD" : {"description" :"Frost depth, depth of frost penetration, non permafrost", "units" : "(IN, CM)"},
        "GL" : {"description" :"Salt content on a surface (e.g., road)", "units" : "(%)"},
        "GP" : {"description" :"Frost, depth of pavement surface", "units" : "(IN, CM)"},
        "GR" : {"description" :"Frost report, structure", "units" : "(coded, see Table 16)"},
        "GS" : {"description" :"Ground state", "units" : "(coded, see Table 18)"},
        "GT" : {"description" :"Frost, depth of surface frost thawed", "units" : "(IN, CM)"},
        "GW" : {"description" :"Frost, depth of pavement surface frost thawed", "units" : "(IN, CM)"},
        "HA" : {"description" :"Height of reading, altitude above surface", "units" : "(FT, M)"},
        "HB" : {"description" :"Depth of reading below surface, or to water table or groundwater", "units" : "(FT, M)"},
        "HC" : {"description" :"Height, ceiling", "units" : "(FT, M)"},
        "HD" : {"description" :"Height, head", "units" : "(FT, M)"},
        "HE" : {"description" :"Height, regulating gate", "units" : "(FT, M)"},
        "HF" : {"description" :"Elevation, project powerhouse forebay", "units" : "(FT, M)"},
        "HG" : {"description" :"Height, river stage", "units" : "(FT, M)"},
        "HH" : {"description" :"Height of reading, elevation in MSL", "units" : "(FT, M)"},
        "HI" : {"description" :"Stage trend indicator", "units" : "(coded, see Table 19)"},
        "HJ" : {"description" :"Height, spillway gate", "units" : "(FT, M)"},
        "HK" : {"description" :"Height, lake above a specified datum", "units" : "(FT, M)"},
        "HL" : {"description" :"Elevation, natural lake", "units" : "(FT, M)"},
        "HM" : {"description" :"Height of tide, MLLW", "units" : "(FT, M)"},
        "HO" : {"description" :"Height, flood stage", "units" : "(FT, M)"},
        "HP" : {"description" :"Elevation, pool", "units" : "(FT, M)"},
        "HQ" : {"description" :"Distance from a ground reference point to the river's edge used to estimate stage", "units" : "(coded, see Chapter 7.4.6)"},
        "HR" : {"description" :"Elevation, lake or reservoir rule curve", "units" : "(FT, M)"},
        "HS" : {"description" :"Elevation, spillway forebay", "units" : "(FT, M)"},
        "HT" : {"description" :"Elevation, project tail water stage", "units" : "(FT, M)"},
        "HU" : {"description" :"Height, cautionary stage", "units" : "(FT, M)"},
        "HV" : {"description" :"Depth of water on a surface (e.g., road)", "units" : "(IN, MM)"},
        "HW" : {"description" :"Height, spillway tail water", "units" : "(FT, M)"},
        "HZ" : {"description" :"Elevation, freezing level", "units" : "(KFT, KM)"},
        "IC" : {"description" :"Ice cover, river", "units" : "(%)"},
        "IE" : {"description" :"Extent of ice from reporting area, upstream \"+\", downstream \"-\"", "units" : "(MI, KM)"},
        "IO" : {"description" :"Extent of open water from reporting area, downstream \"+\", upstream \"-\"", "units" : "(FT, M)"},
        "IR" : {"description" :"Ice report type, structure, and cover", "units" : "(coded, see Table 14)"},
        "IT" : {"description" :"Ice thickness", "units" : "(IN, CM)"},
        "LA" : {"description" :"Lake surface area", "units" : "(KAC,KM2)"},
        "LC" : {"description" :"Lake storage volume change", "units" : "(KAF,MCM)"},
        "LS" : {"description" :"Lake storage volume", "units" : "(KAF,MCM)"},
        "MD" : {"description" :"Dielectric Constant at depth, paired value vector", "units" : "(coded, see Chapter 7.4.6 for format)"},
        "MI" : {"description" :"Moisture, soil index or API", "units" : "(IN, CM)"},
        "ML" : {"description" :"Moisture, lower zone storage", "units" : "(IN, CM)"},
        "MM" : {"description" :"Fuel moisture, wood", "units" : "(%)"},
        "MN" : {"description" :"Soil Salinity at depth, paired value vector", "units" : "(coded, see Chapter 7.4.6 for format)"},
        "MS" : {"description" :"Soil Moisture amount at depth", "units" : "(coded, see Chapter 7.4.6)"},
        "MT" : {"description" :"Fuel temperature, wood probe", "units" : "(DF, DC)"},
        "MU" : {"description" :"Moisture, upper zone storage", "units" : "(IN, CM)"},
        "MV" : {"description" :"Water Volume at Depth, paired value vector", "units" : "(coded, see Chapter 7.4.6 for format)"},
        "MW" : {"description" :"Moisture, soil, percent by weight", "units" : "(%)"},
        "NC" : {"description" :"River control switch", "units" : "(0=manual river control, 1=open river uncontrolled)"},
        "NG" : {"description" :"Total of gate openings", "units" : "(FT, M)"},
        "NL" : {"description" :"Number of large flash boards down", "units" : "(whole number)"},
        "NN" : {"description" :"Number of the spillway gate reported", "units" : "(used with HP, QS)"},
        "NO" : {"description" :"Gate opening for a specific gate", "units" : "(coded, see Chapter 7.4.6)"},
        "NS" : {"description" :"Number of small flash boards down", "units" : "(whole number)"},
        "PA" : {"description" :"Pressure, atmospheric", "units" : "(IN-HG, KPA)"},
        "PC" : {"description" :"Precipitation, accumulator", "units" : "(IN, MM)"},
        "PD" : {"description" :"Pressure, atmospheric net change during past 3 hours", "units" : "(IN-HG, KPA)"},
        "PE" : {"description" :"Pressure, characteristic, NWS Handbook #7, table 10.7", "units" : ""},
        "PJ" : {"description" :"Precipitation, departure from normal", "units" : "(IN, MM)"},
        "PL" : {"description" :"Pressure, sea level", "units" : "(IN-HG, KPA)"},
        "PM" : {"description" :"Probability of measurable precipitation (dimensionless)", "units" : "(coded, see Table 22)"},
        "PN" : {"description" :"Precipitation normal", "units" : "(IN, MM)"},
        "PP" : {"description" :"Precipitation (includes liquid amount of new snowfall), actual increment", "units" : "(IN, MM)"},
        "PR" : {"description" :"Precipitation rate", "units" : "(IN/day, MM/day)"},
        "PT" : {"description" :"Precipitation, type", "units" : "(coded, see Table 17)"},
        "QA" : {"description" :"Discharge, adjusted for storage at project only", "units" : "(KCFS, CMS)"},
        "QB" : {"description" :"Runoff depth", "units" : "(IN, MM)"},
        "QC" : {"description" :"Runoff volume", "units" : "(KAF, MCM)"},
        "QD" : {"description" :"Discharge, canal diversion", "units" : "(KCFS, CMS)"},
        "QE" : {"description" :"Discharge, percent of flow diverted from channel", "units" : "(%)"},
        "QF" : {"description" :"Discharge velocity", "units" : "(MPH, KPH)"},
        "QG" : {"description" :"Discharge from power generation", "units" : "(KCFS, CMS)"},
        "QI" : {"description" :"Discharge, inflow", "units" : "(KCFS, CMS)"},
        "QL" : {"description" :"Discharge, rule curve", "units" : "(KCFS, CMS)"},
        "QM" : {"description" :"Discharge, preproject conditions in basin", "units" : "(KCFS, CMS)"},
        "QP" : {"description" :"Discharge, pumping", "units" : "(KCFS, CMS)"},
        "QR" : {"description" :"Discharge, river", "units" : "(KCFS, CMS)"},
        "QS" : {"description" :"Discharge, spillway", "units" : "(KCFS, CMS)"},
        "QT" : {"description" :"Discharge, computed total project outflow", "units" : "(KCFS, CMS)"},
        "QU" : {"description" :"Discharge, controlled by regulating outlet", "units" : "(KCFS, CMS)"},
        "QV" : {"description" :"Cumulative volume increment", "units" : "(KAF, MCM)"},
        "RA" : {"description" :"Radiation, albedo", "units" : "(%)"},
        "RI" : {"description" :"Radiation, accumulated incoming solar over specified duration in langleys", "units" : "(LY)"},
        "RN" : {"description" :"Radiation, net radiometers", "units" : "(watts/meter squared)"},
        "RP" : {"description" :"Radiation, sunshine percent of possible", "units" : "(%)"},
        "RT" : {"description" :"Radiation, sunshine hours", "units" : "(HRS)"},
        "RW" : {"description" :"Radiation, total incoming solar radiation", "units" : "(watts/meter squared)"},
        "SA" : {"description" :"Snow, areal extent of basin snow cover", "units" : "(%)"},
        "SB" : {"description" :"Snow, Blowing Snow Sublimation", "units" : "(IN)"},
        "SD" : {"description" :"Snow, depth", "units" : "(IN, CM)"},
        "SE" : {"description" :"Snow, Average Snowpack Temperature", "units" : "(DF)"},
        "SF" : {"description" :"Snow, depth, new snowfall", "units" : "(IN, CM)"},
        "SI" : {"description" :"Snow, depth on top of river or lake ice", "units" : "(IN, CM)"},
        "SL" : {"description" :"Snow, elevation of snow line", "units" : "(KFT, M)"},
        "SM" : {"description" :"Snow, Melt", "units" : "(IN)"},
        "SP" : {"description" :"Snowmelt plus rain", "units" : "(IN)"},
        "SR" : {"description" :"Snow report, structure, type, surface, and bottom", "units" : "(coded, see Table 15)"},
        "SS" : {"description" :"Snow density", "units" : "(IN SWE/IN snow, CM SWE/CM snow)"},
        "ST" : {"description" :"Snow temperature at depth measured from ground", "units" : "(See Chapter 7.4.6 for format)"},
        "SU" : {"description" :"Snow, Surface Sublimation", "units" : "(IN)"},
        "SW" : {"description" :"Snow, water equivalent", "units" : "(IN, MM)"},
        "TA" : {"description" :"Temperature, air, dry bulb", "units" : "(DF,DC)"},
        "TB" : {"description" :"Temperature in bare soil at depth", "units" : "(coded, see Chapter 7.4.6 for format)"},
        "TC" : {"description" :"Temperature, degree days of cooling, above 65 DF or 18.3 DC", "units" : "(DF,DC)"},
        "TD" : {"description" :"Temperature, dew point", "units" : "(DF,DC)"},
        "TE" : {"description" :"Temperature, air temperature at elevation above MSL", "units" : "(See Chapter 7.4.6 for format)"},
        "TF" : {"description" :"Temperature, degree days of freezing, below 32 DF or 0 DC", "units" : "(DF,DC)"},
        "TH" : {"description" :"Temperature, degree days of heating, below 65 DF or 18.3 DC", "units" : "(DF,DC)"},
        "TJ" : {"description" :"Temperature, departure from normal", "units" : "(DF, DC)"},
        "TM" : {"description" :"Temperature, air, wet bulb", "units" : "(DF,DC)"},
        "TP" : {"description" :"Temperature, pan water", "units" : "(DF,DC)"},
        "TR" : {"description" :"Temperature, road surface", "units" : "(DF,DC)"},
        "TS" : {"description" :"Temperature, bare soil at the surface", "units" : "(DF,DC)"},
        "TV" : {"description" :"Temperature in vegetated soil at depth", "units" : "(coded, see Chapter 7.4.6 for format)"},
        "TW" : {"description" :"Temperature, water", "units" : "(DF,DC)"},
        "TZ" : {"description" :"Temperature, Freezing, road surface", "units" : "(DF,DC)"},
        "UC" : {"description" :"Wind, accumulated wind travel", "units" : "(MI,KM)"},
        "UD" : {"description" :"Wind, direction", "units" : "(whole degrees)"},
        "UE" : {"description" :"Wind, standard deviation", "units" : "(Degrees)"},
        "UG" : {"description" :"Wind, gust at observation time", "units" : "(MI/HR,M/SEC)"},
        "UH" : {"description" :"Wind gust direction associated with the wind gust", "units" : "(in tens of degrees)"},
        "UL" : {"description" :"Wind, travel length accumulated over specified", "units" : "(MI,KM)"},
        "UP" : {"description" :"Peak wind speed", "units" : "(MPH)"},
        "UQ" : {"description" :"Wind direction and speed combined (SSS.SDDD), a value of 23.0275 would indicate a wind of 23.0 mi/hr from 275 degrees", "units" : ""},
        "UR" : {"description" :"Peak wind direction associated with peak wind speed", "units" : "(in tens of degrees)"},
        "US" : {"description" :"Wind, speed", "units" : "(MI/HR,M/SEC)"},
        "UT" : {"description" :"Minute of the peak wind speed", "units" : "(in minutes past the hour, 0-59)"},
        "VB" : {"description" :"Voltage - battery", "units" : "(volt)"},
        "VC" : {"description" :"Generation, surplus capacity of units on line", "units" : "(megawatts)"},
        "VE" : {"description" :"Generation, energy total", "units" : "(megawatt hours)"},
        "VG" : {"description" :"Generation, pumped water, power produced", "units" : "(megawatts)"},
        "VH" : {"description" :"Generation, time", "units" : "(HRS)"},
        "VJ" : {"description" :"Generation, energy produced from pumped water", "units" : "(megawatt hours)"},
        "VK" : {"description" :"Generation, energy stored in reservoir only", "units" : "(megawatt * \"duration\")"},
        "VL" : {"description" :"Generation, storage due to natural flow only", "units" : "(megawatt * \"duration\")"},
        "VM" : {"description" :"Generation, losses due to spill and other water losses", "units" : "(megawatt * \"duration\")"},
        "VP" : {"description" :"Generation, pumping use, power used", "units" : "(megawatts)"},
        "VQ" : {"description" :"Generation, pumping use, total energy used", "units" : "(megawatt hours)"},
        "VR" : {"description" :"Generation, stored in reservoir plus natural flow, energy potential", "units" : "(megawatt * \"duration\")"},
        "VS" : {"description" :"Generation, station load, energy used", "units" : "(megawatt hours)"},
        "VT" : {"description" :"Generation, power total", "units" : "(megawatts)"},
        "VU" : {"description" :"Generator, status", "units" : "(encoded)"},
        "VW" : {"description" :"Generation station load, power used", "units" : "(megawatts)"},
        "WA" : {"description" :"Water, dissolved nitrogen & argon", "units" : "(PPM, MG/L)"},
        "WC" : {"description" :"Water, conductance", "units" : "(uMHOS/CM)"},
        "WD" : {"description" :"Water, piezometer water depth", "units" : "(IN, CM)"},
        "WG" : {"description" :"Water, dissolved total gases, pressure", "units" : "(IN-HG, MM-HG)"},
        "WH" : {"description" :"Water, dissolved hydrogen sulfide", "units" : "(PPM, MG/L)"},
        "WL" : {"description" :"Water, suspended sediment", "units" : "(PPM, MG/L)"},
        "WO" : {"description" :"Water, dissolved oxygen", "units" : "(PPM, MG/L)"},
        "WP" : {"description" :"Water, ph", "units" : "(PH value)"},
        "WS" : {"description" :"Water, salinity", "units" : "(parts per thousand, PPT)"},
        "WT" : {"description" :"Water, turbidity", "units" : "(JTU)"},
        "WV" : {"description" :"Water, velocity", "units" : "(FT/SEC, M/SEC)"},
        "WX" : {"description" :"Water, Oxygen Saturation", "units" : "(%)"},
        "WY" : {"description" :"Water, Chlorophyll", "units" : "(ppb, ug/L)"},
        "XC" : {"description" :"Total sky cover", "units" : "(tenths)"},
        "XG" : {"description" :"Lightning, number of strikes per grid box", "units" : "(whole number)"},
        "XL" : {"description" :"Lightning, point strike, assumed one strike at transmitted latitude and longitude", "units" : "(whole number)"},
        "XP" : {"description" :"Weather, past NWS synoptic code", "units" : "(see Appendix D)"},
        "XR" : {"description" :"Humidity, relative", "units" : "(%)"},
        "XU" : {"description" :"Humidity, absolute", "units" : "(grams/FT3,grams/M3)"},
        "XV" : {"description" :"Weather, visibility", "units" : "(MI, KM)"},
        "XW" : {"description" :"Weather, present NWS synoptic code", "units" : "(see Appendix C)"},
        "YA" : {"description" :"Number of 15-minute periods a river has been above a specified critical level", "units" : "(whole number)"},
        "YC" : {"description" :"Random report sequence number", "units" : "(whole number)"},
        "YF" : {"description" :"Forward power, a measurement of the DCP, antenna, and coaxial cable", "units" : "(watts)"},
        "YI" : {"description" :"SERFC unique", "units" : ""},
        "YP" : {"description" :"Reserved Code", "units" : ""},
        "YR" : {"description" :"Reflected power, a measurement of the DCP, antenna, and coaxial cable", "units" : "(watts)"},
        "YS" : {"description" :"Sequence number of the number of times the DCP has transmitted", "units" : "(whole number)"},
        "YT" : {"description" :"Number of 15-minute periods since a random report was generated due to an increase of 0.4 inch of precipitation", "units" : "(whole number)"},
        "YU" : {"description" :"GENOR raingage status level 1 - NERON observing sites", "units" : "(YUIRG)"},
        "YV" : {"description" :"A Second Battery Voltage (NERON sites ONLY), voltage 0", "units" : "(YVIRG)"},
        "YW" : {"description" :"GENOR raingage status level 2 - NERON observing sites", "units" : "(YWIRG)"},
        "YY" : {"description" :"GENOR raingage status level 3 - NERON observing sites", "units" : "(YYIRG)"},
        "YZ" : {"description" :"Time of Observation – Minutes of the calendar day, minutes 0 - NERON observing sites", "units" : "(YZIRG)"}}

    PE_CONVERSIONS = {
        #
        # May be modified by SHEFPARM file
        #
        # Numeric values are SI->English unit conversion factors (units specified in manual)
        #
        # Note tha PE code PL was changed from English unit of in-hg (as specified in manual)
        # to mb (as specified in SHEFPARM comment at the top of this script). SI unit not changed.
        #
        "AD" :        1.0, "AF" :        1.0, "AG" :        1.0, "AM" :        1.0, "AT" :        1.0, "AU" :        1.0, "AW" :        1.0,
        "BA" :  0.0393701, "BB" :  0.0393701, "BC" :  0.0393701, "BD" :       -1.0, "BE" :  0.0393701, "BF" :  0.0393701, "BG" :        1.0,
        "BH" :  0.0393701, "BI" :  0.0393701, "BJ" :  0.0393701, "BK" :  0.0393701, "BL" :  0.0393701, "BM" :  0.0393701, "BN" :  0.0393701,
        "BO" :  0.0393701, "BP" :  0.0393701, "BQ" :  0.0393701, "CA" :  0.0393701, "CB" :  0.0393701, "CC" :  0.0393701, "CD" :  0.0393701,
        "CE" :  0.0393701, "CF" :  0.0393701, "CG" :  0.0393701, "CH" :  0.0393701, "CI" :  0.0393701, "CJ" :  0.0393701, "CK" :  0.0393701,
        "CL" :       -1.0, "CM" :       -1.0, "CN" :        1.0, "CO" :        1.0, "CP" :  0.0393701, "CQ" :  0.0393701, "CR" :  0.0393701,
        "CS" :  0.0393701, "CT" :        1.0, "CU" :       -1.0, "CV" :       -1.0, "CW" :  0.0393701, "CX" :  0.0393701, "CY" :  0.0393701,
        "CZ" :        1.0, "EA" :  0.0393701, "ED" :  0.0393701, "EM" :  0.0393701, "EP" :  0.0393701, "ER" :  0.0393701, "ET" :  0.0393701,
        "EV" :  0.0393701, "FA" :        1.0, "FB" :        1.0, "FC" :        1.0, "FE" :        1.0, "FK" :        1.0, "FL" :        1.0,
        "FP" :        1.0, "FS" :        1.0, "FT" :        1.0, "FZ" :        1.0, "GC" :        1.0, "GD" :  0.3937008, "GL" :        1.0,
        "GP" :  0.3937008, "GR" :        1.0, "GS" :        1.0, "GT" :  0.3937008, "GW" :  0.3937008, "HA" :  3.2808399, "HB" :  3.2808399,
        "HC" :  3.2808399, "HD" :  3.2808399, "HE" :  3.2808399, "HF" :  3.2808399, "HG" :  3.2808399, "HH" :  3.2808399, "HI" :        1.0,
        "HJ" :  3.2808399, "HK" :  3.2808399, "HL" :  3.2808399, "HM" :  3.2808399, "HO" :  3.2808399, "HP" :  3.2808399, "HQ" :        1.0,
        "HR" :  3.2808399, "HS" :  3.2808399, "HT" :  3.2808399, "HU" :  3.2808399, "HV" :  0.0393701, "HW" :  3.2808399, "HZ" :  3.2808399,
        "IC" :        1.0, "IE" :  0.6213712, "IO" :  3.2808399, "IR" :        1.0, "IT" :  0.3937008, "LA" :  247.10541, "LC" :  0.8107131,
        "LS" :  0.8107131, "MD" :        1.0, "MI" :        1.0, "ML" :  0.3937008, "MM" :        1.0, "MN" :        1.0, "MS" :        1.0,
        "MT" :       -1.0, "MU" :  0.3937008, "MV" :        1.0, "MW" :        1.0, "NC" :        1.0, "NG" :  3.2808399, "NL" :        1.0,
        "NN" :        1.0, "NO" :        1.0, "NS" :        1.0, "PA" :   0.295297, "PC" :  0.0393701, "PD" :   0.295297, "PE" :        1.0,
        "PJ" :  0.0393701, "PL" :       10.0, "PM" :        1.0, "PN" :  0.0393701, "PP" :  0.0393701, "PR" :  0.0393701, "PT" :        1.0,
        "PY" :  0.0393701, "QA" :  0.0353147, "QB" :  0.0393701, "QC" :  0.8107131, "QD" :  0.0353147, "QE" :        1.0, "QF" :  0.6213712,
        "QG" :  0.0353147, "QI" :  0.0353147, "QL" :  0.0353147, "QM" :  0.0353147, "QP" :  0.0353147, "QR" :  0.0353147, "QS" :  0.0353147,
        "QT" :  0.0353147, "QU" :  0.0353147, "QV" :  0.8107131, "QZ" :        1.0, "RA" :        1.0, "RI" :        1.0, "RN" :        1.0,
        "RP" :        1.0, "RT" :        1.0, "RW" :        1.0, "SA" :        1.0, "SB" :  0.0393701, "SD" :  0.3937008, "SE" :       -1.0,
        "SF" :  0.3937008, "SI" :  0.3937008, "SL" :  0.0032808, "SM" :  0.0393701, "SP" :  0.0393701, "SR" :        1.0, "SS" :        1.0,
        "ST" :        1.0, "SU" :  0.0393701, "SW" :  0.0393701, "TA" :       -1.0, "TB" :        1.0, "TC" :       -1.0, "TD" :       -1.0,
        "TE" :        1.0, "TF" :       -1.0, "TH" :       -1.0, "TJ" :       -1.0, "TM" :       -1.0, "TP" :       -1.0, "TR" :       -1.0,
        "TS" :       -1.0, "TV" :        1.0, "TW" :       -1.0, "TZ" :       -1.0, "UC" :  0.6213712, "UD" :        1.0, "UE" :        1.0,
        "UG" :  2.2369363, "UH" :        1.0, "UL" :  0.6213712, "UP" :        1.0, "UQ" :        1.0, "UR" :        1.0, "US" :  2.2369363,
        "UT" :        1.0, "VB" :        1.0, "VC" :        1.0, "VE" :        1.0, "VG" :        1.0, "VH" :        1.0, "VJ" :        1.0,
        "VK" :        1.0, "VL" :        1.0, "VM" :        1.0, "VP" :        1.0, "VQ" :        1.0, "VR" :        1.0, "VS" :        1.0,
        "VT" :        1.0, "VU" :        1.0, "VW" :        1.0, "WA" :        1.0, "WC" :        1.0, "WD" :  0.3937008, "WG" :  0.0393701,
        "WH" :        1.0, "WL" :        1.0, "WO" :        1.0, "WP" :        1.0, "WS" :        1.0, "WT" :        1.0, "WV" :  3.2808399,
        "WX" :        1.0, "WY" :        1.0, "XC" :        1.0, "XG" :        1.0, "XL" :        1.0, "XP" :        1.0, "XR" :        1.0,
        "XU" :  2.2883564, "XV" :  0.6213712, "XW" :        1.0, "YA" :        1.0, "YC" :        1.0, "YF" :        1.0, "YI" :        1.0,
        "YP" :        1.0, "YR" :        1.0, "YS" :        1.0, "YT" :        1.0, "YV" :        1.0, "YY" :        1.0}

    SEND_CODES = {
        #
        # May be modified by SHEFPARM file
        #
        # Boolean values are whether value is at (or ends at) 0700 local time prior to time stamp
        #
        "AD" : ("ADZZZZZ", False), "AT" : ("ATD",     False), "AU" : ("AUD",     False), "AW" : ("AWD",     False), "EA" : ("EAD",     False),
        "EM" : ("EMD",     False), "EP" : ("EPD",     False), "ER" : ("ERD",     False), "ET" : ("ETD",     False), "EV" : ("EVD",     False),
        "HN" : ("HGIRZNZ", False), "HX" : ("HGIRZXZ", False), "HY" : ("HGIRZZZ", True) , "LC" : ("LCD",     False), "PF" : ("PPTCF",   False),
        "PY" : ("PPDRZZZ", True) , "PP" : ("PPD",     False), "PR" : ("PRD",     False), "QC" : ("QCD",     False), "QN" : ("QRIRZNZ", False),
        "QX" : ("QRIRZXZ", False), "QY" : ("QRIRZZZ", True) , "SF" : ("SFD",     False), "TN" : ("TAIRZNZ", False), "QV" : ("QVZ",     False),
        "RI" : ("RID",     False), "RP" : ("RPD",     False), "RT" : ("RTD",     False), "TC" : ("TCS",     False), "TF" : ("TFS",     False),
        "TH" : ("THS",     False), "TX" : ("TAIRZXZ", False), "UC" : ("UCD",     False), "UL" : ("ULD",     False), "XG" : ("XGJ",     False),
        "XP" : ("XPQ",     False)}

    DURATION_CODES    = {
        #
        # May be modified by SHEFPARM file
        #
        # Quoted numeric values are simply numeric equivalent codes
        #
        'I' :    0, 'U' :    1, 'E' :    5, 'G' :   10, 'C' :   15,
        'J' :   30, 'H' : 1001, 'B' : 1002, 'T' : 1003, 'F' : 1004,
        'Q' : 1006, 'A' : 1008, 'K' : 1012, 'L' : 1018, 'D' : 2001,
        'W' : 2007, 'N' : 2015, 'M' : 3001, 'Y' : 4001, 'Z' : 5000,
        'S' : 5001, 'R' : 5002, 'V' : 5003, 'P' : 5004, 'X' : 5005}

    TS_CODES = set((
        #
        # May be modified by SHEFPARM file
        #
        "12", "13", "14", "15", "16", "17", "18", "19", "1A", "1B", "1C", "1D", "1F", "1G", "1M", "1P", "1R", "1S", "1T", "1V", "1W", "1X",
        "1Z", "22", "23", "24", "25", "26", "27", "28", "29", "2A", "2B", "2C", "2D", "2F", "2G", "2M", "2P", "2R", "2S", "2T", "2V", "2W",
        "2X", "2Z", "32", "33", "34", "35", "36", "37", "38", "39", "3A", "3B", "3C", "3D", "3F", "3G", "3M", "3P", "3R", "3S", "3T", "3V",
        "3W", "3X", "3Z", "42", "43", "44", "45", "46", "47", "48", "49", "4A", "4B", "4C", "4D", "4F", "4G", "4M", "4P", "4R", "4S", "4T",
        "4V", "4W", "4X", "4Z", "52", "53", "54", "55", "56", "57", "58", "59", "5A", "5B", "5C", "5D", "5F", "5G", "5M", "5P", "5R", "5S",
        "5T", "5V", "5W", "5X", "5Z", "62", "63", "64", "65", "66", "67", "68", "69", "6A", "6B", "6C", "6D", "6F", "6G", "6M", "6P", "6R",
        "6S", "6T", "6V", "6W", "6X", "6Z", "72", "73", "74", "75", "76", "77", "78", "79", "7A", "7B", "7C", "7D", "7F", "7G", "7M", "7P",
        "7R", "7S", "7T", "7V", "7W", "7X", "7Z", "82", "83", "84", "85", "86", "87", "88", "89", "8A", "8B", "8C", "8D", "8F", "8G", "8M",
        "8P", "8R", "8S", "8T", "8V", "8W", "8X", "8Z", "92", "93", "94", "95", "96", "97", "98", "99", "9A", "9B", "9C", "9D", "9F", "9G",
        "9M", "9P", "9R", "9S", "9T", "9V", "9W", "9X", "9Z", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "CA", "CB", "CC", "CD",
        "CE", "CF", "CG", "CH", "CI", "CJ", "CK", "CL", "CM", "CN", "CO", "CP", "CQ", "CR", "CS", "CT", "CU", "CV", "CW", "CX", "CY", "CZ",
        "FA", "FB", "FC", "FD", "FE", "FF", "FG", "FL", "FM", "FN", "FP", "FQ", "FR", "FU", "FV", "FW", "FX", "FZ", "HA", "HB", "HC", "HD",
        "HE", "HF", "HG", "HH", "HI", "HJ", "HK", "HL", "HM", "HN", "HO", "HP", "HQ", "HR", "HS", "HT", "HU", "HV", "HW", "HX", "HY", "HZ",
        "MA", "MC", "MH", "MK", "MS", "MT", "MW", "P1", "P2", "P3", "PA", "PB", "PC", "PD", "PE", "PF", "PG", "PH", "PI", "PJ", "PK", "PL",
        "PM", "PN", "PO", "PP", "PQ", "PR", "PS", "PT", "PU", "PV", "PW", "PX", "PY", "PZ", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9",
        "RA", "RB", "RC", "RD", "RF", "RG", "RM", "RP", "RR", "RS", "RT", "RV", "RW", "RX", "RZ", "ZZ"))

    EXTREMUM_CODES = set((
        #
        # May be modified by SHEFPARM file
        #
        'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'P', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z'))

    PROBABILITY_CODES = {
        #
        # May be modified by SHEFPARM file
        #
        # ABS of numeric values are probability of non-exceedence. Not sure why M and Z have negative values
        #
        'A' :  .002, 'B' :  .004, 'C' :   .01, 'D' :   .02, 'E' :   .04, 'F' :   .05,
        '1' :    .1, '2' :    .2, 'G' :   .25, '3' :    .3, '4' :    .4, '5' :    .5,
        '6' :    .6, '7' :    .7, 'H' :   .75, '8' :    .8, '9' :    .9, 'T' :   .95,
        'U' :   .96, 'V' :   .98, 'W' :   .99, 'X' :  .996, 'Y' :  .998, 'J' : .0013,
        'K' : .0228, 'L' : .1587, 'M' :  -0.5, 'N' : .8413, 'P' : .9772, 'Q' : .9987,
        'Z' :  -1.0}

    QUALIFIER_CODES = set((
        #
        # May be modified by SHEFPARM file
        #
        'B', 'D', 'E', 'F', 'G', 'L', 'M', 'N', 'P', 'Q', 'R', 'S', 'T', 'V', 'W', 'Z'))

    DEFAULT_DURATION_CODES = {
        #
        # May not be modified by SHEFPARM file
        #
        # Default durations for PE codes that have default durations other than I
        #
        "AT" : 'D', "AU" : 'D', "AW" : 'D', "EA" : 'D', "EM" : 'D',
        "EP" : 'D', "ER" : 'D', "ET" : 'D', "EV" : 'D', "LC" : 'D',
        "PP" : 'D', "PR" : 'D', "QC" : 'D', "QV" : 'D', "RI" : 'D',
        "RP" : 'D', "RT" : 'D', "SF" : 'D', "TC" : 'S', "TF" : 'S',
        "TH" : 'S', "UC" : 'D', "UL" : 'D', "XG" : 'J', "XP" : 'Q'}

    DURATION_VARIABLE_CODES = {
        #
        # May not be modified by SHEFPARM file
        #
        # Base numeric duration values for durtions specified with DVnxx
        #
        'S' : 7000, 'N' :    0, 'H' : 1000, 'D' : 2000, 'M' : 3000, 'Y' : 4000}

    TZ_NAMES = {
        #
        # May not be modified by SHEFPARM file
        #
        "J"  : "CTT",                              # China

        "HS" : "US/Hawaii",                        # Hawaiian standard
        "HD" : "US/Hawaii",                        # Hawaiian daylight
        "H"  : "US/Hawaii",                        # Hawaiian local

        "BS" : "Etc/GMT+11",                       # Bering standard       (obsolete, Aleutian Islands now use US/Alaska)
        "BD" : "Etc/GMT+10",                       # Bering daylight       (obsolete, Aleutian Islands now use US/Alaska)
        "B"  : "Pacific/Midway",                   # Bering local          (obsolete, Aleutian Islands now use US/Alaska)

        "LS" : "Etc/GMT+9",                        # Alaskan standard
        "LD" : "Etc/GMT+8",                        # Alaskan daylight
        "L"  : "US/Alaska",                        # Alaskan local

        "YS" : "Etc/GMT+8",                        # Yukon standard        (--strict gives bad times always)
        "YD" : "Etc/GMT+7",                        # Yukon daylight        (--strict gives bad times always)
        "Y"  : "Canada/Yukon",                     # Yukon local           (--strict gives bad times always)

        "PS" : "Etc/GMT+8",                        # Pacific standard
        "PD" : "Etc/GMT+7",                        # Pacific daylight
        "P"  : "US/Pacific",                       # Pacific local

        "MS" : "Etc/GMT+7",                        # Mountain standard
        "MD" : "Etc/GMT+6",                        # Mountain daylight
        "M"  : "US/Mountain",                      # Mountain local

        "CS" : "Etc/GMT+6",                        # Central standard
        "CD" : "Etc/GMT+5",                        # Central daylight
        "C"  : "US/Central",                       # Central

        "ES" : "Etc/GMT+5",                        # Eastern standard
        "ED" : "Etc/GMT+4",                        # Eastern daylight
        "E"  : "US/Eastern",                       # Eastern local

        "AS" : "Etc/GMT+4",                        # Atlantic standard
        "AD" : "Etc/GMT+3",                        # Atlantic daylight
        "A"  : "Canada/Atlantic",                  # Atlantic local

        "NS" : "timedelta(hours=-3, minutes=-30)", # Newfoundland standard
        "ND" : "timedelta(hours=-2, minutes=-30)", # Newfoundland daylight (--strict gives bad times always)
        "N"  : "Canada/Newfoundland",              # Newfoundland local    (--strict gives bad times in summer)

        "Z"  : "UTC"}                              # Zulu

    UTC = ZoneInfo("UTC")

    class ParameterControl :
        '''
        Holds .B parameter control info
        '''
        def __init__(
                self,
                parser:         'ShefParser',
                parameter_code: str,
                obstime:        Dt24,
                relativetime:   Union[timedelta, MonthsDelta],
                createtime:     Dt24,
                units:          str,
                qualifier:      str,
                duration_unit:  str,
                duration_value: int) :

            if not parameter_code or len(parameter_code) != 7 :
                raise ShefParserException(f"Invalid parameter code: {parameter_code}")

            if not obstime :
                raise ShefParserException("Missing observation time")

            self._parser         = parser
            self._parameter_code = parameter_code
            self._obstime        = Dt24.clone(obstime)
            self._relativetime   = Dt24.clone(relativetime) if relativetime else None
            self._createtime     = Dt24.clone(createtime) if createtime else None
            self._units          = units
            self._qualifier      = qualifier
            self._duration_unit  = duration_unit
            self._duration_value = duration_value

        @property
        def qualifier(self) :
            return self._qualifier

        @property
        def pe_code(self) :
            return self._parameter_code[:2]
        @property

        def obstime(self) :
            return self._obstime

        @property
        def units(self) :
            return self._units

        @property
        def obstime(self) :
            return self._obstime

        @property
        def obstime(self) :
            return self._obstime

        @property
        def relativetime(self) :
            return self._relativetime

        def get_output_record(
                self:           'ParameterControl',
                shefParser:     'ShefParser',
                revised:        bool,
                msg_source:     str,
                location:       str,
                time_override:  Dt24,
                value:          float,
                qualifier:      str,
                comment:        str) -> 'OutputRecord' :

            t = time_override if time_override else self.obstime
            if self.relativetime : t.clone() + self.relativetime
            return OutputRecord(
                location,
                self._parameter_code,
                t.astimezone("Z" if parser.strict else ShefParser.UTC),
                self._createtime.astimezone("Z" if parser.strict else ShefParser.UTC) if self._createtime else None,
                value if self._units == "EN" else value * shefParser._pe_conversions[self._parameter_code[:2]],
                qulifier if qualifier else self.qualifier,
                revised,
                self._duration_unit,
                self._duration_value,
                msg_source,
                0,
                comment)

        def __repr__(self) :
            if self._relativetime :
                return f'{self._parameter_code} @ {self._obstime.astimezone("Z" if parser.strict else ShefParser.UTC)} ({self._relativetime})'
            else :
                return f'{self._parameter_code} @ {self._obstime.astimezone("Z" if parser.strict else ShefParser.UTC)}'


    def __init__(self, output_format, shefparm_pathname=None, strict=False) :
        '''
        Constructor
        '''
        self._shefparm_pathname = shefparm_pathname
        self._output_format     = output_format
        self._strict            = strict
        #-----------------------------#
        # initialize program defaults #
        #-----------------------------#
        self._pe_conversions             = copy.deepcopy(ShefParser.PE_CONVERSIONS)
        self._send_codes                 = copy.deepcopy(ShefParser.SEND_CODES)
        self._duration_codes             = copy.deepcopy(ShefParser.DURATION_CODES)
        self._ts_codes                   = copy.deepcopy(ShefParser.TS_CODES)
        self._extremum_codes             = copy.deepcopy(ShefParser.EXTREMUM_CODES)
        self._probability_codes          = copy.deepcopy(ShefParser.PROBABILITY_CODES)
        self._qualifier_codes            = copy.deepcopy(ShefParser.QUALIFIER_CODES)
        self._max_error_count            = 1500 # May be modified by SHEFPARM file
        self._error_count                = 0
        self._default_duration_code      = 'I' # May not be modified by SHEFPARM file
        self._default_type_code          = 'R' # May not be modified by SHEFPARM file
        self._default_source_code        = 'Z' # May not be modified by SHEFPARM file
        self._default_extremum_code      = 'Z' # May not be modified by SHEFPARM file
        self._default_probability_code   = 'Z' # May not be modified by SHEFPARM file
        self._input                      = None
        self._output                     = None
        self._input_lines                = None
        self._msg_start_pattern          = re.compile(r"^\.[ABE]R?\s", re.I)
        self._msg_continue_patterns      = {'A' : (re.compile(r"^\.A\d", re.I), re.compile(r"^\.AR?\d", re.I)),
                                            'E' : (re.compile(r"^\.E\d", re.I), re.compile(r"^\.ER?\d", re.I)),
                                            'B' : (re.compile(r"^\.B\d", re.I), re.compile(r"^\.BR?\d", re.I))}
        self._input_name                 = None
        self._line_number                = 0
        self._positional_fields_pattern   = re.compile(
                                           # 1 = location id
                                           # 2 = date-time
                                           # 6 = time zone
                                           #                 1           23       4
                                              r"^\.[AEB]R?\s+(\w{3,8})\s+((\d{2})?(\d{2})?\d{4})" \
                                           #    5   6
                                              r"(\s+([NAECMPYLHB][DS]?|[JZ])\s{1,15})?", re.I|re.M)
        self._dot_b_header_lines_pattern = re.compile(r"^.B(R?)\s.+?$(\n^.B\1?\d\s.+?$)*", re.I|re.M)
        self._dot_b_body_line_pattern    = re.compile(r"^(\w{3,8})\s+\S+.*$")
        self._obs_time_pattern           = re.compile(
                                           # 1 = date/time
                                           # 2 = date/time code
                                           # 3 = date/time value
                                           #    12                           3
                                              r"(D[SNHDMYJ]|DR[SNHDMYE][+-]?)(\d+)", re.I)
        self._multiple_obs_time_pattern  = re.compile(
                                           # 1 = first date/time
                                           # 2 = first date/time code
                                           # 3 = first date/time value
                                           # 4 = next data
                                           # 5 = separator
                                           # 6 = next date/time code
                                           # 7 = next date/time value
                                           #    12                            3     45      6                           7
                                              r"((D[SNHDMYJ]|DR[SNHDMYE][+-]?)(\d+))((\s+|/)(D[SNHDMYJ]|DR[SNHDMYE][+-])(\d+))+", re.I)
        self._obs_time_pattern2          = re.compile(
                                           # 1 = first date/time
                                           # 2 = first date/time code
                                           # 3 = first date/time value
                                           # 4 = next data
                                           # 5 = next date/time code
                                           # 6 = next date/time value
                                           #    12                            3     4 5                           6
                                              r"((D[SNHDMYJ]|DR[SNHDMYE][+-]?)(\d+))(@(D[SNHDMYJ]|DR[SNHDMYE][+-])(\d+))*", re.I)
        self._create_time_pattern        = re.compile(r"DC\d+", re.I)
        self._unit_system_pattern        = re.compile(r"DU[ES]", re.I)
        self._data_qualifier_pattern     = re.compile(r"DQ.", re.I)
        self._duration_code_pattern      = re.compile(r"(DV[SNHDMY]\d{2}|DVZ)", re.I)
        self._parameter_code_pattern     = re.compile(r"^[A-Z]{2}([A-Z]([A-Z0-9]{2}[A-Z]{,2})?)?$", re.I)
        self._interval_pattern           = re.compile(r"DI[SNHDMEY][+-]?\d{1,2}", re.I)
        self._value_pattern              = re.compile(
                                          # 1 = sign
                                          # 2 = numeric value
                                          # 4 = trace value
                                          # 5 = missing valule
                                          # 6 = value qualifier
                                          #     1      2   3               4   5   6
                                              r"([+-]?)(\d+(\.\d*)?|\.\d+)|(T)|(M+)([A-Z]?)", re.I)

        if self._shefparm_pathname :
            self.read_shefparm(self._shefparm_pathname)

    @property
    def strict(self) :
        return self._strict

    def read_shefparm(self, shefparm_pathname) :
        '''
        modify program defaults with content of SHEFPARM file
        '''

        # SHEFPARM Section Marker Lines
        #
        # *1                      PE CODES AND CONVERSION FACTORS
        # *2                      DURATION CODES AND ASSOCIATED VALUES
        # *3                      TS CODES
        # *4                      EXTREMUM CODES
        # *5                      PROBILITY CODES AND ASSOCIATED VALUES
        # *6                      SEND CODES OR DURATION DEFAULTS OTHER THAN I
        # *7                      DATA QUALIFIER CODES
        # **                      MAX NUMBER OF ERRORS (I4 FORMAT)
        section_info = {
            '1' : {"name" : "PE CODES",             "func" : self.set_pe_code,          "visited" : False},
            '2' : {"name" : "DURATION CODES",       "func" : self.set_duration_code,    "visited" : False},
            '3' : {"name" : "TS CODES",             "func" : self.set_ts_code,          "visited" : False},
            '4' : {"name" : "EXTREMUM CODES",       "func" : self.set_extremum_code,    "visited" : False},
            '5' : {"name" : "PROBABILITY CODES",    "func" : self.set_probability_code, "visited" : False},
            '6' : {"name" : "SEND CODES",           "func" : self.set_send_code,        "visited" : False},
            '7' : {"name" : "DATA QUALIFIER CODES", "func" : self.set_qualifier_code,   "visited" : False},
            '*' : {"name" : "MAX ERROR COUNT",      "func" : self.set_max_error_count,  "visited" : False}}
        section = None
        p = Path(shefparm_pathname)
        if not p.exists() or p.is_dir() :
            self.error(f"No such file: {shefparm_pathname}", abort=True)
        #------------------------#
        # read and process lines #
        #------------------------#
        with p.open() as f : lines = f.read().strip().split("\n")
        for i in range(len(lines)) :
            line = lines[i]
            if not line or line[0] == '$' or line.upper().startswith("SHEFPARM") :
                #-------------#
                # ignore line #
                #-------------#
                continue
            if line[0] == '*' :
                #---------------------#
                # section marker line #
                #---------------------#
                try    : section = line[1]
                except : self.error(f"{shefparm_pathname}: Invalid line at line {i+1}: {line}", abort=True)
                if section not in section_info :
                    self.error(f'{shefparm_pathname}: Unexpected section "{section}" at line {i+1}', abort=True)
            else :
                #--------------------------------------#
                # process line for appropriate section #
                #--------------------------------------#
                section_info[section]["func"](line)
                section_info[section]["visited"] = True
        #------------------------------------#
        # output info about missing sections #
        #------------------------------------#
        for section in sorted(section_info) :
            if not section_info[section]["visited"] :
                logger.info(f'{shefparm_pathname} does not contain section {section} ({section_info[section]["name"]})')

    def set_pe_code(self, line) :
        '''
        Update PE codes from SHEFPARM line
        '''
        key, value = line[0:2], float(line[3:23].strip())
        if key not in self._pe_conversions :
            if key  not in self._send_codes :
                logger.info(f"{self._shefparm_pathname}: Adding non-standard physical element code {key} with conversion factor {value}")
        else:
            if 0.9999 <= value / self._pe_conversions[key] <= 1.001 :
                pass
            else :
                logger.warning(f"{self._shefparm_pathname}: Updating standard physical element code {key} conversion factor from {self._pe_conversions[key]} to {value}")
        self._pe_conversions[key] = value

    def set_duration_code(self, line) :
        '''
        Update Duration codes from SHEFPARM line
        '''
        key, value = line[0], line[3:8].strip()
        if key not in self._duration_codes :
            logger.info(f"{self._shefparm_pathname}: Adding non-standard duration code {key} with numerical value {value}")
        elif value != self._duration_codes[key] :
            logger.warning(f"{self._shefparm_pathname}: Updating standard duration code {key} numerical value from {self._duration_codes[key]} to {value}")
        self._duration_codes[key] = value

    def set_ts_code(self, line) :
        '''
        Update TS codes from SHEFPARM line
        '''
        key, value = line[0:2], int(line[3:5].strip()) if len(line) > 3 else 0
        if value :
            if key not in self._ts_codes :
                logger.info(f"{self._shefparm_pathname}: Adding non-standard type-and-source code {key}")
                self._ts_codes.add(key)
        else :
            if key in self._ts_codes :
                logger.warning(f"{self._shefparm_pathname}: Disabling standard type-and-source code {key}")
                self._ts_codes.remove(key)

    def set_extremum_code(self, line) :
        '''
        Update Extremum codes from SHEFPARM line
        '''
        key, value = line[0:1], int(line[3:5].strip()) if len(line) > 3 else 0
        if value :
            if key not in self._extremum_codes :
                logger.info(f"{self._shefparm_pathname}: Adding non-standard extremum code {key}")
                self._extremum_codes.add(key)
        else :
            if key in self._extremum_codes :
                logger.warning(f"{self._shefparm_pathname}: Disabling standard extremum code {key}")
                self._extremum_codes.remove(key)

    def set_probability_code(self, line) :
        '''
        Update Probability codes from SHEFPARM line
        '''
        key, value = line[0], float(line[2:22].strip())
        if key not in self._probability_codes :
            logger.info(f"{self._shefparm_pathname}: Adding non-standard probability code {key} with conversion factor {value}")
        elif value != self._probability_codes[key] :
            logger.warning(f"{self._shefparm_pathname}: Updating standard probability code {key} conversion factor from {self._probability_codes[key]} to {value}")
        self._probability_codes[key] = value

    def set_send_code(self, line) :
        '''
        Update Send codes from SHEFPARM line
        '''
        use_prev_7am = len(line) > 12 and line[12] == '1'
        key, value = line[0:2], (line[3:10], len(line) > 12 and line[12] == '1')
        if key not in self._send_codes :
            logger.info(f"{self._shefparm_pathname}: Adding non-standard send code {key} with parmameter {value[0]} and use-prev-0700 = {value[1]}")
        elif value != self._send_codes[key] :
            cur_val = self._send_codes[key]
            logger.warning(
                f"{self._shefparm_pathname}: Updating standard send code {key} from parmameter {cur_val[0]} and use-prev-0700 = {cur_val[1]} " \
                    f"to parmameter {value[0]} and use-prev-0700 = {value[1]}")
        self._send_codes[key] = value

    def set_qualifier_code(self, line) :
        '''
        Update Data qualifiers from SHEFPARM line
        '''
        key = line[0]
        if key not in self._qualifier_codes :
            logger.info(f"{self._shefparm_pathname}: Adding non-standard data qualifier code {key}")

    def set_max_error_count(self, line) :
        '''
        Update Max error count from SHEFPARM line
        '''
        value = int(line[:4].replace(' ', ''))
        if value != self._max_error_count :
            logger.info(f"{self._shefparm_pathname}: Maximum error count set to {self._max_error_count}")
        self._max_error_count = value

    def error(self, message, abort=False) :
        '''
        Log and track errors. Abort if max errors exceeded.
        '''
        raise Exception(message)
        logger.error(message)
        if abort :
            raise ShefParserException(message)
        self._error_count += 1
        if self._error_count > self._max_error_count :
            msg = f"Maximum number of errors ({self._max_error_count}) exceeded - aborting"
            logger.error(msg)
            raise ShefParserException(msg)

    def get_parameter_code(self, partial_parameter_code) :
        '''
        Generate a complete parameter code from a partial parameter code and defaults
        '''
        value_at_prev_0700 = False
        try :
            code, value_at_prev_0700 = self._send_codes[partial_parameter_code]
        except KeyError :
            code = partial_parameter_code
        length = len(code)
        if length == 2 :
            try :
                code += ShefParser.DEFAULT_DURATION_CODES[code]
            except KeyError :
                code += self._default_duration_code
            code += self._default_type_code + self._default_source_code + self._default_extremum_code + self._default_probability_code
        elif length == 3 :
            code += self._default_type_code + self._default_source_code + self._default_extremum_code + self._default_probability_code
        elif length == 4 :
            code += self._default_source_code + self._default_extremum_code + self._default_probability_code
        elif length == 5 :
            code += self._default_extremum_code + self._default_probability_code
        elif length == 6 :
            code += self._default_probability_code
        return code, value_at_prev_0700

    def close_input(self) :
        '''
        Close and detach the message input device
        '''
        if self._input :
            if not self._input.isatty() :
                self._input.close()
            self._input = None
        else :
            logger.info("Input is already closed or was never set")

    def set_input(self, input_object) :
        '''
        Attach the message input device, opening if necessary
        '''
        if self._input :
            self.close_input()
        if input_object.__class__.__name__ == "TextIOWrapper" :
            self._input = input_object
        else :
            self._input = open(input_object)

        self._input_lines = deque()
        self._line_number = 0
        self._input_name = self._input.name
        logger.debug(f"Message input set to {self._input_name}")

    def close_output(self) :
        '''
        Close and detach the data output device
        '''
        if self._output :
            if not self._output.isatty() :
                self._output.close()
            self._output = None
        else :
            logger.debug("Output is already closed or was never set")

    def set_output(self, output_object) :
        '''
        Attach the data output device, opening if necessary
        '''
        if self._output :
            self.close_output()
        if output_object.__class__.__name__ == "TextIOWrapper" :
            self._output = output_object
        else :
            self._output = open(output_object, "wb")
        self._output_name = self._output.name
        logger.debug(f"Data output set to {self._output_name}")

    def output(self, outrec : OutputRecord) :
        if not self._output :
            raise ShefParserException("Cannot output record; output is closed or never opened")
        outstr = f"{outrec.format(self._output_format)}\n"
        outdev_type = self._output.__class__.__name__
        if outdev_type == "TextIOWrapper" :
            self._output.write(outstr)
        elif outdev_type == "BufferedWriter" :
            self._output.write(outstr.encode("utf-8"))
        else :
            raise ShefParserException(f"Unexpected output device type: {outdev_type}")

    def remove_comment_fields(self, line) :
        '''
        Remove colon-delimited comments from a message line
        '''
        in_comment_field = False
        chars = []
        for c in line :
            if c == ':' :
                in_comment_field = not in_comment_field
            elif not in_comment_field :
                chars.append(c)
        message_line = "".join(chars)
        return message_line

    def get_next_message(self) :
        '''
        Retrieve the next complete message from the message input device
        '''
        message_lines = deque()
        message_type = ''
        revised = False
        in_header = False
        while True :
            while self._input_lines :
                line = self._input_lines.popleft()
                message_line = self.remove_comment_fields(line)
                self._line_number += 1
                if not message_type :
                    #-----------------------------------#
                    # looking for first line of message #
                    #-----------------------------------#
                    if not message_line or message_line[0] != '.' :  continue
                    if not self._msg_start_pattern.search(message_line) :
                        self.error(f"Invalid line: ({self._input_name}:{self._line_number}) {line}")
                        continue
                    message_type = message_line[1]
                    revised = message_line[2] == 'R'
                    message_lines.append(message_line)
                    in_header = message_type == 'B'
                else :
                    #----------------------------#
                    # looking for end of message #
                    #----------------------------#
                    if message_type == 'B' :
                        message_lines.append(message_line)
                        if message_line and message_line[0] == '.' :
                            if in_header and self._msg_continue_patterns[message_type][int(revised)].search(message_line) :
                                continue
                            if not message_line.startswith(".END") :
                                self._line_number -= 1
                                if self._msg_continue_patterns[message_type][int(revised)].search(message_line) :
                                    self.error(f".B message starting at {self._input_name}:{self._line_number-len(message_lines)+2} has data between header lines")
                                else :
                                    self.error(f".B message starting at {self._input_name}:{self._line_number-len(message_lines)+2} not finished before next message")
                                self._input_lines.appendleft(message_lines.pop())
                            in_header = False
                            message_type = ''
                            break
                        else :
                            in_header = False
                    else :
                        if self._msg_continue_patterns[message_type][int(revised)].search(message_line) :
                            message_lines.append(message_line)
                        else :
                            self._line_number -= 1
                            self._input_lines.appendleft(line)
                            message_type = ''
                            break
            if message_lines and not message_type :
                #-------------------#
                # done with message #
                #-------------------#
                break
            elif not self._input :
                break
            else :
                #----------------#
                # read more data #
                #----------------#
                if message_type == 'B' and not self._input :
                    error(f".B message starting at {self._input_name}:{self._line_number-len(message_lines)} not complete before input exhausted")
                    break
                for i in range(100) :
                    try :
                        line = self._input.readline()
                    except Exception as e:
                        self.error(f"Error reading line {self._input_name}:{self._line_number-len(message_lines)}")
                        continue
                    if line :
                        if line[-1] == '\n' :
                            self._input_lines.append(line[:-1])
                        else :
                            self._input_lines.append(line)
                            self.close_input()
                            break
                    else :
                        self.close_input()
                        break
        start_line = self._line_number-len(message_lines)+1
        return (f"{self._input_name}:{start_line}", "\n".join(message_lines))

    def parse_header_date(self, datestr_ : str) :
        '''
        Parses the header date/time into a Dt24 object
        '''
        cur_time = Dt24.now()
        length = len(datestr_)
        if length == 4 : # mmdd
            datestr = str(cur_time.year) + datestr_
        elif length == 6 : # yymmdd
            datestr = str(cur_time.year)[:2] + datestr_
            yr = int(datestr[:4])
            if yr - int(cur_time.year) > 10 :
                datestr = f"{yr-100:04d}{datestr[4:]}"
        elif length == 8 : # ccyymmdd
            datestr = datestr_
        else :
            raise ShefParserException(f"Bad date string: {datestr}")
        try :
            dateval = Dt24(int(datestr[:4]), int(datestr[4:6]), int(datestr[6:]), tzinfo="Z" if self.strict else ShefParser.UTC)
            if length == 4 :
                # no year specified, use closeset date
                prev_year = dateval - MonthsDelta(12)
                if (cur_time - prev_year) < (dateval - cur_time) :
                    dateval = prev_year
            return dateval
        except :
            raise
            raise ShefParserException(f"Bad date string: {datestr}")

    def crack_a_e_data_string(self, datastr: str, message_type: str, is_revised: bool) :
        '''
        Convert a .A(R) or .E(R) data string into tokens

            datastr      = SHEF message with header (positional fields) removed
            message_type = 'A' or 'E'
            is_revised   = True or False
        '''
        #-----------------------#
        # parse the data string #
        #-----------------------#
        #------------------------------------------------------------------------------------------#
        # change any '/' characters in observation time(s) to '@' to prevent tokenization problems #
        #------------------------------------------------------------------------------------------#
        while self._multiple_obs_time_pattern.search(datastr) :
            datastr = self._multiple_obs_time_pattern.sub(r"\1@\6\7", datastr)
        #------------------------#
        # parse individual lines #
        #------------------------#
        lines = datastr.strip().split('\n')
        prev = 0
        for i in range(len(lines)) :
            #----------------------------------------------------------------------------#
            # remove continuation headers and handle implicit '/' across line boundaries #
            #----------------------------------------------------------------------------#
            lines[i] = self._msg_continue_patterns[message_type][int(is_revised)].sub("", lines[i]).strip()
            if not lines[i] :
                continue
            if i > 0 :
                if lines[prev][-1] != '/' and lines[i][0] != '/' :
                    lines[i] = "/" + lines[i]
            prev = i
            #--------------------------------------------------------------------#
            # keep spaces in retained comments, replace with NULL char elsewhere #
            #--------------------------------------------------------------------#
            buf = io.StringIO()
            quote = ""
            space = False
            for c in lines[i] :
                if c in "'\"" :
                    quote = "" if c == quote else c
                    if quote and not space: buf.write(chr(0)) # ensure quotes are separated from other text
                    buf.write(c)
                    space = False
                else :
                    if c.isspace() :
                        if quote :
                            buf.write(c)
                        else :
                            if not space :
                                buf.write(chr(0))
                                space = True
                    else :
                        buf.write(c)
                        space = False
            #-------------------------------------------------------#
            # close quote on retained comments at the end of a line #
            #-------------------------------------------------------#
            if quote :
                buf.write(quote)
            lines[i] = buf.getvalue()
            buf.close()
        #------------------------------------------------------#
        # convert lines back into a single string and tokenize #
        #------------------------------------------------------#
        datastr = "".join(lines).strip('/')
        tokens = datastr.split("/")
        for i in range(len(tokens)) :
            tokens[i] = tokens[i].strip(chr(0)).split(chr(0))
        return tokens

    def get_observation_time(self, base_time: Dt24, token: str, dot_b: bool=False) :
        '''
        Return the observation time as updated by the token
        '''
        bt = obstime = base_time
        relativetime = None
        subtokens = token.strip("@").split("@")
        if len(subtokens) > 1 and subtokens[0][1] == 'J' :
            raise ShefParserException(f"Bad observation time: {subtokens[0]}/{subtokens[1]}")
        for subtoken in subtokens :
            try :
                cur_time = Dt24.now()
                v = subtoken[2:]
                length = len(v)
                if subtoken[1] == 'S' :
                    if length == 2 : # DSss
                        obstime = Dt24(bt.year, bt.month, bt.day, bt.hour, bt.minute, int(v[0:2]), tzinfo=bt.tzinfo)
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                elif subtoken[1] == 'N' :
                    if length == 4 : # DNnnss
                        obstime = Dt24(bt.year, bt.month, bt.day, bt.hour, int(v[0:2]), int(v[2:4]), tzinfo=bt.tzinfo)
                    elif length == 2 : # DNnn
                        obstime = Dt24(bt.year, bt.month, bt.day, bt.hour, int(v[0:2]), bt.second, tzinfo=bt.tzinfo)
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                        return None
                elif subtoken[1] == 'H' :
                    if length == 6 : # DHhhnnss
                        obstime = Dt24(bt.year, bt.month, bt.day, int(v[0:2]), int(v[2:4]), int(v[4:6]), tzinfo=bt.tzinfo)
                    elif length == 4 : # DHhhnn
                        obstime = Dt24(bt.year, bt.month, bt.day, int(v[0:2]), int(v[2:4]), bt.second, tzinfo=bt.tzinfo)
                    elif length == 2 : # DHhh
                        obstime = Dt24(bt.year, bt.month, bt.day, int(v[0:2]), bt.minute, bt.second, tzinfo=bt.tzinfo)
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                elif subtoken[1] == 'D' :
                    if length == 8 : # DDddhhnnss
                        obstime = Dt24(bt.year, bt.month, int(v[0:2]), int(v[2:4]), int(v[4:6]), int(v[6:8]), tzinfo=bt.tzinfo)
                    elif length == 6 : # DDddhhnn
                        obstime = Dt24(bt.year, bt.month, int(v[0:2]), int(v[2:4]), int(v[4:6]), bt.second, tzinfo=bt.tzinfo)
                    elif length == 4 : # DDddhh
                        obstime = Dt24(bt.year, bt.month, int(v[0:2]), int(v[2:4]), bt.hour, bt.second, tzinfo=bt.tzinfo)
                    elif length == 2 : # DDdd
                        obstime = Dt24(bt.year, bt.month, int(v[0:2]), bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo)
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                elif subtoken[1] == 'M' :
                    if length == 10 : # DMmmddhhnnss
                        obstime = Dt24(bt.year, int(v[0:2]), int(v[2:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), tzinfo=bt.tzinfo)
                    elif length == 8 : # DMmmddhhnn
                        obstime = Dt24(bt.year, int(v[0:2]), int(v[2:4]), int(v[4:6]), int(v[6:8]), bt.second, tzinfo=bt.tzinfo)
                    elif length == 6 : # DMmmddhh
                        obstime = Dt24(bt.year, int(v[0:2]), int(v[2:4]), int(v[4:6]), bt.minute, bt.second, tzinfo=bt.tzinfo)
                    elif length == 4 : # DMmmdd
                        obstime = Dt24(bt.year, int(v[0:2]), int(v[2:4]), bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo)
                    elif length == 2 : # DMmm
                        obstime = Dt24(bt.year, int(v[0:2]), bt.day, bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo)
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                elif subtoken[1] == 'Y' :
                    if length > 1 :
                        y = cur_time.year - cur_time.year % 100 + int(v[0:2])
                        if y - cur_time.year > 10 : y -= 100
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                        return
                    if length == 12 : # DYyymmddhhnnss
                        obstime = Dt24(y, int(v[2:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), int(v[10:12]), tzinfo=bt.tzinfo)
                    elif length == 10 : # DYyymmddhhnn - set date and time
                        obstime = Dt24(y, int(v[2:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), bt.second, tzinfo=bt.tzinfo)
                    elif length == 8 : # DYyymmddhh
                        obstime = Dt24(y, int(v[2:4]), int(v[4:6]), int(v[6:8]), bt.minute, bt.second, tzinfo=bt.tzinfo)
                    elif length == 6 : # DYyymmdd
                        obstime = Dt24(y, int(v[2:4]), int(v[4:6]), bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo)
                    elif length == 4 : # DYyymm
                        obstime = Dt24(y, int(v[2:4]), bt.day, bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo)
                    elif length == 2 : # DYyy
                        obstime = Dt24(y, bt.month, bt.day, bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo)
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                elif subtoken[1] == 'T' :
                    if length == 14 : #DTccyymmddhhnnss
                        obstime = Dt24(int(v[0:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), int(v[10:12]), int(v[12:14]), tzinfo=bt.tzinfo)
                    elif length == 12 : #DTccyymmddhhnn
                        obstime = Dt24(int(v[0:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), int(v[10:12]), bt.second, tzinfo=bt.tzinfo)
                    elif length == 10 : #DTccyymmddhh
                        obstime = Dt24(int(v[0:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), bt.minute, bt.second, tzinfo=bt.tzinfo)
                    elif length == 8 : #DTccyymmdd
                        obstime = Dt24(int(v[0:4]), int(v[4:6]), int(v[6:8]), bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo)
                    elif length == 6 : #DTccyymm
                        obstime = Dt24(int(v[0:4]), int(v[4:6]), bt.day, bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo)
                    elif length == 4 : #DTccyy
                        obstime = Dt24(int(v[0:4]), bt.month, bt.day, bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo)
                    elif length == 2 : #DTcc
                        obstime = Dt24(100*int(v[0:2])+bt.year%100, bt.month, bt.day, bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo)
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                elif subtoken[1] == 'J' :
                    if length == 7 : # DJccyyddd
                        obstime = Dt24(int(bt[0:4]), 1, 1, bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo) + timedelta(days=int(v[4:7])-1)
                    elif length == 5 : # DJyyddd
                        y = cur_time.year - cur_time.year % 100 + int(v[0:2])
                        if y - cur_time.year > 10 : y -= 100
                        obstime = Dt24(y, 1, 1, bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo) + timedelta(days=int(v[2:5])-1)
                    elif length == 3 : # DJddd
                        obstime = Dt24(bt.year, 1, 1, bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo) + timedelta(days=int(v[0:3])-1)
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                elif subtoken[1] == 'R' :
                    # for .B messages the relative times are kept in the parameter control objects
                    v = subtoken[3:]
                    if subtoken[2] == 'S' :
                        if dot_b :
                            relativetime = timedelta(seconds=int(v))
                        else :
                            obstime = bt + timedelta(seconds=int(v))
                    elif subtoken[2] == 'N' :
                        if dot_b :
                            relativetime = timedelta(minutes=int(v))
                        else :
                            obstime = bt + timedelta(minutes=int(v))
                    elif subtoken[2] == 'H' :
                        if dot_b :
                            relativetime = timedelta(hours=int(v))
                        else :
                            obstime = bt + timedelta(hours=int(v))
                    elif subtoken[2] == 'D' :
                        if dot_b :
                            relativetime = timedelta(days=int(v))
                        else :
                            obstime = bt + timedelta(days=int(v))
                    elif subtoken[2] == 'M' :
                        if dot_b :
                            relativetime = MonthsDelta(int(v))
                        else :
                            obstime = bt + MonthsDelta(int(v))
                    elif subtoken[2] == 'E' :
                        if dot_b :
                            relativetime = MonthsDelta(int(v), eom=True)
                        else :
                            obstime = bt + MonthsDelta(int(v), eom=True)
                    elif subtoken[2] == 'Y' :
                        if dot_b :
                            relativetime = MonthsDelta(12*int(v))
                        else :
                            obstime = bt + MonthsDelta(12*int(v))
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
            except :
                raise ShefParserException(f"Bad observation time: {subtoken}")
        return obstime, relativetime

    def get_creation_time(self, zi: ZoneInfo, token: str) :
        '''
        Generate a createtion time from the token
        '''
        v = token[2:]
        length = len(token)
        cur_time = Dt24.now()
        try :
            if length == 12 :
                y, m, d, h, n = int(v[0:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), int(v[10:12])
            elif length == 10 :
                y = cur_time.year - cur_time.year % 100 + int(v[0:2])
                if y - cur_time.year > 10 : y -= 100
                m, d, h, n = int(v[2:4]), int(v[4:6]), int(v[6:8]), int(v[8:10])
            elif length == 8 :
                y, m, d, h, n = cur_time.year, int(v[0:2]), int(v[2:4]), int(v[4:6]), int(v[6:8])
            elif length == 6 :
                y, m, d, h, n = cur_time.year, int(v[0:2]), int(v[2:4]), int(v[4:6]), 0
            elif length == 4 :
                y, m, d, h, n = cur_time.year, int(v[0:2]), int(v[2:4]), 0, 0
            else :
                raise ShefParserException(f"Bad creation time: {token}")
                return None
            return Dt24(y, m, d, h, n, 0, tzinfo=zi)
        except :
            raise ShefParserException(f"Bad creation time: {token}")
            return None

    def parse_value_token(self, token: str, pe_code: str, units: str) :
        '''
        Returns the numeric value and data qualifier from a token
        '''
        m = self._value_pattern.match(token)
        if not m :
            raise ShefParserException(f"Invalid value: {token}")
        # groups
        # 1 = sign
        # 2 = numeric value
        # 3 = trace value
        # 4 = missing valule
        # 5 = qualifier
        matched_groups = "".join(map(lambda x : "T" if bool(x) else "F", [m.group(i) for i in (1,2,4,5)]))
        if matched_groups == "TFFF" :
            #-----------------------------------#
            # sign only - implicit missing data #
            #-----------------------------------#
            value = -9999.
        elif matched_groups in ("FTFF", "TTFF") :
            #------------------------------#
            # value (with or without sign) #
            #------------------------------#
            value = float(f"{m.group(1)}{m.group(2)}")
            if units == "EN" and pe_code in ("PC", "PP") and '.' not in m.group(2) :
                value /= 100
            if units == "SI" and value != -9999. :
                value *= self._pe_conversions[pe_code]
        elif matched_groups ==  "FFTF" :
            #---------------------------#
            # Precipitation trace value #
            #---------------------------#
            if pe_code not in ("PC", "PP") :
                raise ShefParserException(f"Value {m.group(4)} is not valid for pe_code {pe_code}")
            value + .001
        elif matched_groups == "FFFT" :
            #-----------------------#
            # explicit missing data #
            #-----------------------#
            value = -9999.
        else :
            #---------------------------------------#
            # invalid combination of matched groups #
            #---------------------------------------#
            raise ShefParserException(f"Invalid data value: {token})")
        qualifier = m.group(6)
        return value, qualifier

    def get_time_zone(self, name) :
        '''
        Create a time zone from the name
        '''
        if self.strict :
            return name
        else :
            text = ShefParser.TZ_NAMES[name]
            try :
                if text.startswith("timedelta") :
                    return timezone(eval(text))
                else :
                    return ZoneInfo(text)
            except :
                raise # ShefParserException(f"Cannot instantiate time zone {name}")

    def parse_dot_a_message(self, message: str) :
        '''
        Parses a .A or .AR message
        '''
        #-----------------------------#
        # parse the positional fields #
        #-----------------------------#
        revised   = None
        location  = None
        date_time = None
        time_zone = None
        length    = None
        m = self._positional_fields_pattern.search(message)
        if not m :
            raise ShefParserException(f"Mal-formed positional fields: {message}")
        #------------------------------#
        # process the positionl fields #
        #------------------------------#
        revised   = message[2].upper() == 'R'
        location  = m.group(1).upper()
        dateval   = self.parse_header_date(m.group(2).upper())
        time_zone = m.group(6).upper() if m.group(6) else 'Z'
        length    = m.end()
        zi = self.get_time_zone(time_zone)
        if not time_zone : time_zone = 'Z'
        zi      = self.get_time_zone(time_zone)
        dateval = Dt24(dateval.year, dateval.month, dateval.day, tzinfo=zi)
        datastr = message[length:].strip()
        tokens  = self.crack_a_e_data_string(datastr, 'A', revised)
        #-----------------------------#
        # set the default data values #
        #-----------------------------#
        if time_zone == 'Z' :
            obstime = Dt24(dateval.year, dateval.month, dateval.day, 12, 0, 0, tzinfo=zi)
        else :
            obstime = Dt24(dateval.year, dateval.month, dateval.day, 0, 0, 0, tzinfo=zi) - timedelta(days=1)
        obstime_defined   = False
        createtime        = None
        default_qualifier = 'Z'
        units             = "EN"
        duration_unit     = 'Z'
        duration_value    = None
        outrecs           = []
        #--------------------------------#
        # process the data string fields #
        #--------------------------------#
        for i in range(len(tokens)) :
            if len(tokens[i]) == 1 :
                token = tokens[i][0]
                if self._obs_time_pattern2.search(token) :
                    #------------------------------------------------#
                    # set the observation time for subsequent values #
                    #------------------------------------------------#
                    pos = 0
                    while True :
                        m = self._obs_time_pattern2.search(token[pos:])
                        if not m : break
                        if not obstime_defined :
                            obstime = Dt24(dateval.year, dateval.month, dateval.day, 0, 0, 0, tzinfo=zi)
                            obstime_defined = True
                        obstime, relativetime = self.get_observation_time(obstime, token.upper(), dot_b=False)
                        pos += m.end(1)+1
                    if token[pos:] :
                        self.error(f"Unexpected data string item: {token}")
                        return outrecs
                elif self._create_time_pattern.match(token) :
                    #---------------------------------------------#
                    # set the creation time for subsequent values #
                    #---------------------------------------------#
                    createtime = self.get_creation_time(zi, token.upper())
                elif self._unit_system_pattern.match(token) :
                    #-------------------------------------------#
                    # set the unit system for subsequent values #
                    #-------------------------------------------#
                    units = "EN" if token[2].upper() == 'E' else "SI"
                elif self._data_qualifier_pattern.match(token) :
                    #-------------------------------------------------#
                    # set the default qualifier for subsequent values #
                    #-------------------------------------------------#
                    default_qualifier = token[2].upper()
                    if default_qualifier not in self._qualifier_codes :
                        self.error(f"Bad data qualifier: {default_qualifier}")
                        return outrecs
                elif self._duration_code_pattern.match(token) :
                    #----------------------------------------------------------------#
                    # set the duration for subequent values with duration code = 'V' #
                    #----------------------------------------------------------------#
                    duration_unit = token[2].upper()
                    if duration_unit == 'Z' :
                        duration_value = None
                    else :
                        duration_value = int(token[3:])
                elif not token :
                    #----------------------------------#
                    # ignore NULL fields in .A message #
                    #----------------------------------#
                    pass
                else :
                    self.error(f"Unexpected data string item: {token}")
                    return outrecs
            else :
                #------------#
                # data value #
                #------------#
                code = tokens[i][0].upper()
                if len(code) < 2 or (code[:2] not in self._send_codes and code[:2] not in self._pe_conversions) :
                    self.error(f"Invalid PE code: {code[:min(2, len(code))]}")
                    continue
                try :
                    parameter_code, use_prev_7am = self.get_parameter_code(code)
                except ShefParserException as spe :
                    self.error(str(spe))
                    continue
                if use_prev_7am :
                    t = Dt24(obstime.year, obstime.month, obstime.day, obstime.hour, obstime.minute, obstime.second, tzinfo = obstime.tzinfo)
                    if t.hour < 7 : t -= timedelta(days=1)
                    obstime = Dt24(t.year, t.month, t.day, 7, 0, 0, t.tzinfo)
                if len(tokens[i]) == 1 :
                    continue # same as a NULL field - a parameter code with no value
                try :
                    value, qualifier = self.parse_value_token(tokens[i][1].upper(), parameter_code[:2], units)
                except ShefParserException as spe :
                    self.error(str(spe))
                    continue
                if not qualifier : qualifier = default_qualifier
                if qualifier not in self._qualifier_codes :
                    self.error(f"Invalid data qualifier: {qualifier}")
                    return outrecs
                comment = None
                if len(tokens[i]) > 2 :
                    comment = tokens[i][2]
                    if comment :
                        if comment[0] not in "'\"" :
                            self.error(f"Invalid retained comment {tokens[i][2]}")
                            return outrecs
                        comment = comment.strip("'").strip('"')

                outrecs.append(OutputRecord(
                    location,
                    parameter_code,
                    obstime.astimezone("Z" if self.strict else ShefParser.UTC),
                    createtime.astimezone("Z" if self.strict else ShefParser.UTC) if createtime else None,
                    value,
                    qualifier,
                    revised,
                    duration_unit,
                    duration_value,
                    comment = comment))
        return outrecs

    def parse_dot_e_message(self, message: str) :
        '''
        Parses a .E or .ER message
        '''
        #-----------------------------#
        # parse the positional fields #
        #-----------------------------#
        revised   = None
        location  = None
        date_time = None
        time_zone = None
        length    = None
        m = self._positional_fields_pattern.search(message)
        if not m :
            raise ShefParserException(f"Mal-formed positional fields: {message}")
        #-------------------------------#
        # process the positional fields #
        #-------------------------------#
        revised   = message[2].upper() == 'R'
        location  = m.group(1).upper()
        dateval   = self.parse_header_date(m.group(2).upper())
        time_zone = m.group(6).upper() if m.group(6) else 'Z'
        length    = m.end()
        if not time_zone : time_zone = 'Z'
        zi      = self.get_time_zone(time_zone)
        dateval = Dt24(dateval.year, dateval.month, dateval.day, tzinfo=zi)
        datastr = message[length:].strip()
        tokens  = self.crack_a_e_data_string(datastr, 'E', revised)
        #-----------------------------#
        # set the default data values #
        #-----------------------------#
        if time_zone == 'Z' :
            obstime = Dt24(dateval.year, dateval.month, dateval.day, 12, 0, 0, tzinfo=zi)
        else :
            obstime = Dt24(dateval.year, dateval.month, dateval.day, 0, 0, 0, tzinfo=zi) - timedelta(days=1)
        dateval = Dt24(dateval.year, dateval.month, dateval.day, tzinfo=zi)
        parameter_code    = None
        obstime_defined   = False
        createtime        = None
        interval          = None
        time_series_code  = 0
        default_qualifier = 'Z'
        units             = "EN"
        duration_unit     = 'Z'
        duration_value    = None
        outrecs           = []
        #--------------------------------#
        # process the data string fields #
        #--------------------------------#
        for i in range(len(tokens)) :
            if len(tokens[i]) > 1 : raise ShefParserException(f"Invalid data string")
            token = tokens[i][0]
            value = None
            comment = None
            if self._obs_time_pattern2.search(token) :
                #------------------------------------------------#
                # set the observation time for subsequent values #
                #------------------------------------------------#
                pos = 0
                while True :
                    m = self._obs_time_pattern2.search(token[pos:])
                    if not m : break
                    if not obstime_defined :
                        obstime = Dt24(dateval.year, dateval.month, dateval.day, 0, 0, 0, tzinfo=zi)
                        obstime_defined = True
                    obstime, relativetime = self.get_observation_time(obstime, token.upper(), dot_b=False)
                    pos += m.end(1)+1
                if token[pos:] :
                    self.error(f"Unexpected data string item: {token}")
                    return outrecs
                time_series_code = 1
            elif self._create_time_pattern.match(token) :
                #---------------------------------------------#
                # set the creation time for subsequent values #
                #---------------------------------------------#
                createtime = self.get_creation_time(zi, token.upper())
            elif self._unit_system_pattern.match(token) :
                #-------------------------------------------#
                # set the unit system for subsequent values #
                #-------------------------------------------#
                units = "EN" if token[2].upper() == 'E' else "SI"
            elif self._data_qualifier_pattern.match(token) :
                #-------------------------------------------------#
                # set the default qualifier for subsequent values #
                #-------------------------------------------------#
                default_qualifier = token[2].upper()
                if default_qualifier not in self._qualifier_codes :
                    self.error(f"Bad data qualifier: {default_qualifier}")
                    return outrecs
            elif self._duration_code_pattern.match(token) :
                #----------------------------------------------------------------#
                # set the duration for subequent values with duration code = 'V' #
                #----------------------------------------------------------------#
                duration_unit = token[2].upper()
                if duration_unit == 'Z' :
                    duration_value = None
                else :
                    duration_value = int(token[3:])
                time_series_code = 1
            elif self._interval_pattern.match(token) :
                #-----------------------------------------#
                # set the intrerval for subsequent values #
                #-----------------------------------------#
                if interval :
                    self.error("Interval specified more than once")
                    return outrecs
                time_series_code = 1
                interval_unit = token[2].upper()
                interval_value = int(token[3:])
                if interval_unit == 'S' :
                    interval = timedelta(seconds=interval_value)
                elif interval_unit == 'N' :
                    interval = timedelta(minutes=interval_value)
                elif interval_unit == 'H' :
                    interval = timedelta(hours=interval_value)
                elif interval_unit == 'D' :
                    interval = timedelta(days=interval_value)
                elif interval_unit == 'M' :
                    interval = MonthsDelta(interval_value)
                elif interval_unit == 'E' :
                    interval = MonthsDelta(interval_value, eom=True)
                elif interval_unit == 'Y' :
                    interval = {"months" : 12 * interval_value, "eom" : False}
            elif self._parameter_code_pattern.match(token) :
                #-------------------------------------------------#
                # set the parameter code for the susequent values #
                #-------------------------------------------------#
                if parameter_code :
                    self.error("Parameter code specified more than once")
                    return outrecs
                code = token.upper()
                if len(code) < 2 or (code[:2] not in self._send_codes and code[:2] not in self._pe_conversions) :
                    self.error(f"Invalid PE code: {code[:min(2, len(code))]}")
                    return outrecs
                parameter_code, use_prev_7am = self.get_parameter_code(code)
            elif self._value_pattern.match(token) :
                #------------#
                # data value #
                #------------#
                value, qualifier = self.parse_value_token(token.upper(), parameter_code[:2], units)
                if not qualifier : qualifier = default_qualifier
                if qualifier not in self._qualifier_codes :
                    self.error(f"Invalid data qualifier: {qualifier}")
                    return outrecs
                comment = None
                if len(tokens[i]) > 2 :
                    comment = tokens[i][2]
                    if comment :
                        if comment[0] not in "'\"" :
                            raise ShefParserException(f"Invalid retained comment {tokens[i][2]}")
                        comment = comment.strip("'").strip('"')
            elif not token :
                #------------------------------------#
                # missing value if in list of values #
                #------------------------------------#
                if not (parameter_code and interval) :
                    raise ShefParserException("Null field in data definition")
                obstime += interval
            elif token[0] in "\"'" :
                #------------------#
                # retained comment #
                #------------------#
                if not value :
                    raise ShefParserException("Comment encountered before value")
                comment = token.strip("'").strip('"')
            else :
                raise ShefParserException(f"Unexpected data string item: {token}")

            if value :
                if not parameter_code :
                    raise ShefParserException("Value encountered before parameter code")
                if not interval :
                    raise ShefParserException("Value encountered before interval")
                outrec = OutputRecord(
                    location,
                    parameter_code,
                    obstime.astimezone("Z" if self.strict else ShefParser.UTC),
                    createtime.astimezone("Z" if self.strict else ShefParser.UTC) if createtime else None,
                    value,
                    qualifier,
                    revised,
                    duration_unit,
                    duration_value,
                    time_series_code = time_series_code,
                    comment = comment)
                outrecs.append(outrec)
                time_series_code = 2
                obstime += interval
        return outrecs

    def parse_dot_b_message(self, message: str) :
        '''
        Parses a .B or .BR message
        '''
        #------------------------------------------------------------------------------------#
        # separate the header (positional fields and parameter control) from the data string #
        #------------------------------------------------------------------------------------#
        m = self._dot_b_header_lines_pattern.search(message)
        if not m :
            raise ShefParserException(f"Invalid .B message: {message}")
        lines = m.group(0).strip().split("\n")
        lines[0] = lines[0].strip()
        for i in range(1, len(lines)) :
            lines[i] = lines[i][len(lines[i].split()[0]):].strip()
            if lines[0][-1] != '/' and lines[i][0] != '/' : lines[0] += '/'
            lines[0] += lines[i]
        header = lines[0]
        body = "\n".join(message[m.end():].strip().split("\n")[:-1]).strip()
        #------------------------------------#
        # parse the header positional fields #
        #------------------------------------#
        revised    = None
        msg_source = None
        date_time  = None
        time_zone  = None
        length     = None
        m = self._positional_fields_pattern.search(message)
        if not m :
            raise ShefParserException(f"Mal-formed positional fields: {message}")
        #--------------------------------------#
        # process the header positional fields #
        #--------------------------------------#
        revised    = message[2].upper() == 'R'
        msg_source = m.group(1).upper()
        dateval    = self.parse_header_date(m.group(2).upper())
        time_zone  = m.group(6).upper() if m.group(6) else 'Z'
        length     = m.end()
        if not time_zone : time_zone = 'Z'
        zi      = self.get_time_zone(time_zone)
        dateval = Dt24(dateval.year, dateval.month, dateval.day, tzinfo=zi)
        #-----------------------------#
        # set the default data values #
        #-----------------------------#
        if time_zone == 'Z' :
            default_obstime = Dt24(dateval.year, dateval.month, dateval.day, 12, 0, 0, tzinfo=zi)
        else :
            default_obstime = Dt24(dateval.year, dateval.month, dateval.day, 0, 0, 0, tzinfo=zi) - timedelta(days=1)
        dateval = Dt24(dateval.year, dateval.month, dateval.day, tzinfo=zi)
        parameter_code    = None
        obstime_defined   = False
        relativetime      = None
        createtime        = None
        interval          = None
        time_series_code  = 0
        qualifier         = 'Z'
        units             = "EN"
        duration_unit     = 'Z'
        duration_value    = None
        use_prev_7am      = False
        param_control     = []
        outrecs           = []
        #--------------------------------------#
        # process the parameter control fields #
        #--------------------------------------#
        param_str = header[m.end():].strip()
        while self._multiple_obs_time_pattern.match(param_str) :
            param_str = self._multiple_obs_time_pattern.sub(r"\1@\6\7", param_str)
        param_tokens = list(map(lambda s : s.strip().strip('@'), param_str.split('/')))
        for token in param_tokens :
            if self._obs_time_pattern2.search(token) :
                #----------------------------------------------------#
                # set the observation time for subsequent parameters #
                #----------------------------------------------------#
                pos = 0
                while True :
                    m = self._obs_time_pattern2.search(token[pos:])
                    if not m : break
                    if not obstime_defined :
                        obstime = Dt24(dateval.year, dateval.month, dateval.day, 0, 0, 0, tzinfo=zi)
                        obstime_defined = True
                    obstime, relativetime = self.get_observation_time(obstime, token.upper(), dot_b=True)
                    if relativetime :
                        raise ShefParserException(f"Relative time not allowed in .B body: {token.replace('@', '/')}")
                    pos += m.end(1)+1
                if token[pos:] :
                    self.error(f"Unexpected data string item: {token.replace('@', '/')}")
                    return outrecs
            elif self._create_time_pattern.match(token) :
                #-------------------------------------------------#
                # set the creation time for subsequent parameters #
                #-------------------------------------------------#
                createtime = self.get_creation_time(zi, token.upper())
            elif self._unit_system_pattern.match(token) :
                #-----------------------------------------------#
                # set the unit system for subsequent parameters #
                #-----------------------------------------------#
                units = "EN" if token[2].upper() == 'E' else "SI"
            elif self._data_qualifier_pattern.match(token) :
                #---------------------------------------------#
                # set the qualifier for subsequent parameters #
                #---------------------------------------------#
                qualifier = token[2].upper()
                if qualifier not in self._qualifier_codes :
                    self.error(f"Bad data qualifier: {qualifier}")
                    return outrecs
            elif self._duration_code_pattern.match(token) :
                #--------------------------------------------------------------------#
                # set the duration for subequent parameters with duration code = 'V' #
                #--------------------------------------------------------------------#
                duration_unit = token[2].upper()
                if duration_unit == 'Z' :
                    duration_value = None
                else :
                    duration_value = int(token[3:])
                time_series_code = 1
            elif self._parameter_code_pattern.match(token) :
                #----------------------------------------------------------#
                # create a new parameter control object for this parameter #
                #----------------------------------------------------------#
                code = token.upper()
                if len(code) < 2 or (code[:2] not in self._send_codes and code[:2] not in self._pe_conversions) :
                    self.error(f"Invalid PE code: {code[:min(2, len(code))]}")
                    return outrecs
                parameter_code, use_prev_7am = self.get_parameter_code(code)
                t = obstime if obstime else default_obstime
                if use_prev_7am :
                    t = t.clone()
                    if t.hour < 7 :
                        t -= timedelta(days=1)
                    t = Dt24(t.year, t.month, t.day, 7, 0, 0, tzinfo=t.tzinfo)
                param_control.append(ShefParser.ParameterControl(
                    self,
                    parameter_code,
                    t,
                    relativetime,
                    createtime,
                    units,
                    qualifier,
                    duration_unit,
                    duration_value))
                relativetime = None
            elif not token :
                #------------------------------------#
                # missing value if in list of values #
                #------------------------------------#
                self.error("Null field in parameter control string")
                return outrecs
            else :
                self.error(f"Unexpected data string item: {token}")
                return outrecs
        #------------------#
        # process the body #
        #------------------#
        body = body.replace(",", "\n")
        bodylines = list(map(lambda x : x.strip(), body.split("\n")))
        for i in range(len(bodylines)) :
            p = 0
            time_override = None
            if not self._dot_b_body_line_pattern.match(bodylines[i]) and bodylines[i].strip() :
                self.error(f"Invalid body line: {bodylines[i]}")
                return outrecs
            if not bodylines[i].strip() :
                continue;
            location = bodylines[i].split()[0]
            bodytokens = list(map(lambda s: s.strip(), bodylines[i][len(location):].strip().split("/")))
            for token in bodytokens :
                if token[0] == 'D' :
                    try :
                        if token[1] not in "SNHDMYJ" :
                            self.error(f"Bad date/data override in data: {token}")
                            return outrecs
                        j = int(token[2:])
                    except :
                        self.error(f"Bad date/data override in data: {token}")
                        return outrecs
                    t = obstime if obstime else default_obstime
                    time_override = self.get_observation_time(t, token, dot_b=True)
                else :
                    m = self._value_pattern.search(token)
                    if not m :
                        self.error(f"Bad field in data: {token}")
                        return outrecs
                    value, qualifier = self.parse_value_token(token, param_control[p].pe_code, param_control[p].units)
                    comment = token[m.end():].strip()
                    if comment :
                        if comment[0] not in "'\"" :
                            self.error(f"Bad field in data: {token}")
                            return outrecs
                            comment = comment.strip("'").strip('"')

                    outrecs.append(param_control[p].get_output_record(
                        self,
                        revised,
                        msg_source,
                        location,
                        time_override,value,
                        qualifier,
                        comment))
                    p += 1
        return outrecs

def main() :
    '''
    Driver routine
    '''
    global logger
    progname = Path(sys.argv[0]).stem
    #--------------------#
    # parse command line #
    #--------------------#
    argparser = ArgumentParser(
        prog = progname,
        description="Parses SHEF text into different output formats (like shefit)")
    group = argparser.add_mutually_exclusive_group()
    group.add_argument(
        "-s",
        "--shefparm",
        action="store",
        help="specifies path of SHEFPARM file to use")
    group.add_argument(
        "-d",
        "--defaults",
        action="store_true",
        help="specifies using program defaults (ignore SHEFPARM in $rfs_sys_dir or current directory)")
    argparser.add_argument(
        "-i",
        "--infile",
        action="store",
        default=sys.stdin,
        help="specifies path of input file (defaults to <stdin>)")
    argparser.add_argument(
        "-o",
        "--outfile",
        action="store",
        default=sys.stdout,
        help="specifies path of output file (defaults to <stdout>)")
    argparser.add_argument(
        "-l",
        "--logfile",
        action="store",
        default=sys.stderr,
        help="specifies path of log file (defaults to <sterr>)")
    argparser.add_argument(
        "-f",
        "--format",
        action="store",
        choices=OutputRecord.OUTPUT_FORMATS,
        default=OutputRecord.SHEFIT_TEXT_V2,
        help=f"specifies output format (defaults to {OutputRecord.SHEFIT_TEXT_V2})")
    argparser.add_argument(
        "-v",
        "--loglevel",
        action="store",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "ALL"],
        default="INFO",
        help="specifies logging level (defaults to INFO)")
    argparser.add_argument(
        "-t",
        "--timestamps",
        action="store_true",
        help="specifies timestamping log records")
    argparser.add_argument(
        "--strict",
        action="store_true",
        help="specifies strict adherence to NOAA shefit program")
    args = argparser.parse_args()
    #-----------------------------------------------------------------#
    # get default SHEFPARM file if exists and --default not specified #
    #-----------------------------------------------------------------#
    if not args.shefparm and not args.defaults :
        p = Path.joinpath(Path(os.getenv("rfs_sys_dir", Path.cwd())), Path("SHEFPARM"))
        if p.exists() and not p.is_dir() :
            args.shefparm = p._str
    elif args.defaults :
        args.shefparm = None
    #-------------------#
    # set up the logger #
    #-------------------#
    logger  = logging.getLogger(progname)
    datefmt = "%Y-%m-%d %H:%M:%S"
    if args.timestamps :
        format  = "%(asctime)s %(levelname)s: %(msg)s"
    else :
        format  = "%(levelname)s: %(msg)s"
    level  = {
        "DEBUG"    : logging.DEBUG,
        "INFO"     : logging.INFO,
        "WARNING"  : logging.WARNING,
        "ERROR"    : logging.ERROR,
        "CRITICAL" : logging.CRITICAL,
        "ALL"      : logging.NOTSET}[args.loglevel]
    if isinstance(args.logfile, str) :
        logging.basicConfig(filename=args.logfile, format=format, datefmt=datefmt, level=level)
        logfile_name = args.logfile
    else :
        logging.basicConfig(stream=args.logfile, format=format, datefmt=datefmt, level=level)
        logfile_name = args.logfile.name
    #------------------#
    # log startup info #
    #------------------#
    infile_name  = args.infile  if isinstance(args.infile,  str) else args.infile.name
    outfile_name = args.outfile if isinstance(args.outfile, str) else args.outfile.name
    logger.debug(f"Program {progname} starting up")
    logger.debug(f"Input file set to {infile_name}")
    logger.debug(f"Output file set to {outfile_name}")
    logger.debug(f"Log file set to {logfile_name}")
    logger.debug(f"Log level set to {args.loglevel}")
    if args.shefparm and not args.default :
        logger.debug(f"Will modify program defaults with content of file {args.shefparm}")
    else :
        logger.debug(f"Will use program defaults")
    #-------------------#
    # create the parser #
    #-------------------#
    parser = ShefParser(args.format, args.shefparm, strict=args.strict)
    parser.set_input(args.infile)
    parser.set_output(args.outfile)

    while True :
        message_location, message = parser.get_next_message()
        if not message : break
        # print(f"message = {message}")
        outrecs = None
        try :
            if message.startswith(".A") :
                outrecs = parser.parse_dot_a_message(message)
            elif message.startswith(".B") :
                outrecs = parser.parse_dot_b_message(message)
            elif message.startswith(".E") :
                outrecs = parser.parse_dot_e_message(message)
            if outrecs :
                for outrec in outrecs : parser.output(outrec)
        except Exception as e :
            parser.error(f"{e} in message at {message_location}: {message}")

if __name__ == "__main__" :
    main()
