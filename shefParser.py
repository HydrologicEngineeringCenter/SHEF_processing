import copy, io, logging, os, re, sys
from argparse    import ArgumentParser
from collections import deque
from datetime    import datetime
from datetime    import timedelta
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
    
class Dt24 :
    '''
    Datetime class that accepts and generates 2400 instead of 0000
    '''
    def __init__(self, *args, **kwargs) :
        '''
        Constructor allowing 2400
        '''
        args2   = args[:]
        adjust = False
        length = len(args2)
        if length > 3 :
            if args2[3] == 24 :
                adjust = True
                args2 = args2[:3]+(23,)+args2[4:]
        self._dt = datetime(*args2, **kwargs)
        if adjust :
            self._dt += timedelta(hours=1)
        self._adjusted = adjust

    @staticmethod
    def is_leap(y: int) :
        return (not bool(y % 4) and bool(y % 100)) or (not bool(y % 400))
        
    @staticmethod
    def last_day(y: int, m: int) :
        return m if m in (1,3,5,7,8,10,12) else 30 if m in (4,6,9,11) else 29 if Dt24.is_leap(y) else 28

    @staticmethod
    def now() :
        t = datetime.now()
        return Dt24(t.year, t.month, t.day, t.hour, t.minute, t.second)

    def clone(self) :
        '''
        Create a (distinct) copy of this object
        '''
        dt = self._dt
        y, m, d, h, n, s, z = dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.tzinfo
        return Dt24(y, m, d, h, n, s, tzinfo=z)
        
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
            return self._dt.__add__(other)
        if isinstance(other, MonthsDelta) :
            return self.add_months(other.months, other.eom)

    def __sub__(self, other : Union[timedelta, MonthsDelta]) :
        if isinstance(other, timedelta) :
            return self._dt.__sub__(other)
        if isinstance(other, MonthsDelta) :
            return self.add_months(-other.months, other.eom)
        if isinstance(other, Dt24) :
            return self._dt - other._dt

    def __str__(self) :
        dt = self._dt
        if dt.hour == dt.minute == dt.second == 0 :
            s = (dt - timedelta(hours=1)).__str__()
            return s[:11] + "24" + s[13:]
        return self._dt.__str__()

    def __getattribute__(self, name) :
        if name in ("_dt", "_adjusted", "clone", "add_months") :
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
        else :
            return super().__getattribute__("_dt").__getattribute__(name)

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
            obstime:          Dt24,
            create_time:      Dt24 = None,
            value:            float = -9999.,
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
        if not obstime :
            raise ShefParserException("Observed time must not be empty")
            
        self._location             = location
        self._observation_time     = obstime
        self._creation_time        = create_time
        self._parameter_code       = parameter_code
        self._value                = value
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
    PE_CODES = {
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
        'S' : 7000, 'N' :    0, 'H' : 1000, 'D' : 2000, 'M' : 3000, 'Y' : 4000}

    TZ_NAMES = {
        "N"  : "Canada/Newfoundland", # Newfoundland local
        "NS" : "Canada/Newfoundland", # Newfoundland standard (this will be off by 1 hour during DST)
        "A"  : "Canada/Atlantic",     # Atlantic local
        "AD" : "Etc/GMT+3",           # Atlantic daylight
        "AS" : "Etc/GMT+4",           # Atlantic standard
        "E"  : "US/Eastern",          # Eastern local
        "ED" : "Etc/GMT+4",           # Eastern daylight
        "ES" : "Etc/GMT+5",           # Eastern standard
        "C"  : "US/Central",          # Central
        "CD" : "Etc/GMT+5",           # Central daylight
        "CS" : "Etc/GMT+6",           # Central standard
        "J"  : "CTT",                 # China
        "M"  : "US/Mountain",         # Mountain local
        "MD" : "Etc/GMT+6",           # Mountain daylight
        "MS" : "Etc/GMT+7",           # Mountain standard
        "P"  : "US/Pacific",          # Pacific local
        "PD" : "Etc/GMT+7",           # Pacific daylight
        "PS" : "Etc/GMT+8",           # Pacific standard
        "Y"  : "Canada/Yukon",        # Yukon local
        "YD" : "Etc/GMT+7",           # Yukon daylight
        "YS" : "Etc/GMT+8",           # Yukon standard
        "H"  : "US/Hawaii",           # Hawaiian local
        "HS" : "US/Hawaii",           # Hawaiian standard
        "L"  : "US/Alaska",           # Alaskan local
        "LD" : "Etc/GMT+8",           # Alaskan daylight
        "LS" : "Etc/GMT+9",           # Alaskan standard
        "B"  : "Pacific/Midway",      # Bering local
        "BD" : "Pacific/Midway",      # Bering daylight
        "BS" : "Pacific/Midway",      # Bering standard
        "Z"  : "UTC"}                 # Zulu

    def __init__(self, output_format, shefparm_pathname=None) :
        '''
        Constructor
        '''
        self._shefparm_pathname = shefparm_pathname
        self._output_format     = output_format
        #-----------------------------#
        # initialize program defaults #
        #-----------------------------#
        self._pe_codes                 = copy.deepcopy(ShefParser.PE_CODES)
        self._send_codes               = copy.deepcopy(ShefParser.SEND_CODES)
        self._duration_codes           = copy.deepcopy(ShefParser.DURATION_CODES)
        self._ts_codes                 = copy.deepcopy(ShefParser.TS_CODES)
        self._extremum_codes           = copy.deepcopy(ShefParser.EXTREMUM_CODES)
        self._probability_codes        = copy.deepcopy(ShefParser.PROBABILITY_CODES)
        self._qualifier_codes          = copy.deepcopy(ShefParser.QUALIFIER_CODES)
        self._default_duration_codes   = copy.deepcopy(ShefParser.DEFAULT_DURATION_CODES)
        self._tz_names                 = copy.deepcopy(ShefParser.TZ_NAMES)
        self._max_error_count          = 500 # May be modified by SHEFPARM file
        self._error_count              = 0
        self._default_duration_code    = 'I' # May not be modified by SHEFPARM file
        self._default_type_code        = 'R' # May not be modified by SHEFPARM file
        self._default_source_code      = 'Z' # May not be modified by SHEFPARM file
        self._default_extremum_code    = 'Z' # May not be modified by SHEFPARM file
        self._default_probability_code = 'Z' # May not be modified by SHEFPARM file
        self._input                    = None
        self._output                   = None
        self._input_lines              = None
        self._msg_start_pattern        = re.compile(r"^\.[ABE]R?\s")
        self._msg_continue_patterns    = {'A' : (re.compile(r"^\.A\d"), re.compile(r"^\.AR?\d")),
                                          'E' : (re.compile(r"^\.E\d"), re.compile(r"^\.ER?\d")),
                                          'B' : (re.compile(r"^\.B\d"), re.compile(r"^\.BR?\d"))}
        self._input_name               = None
        self._line_number              = 0
        self._dot_a_e_header_pattern   = re.compile(
                                         # 1 = location id
                                         # 2 = date-time
                                         # 6 = time zone
                                         #               1           23       4
                                           r"^\.[AE]R?\s+(\w{3,8})\s+((\d{2})?(\d{2})?\d{4})\s+" \
                                         #    56
                                           r"(([NH]S?|[AECMPYLB][DS]?|[JZ])\s{1,15})?", re.M)
        self._obs_time_pattern         = re.compile(
                                         #    12                            3     45      6                          7
                                            r"((D[SNHDMYJ]|DR[SNHDMYE][+-]?)(\d+))((\s+|/)(D[SNHDMYJ]|DR[SNHDMYE][+-])(\d+))?")
        self._obs_time_pattern2        = re.compile(r"((D[SNHDMYJ]|DR[SNHDMYE][+-]?)(\d+))(@(D[SNHDMYJ]|DR[SNHDMYE][+-])(\d+))?")
        self._create_time_pattern      = re.compile(r"DC\d+")
        self._unit_system_pattern      = re.compile(r"DU[ES]")
        self._data_qualifier_pattern   = re.compile(r"DQ.")
        self._duration_code_pattern    = re.compile(r"(DV[SNHDMY]\d{2}|DVZ)")
        self._parameter_code_pattern   = re.compile(r"^[A-Z]{2}([A-Z]([A-Z0-9]{2}[A-Z]{,2})?)?$")
        self._interval_pattern         = re.compile(r"DI[SNHDMEY][+-]?\d{1,2}")
        self._value_pattern            = re.compile(
                                        # 1 = sign
                                        # 2 = numeric value
                                        # 4 = trace value
                                        # 5 = missing valule
                                        # 6 = value qualifier
                                         #    1      2   3               4      5            6
                                            r"([+-]?)(\d+(\.\d*)?|\.\d+)|([Tt])|([Mm]{1,2})(\D?)")
        self._UTC                      = ZoneInfo("UTC")

        if self._shefparm_pathname :
            self.read_shefparm(self._shefparm_pathname)

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
        if key not in self._pe_codes :
            if key  not in self._send_codes :
                logger.info(f"{self._shefparm_pathname}: Adding non-standard physical element code {key} with conversion factor {value}")
        else:
            if 0.9999 <= value / self._pe_codes[key] <= 1.001 :
                pass
            else :
                logger.warning(f"{self._shefparm_pathname}: Updating standard physical element code {key} conversion factor from {self._pe_codes[key]} to {value}")
        self._pe_codes[key] = value

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
                code += self._default_duration_codes[code]
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
            self._output = open(output_object)
        self._output_name = self._output.name
        logger.debug(f"Data output set to {self._output_name}")

    def output(self, outrec : OutputRecord) :
        if not self._output :
            raise ShefParserException("Cannot output record; output is closed or never opened")
        self._output.write(f"{outrec.format(self._output_format)}\n")

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
            dateval = Dt24(int(datestr[:4]), int(datestr[4:6]), int(datestr[6:]))
            if length == 4 : 
                # no year specified, use closeset date
                prev_year = dateval.add_months(-12)
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
        datastr = self._obs_time_pattern.sub(r"\1@\6", datastr).strip('@')
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

    def get_observation_time(self, current_observation_time: Dt24, zi : ZoneInfo, token: str) :
        '''
        Update the observation time based on the token
        '''
        obstime = current_observation_time.clone()
        for subtoken in token.split("@") :
            try :
                cur_time = Dt24.now()
                v = subtoken[2:]
                length = len(v)
                if subtoken[1] == 'S' :
                    if length == 2 : # DSss
                        obstime = Dt24(obstime.year, obstime.month, obstime.day, obstime.hour, obstime.minute, int(v[0:2]), tzinfo=zi)
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                elif subtoken[1] == 'N' :
                    if length == 4 : # DNnnss
                        obstime = Dt24(obstime.year, obstime.month, obstime.day, obstime.hour, int(v[0:2]), int(v[2:4]), tzinfo=zi)
                    elif length == 2 : # DNnn
                        obstime = Dt24(obstime.year, obstime.month, obstime.day, obstime.hour, int(v[0:2]), obstime.second, tzinfo=zi)
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                        return None
                elif subtoken[1] == 'H' :
                    if length == 6 : # DHhhnnss
                        obstime = Dt24(obstime.year, obstime.month, obstime.day, int(v[0:2]), int(v[2:4]), int(v[4:6]), tzinfo=zi)
                    elif length == 4 : # DHhhnn
                        obstime = Dt24(obstime.year, obstime.month, obstime.day, int(v[0:2]), int(v[2:4]), obstime.second, tzinfo=zi)
                    elif length == 2 : # DHhh
                        obstime = Dt24(obstime.year, obstime.month, obstime.day, int(v[0:2]), obstime.minute, obstime.second, tzinfo=zi)
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                elif subtoken[1] == 'D' :
                    if length == 8 : # DDddhhnnss
                        obstime = Dt24(obstime.year, obstime.month, int(v[0:2]), int(v[2:4]), int(v[4:6]), int(v[6:8]), tzinfo=zi)
                    elif length == 6 : # DDddhhnn
                        obstime = Dt24(obstime.year, obstime.month, int(v[0:2]), int(v[2:4]), int(v[4:6]), obstime.second, tzinfo=zi)
                    elif length == 4 : # DDddhh
                        obstime = Dt24(obstime.year, obstime.month, int(v[0:2]), int(v[2:4]), obstime.hour, obstime.second, tzinfo=zi)
                    elif length == 2 : # DDdd
                        obstime = Dt24(obstime.year, obstime.month, int(v[0:2]), obstime.hour, obstime.minute, obstime.second, tzinfo=zi)
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                elif subtoken[1] == 'M' :
                    if length == 10 : # DMmmddhhnnss
                        obstime = Dt24(obstime.year, int(v[0:2]), int(v[2:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), tzinfo=zi)
                    elif length == 8 : # DMmmddhhnn
                        obstime = Dt24(obstime.year, int(v[0:2]), int(v[2:4]), int(v[4:6]), int(v[6:8]), obstime.second, tzinfo=zi)
                    elif length == 6 : # DMmmddhh
                        obstime = Dt24(obstime.year, int(v[0:2]), int(v[2:4]), int(v[4:6]), obstime.minute, obstime.second, tzinfo=zi)
                    elif length == 4 : # DMmmdd
                        obstime = Dt24(obstime.year, int(v[0:2]), int(v[2:4]), obstime.hour, obstime.minute, obstime.second, tzinfo=zi)
                    elif length == 2 : # DMmm
                        obstime = Dt24(obstime.year, int(v[0:2]), obstime.day, obstime.hour, obstime.minute, obstime.second, tzinfo=zi)
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
                        obstime = Dt24(y, int(v[2:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), int(v[10:12]), tzinfo=zi)
                    elif length == 10 : # DYyymmddhhnn - set date and time
                        obstime = Dt24(y, int(v[2:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), obstime.second, tzinfo=zi)
                    elif length == 8 : # DYyymmddhh
                        obstime = Dt24(y, int(v[2:4]), int(v[4:6]), int(v[6:8]), obstime.minute, obstime.second, tzinfo=zi)
                    elif length == 6 : # DYyymmdd
                        obstime = Dt24(y, int(v[2:4]), int(v[4:6]), obstime.hour, obstime.minute, obstime.second, tzinfo=zi)
                    elif length == 4 : # DYyymm
                        obstime = Dt24(y, int(v[2:4]), obstime.day, obstime.hour, obstime.minute, obstime.second, tzinfo=zi)
                    elif length == 2 : # DYyy
                        obstime = Dt24(y, obstime.month, obstime.day, obstime.hour, obstime.minute, obstime.second, tzinfo=zi)
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                elif subtoken[1] == 'T' :
                    if length == 14 : #DTccyymmddhhnnss
                        obstime = Dt24(int(v[0:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), int(v[10:12]), int(v[12:14]), tzinfo=zi)
                    elif length == 12 : #DTccyymmddhhnn
                        obstime = Dt24(int(v[0:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), int(v[10:12]), obstime.second, tzinfo=zi)
                    elif length == 10 : #DTccyymmddhh
                        obstime = Dt24(int(v[0:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), obstime.minute, obstime.second, tzinfo=zi)
                    elif length == 8 : #DTccyymmdd
                        obstime = Dt24(int(v[0:4]), int(v[4:6]), int(v[6:8]), obstime.hour, obstime.minute, obstime.second, tzinfo=zi)
                    elif length == 6 : #DTccyymm
                        obstime = Dt24(int(v[0:4]), int(v[4:6]), obstime.day, obstime.hour, obstime.minute, obstime.second, tzinfo=zi)
                    elif length == 4 : #DTccyy
                        obstime = Dt24(int(v[0:4]), obstime.month, obstime.day, obstime.hour, obstime.minute, obstime.second, tzinfo=zi)
                    elif length == 2 : #DTcc
                        obstime = Dt24(100*int(v[0:2])+obstime.year%100, obstime.month, obstime.day, obstime.hour, obstime.minute, obstime.second, tzinfo=zi)
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                elif subtoken[1] == 'J' : 
                    if length == 7 : # DJccyyddd
                        obstime = Dt24(int(obstime[0:4]), 1, 1, obstime.hour, obstime.minute, obstime.second, tzinfo=zi) + timedelta(days=int(v[4:7]))
                    elif length == 5 : # DJyyddd
                        y = cur_time.year - cur_time.year % 100 + int(v[0:2])
                        if y - cur_time.year > 10 : y -= 100
                        obstime = Dt24(y, 1, 1, obstime.hour, obstime.minute, obstime.second, tzinfo=zi) + timedelta(days=int(v[2:5]))
                    elif length == 3 : # DJddd
                        obstime = Dt24(obstime.year, 1, 1, obstime.hour, obstime.minute, obstime.second, tzinfo=zi) + timedelta(days=int(v[0:3]))
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                elif subtoken[1] == 'R' :
                    v = subtoken[3:]
                    length = len(v)
                    if length != 3 :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                        return None
                    if subtoken[2] == 'S' :
                        objtime += timedelta(seconds=int(v))
                    elif subtoken[2] == 'N' :
                        objtime += timedelta(minutes=int(v))
                    elif subtoken[2] == 'H' :
                        objtime += timedelta(hours=int(v))
                    elif subtoken[2] == 'D' :
                        objtime += timedelta(days=int(v))
                    elif subtoken[2] == 'M' :
                        obstime = obstime.add_months(int(v))
                    elif subtoken[2] == 'E' :
                        obstime = obstime.add_months(int(v), end_of_month = True)
                    elif subtoken[2] == 'Y' :
                        obstime = obstime.add_months(12*int(v))
                    else :
                        raise ShefParserException(f"Bad observation time: {subtoken}")
                return obstime
            except :
                raise ShefParserException(f"Bad observation time: {subtoken}")

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
                value *= self._pe_codes[pe_code]
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

    def parse_dot_a_message(self, message: str) :
        '''
        Parses a .A or .AR message
        '''
        #------------------#
        # parse the header #
        #------------------#
        revised   = None
        location  = None
        date_time = None
        time_zone = None
        hdr_len   = None
        m = self._dot_a_e_header_pattern.search(message)
        if m :
            revised   = message[2] == 'R'
            location  = m.group(1)
            dateval   = self.parse_header_date(m.group(2))
            time_zone = m.group(6)
            hdr_len   = m.end()
        else :
            self.error(f"Mal-formed message header: {message}")
            return
        #-------------------------#
        # process the header info #
        #-------------------------#
        if not time_zone : time_zone = 'Z'
        try :
            zi = ZoneInfo(self._tz_names[time_zone])
        except :
            self.error(f"Cannot instantiate time zone {self._tz_names[time_zone]} for SHEF time zone {time_zone}")
            return
        dateval = Dt24(dateval.year, dateval.month, dateval.day, tzinfo=zi)
        datastr = message[hdr_len:].strip()
        tokens = self.crack_a_e_data_string(datastr, 'A', revised)
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
        #--------------------------------#
        # process the data string fields #
        #--------------------------------#
        for i in range(len(tokens)) :
            if len(tokens[i]) == 1 :
                token = tokens[i][0]
                if self._obs_time_pattern2.match(token) :
                    #------------------------------------------------#
                    # set the observation time for subsequent values #
                    #------------------------------------------------#
                    if not obstime_defined :
                        obstime = Dt24(dateval.year, dateval.month, dateval.day, 0, 0, 0, tzinfo=zi)
                    obstime = self.get_observation_time(obstime, zi, token)
                elif self._create_time_pattern.match(token) :
                    #---------------------------------------------#
                    # set the creation time for subsequent values #
                    #---------------------------------------------#
                    createtime = self.get_creation_time(zi, token)
                elif self._unit_system_pattern.match(token) :
                    #-------------------------------------------#
                    # set the unit system for subsequent values #
                    #-------------------------------------------#
                    units = "EN" if token[2] == 'E' else "SI"
                elif self._data_qualifier_pattern.match(token) :
                    #-------------------------------------------------#
                    # set the default qualifier for subsequent values #
                    #-------------------------------------------------#
                    default_qualifier = token[2]
                    if default_qualifier not in self._qualifier_codes :
                        error(f"Bad data qualifier: {default_qualifier}")
                        return
                elif self._duration_code_pattern.match(token) :
                    #----------------------------------------------------------------#
                    # set the duration for subequent values with duration code = 'V' #
                    #----------------------------------------------------------------#
                    duration_unit = token[2]
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
                    raise ShefParserException(f"Unexpected data string item: {token}")
            else :
                #------------#
                # data value #
                #------------#
                code = tokens[i][0]
                if len(code) < 2 or (code[:2] not in self._send_codes and code[:2] not in self._pe_codes) :
                    raise ShefParserException(f"Invalid PE code: {code[:min(2, len(code))]}")
                parameter_code, use_prev_7am = self.get_parameter_code(code)
                if use_prev_7am :
                    t = Dt24(obstime.year, obstime.month, obstime.day, obstime.hour, obstime.minute, obstime.second, tzinfo = obstime.tzinfo)
                    if t.hour < 7 : t -= timedelta(days=1)
                    obstime = Dt24(t.year, t.month, t.day, 7, 0, 0, t.tzinfo)
                if len(tokens[i]) == 1 :
                    continue # same as a NULL field - a parameter code with no value
                value, qualifier = self.parse_value_token(tokens[i][1], parameter_code[:2], units)
                if not qualifier : qualifier = default_qualifier
                if qualifier not in self._qualifier_codes :
                    raise ShefParserException(f"Invalid data qualifier: {qualifier}")
                comment = None
                if len(tokens[i]) > 2 :
                    comment = tokens[i][2]
                    if comment :
                        if comment[0] not in "'\"" :
                            if qualifier in self._qualifier_codes :
                                raise ShefParserException(f"Data qualifier: {qualifier} does not immediately follow value {tokens[i][1]}")
                            else :
                                raise ShefParserException(f"Invalid retained comment {tokens[i][2]}")
                        comment = comment[1:-1]

                outrec = OutputRecord(
                    location,
                    parameter_code,
                    obstime.astimezone(self._UTC),
                    createtime.astimezone(self._UTC) if createtime else None,
                    value,
                    qualifier,
                    revised,
                    duration_unit,
                    duration_value,
                    comment = comment)
                return [outrec]

    def parse_dot_e_message(self, message) :
        '''
        Parses a .E or .ER message
        '''
        #------------------#
        # parse the header #
        #------------------#
        revised   = None
        location  = None
        date_time = None
        time_zone = None
        hdr_len   = None
        m = self._dot_a_e_header_pattern.search(message)
        if m :
            revised   = message[2] == 'R'
            location  = m.group(1)
            dateval   = self.parse_header_date(m.group(2))
            time_zone = m.group(6)
            hdr_len   = m.end()
        else :
            self.error(f"Mal-formed message header: {message}")
            return
        #-------------------------#
        # process the header info #
        #-------------------------#
        if not time_zone : time_zone = 'Z'
        try :
            zi = ZoneInfo(self._tz_names[time_zone])
        except :
            raise ShefParserException(f"Cannot instantiate time zone {self._tz_names[time_zone]} for SHEF time zone {time_zone}")
        dateval = Dt24(dateval.year, dateval.month, dateval.day, tzinfo=zi)
        datastr = message[hdr_len:].strip()
        tokens = self.crack_a_e_data_string(datastr, 'E', revised)
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
            if self._obs_time_pattern2.match(token) :
                #------------------------------------------------#
                # set the observation time for subsequent values #
                #------------------------------------------------#
                if not obstime_defined :
                    obstime = Dt24(dateval.year, dateval.month, dateval.day, 0, 0, 0, tzinfo=zi)
                obstime = self.get_observation_time(obstime, zi, token)
                time_series_code = 1
            elif self._create_time_pattern.match(token) :
                #---------------------------------------------#
                # set the creation time for subsequent values #
                #---------------------------------------------#
                createtime = self.get_creation_time(zi, token)
            elif self._unit_system_pattern.match(token) :
                #-------------------------------------------#
                # set the unit system for subsequent values #
                #-------------------------------------------#
                units = "EN" if token[2] == 'E' else "SI"
            elif self._data_qualifier_pattern.match(token) :
                #-------------------------------------------------#
                # set the default qualifier for subsequent values #
                #-------------------------------------------------#
                default_qualifier = token[2]
                if default_qualifier not in self._qualifier_codes :
                    error(f"Bad data qualifier: {default_qualifier}")
                    return
            elif self._duration_code_pattern.match(token) :
                #----------------------------------------------------------------#
                # set the duration for subequent values with duration code = 'V' #
                #----------------------------------------------------------------#
                duration_unit = token[2]
                if duration_unit == 'Z' :
                    duration_value = None
                else :
                    duration_value = int(token[3:])
                time_series_code = 1
            elif self._parameter_code_pattern.match(token) :
                #-------------------------------------------------#
                # set the parameter code for the susequent values #
                #-------------------------------------------------#
                if parameter_code :
                    raise ShefParserException("Parameter code specified more than once")
                code = token
                if len(code) < 2 or (code[:2] not in self._send_codes and code[:2] not in self._pe_codes) :
                    raise ShefParserException(f"Invalid PE code: {code[:min(2, len(code))]}")
                parameter_code, use_prev_7am = self.get_parameter_code(code)
            elif self._interval_pattern.match(token) :
                #-----------------------------------------#
                # set the intrerval for subsequent values #
                #-----------------------------------------#
                if interval :
                    raise ShefParserException("Interval specified more than once")
                time_series_code = 1
                interval_unit = token[2]
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
            elif self._value_pattern.match(token) :
                #------------#
                # data value #
                #------------#
                value, qualifier = self.parse_value_token(token, parameter_code[:2], units)
                if not qualifier : qualifier = default_qualifier
                if qualifier not in self._qualifier_codes :
                    raise ShefParserException(f"Invalid data qualifier: {qualifier}")
                comment = None
                if len(tokens[i]) > 2 :
                    comment = tokens[i][2]
                    if comment :
                        if comment[0] not in "'\"" :
                            if qualifier in self._qualifier_codes :
                                raise ShefParserException(f"Data qualifier: {qualifier} does not immediately follow value {tokens[i][1]}")
                            else :
                                raise ShefParserException(f"Invalid retained comment {tokens[i][2]}")
                        comment = comment[1:-1]
            elif not token :
                #------------------------------------#
                # missing value if in list of values #
                #------------------------------------#
                if not (parameter_code and interval) :
                    raise ShefParserException("Null field in data definition")
                value = -9999.
                qualifier = default_qualifier
                obstime += interval
            elif token[0] in "\"'" :
                #------------------#
                # retained comment #
                #------------------#
                if not value :
                    raise ShefParserException("Comment encountered before value")
                comment = token[1:-1]
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
                    obstime.astimezone(self._UTC),
                    createtime.astimezone(self._UTC) if createtime else None,
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
    parser = ShefParser(args.format, args.shefparm)
    parser.set_input(args.infile)
    parser.set_output(args.outfile)

    while True :
        message_location, message = parser.get_next_message()
        if not message : break
        try :
            if message.startswith(".A") :
                outrecs = parser.parse_dot_a_message(message)
                if outrecs : 
                    for outrec in outrecs : parser.output(outrec)
            elif message.startswith(".E") :
                outrecs = parser.parse_dot_e_message(message)
                if outrecs : 
                    for outrec in outrecs : parser.output(outrec)
        except Exception as e :
            parser.error(f"{e} in message at {message_location}: {message}")
            if str(e).find("supported") != -1 : raise

if __name__ == "__main__" :
    main()
