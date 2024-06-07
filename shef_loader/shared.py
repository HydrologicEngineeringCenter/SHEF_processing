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

DURATION_CODES    = {
       0 : 'I',    1 : 'U',    5 : 'E',   10 : 'G',   15 : 'C',
      30 : 'J', 1001 : 'H', 1002 : 'B', 1003 : 'T', 1004 : 'F',
    1006 : 'Q', 1008 : 'A', 1012 : 'K', 1018 : 'L', 2001 : 'D',
    2007 : 'W', 2015 : 'N', 3001 : 'M', 4001 : 'Y', 5000 : 'Z',
    5001 : 'S', 5002 : 'R', 5003 : 'V', 5004 : 'P', 5005 : 'X'}

DURATION_VALUES = {value : key for key, value in DURATION_CODES.items()}

PROBABILITY_CODES = {
     .002 : 'A',  .004 : 'B',   .01 : 'C',   .02 : 'D',   .04 : 'E',   .05 : 'F',
       .1 : '1',    .2 : '2',   .25 : 'G',    .3 : '3',    .4 : '4',    .5 : '5',
       .6 : '6',    .7 : '7',   .75 : 'H',    .8 : '8',    .9 : '9',   .95 : 'T',
      .96 : 'U',   .98 : 'V',   .99 : 'W',  .996 : 'X',  .998 : 'Y', .0013 : 'J',
    .0228 : 'K', .1587 : 'L',  -0.5 : 'M', .8413 : 'N', .9772 : 'P', .9987 : 'Q',
     -1.0 : 'Z'}

PROBABILITY_VALUES = {value : key for key, value in PROBABILITY_CODES.items()}

SEND_CODES = {
    "AD" : ("ADZZZZZ", False), "AT" : ("ATD",     False), "AU" : ("AUD",     False), "AW" : ("AWD",     False), "EA" : ("EAD",     False),
    "EM" : ("EMD",     False), "EP" : ("EPD",     False), "ER" : ("ERD",     False), "ET" : ("ETD",     False), "EV" : ("EVD",     False),
    "HN" : ("HGIRZNZ", False), "HX" : ("HGIRZXZ", False), "HY" : ("HGIRZZZ", True) , "LC" : ("LCD",     False), "PF" : ("PPTCF",   False),
    "PY" : ("PPDRZZZ", True) , "PP" : ("PPD",     False), "PR" : ("PRD",     False), "QC" : ("QCD",     False), "QN" : ("QRIRZNZ", False),
    "QX" : ("QRIRZXZ", False), "QY" : ("QRIRZZZ", True) , "SF" : ("SFD",     False), "TN" : ("TAIRZNZ", False), "QV" : ("QVZ",     False),
    "RI" : ("RID",     False), "RP" : ("RPD",     False), "RT" : ("RTD",     False), "TC" : ("TCS",     False), "TF" : ("TFS",     False),
    "TH" : ("THS",     False), "TX" : ("TAIRZXZ", False), "UC" : ("UCD",     False), "UL" : ("ULD",     False), "XG" : ("XGJ",     False),
    "XP" : ("XPQ",     False)}


valueUnitsPattern = re.compile("([0-9]+)([a-z]+)", re.I)

datetime_pattern = re.compile("[ :-]")

format_1_pattern = re.compile(
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

def make_shef_value(format_1_output_line: str) -> ShefValue :
  m = format_1_pattern.match(format_1_output_line)
  if not m :
    raise LoaderException(f"Unexpected line from parser: [{line}]")
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
    return datetime(*tuple(map(int, datetime_pattern.split(datetime_str))))

def duration_interval(parameter_code: str) -> timedelta :
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
