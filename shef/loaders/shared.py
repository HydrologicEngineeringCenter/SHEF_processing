import re
from collections import namedtuple
from datetime    import datetime
from datetime    import timedelta

class LoaderException(Exception) :
    pass


ShefValue = namedtuple("ShefValue", [
    "location",
    "obs_date",
    "obs_time",
    "create_date",
    "create_time",
    "parameter_code",
    "value",
    "data_qualifier",
    "revised_code",
    "time_series_code",
    "comment"])

DURATION_CODES: dict[int, str] = {
       0 : 'I',    1 : 'U',    5 : 'E',   10 : 'G',   15 : 'C',
      30 : 'J', 1001 : 'H', 1002 : 'B', 1003 : 'T', 1004 : 'F',
    1006 : 'Q', 1008 : 'A', 1012 : 'K', 1018 : 'L', 2001 : 'D',
    2007 : 'W', 2015 : 'N', 3001 : 'M', 4001 : 'Y', 5000 : 'Z',
    5001 : 'S', 5002 : 'R', 5003 : 'V', 5004 : 'P', 5005 : 'X'}

DURATION_VALUES: dict[str, int] = {value : key for key, value in DURATION_CODES.items()}

PROBABILITY_CODES: dict[float, str] = {
     .002 : 'A',  .004 : 'B',   .01 : 'C',   .02 : 'D',   .04 : 'E',   .05 : 'F',
       .1 : '1',    .2 : '2',   .25 : 'G',    .3 : '3',    .4 : '4',    .5 : '5',
       .6 : '6',    .7 : '7',   .75 : 'H',    .8 : '8',    .9 : '9',   .95 : 'T',
      .96 : 'U',   .98 : 'V',   .99 : 'W',  .996 : 'X',  .998 : 'Y', .0013 : 'J',
    .0228 : 'K', .1587 : 'L',  -0.5 : 'M', .8413 : 'N', .9772 : 'P', .9987 : 'Q',
     -1.0 : 'Z'}

PROBABILITY_VALUES: dict[str, float] = {value : key for key, value in PROBABILITY_CODES.items()}

SEND_CODES: dict[str, tuple[str, bool]] = {
    "AD" : ("ADZZZZZ", False), "AT" : ("ATD",     False), "AU" : ("AUD",     False), "AW" : ("AWD",     False), "EA" : ("EAD",     False),
    "EM" : ("EMD",     False), "EP" : ("EPD",     False), "ER" : ("ERD",     False), "ET" : ("ETD",     False), "EV" : ("EVD",     False),
    "HN" : ("HGIRZNZ", False), "HX" : ("HGIRZXZ", False), "HY" : ("HGIRZZZ", True) , "LC" : ("LCD",     False), "PF" : ("PPTCF",   False),
    "PY" : ("PPDRZZZ", True) , "PP" : ("PPD",     False), "PR" : ("PRD",     False), "QC" : ("QCD",     False), "QN" : ("QRIRZNZ", False),
    "QX" : ("QRIRZXZ", False), "QY" : ("QRIRZZZ", True) , "SF" : ("SFD",     False), "TN" : ("TAIRZNZ", False), "QV" : ("QVZ",     False),
    "RI" : ("RID",     False), "RP" : ("RPD",     False), "RT" : ("RTD",     False), "TC" : ("TCS",     False), "TF" : ("TFS",     False),
    "TH" : ("THS",     False), "TX" : ("TAIRZXZ", False), "UC" : ("UCD",     False), "UL" : ("ULD",     False), "XG" : ("XGJ",     False),
    "XP" : ("XPQ",     False)}

SHEF_ENGLISH_UNITS : dict[str, str] = {
    "AD": "unkonwn", "AF": "code",    "AG": "%",       "AM": "code",    "AT": "hr",      "AU": "hr",      "AW": "hr",
    "BA": "in",      "BB": "in",      "BC": "in",      "BD": "F",       "BE": "in",      "BF": "in",      "BG": "%",
    "BH": "in",      "BI": "in",      "BJ": "in",      "BK": "in",      "BL": "in",      "BM": "in",      "BN": "in",
    "BO": "in",      "BP": "in",      "BQ": "in",      "CA": "in",      "CB": "in",      "CC": "in",      "CD": "in",
    "CE": "in",      "CF": "in",      "CG": "in",      "CH": "in",      "CI": "in",      "CJ": "in",      "CK": "in",
    "CL": "F",       "CM": "F",       "CN": "%",       "CO": "code",    "CP": "in",      "CQ": "in",      "CR": "in",
    "CS": "in",      "CT": "unit",    "CU": "F",       "CV": "F",       "CW": "in",      "CX": "in",      "CY": "in",
    "CZ": "code",    "EA": "in",      "ED": "in",      "EM": "in",      "EP": "in",      "ER": "in",      "ET": "in",
    "EV": "in",      "FA": "unit",    "FB": "unit",    "FC": "unit",    "FE": "unit",    "FK": "unit",    "FL": "unit",
    "FP": "unit",    "FS": "unit",    "FT": "unit",    "FZ": "unit",    "GC": "code",    "GD": "in",      "GL": "%",
    "GP": "in",      "GR": "code",    "GS": "code",    "GT": "in",      "GW": "in",      "HA": "ft",      "HB": "ft",
    "HC": "ft",      "HD": "ft",      "HE": "ft",      "HF": "ft",      "HG": "ft",      "HH": "ft",      "HI": "code",
    "HJ": "ft",      "HK": "ft",      "HL": "ft",      "HM": "ft",      "HN": "ft",      "HO": "ft",      "HP": "ft",
    "HQ": "code",    "HR": "ft",      "HS": "ft",      "HT": "ft",      "HU": "ft",      "HV": "ft",      "HW": "ft",
    "HX": "ft",      "HY": "ft",      "HZ": "kft",     "IC": "%",       "IE": "mi",      "IO": "ft",      "IR": "code",
    "IT": "in",      "LA": "kac",     "LC": "kaf",     "LS": "kaf",     "MD": "code",    "MI": "in",      "ML": "in",
    "MM": "%",       "MN": "code",    "MS": "code",    "MT": "F",       "MU": "in",      "MV": "code",    "MW": "%",
    "NC": "code",    "NG": "ft",      "NL": "unit",    "NN": "unit",    "NO": "code",    "NS": "unit",    "PA": "in-hg",
    "PC": "in",      "PD": "in-hg",   "PE": "code",    "PF": "in",      "PJ": "in",      "PL": "mb",      "PM": "code",
    "PN": "in",      "PP": "in",      "PR": "in/day",  "PT": "code",    "PY": "in",      "QA": "kcfs",    "QB": "in",
    "QC": "kaf",     "QD": "kcfs",    "QE": "%",       "QF": "mph",     "QG": "kcfs",    "QI": "kcfs",    "QL": "kcfs",
    "QM": "kcfs",    "QN": "kcfs",    "QP": "kcfs",    "QR": "kcfs",    "QS": "kcfs",    "QT": "kcfs",    "QU": "kcfs",
    "QV": "kaf",     "QX": "kcfs",    "QY": "kcfs",    "QZ": "unkonwn", "RA": "%",       "RI": "ly",      "RN": "w/m2",
    "RP": "%",       "RT": "hr",      "RW": "w/m2",    "SA": "%",       "SB": "in",      "SD": "in",      "SE": "F",
    "SF": "in",      "SI": "in",      "SL": "kft",     "SM": "in",      "SP": "in",      "SR": "code",    "SS": "n/a",
    "ST": "code",    "SU": "in",      "SW": "in",      "TA": "F",       "TB": "code",    "TC": "F",       "TD": "F",
    "TE": "code",    "TF": "F",       "TH": "F",       "TJ": "F",       "TM": "F",       "TN": "F",       "TP": "F",
    "TR": "F",       "TS": "F",       "TV": "code",    "TW": "F",       "TX": "F",       "TZ": "F",       "UC": "mi",
    "UD": "deg",     "UE": "deg",     "UG": "mph",     "UL": "mi",      "UP": "mph",     "UQ": "code",    "UR": "deg/10",
    "US": "mph",     "UT": "min",     "VB": "v",       "VC": "mw",      "VE": "mwh",     "VG": "mw",      "VH": "hr",
    "VJ": "mwh",     "VK": "mwh",     "VL": "mwh",     "VM": "mwh",     "VP": "mw",      "VQ": "mwh",     "VR": "mwh",
    "VS": "mwh",     "VT": "mw",      "VU": "code",    "VW": "mw",      "WA": "ppm",     "WC": "umho/cm", "WD": "in",
    "WG": "in-hg",   "WH": "ppm",     "WL": "ppm",     "WO": "ppm",     "WP": "ph",      "WS": "ppt",     "WT": "jtu",
    "WV": "ft/s",    "WX": "%",       "WY": "ppb",     "XC": "unit*10", "XG": "unit",    "XL": "unit",    "XP": "code",
    "XR": "%",       "XU": "g/ft3",   "XV": "mi",      "XW": "code",    "YA": "unit",    "YC": "unit",    "YF": "w",
    "YI": "code",    "YP": "code",    "YR": "w",       "YS": "unit",    "YT": "unit",    "YV": "v",       "YY": "code",
}

VALUE_UNITS_PATTERN: re.Pattern = re.compile("([0-9]+)([a-z]+)", re.I)

DATETIME_PATTERN: re.Pattern = re.compile("[ :-]")

FORMAT_1_PATTERN: re.Pattern = re.compile(
# groups:  1 - Location
#          2 - Obs date
#          3 - Obs time
#          4 - Create date
#          5 - Create time
#          6 - PEDTSE
#          7 - Value
#          8 - Data qualifier
#          9 - Probability code number
#         10 - Reivsed code
#         11 - Time series code
#         12 - Message source (.B only)
#         13 - Comment
#     1       2                   3                    4                   5                   6
    r"(\w+\s*)(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})  (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})  ([A-Z]{3}[A-Z0-9]{3})." +\
#                                                  1      1        1                1
#     7               8      9                     0      1        2                3
    r"([ 0-9.+-]{15}) ([A-Z])([ 0-9.+-]{9})  \d{4} ([01]) ([012])  ((?: |\w){8})  \"(.+)\"")

def exc_info(e: Exception) -> str :
    '''
    Get exception info for logging
    '''
    info = f"{e.__class__.__name__}: {str(e)}"
    if e.args and " ".join(e.args) != str(e):
        info += f" args = {e.args}"
    return info

def make_shef_value(format_1_line: str) -> ShefValue :
    '''
    Creates a ShefValue object from a shefParser -f 1 (shefit -1) line
    '''
    m = FORMAT_1_PATTERN.match(format_1_line)
    if not m :
        raise LoaderException(f"Unexpected line from parser: [{format_1_line}]")
    try :
        probability_code = PROBABILITY_CODES[float(m.group(9))]
    except KeyError :
        probability_code = 'Z'
    if len(m.group(1)) != 10 :
        raise ValueError(f"Expected length location group to be 10, got {len(m.group(1))}")
    return ShefValue(
          location         = m.group(1).strip(),
          obs_date         = m.group(2),
          obs_time         = m.group(3),
          create_date      = m.group(4),
          create_time      = m.group(5),
          parameter_code   = f"{m.group(6)}{probability_code}",
          value            = float(m.group(7)),
          data_qualifier   = m.group(8),
          revised_code     = m.group(10),
          time_series_code = m.group(11),
          comment          = m.group(13).strip())

def get_datetime(datetime_str: str) -> datetime :
    '''
    Creates a datetime object from a string like "yyyy-mm-dd hh:nn:ss"
    '''
    y, m, d, h, n, s = map(int, DATETIME_PATTERN.split(datetime_str))
    return datetime(y, m, d, h, n, s)

def duration_interval(parameter_code: str) -> timedelta :
    '''
    Creates a timedelta object that represents the duration in a SHEF parameter code
    '''
    dv = DURATION_VALUES[parameter_code[2]]
    if dv > 5000 :
        intvl = timedelta(seconds = 0)
    elif dv == 4001 :
        intvl = timedelta(days = 365)
    elif dv == 3001 :
        intvl = timedelta(days = 30)
    elif dv > 2000 :
        intvl = timedelta(days = dv % 1000)
    elif dv > 1000 :
        intvl = timedelta(hours = dv % 1000)
    else :
        intvl = timedelta(minutes = dv % 1000)
    return intvl
