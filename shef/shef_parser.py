#!/bin/python3
import argparse, copy, logging, os, re, sys, textwrap, types
from collections import deque
from datetime    import datetime
from datetime    import timedelta
from datetime    import timezone
from io          import BufferedRandom
from io          import StringIO
from io          import TextIOWrapper
from pathlib     import Path
from typing      import Any
from typing      import Optional
from typing      import TextIO
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
| 1.0.0 | 28May2024 | MDP | Initial version                                                         |
+-------+-----------+-----+-------------------------------------------------------------------------+
| 1.0.1 | 28May2024 | MDP | Mods to pass mypy type checks                                           |
+-------+-----------+-----+-------------------------------------------------------------------------+
| 1.0.2 | 29May2024 | MDP | Reorg, clean up, improve comments, add --make_shefparm                  |
+-------+-----------+-----+-------------------------------------------------------------------------+
| 1.0.3 | 30May2024 | MDP | Bugfixs in info(), warning(), error(), and critcal() methods            |
+-------+-----------+-----+-------------------------------------------------------------------------+
| 1.0.4 | 30May2024 | MDP | More bugfixes after reorg and cleanup                                   |
+-------+-----------+-----+-------------------------------------------------------------------------+
| 1.0.5 | 05Jun2024 | MDP | Add --append_out and --append_log options                               |
+-------+-----------+-----+-------------------------------------------------------------------------+
| 1.1.0 | 06Jun2024 | MDP | Add --loader option to store time series                                |
+-------+-----------+-----+-------------------------------------------------------------------------+
| 1.1.1 | 11Jun2024 | MDP | Add --unload option to have loader write SHEF text                      |
+-------+-----------+-----+-------------------------------------------------------------------------+
| 1.2.0 | 02Jul2024 | MDP | Fix several issues with parsing and interaction with loaders            |
|       |           |     | Loading/unloading/reloading mesonet.shef now yields identical DSS files |
+-------+-----------+-----+-------------------------------------------------------------------------+
| 1.2.1 | 23Jul2024 | MDP | Correct not calling set_ouput() unless using loader                     |
+-------+-----------+-----+-------------------------------------------------------------------------+
| 1.2.2 | 24Jul2024 | MDP | Prevent an error in importing a loader from importing other loaders.    |
+-------+-----------+-----+-------------------------------------------------------------------------+

Authors:
    MDP  Mike Perryman, USACE IWR-HEC
'''

progname     = Path(sys.argv[0]).stem
version      = "1.2.2"
version_date = "24Jul2024"
logger       = logging.getLogger()

def exc_info(e: Exception) -> str :
    '''
    Get exception info for logging
    '''
    info = f"{e.__class__.__name__}: {str(e)}"
    if e.args :
        info += f"args = {e.args}"
    return info

#------------------------------------------------------#
# ensure 'loaders' package is available whether main   #
# script is executed within or outside of shef package #
#                                                      #
# --Either--                                           #
# python3 shefParser                                   #
# --Or--                                               #
# python3 shef\shef_parser.py                          #
#------------------------------------------------------#
script_dir = os.path.dirname(__file__)
if script_dir not in sys.path :
    sys.path.append(script_dir)
#-----------------------------------------------------#
# catalog the SHEF data loaders in the loaders module #
#-----------------------------------------------------#
available_loaders = {}
try :
    from . import loaders
except Exception as e:
    msg = str(e)
    parts = msg.split("|", 1)
    if parts[0] == 'ERROR' :
        logger.error(parts[1])
    elif parts[0] == 'WARNING' :
        logger.warning(parts[1])
    elif parts[0] == 'INFO' :
        logger.info(parts[1])
    else :
        logger.error(exc_info(e))
else :
    if loaders.error_modules :
        logger.warning("Errors loading the following modules:\n\t{}".format("\n\t".join(loaders.error_modules)))
    for loader in [item for item in dir(loaders) if eval(f"loaders.{item}.__class__.__name__") == "module"] :
        exec(f"from loaders import {loader}")
        try :
            opts   = eval(f"{loader}.loader_options")
            desc   = eval(f"{loader}.loader_description")
            vers   = eval(f"{loader}.loader_version")
            clazz  = eval(f"{loader}.loader_class")
            unload = eval(f"{loader}.can_unload")
            available_loaders[loader] = {"option_format" : opts, "description" : desc, "version" : vers, "class" : clazz, "can_unload" : unload}
        except :
            pass

class MonthsDelta :
    '''
    Class to hold a calendar increment

        months = the number of months in the increment
        eom    = whether this is an end-of-month increment
    '''
    def __init__(self, months: int, eom: bool=False)  -> None :
        '''
        MontsDelta constructor
        '''
        self._months = months
        self._eom    = eom

    @property
    def months(self) -> int :
        '''
        Get months count
        '''
        return self._months

    @property
    def eom(self) -> bool :
        '''
        Get end-of-month flag
        '''
        return self._eom

    def __str__(self) -> str :
        return f"months={self._months}, eom={self._eom}"

    def __repr__(self) -> str :
        return f"MonthsDelta({self.__str__()})"

class ShefParser :
    '''
    The parser
    '''
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
        # numeric values are simply numeric equivalent codes
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
        # Not modified by SHEFPARM file
        #
        # Base numeric duration values for durtions specified with DVnxx
        #
        'S' : 7000, 'N' :    0, 'H' : 1000, 'D' : 2000, 'M' : 3000, 'Y' : 4000}

    TZ_NAMES = {
        #
        # Not modified by SHEFPARM file
        #
        'J'  : "PRC",                              # China

        "HS" : "US/Hawaii",                        # Hawaiian standard
        "HD" : "US/Hawaii",                        # Hawaiian daylight
        'H'  : "US/Hawaii",                        # Hawaiian local

        "BS" : "Etc/GMT+11",                       # Bering standard       (obsolete, Aleutian Islands now use US/Alaska)
        "BD" : "Etc/GMT+10",                       # Bering daylight       (obsolete, Aleutian Islands now use US/Alaska)
        'B'  : "Pacific/Midway",                   # Bering local          (obsolete, Aleutian Islands now use US/Alaska)

        "LS" : "Etc/GMT+9",                        # Alaskan standard
        "LD" : "Etc/GMT+8",                        # Alaskan daylight
        'L'  : "US/Alaska",                        # Alaskan local

        "YS" : "Etc/GMT+8",                        # Yukon standard        (--shefit_times gives bad times always)
        "YD" : "Etc/GMT+7",                        # Yukon daylight        (--shefit_times gives bad times always)
        'Y'  : "Canada/Yukon",                     # Yukon local           (--shefit_times gives bad times always)

        "PS" : "Etc/GMT+8",                        # Pacific standard
        "PD" : "Etc/GMT+7",                        # Pacific daylight
        'P'  : "US/Pacific",                       # Pacific local

        "MS" : "Etc/GMT+7",                        # Mountain standard
        "MD" : "Etc/GMT+6",                        # Mountain daylight
        'M'  : "US/Mountain",                      # Mountain local

        "CS" : "Etc/GMT+6",                        # Central standard
        "CD" : "Etc/GMT+5",                        # Central daylight
        'C'  : "US/Central",                       # Central

        "ES" : "Etc/GMT+5",                        # Eastern standard
        "ED" : "Etc/GMT+4",                        # Eastern daylight
        'E'  : "US/Eastern",                       # Eastern local

        "AS" : "Etc/GMT+4",                        # Atlantic standard
        "AD" : "Etc/GMT+3",                        # Atlantic daylight
        'A'  : "Canada/Atlantic",                  # Atlantic local

        "NS" : "timedelta(hours=-3, minutes=-30)", # Newfoundland standard
        "ND" : "timedelta(hours=-2, minutes=-30)", # Newfoundland daylight (--shefit_times gives bad times always)
        'N'  : "Canada/Newfoundland",              # Newfoundland local    (--shefit_times gives bad times in summer)

        'Z'  : "UTC"}                              # Zulu

    UTC = ZoneInfo("UTC")

    class Exc(Exception) :
        '''
        Base class for ShefParser exceptions
        '''
        pass

    class InputException(Exc) :
        '''
        Exceptions related to data input
        '''
        pass

    class OutputException(Exc) :
        '''
        Exceptions related to data output
        '''
        pass

    class ParseException(Exc) :
        '''
        Exceptions related to parsing
        '''
        pass

    class DateTimeException(Exc) :
        '''
        Exceptions in ShefParser.DateTime class
        '''
        pass

    class DateTime :
        '''
        Datetime class for use with SHEF
        * accepts and produces 2400 for midnight
        * can be incremented by MonthsDelta
        * can replicate time zone adjustments in NWS program shefit (when time zone is a string)
        '''

        DST_DATES = (
            #
            # DOM of transition for winter->summer and summer->winter for years 1976-2040.
            # Before 2007, months are April/October, afterward months are March/November
            # Used only when time zone is a string.
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
            #
            # Time zone offsets in minutes from UTC.
            # Used only when time zone is a string.
            #
            'Z' :  0,
            'N' :  210, "NS" : 210, "ND" : 210,
            'A' :  240, "AS" : 240, "AD" : 180,
            'E' :  300, "ES" : 300, "ED" : 240,
            'C' :  360, "CS" : 360, "CD" : 300,
            'M' :  420, "MS" : 420, "MD" : 360,
            'P' :  480, "PS" : 480, "PD" : 420,
            'Y' :  540, "YS" : 540, "YD" : 480,
            'L' :  540, "LS" : 540, "LD" : 480,
            'H' :  600, "HS" : 600, "HD" : 600,
            'B' :  660, "BS" : 660, "BD" : 600,
            'J' : -480}

        @staticmethod
        def is_leap(y: int) -> bool :
            '''
            Is year a leap year?
            '''
            return (not bool(y % 4) and bool(y % 100)) or (not bool(y % 400))

        @staticmethod
        def last_day(y: int, m: int) -> int :
            '''
            Get last day of month (year required for February)
            '''
            return 31 if m in (1,3,5,7,8,10,12) else 30 if m in (4,6,9,11) else 29 if ShefParser.DateTime.is_leap(y) else 28

        @staticmethod
        def is_shef_summer_time(y: int, m: int, d: int, h: int, n: int) -> bool :
            '''
            Shefit algorithm for determining whether a date/time is in daylight savings (summer) time.
            Used only when time zone is a string.
            '''
            summer_time = False
            y = max(min(y, 2040), 1976)
            if 1976 <= y <= 2040 and 3 <= m <= 10 :
                dom = ShefParser.DateTime.DST_DATES[y-1976]
                if y < 2007 :
                    months = (4, 10)
                else :
                    months = (3, 11)
                if months[0] < m < months[1] :
                    summer_time = True
                elif m == months[0] and (d > dom[0] or (d == dom[0] and h > 2) or (d == dom[0] and h == 2 and n > 0)) :
                    summer_time = True
                elif m == months[1] and (d < dom[1] or (d == dom[1] and h < 2) or (d == dom[1] and h == 2 and n == 0)) :
                    summer_time = True
            return summer_time

        @staticmethod
        def now(tz: Union[timezone, ZoneInfo, str]) -> "ShefParser.DateTime" :
            '''
            Get current time in specified time zone
            '''
            t = datetime.now()
            return ShefParser.DateTime(t.year, t.month, t.day, t.hour, t.minute, t.second, tzinfo=tz)

        @staticmethod
        def clone(other: "ShefParser.DateTime") -> "ShefParser.DateTime" :
            '''
            Create a copy
            '''
            y, m, d, h, n, s, z = other.year, other.month, other.day, other.hour, other.minute, other.second, other.tzinfo
            if isinstance(other._tzinfo, str) :
                z = other._tzinfo
            return ShefParser.DateTime(y, m, d, h, n, s, tzinfo=z)

        def __init__(self, *args: Any, **kwargs: Any) -> None :
            '''
            DateTime constructor
            '''
            args2   = args[:]
            kwargs2 = copy.deepcopy(kwargs)
            if "tzinfo" in kwargs2 :
                tzinfo = kwargs2["tzinfo"]
            else :
                raise ShefParser.DateTimeException(f"Cannot instantiate {self.__class__.__name__} object without tzinfo")
            #----------------#
            # allow 24:00:00 #
            #----------------#
            adjust = False
            length = len(args2)
            if length > 3 :
                if args2[3] == 24 :
                    if length > 5 and args2[5] != 0 or length > 4 and args2[4] != 0 :
                        raise ShefParser.DateTimeException(f"Non-zero minutes or seconds on hour = 24: [{''.join(args2[3:])}]")
                    adjust = True
                    args2 = args2[:3]+(23,)+args2[4:]
            #------------------#
            # handle time zone #
            #------------------#
            if isinstance(tzinfo, str) :
                del kwargs2["tzinfo"]
                tzinfo = tzinfo.upper()
                if tzinfo not in ShefParser.DateTime.TZ_OFFSETS :
                    raise ShefParser.DateTimeException(f"Invalid SHEF time zone: [{tzinfo}]")
            elif isinstance(tzinfo, (timezone, ZoneInfo)) :
                pass
            else :
                raise ShefParser.DateTimeException(f"Invalid type for tzinfo: [{tzinfo.__class__.__name__}]")
            #-----------------#
            # populate fields #
            #-----------------#
            self._dt       = datetime(*args2, **kwargs2)
            self._tzinfo   = tzinfo
            self._adjusted = adjust
            if self._adjusted :
                self._dt += timedelta(hours=1)
            #------------------------------------------------------------------#
            # test for invalid time (shefit allows 02:00:00 on DST transition) #
            #------------------------------------------------------------------#
            if isinstance(tzinfo, str) :
                #--------------#
                # shefit times #
                #--------------#
                if len(tzinfo) == 1 and tzinfo not in "ZNH" :
                    y, m, d, h, n, s = self._dt.year, self._dt.month, self._dt.day, self._dt.hour, self._dt.minute, self._dt.second
                    if 1976 <= y <= 2040 and m in (3,4) and h == 2 and (n != 0 or s != 0) :
                        dom = ShefParser.DateTime.DST_DATES[y-1976]
                        mo = 4 if y < 2007 else 3
                        if m == mo and d == dom[0] :
                            raise ShefParser.DateTimeException(f"Invalid time: [{self._dt}]. 02:00:01..02:59:59 is not allowed on date of transition to Daylight Saving with time zone [{tzinfo}]")
            else :
                #--------------#
                # normal times #
                #--------------#
                if self._dt.hour == 2 and self._dt.astimezone(ShefParser.UTC).astimezone(tzinfo).hour == 3 :
                    raise ShefParser.DateTimeException(f"Invalid time: [{self._dt}]. 02:00:00..02:59:59 is not allowed on date of transition to Daylight Saving with time zone [{tzinfo}]")

        def is_dst(self) -> bool :
            '''
            Determine whether this object has a daylight saving offset applied
            '''
            dt = self._dt
            if isinstance(self._tzinfo, str) :
                if len(self._tzinfo) == 1 and self._tzinfo not in "ZNH" :
                    return  ShefParser.DateTime.is_shef_summer_time(dt.year, dt.month, dt.day, dt.hour, dt.minute)
                return False
            else :
                return dt.timetuple().tm_isdst == 1

        def to_timezone(self, tz: Union[timezone, ZoneInfo, str]) -> "ShefParser.DateTime" :
            '''
            Create a new object translated to the specified time zone
            '''
            if not isinstance(tz, (timezone, ZoneInfo, str)) :
                raise ShefParser.DateTimeException(f"Invalid time zone type: [{tz.__class__.__name__}]")
            if isinstance(tz, str) :
                tz = tz.upper()
                if tz not in ShefParser.DateTime.TZ_OFFSETS :
                    raise ShefParser.DateTimeException(f"Invalid SHEF time zone: [{tz}]")

            if isinstance(self._tzinfo, (timezone, ZoneInfo)) and isinstance(tz, (timezone, ZoneInfo)) :
                dt = self._dt.astimezone(tz)
            elif isinstance(self._tzinfo, str) and isinstance(tz, str) :
                dt = self._dt
                if tz != self._tzinfo :
                    if self.is_dst() :
                        dt -= timedelta(hours=1)
                    dt += timedelta(minutes=ShefParser.DateTime.TZ_OFFSETS[self._tzinfo])
                    dt -= timedelta(minutes=ShefParser.DateTime.TZ_OFFSETS[tz])
            else :
                type1 = self._tzinfo.__class__.__name__
                type2 = tz.__class__.__name__
                raise ShefParser.DateTimeException(f"Cannot move a DateTime object with a [{type1}] time zone to a [{type2}] time zone")

            rv = ShefParser.DateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, tzinfo=tz)
            return rv

        def add_months(self, months: int, end_of_month: Optional[bool]=False) -> "ShefParser.DateTime" :
            '''
            Add a number of months this object and return result
            '''
            dt = self
            y, m, d, h, n, s, z = dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, self._tzinfo
            islastday = d == ShefParser.DateTime.last_day(y, m)
            if end_of_month and not islastday :
                raise ShefParser.DateTimeException(f"End-of-month interval specified on non-end-of-month date [{dt}]")
            m += months
            while m > 12 :
                y += 1
                m -= 12
            while m < 1 :
                y -= 1
                m += 12
            if islastday :
                if end_of_month :
                    #--------------------------#
                    # set to last day of month #
                    #--------------------------#
                    dt = ShefParser.DateTime(y, m, ShefParser.DateTime.last_day(y, m), h, n, s, tzinfo=z)
                else :
                    #------------------------------------#
                    # don't set beyond last day of month #
                    #------------------------------------#
                    dt = ShefParser.DateTime(y, m, min(d, ShefParser.DateTime.last_day(y, m)), h, n, s, tzinfo=z)
            else :
                dt = ShefParser.DateTime(y, m, d, h, n, s, tzinfo=z)
            return dt

        def replace(
                self,
                year:   Optional[int] = None,
                month:  Optional[int] = None,
                day:    Optional[int] = None,
                hour:   Optional[int] = None,
                minute: Optional[int] = None,
                second: Optional[int] = None,
                tzinfo: Optional[Union[timezone, ZoneInfo, str]] = None) -> "ShefParser.DateTime" :
            '''
            Replace component values
            '''
            y = year   if year   else self.year
            m = month  if month  else self.month
            d = day    if day    else self.day
            h = hour   if hour   else self.hour
            n = minute if minute else self.minute
            s = second if second else self.second
            z = tzinfo if tzinfo else self._tzinfo

            adjust = False
            if h == 24 :
                if not (n == 0 and s == 0) :
                    raise ShefParser.DateTimeException("Cannot set hour to 24 with non-zero minute or second")
                adjust = True
                h = 23

            self._dt = self._dt.replace(year=y, month=m, day=d, hour=h, minute=n, second=s, tzinfo=None if isinstance(z, str) else z)
            self._tzinfo = z
            self._adjusted = adjust
            if self._adjusted :
                self._dt += timedelta(hours=1)
            dt = self
            return ShefParser.DateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, tzinfo=self._tzinfo)

        def __add__(self, other : Union[None, timedelta, MonthsDelta]) -> "ShefParser.DateTime" :
            '''
            Add a time increment (timedelta) or calendar increment (MonthsDelta)
            '''
            if not other :
                dt = self._dt
            elif isinstance(other, timedelta) :
                dt = self._dt.__add__(other)
            elif isinstance(other, MonthsDelta) :
                dt = self.add_months(other.months, other.eom)._dt
            else :
                raise ShefParser.DateTimeException(f"Invalid type to add: [{other.__class__.__name__}]")
            rv = ShefParser.DateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, tzinfo=self._tzinfo)
            if self._adjusted and dt.hour == dt.minute == dt.second == 0 :
                rv._adjusted = True
            return rv

        def __sub__(self, other : Union[None, timedelta, MonthsDelta, "ShefParser.DateTime"]) -> Union[timedelta, "ShefParser.DateTime"] :
            '''
            Subtract a time increment (timedelta), calendar increment (MonthsDelta), or datetime (DateTime).
            Returns a timedelta if subtracting a DateTime, otherwise returns a DateTime
            '''
            if not other :
                dt = self._dt
            elif isinstance(other, timedelta) :
                dt = self._dt.__sub__(other)
            elif isinstance(other, MonthsDelta) :
                dt = self.add_months(-other.months, other.eom)._dt
            elif isinstance(other, ShefParser.DateTime) :
                dt1 = self.astimezone('Z' if isinstance(self._tzinfo, str) else ShefParser.UTC)
                dt1 = datetime(dt1.year, dt1.month, dt1.day, dt1.hour, dt1.minute, dt1.second)
                dt2 = other.astimezone('Z' if isinstance(self._tzinfo, str) else ShefParser.UTC)
                dt2 = datetime(dt2.year, dt2.month, dt2.day, dt2.hour, dt2.minute, dt2.second)
                return dt1 - dt2
            else :
                raise ShefParser.DateTimeException(f"Invalid type to add: [{other.__class__.__name__}]")
            return ShefParser.DateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, tzinfo=self._tzinfo)

        def __lt__(self, other: "ShefParser.DateTime") -> bool :
            '''
            Compare to another datetime
            '''
            utc = 'Z' if isinstance(self._tzinfo, str) else ShefParser.UTC
            return self.astimezone(utc)._dt < other.astimezone(utc)._dt

        def __le__(self, other: "ShefParser.DateTime") -> bool :
            '''
            Compare to another datetime
            '''
            utc = 'Z' if isinstance(self._tzinfo, str) else ShefParser.UTC
            return self.astimezone(utc)._dt <= other.astimezone(utc)._dt

        def __eq__(self, other: object) -> bool :
            '''
            Compare to another datetime
            '''
            if not isinstance(other, ShefParser.DateTime) :
                raise ShefParser.DateTimeException(f"Expected object type to be ShefParser.DateTime, got {other.__class__.__name__}")
            utc = 'Z' if isinstance(self._tzinfo, str) else ShefParser.UTC
            return self.astimezone(utc)._dt == other.astimezone(utc)._dt

        def __ge__(self, other: "ShefParser.DateTime") -> bool :
            '''
            Compare to another datetime
            '''
            utc = 'Z' if isinstance(self._tzinfo, str) else ShefParser.UTC
            return self.astimezone(utc)._dt >= other.astimezone(utc)._dt

        def __gt__(self, other: "ShefParser.DateTime") -> bool :
            '''
            Compare to another datetime
            '''
            utc = 'Z' if isinstance(self._tzinfo, str) else ShefParser.UTC
            return self.astimezone(utc)._dt > other.astimezone(utc)._dt

        def __str__(self) -> str :
            '''
            Get a string representation
            '''
            dt = self._dt.replace(tzinfo=None)
            if self._adjusted and dt.hour == dt.minute == dt.second == 0 :
                # show 24:00:00 instead of 00:00:00
                s = str(dt - timedelta(hours=1))
                return s[:11] + "24" + s[13:] + f" tzinfo={self._tzinfo}"
            return dt.__str__() + f" tzinfo={self._tzinfo}"

        def __repr__(self) -> str :
            '''
            Get a string representation
            '''
            return f"ShefParser.DateTime({self.__str__()})"

        def __getattribute__(self, name: str) -> Any :
            '''
            Manage retrieval of members
            '''
            if name in ("_dt", "_adjusted", "is_dst", "to_timezone", "add_months", "replace", "_tzinfo", "__class__", "__str__", "__repr__") :
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

    class DotBHeaderParameterInfo :
        '''
        Holds parameter info from the header of a .B message
        '''
        def __init__(
                self,
                parser:              "ShefParser",
                parameter_code:      str,
                orig_parameter_code: str,
                obstime:             Union[None, "ShefParser.DateTime"],
                use_prev_7am:        bool,
                relativetime:        Union[None, timedelta, MonthsDelta],
                createtime_str:      Union[None, str],
                createtime:          Union[None, "ShefParser.DateTime"],
                units:               str,
                qualifier:           str,
                duration_unit:       str,
                duration_value:      Union[None, int]) -> None :
            '''
            DotBHeaderParameterInfo constructor
            '''

            if not parameter_code or len(parameter_code) != 7 :
                raise ShefParser.ParseException(f"Invalid parameter code: [{parameter_code}]")

            if not obstime :
                raise ShefParser.ParseException("Missing observation time")

            if use_prev_7am :
                if relativetime :
                    raise ShefParser.ParseException("Cannot use relative date/time offsets with send codes QY, HY, or PY")
                if obstime.tzinfo == ('Z' if parser.shefit_times else ShefParser.UTC) :
                    raise ShefParser.ParseException("Cannot use Zulu/UTC time zone with send codes QY, HY, or PY")

            self._parser              = parser
            self._parameter_code      = parameter_code
            self._orig_parameter_code = orig_parameter_code
            self._obstime             = ShefParser.DateTime.clone(obstime)
            self._use_prev_7am        = use_prev_7am
            self._relativetime        = copy.deepcopy(relativetime)
            self._createtime          = createtime
            self._units               = units
            self._qualifier           = qualifier
            self._duration_unit       = duration_unit
            self._duration_value      = duration_value

            if not createtime :
                dt = obstime
                if relativetime :
                    dt = dt.astimezone('Z' if parser.shefit_times else ShefParser.UTC) + relativetime
                self._createtime = parser.get_creation_time(dt, createtime_str)

        @property
        def qualifier(self) -> str :
            '''
            Get the data qualifier
            '''
            return self._qualifier

        @property
        def parameter_code(self) -> str :
            '''
            Get the parameter code
            '''
            return self._parameter_code

        @property
        def pe_code(self) -> str :
            '''
            Get the physical element code
            '''
            return self._parameter_code[:2]

        @property
        def orig_parameter_code(self) -> str :
            '''
            Get the parameter code as specified in the message
            '''
            return self._orig_parameter_code

        @property
        def obstime(self) -> "ShefParser.DateTime" :
            '''
            Get the observation time
            '''
            return self._obstime

        @property
        def units(self) -> str :
            '''
            Get the units system
            '''
            return self._units

        @property
        def createtime(self) -> Union[None, "ShefParser.DateTime"] :
            '''
            Get the creation time
            '''
            return self._createtime

        @property
        def relativetime(self) -> Union[None, timedelta, MonthsDelta] :
            '''
            Get the relative time
            '''
            return self._relativetime

        @property
        def parser(self) -> "ShefParser" :
            '''
            Get the parser that created this object
            '''
            return self._parser

        def get_output_record(
                self,
                revised:                 bool,
                msg_source:              str,
                location:                str,
                obstime_override:        "ShefParser.DateTime",
                relativetime_override:   "ShefParser.DateTime",
                createtime_override_str: str,
                units_override:          str,
                duration_unit:           str,
                duration_value:          int,
                value:                   float,
                qualifier:               str,
                comment:                 str) -> "ShefParser.OutputRecord" :
            '''
            Create an OutputRecord from the positional info in the header and the info in the body
            '''
            parser = self._parser
            if self._use_prev_7am :
                if obstime_override and obstime_override._tzinfo == ('Z' if parser.shefit_times else ShefParser.UTC) :
                    raise ShefParser.ParseException("Cannot use Zulu/UTC time zone with send codes QY, HY, or PY")
                if relativetime_override :
                    raise ShefParser.ParseException("Cannot use relative date/time offsets with send codes QY, HY, or PY")

            shift = relativetime_override if relativetime_override is not None else self.relativetime
            obst = obstime_override if obstime_override else self.obstime
            #---------------------------------------------------------------------------#
            # adjust observation time (this order of operations is from shefit program) #
            #---------------------------------------------------------------------------#
            # 1 - adjust to 7am or shift year, month, day (in local time)
            if self._use_prev_7am :
                if obst.hour < 7 :
                    obst += timedelta(days=-1) # dont use "obst -1 timedelta(days=1)" - it causes mypy to complain
                obst = obst.replace(hour=7, minute=0, second=0)
            elif shift :
                if isinstance(shift, MonthsDelta) :
                    obst = obst.add_months(shift.months)
                else :
                    # DON'T use shift.days!!! If shift is negative it will be incorrect as shown below.
                    # >>> timedelta(seconds=-3600).days
                    # -1
                    # >>> timedelta(seconds=-3600).total_seconds()
                    # -3600.0
                    seconds = shift.total_seconds()
                    days = abs(seconds) // 86400 * (-1 if seconds < 0 else 1)
                    obst += timedelta(days=days)
            # 2 - convert to UTC, but keep timezone for later use
            zi = obst.tzinfo
            obst = obst.astimezone('Z' if parser.shefit_times else ShefParser.UTC)
            # 3 - adjust to shift hour, minutes, and seconds
            if shift is not None and isinstance(shift, timedelta):
                # DON'T use shift.seconds!!! If shift is negative it will be incorrect as shown below.
                # >>> timedelta(seconds=-3600).seconds
                # 82800
                # >>> timedelta(seconds=-3600).total_seconds()
                # -3600.0
                seconds = seconds=shift.total_seconds() % (86400 if shift.total_seconds() > 0 else -86400)
                obst += timedelta(seconds=seconds)
            #----------------------------------#
            # done adjusting observation time, #
            #----------------------------------#
            if createtime_override_str :
                creat = parser.get_creation_time(obst.astimezone(zi), createtime_override_str)
            else :
                creat = self.createtime
            if creat :
                creat = creat.astimezone('Z' if parser.shefit_times else ShefParser.UTC)
            if units_override == "SI" :
                value = parser.get_english_unit_value(value, self._parameter_code)

            return ShefParser.OutputRecord(
                parser,
                location,
                self.parameter_code,
                self.orig_parameter_code,
                obst,
                creat,
                value,
                qualifier if qualifier else self.qualifier,
                revised,
                duration_unit if duration_unit else self._duration_unit,
                duration_value if duration_unit else self._duration_value,
                msg_source,
                0,
                comment)

        def __str__(self) -> str :
            '''
            Get a string representation of the DotBHeaderParameterInfo object
            '''
            if self._relativetime :
                return f"{self._parameter_code} @ {self._obstime.astimezone('Z' if self.parser.shefit_times else ShefParser.UTC)} ({self._relativetime})"
            else :
                return f"{self._parameter_code} @ {self._obstime.astimezone('Z' if self.parser.shefit_times else ShefParser.UTC)}"

        def __repr__(self) -> str :
            '''
            Get a string representation of the DotBHeaderParameterInfo object
            '''
            return f"ShefParser.DotBParameterInfo({self.__str__()})"

    class OutputRecord :
        '''
        Parsed value, ready for output in various formats
        '''
        SHEFIT_TEXT_V1 = "SHEFIT-TEXT1"
        SHEFIT_TEXT_V2 = "SHEFIT-TEXT2"

        OUTPUT_FORMATS = [SHEFIT_TEXT_V1, SHEFIT_TEXT_V2]

        def __init__(
                self,
                parser:              "ShefParser",
                location:            str,
                parameter_code:      str,
                orig_parameter_code: str,
                obstime:             "ShefParser.DateTime",
                create_time:         Union[None, "ShefParser.DateTime", str] = None,
                en_value:            float = -9999.,
                qualifier:           str = 'Z',
                revised:             bool = False,
                duration_unit:       str  = 'Z',
                duration_value:      Optional[int]  = None,
                message_source:      Optional[str] = None,
                time_series_code:    int = 0,
                comment:             Optional[str] = None) -> None :
            '''
            OutputRecord constuctor
            '''
            if not location :
                raise ShefParser.OutputException("Location must not be empty")
            if not 3 <= len(location) <= 8 :
                raise ShefParser.OutputException(f"Location [{location}] must be 3 to 8 characters in length")
            if not parameter_code :
                raise ShefParser.OutputException("Parameter code must not be empty")
            if len(parameter_code) != 7 :
                raise ShefParser.OutputException(f"Parameter code [{parameter_code}] must be 7 characters in length")
            if not obstime :
                raise ShefParser.OutputException("Observed time must not be empty")

            self._parser               = parser
            self._location             = location
            self._observation_time     = obstime
            self._parameter_code       = parameter_code
            self._orig_parameter_code  = orig_parameter_code
            self._value                = en_value
            self._qualifier            = qualifier
            self._revised              = revised
            self._duration_unit        = duration_unit
            self._duration_value       = duration_value
            self._message_source       = message_source
            self._time_series_code     = time_series_code
            self._comment              = comment

            self._creation_time: Union[None, ShefParser.DateTime] = None
            if create_time and isinstance(create_time, str) :
                self._creation_time = parser.get_creation_time(obstime, create_time)
            elif isinstance(create_time, ShefParser.DateTime) :
                self._creation_time = create_time
            self._observation_time = self._observation_time.astimezone('Z' if parser.shefit_times else ShefParser.UTC)
            if self._creation_time :
                self._creation_time = self._creation_time.astimezone('Z' if parser.shefit_times else ShefParser.UTC)

        def format(self, fmt: str) -> str :
            '''
            Generate the output in the specified format
            '''
            if fmt == ShefParser.OutputRecord.SHEFIT_TEXT_V1 :
                #----------------------------#
                # shefit -1 format (default) #
                #----------------------------#
                buf = StringIO()
                buf.write(self.location.ljust(10))
                buf.write(f"{self.obstime.year:4d}-")
                buf.write(f"{self.obstime.month:02d}-")
                buf.write(f"{self.obstime.day:02d} ")
                buf.write(f"{self.obstime.hour:02d}:")
                buf.write(f"{self.obstime.minute:02d}:")
                buf.write(f"{self.obstime.second:02d}  ")
                if self.create_time :
                    buf.write(f"{self.create_time.year:4d}-")
                    buf.write(f"{self.create_time.month:02d}-")
                    buf.write(f"{self.create_time.day:02d} ")
                    buf.write(f"{self.create_time.hour:02d}:")
                    buf.write(f"{self.create_time.minute:02d}:")
                    buf.write(f"{self.create_time.second:02d}  ")
                else :
                    buf.write("0000-00-00 00:00:00  ")
                if len(self.orig_parameter_code) == 7 :
                    if self.orig_parameter_code[3] == 'Z' :
                        # replace Z type code
                        buf.write(f"{self.orig_parameter_code[:3]}R{self._orig_parameter_code[4:]}")
                    else :
                        buf.write(self.orig_parameter_code)
                else :
                    output_full_parameter = False
                    if len(self.orig_parameter_code) == 7 :
                        output_full_parameter = True
                    else :
                        pe_code = self.orig_parameter_code[:2]
                        try :
                            param_code = self.parser._send_codes[pe_code][0]
                            output_full_parameter = len(param_code) == 7
                        except KeyError :
                            pass
                        if output_full_parameter :
                            buf.write(self.parameter_code)
                        else :
                            buf.write(f"{self.parameter_code[:-1]} ")
                buf.write(f"{self.value:15.4f}")
                buf.write(f" {self.qualifier}")
                buf.write(f"{self.probability_code_number:9.3f}  ")
                buf.write(f"{self.duration_code_number:04d}")
                buf.write(f"{self.revised:2d}")
                buf.write(f"{self.time_series_code:2d}")
                buf.write("  ")
                buf.write(self.message_source.ljust(8) if self.message_source else "        ")
                buf.write("  ")
                if self.comment :
                    buf.write(f'"{self.comment[1:-1]}"')
                else :
                    buf.write('" "')
                rec = buf.getvalue()
                buf.close()
            elif fmt == ShefParser.OutputRecord.SHEFIT_TEXT_V2 :
                #------------------#
                # shefit -2 output #
                #------------------#
                buf = StringIO()
                buf.write(self.location.ljust(8))
                buf.write(f"{self.obstime.year:4d}")
                buf.write(f"{self.obstime.month:2d}")
                buf.write(f"{self.obstime.day:2d}")
                buf.write(f"{self.obstime.hour:2d}")
                buf.write(f"{self.obstime.minute:2d}")
                buf.write(f"{self.obstime.second:2d}")
                buf.write(' ')
                if self.create_time :
                    buf.write(f"{self.create_time.year:4d}")
                    buf.write(f"{self.create_time.month:2d}")
                    buf.write(f"{self.create_time.day:2d}")
                    buf.write(f"{self.create_time.hour:2d}")
                    buf.write(f"{self.create_time.minute:2d}")
                    buf.write(f"{self.create_time.second:2d}")
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
                buf.write(f"{self.time_series_code}")
                if self.comment :
                    buf.write(f'\n        "{self.comment[1:-1]}"')
                rec = buf.getvalue()
                buf.close()
            else :
                raise ShefParser.OutputException(f'Invalid output format: "[{fmt}]"')
            return rec

        @property
        def parser(self) -> "ShefParser" :
            '''
            Get the ShefParser object that created this record
            '''
            return self._parser

        @property
        def location(self) -> str:
            '''
            Get the location
            '''
            return self._location

        @property
        def obstime(self) -> "ShefParser.DateTime" :
            '''
            Get the observation time
            '''
            return self._observation_time

        @property
        def create_time(self) -> Union[None, "ShefParser.DateTime"] :
            '''
            Get the creation time
            '''
            return self._creation_time

        @property
        def physical_element_code(self) -> str :
            '''
            Get the physical element code
            '''
            return self._parameter_code[:2]

        @property
        def duration_code(self) -> str :
            '''
            Get the parameter code
            '''
            return self._parameter_code[2]

        @property
        def duration_code_number(self) -> int :
            '''
            Get the numeric value of the duration code
            '''
            if self.duration_code == 'V' :
                if self._duration_unit and self._duration_value is not None and self._duration_unit != 'Z' :
                    return ShefParser.DURATION_VARIABLE_CODES[self._duration_unit] + self._duration_value
                raise ShefParser.OutputException(f"No duration specified for parameter code [{self.parameter_code}]")
            else :
                if self.duration_code == 'Z' :
                    if self.physical_element_code in ShefParser.DEFAULT_DURATION_CODES :
                        return ShefParser.DURATION_CODES[ShefParser.DEFAULT_DURATION_CODES[self.physical_element_code]]
                    else :
                        return ShefParser.DURATION_CODES[self.duration_code]
                else :
                    return ShefParser.DURATION_CODES[self.duration_code]

        @property
        def parameter_code(self) -> str :
            '''
            Get the parameter code
            '''
            return self._parameter_code

        @property
        def type_code(self) -> str :
            '''
            Get the type code (1st char of type & source code)
            '''
            return self._parameter_code[3]

        @property
        def source_code(self) -> str :
            '''
            Get the source code (2nd char of the type & source code)
            '''
            return self._parameter_code[4]

        @property
        def extremum_code(self) -> str :
            '''
            Get the extremum code
            '''
            return self._parameter_code[5]

        @property
        def probability_code(self) -> str :
            '''
            Get the probability code
            '''
            return self._parameter_code[6]

        @property
        def probability_code_number(self) -> float :
            '''
            Get the numeric value of the probability code
            '''
            return float(ShefParser.PROBABILITY_CODES[self._parameter_code[6]])

        @property
        def orig_parameter_code(self) -> str :
            '''
            Get the parameter code as specified in the message
            '''
            return self._orig_parameter_code

        @property
        def value(self) -> float :
            '''
            Get the value
            '''
            return self._value

        @property
        def qualifier(self) -> str :
            '''
            Get the data qualifier (default or otherwise)
            '''
            return self._qualifier

        @property
        def revised(self) -> bool :
            '''
            Is the revision flag set?
            '''
            return self._revised

        @property
        def message_source(self) -> Union[None, str] :
            '''
            Get the source of the .B message
            '''
            return self._message_source

        @property
        def time_series_code(self) -> int :
            '''
            Get the time series code (0=not time series, 1=first value, 2=other value)
            '''
            return self._time_series_code

        @property
        def comment(self) -> Union[None, str] :
            '''
            Get the retained comment
            '''
            return self._comment

    @staticmethod
    def write_shefparm_data(output_object: Union[TextIO, str]) -> None :
        '''
        Write SHEFPARM data to the specified output
        '''
        out = None
        if isinstance(output_object, (BufferedRandom, TextIOWrapper)) :
            out = output_object
        elif isinstance(output_object, str) :
            out = open(output_object, "w")
        else :
            raise ShefParser.OutputException(f"Expected BufferedRandom or str object, got [{output_object.__class__.__name__}]")
        out.write(f"$\n$ This file generated on {str(datetime.now())[:-7]} by {progname} version {version} ({version_date})\n$\n")
        out.write("SHEFPARM\n")
        out.write("*1                      PE CODES AND CONVERSION FACTORS\n")
        # get the non-send codes
        conversions = dict(ShefParser.PE_CONVERSIONS)
        # add in the send codes
        for code in ShefParser.SEND_CODES :
            conversions[code] = conversions[ShefParser.SEND_CODES[code][0][:2]]
        for code in sorted(conversions) :
            out.write(f"{code} {conversions[code]}\n")
        out.write("*2                      DURATION CODES AND ASSOCIATED VALUES\n")
        for code in sorted(ShefParser.DURATION_CODES) :
            out.write(f"{code}   {ShefParser.DURATION_CODES[code]:04d}\n")
        out.write("*3                      TS CODES\n")
        for code in sorted(ShefParser.TS_CODES) :
            out.write(f"{code}  1\n")
        out.write("*4                      EXTREMUM CODES\n")
        for code in sorted(ShefParser.EXTREMUM_CODES) :
            out.write(f"{code}   1\n")
        out.write("*5                      PROBILITY CODES AND ASSOCIATED VALUES\n")
        for code in sorted(ShefParser.PROBABILITY_CODES) :
            out.write(f"{code} {ShefParser.PROBABILITY_CODES[code]}\n")
        out.write("*6                      SEND CODES OR DURATION DEFAULTS OTHER THAN I\n")
        for code in sorted(ShefParser.SEND_CODES) :
            out.write(f"{code} {ShefParser.SEND_CODES[code][0].ljust(7)}")
            out.write("  1\n" if ShefParser.SEND_CODES[code][1] else "\n")
        out.write("*7                      DATA QUALIFIER CODES\n")
        for code in sorted(ShefParser.QUALIFIER_CODES) :
            out.write(f"{code}\n")
        out.write("**                      MAX NUMBER OF ERRORS (I4 FORMAT)\n 500\n**\n")
        if isinstance(output_object, str) :
            out.close()

    @staticmethod
    def hide_quoted_whitespace(s: str) -> str :
        '''
        Replaces whitespace chars (' ', '\t') in quotes with non-whitespace characters (NUL, SOH)
        to allow split() to not break quotes.
        '''
        NUL, SOH = chr(0), chr(1)
        quote = None
        with StringIO() as buf :
            for c in s :
                if quote :
                    if c == ' ' :
                        buf.write(NUL)
                    elif c == '\t' :
                        buf.write(SOH)
                    else :
                        buf.write(c)
                    if c == quote :
                        quote = None
                else :
                    buf.write(c)
                    if c in "'\"" : quote = c
            return buf.getvalue()

    @staticmethod
    def unhide_quoted_whitespace(s: str) -> str :
        '''
        Restored replaced whitespace chars in quotes with original characters
        '''
        NUL, SOH = chr(0), chr(1)
        with StringIO() as buf :
            for c in s :
                if c == NUL :
                    buf.write(' ')
                elif c == SOH :
                    buf.write('\t')
                else :
                    buf.write(c)
            return buf.getvalue()
    def __init__(self, output_format: int, shefparm_pathname: Union[None, str]=None, shefit_times: bool=False, reject_problematic: bool=False) :
        '''
        ShefParser Constructor
        '''
        self._shefparm_pathname:    Union[None, str] = shefparm_pathname
        self._output_format:        str  = ShefParser.OutputRecord.OUTPUT_FORMATS[output_format-1]
        self._shefit_times:         bool = shefit_times
        self._reject_problematic:   bool = reject_problematic
        self._message:              Union[None, str] = None
        self._message_location:     Union[None, int] = None
        self._log_line_len:         int = 100
        self._previous_raw_message: Union[None, str] = None
        self._raw_message:          Union[None, str] = None
        #-----------------------------#
        # initialize program defaults #
        #-----------------------------#
        self._pe_conversions              = copy.deepcopy(ShefParser.PE_CONVERSIONS)
        self._send_codes                  = copy.deepcopy(ShefParser.SEND_CODES)
        self._addional_pe_codes:          set[str] = set() # any extra PE codes recognized by a loader
        self._duration_codes              = copy.deepcopy(ShefParser.DURATION_CODES)
        self._ts_codes                    = copy.deepcopy(ShefParser.TS_CODES)
        self._extremum_codes              = copy.deepcopy(ShefParser.EXTREMUM_CODES)
        self._probability_codes           = copy.deepcopy(ShefParser.PROBABILITY_CODES)
        self._qualifier_codes             = copy.deepcopy(ShefParser.QUALIFIER_CODES)
        self._max_error_count:            int  = 1500 # May be modified by SHEFPARM file
        self._error_count:                int = 0
        self._warning_count:              int = 0
        self._messages_with_error_count:  int = 0
        self._messages_with_warning_count:int = 0
        self._last_message_with_error:    Union[None, str] = None
        self._last_message_with_warning:  Union[None, str] = None
        self._default_duration_code       = 'I' # May not be modified by SHEFPARM file
        self._default_type_code           = 'R' # May not be modified by SHEFPARM file
        self._default_source_code         = 'Z' # May not be modified by SHEFPARM file
        self._default_extremum_code       = 'Z' # May not be modified by SHEFPARM file
        self._default_probability_code    = 'Z' # May not be modified by SHEFPARM file
        self._input:                      Union[None, TextIOWrapper] = None
        self._input_name:                 Union[None, str] = None
        self._line_number                 = 0
        self._output:                     Union[None, BufferedRandom, TextIOWrapper] = None
        self._output_name:                Union[None, str] = None
        self._input_lines:                deque = deque()
        self._msg_start_pattern           = re.compile(r"^\.[ABE]R?\s", re.I)
        self._msg_continue_patterns       = {'A' : (re.compile(r"^\.A\d{1,2}", re.I), re.compile(r"^\.AR?\d{1,2}", re.I)),
                                             'E' : (re.compile(r"^\.E\d{1,2}", re.I), re.compile(r"^\.ER?\d{1,2}", re.I)),
                                             'B' : (re.compile(r"^\.B\d{1,2}", re.I), re.compile(r"^\.BR?\d{1,2}", re.I))}
        self._positional_fields_pattern    = re.compile(
                                            # 1 = location id
                                            # 2 = date-time
                                            # 6 = time zone
                                            #                 1           23       4
                                               r"^\.[AEB]R?\s+(\w{3,8})\s+((\d{2})?(\d{2})?\d{4})" \
                                            #    5   6
                                               r"(\s+([NAECMPYLHB][DS]?|[JZ]))?\s+?", re.I|re.M)
        self._dot_b_header_lines_pattern  = re.compile(r"^.B(R?)\s.+?$(\n^.B\1?\d\s.+?$)*", re.I|re.M)
        self._dot_b_body_line_pattern     = re.compile(r"^(\w{3,8})\s+\S+.*$")
        self._obs_time_pattern            = re.compile(
                                            # 1 = date/time
                                            # 2 = date/time code
                                            # 3 = date/time value
                                            #    12                           3
                                               r"(D[SNHDMYJT]|DR[SNHDMYE][+-]?)(\d+)", re.I)
        self._multiple_obs_time_pattern   = re.compile(
                                            # 1 = first date/time
                                            # 2 = first date/time code
                                            # 3 = first date/time value
                                            # 4 = next data
                                            # 5 = separator
                                            # 6 = next date/time code
                                            # 7 = next date/time value
                                            #    12                            3     45      6                           7
                                               r"((D[SNHDMYJT]|DR[SNHDMYE][+-]?)(\d+))((\s+|/)(D[SNHDMYJT]|DR[SNHDMYE][+-])(\d+))+?", re.I)
        self._obs_time_pattern2           = re.compile(
                                            # 1 = first date/time
                                            # 2 = first date/time code
                                            # 3 = first date/time value
                                            # 4 = next data
                                            # 5 = next date/time code
                                            # 6 = next date/time value
                                            #    12                        3          4 5                        6
                                               r"((D[SNHDMYJT]|DR[SNHDMYE])([+-]?\d+))(@(D[SNHDMYJT]|DR[SNHDMYE])([+-]?\d+))*?", re.I)
        self._create_time_pattern         = re.compile(r"DC\d+", re.I)
        self._unit_system_pattern         = re.compile(r"DU[ES]", re.I)
        self._data_qualifier_pattern      = re.compile(r"DQ.", re.I)
        self._duration_code_pattern       = re.compile(r"(DV[SNHDMY]\d{1,2}|DVZ)", re.I)
        self._parameter_code_pattern      = re.compile(r"^[A-CE-IL-NP-Y][A-Z](([A-Z]([A-Z0-9]{2})?[A-Z]{1,2})?)?", re.I)
        self._interval_pattern            = re.compile(r"DI[SNHDMEY][+-]?\d{1,2}", re.I)
        self._value_pattern               = re.compile(
                                           # 1 = value
                                           # 2 = numeric value
                                           # 3 = trace value
                                           # 4 = missing valule
                                           # 5 = value qualifier
                                           #     1 2                              3    4                 5
                                               r"(^([+-]?(?:\d+(?:\.\d*)?|\.\d+))|(T+)|([M.+-]+|\+{1,2}))([A-Z]?$)", re.I)
        self._retained_comment_pattern    = re.compile(r"(([\"']).+(\2|$))")
        self._replacement_strip_pattern   = re.compile("^["+chr(0)+chr(9)+"]+|["+chr(0)+chr(9)+"]+$")
        self._replacement_split_pattern   = re.compile('['+chr(0)+chr(9)+']')

        if self._shefparm_pathname :
            self.read_shefparm(self._shefparm_pathname)
            
        self._duration_ids = {}
        for key in self._duration_codes :
            self._duration_ids[self._duration_codes[key]] = key

    @property
    def shefit_times(self) -> bool :
        '''
        Get whether the parser is using shefit-style datetime operations
        '''
        return self._shefit_times

    def read_shefparm(self, shefparm_pathname: str) -> None :
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
            self.critical(f"No such file: [{shefparm_pathname}]")
        #------------------------#
        # read and process lines #
        #------------------------#
        with p.open() as f : lines = f.read().strip().split('\n')
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
                except : self.critical(f"{shefparm_pathname}: Invalid line at line {i+1}: [{line}]")
                if section not in section_info :
                    self.critical(f'{shefparm_pathname}: Unexpected section "[{section}]" at line {i+1}')
            elif section is not None :
                #--------------------------------------#
                # process line for appropriate section #
                #--------------------------------------#
                func = section_info[section]["func"]
                assert isinstance(func, types.MethodType)
                func(line)
                section_info[section]["visited"] = True
            else :
                #------------#
                # unexpected #
                #------------#
                self.critical(f'{shefparm_pathname}: No section for line {i+1} [{line}]')
        #------------------------------------#
        # output info about missing sections #
        #------------------------------------#
        for section in sorted(section_info) :
            if not section_info[section]["visited"] :
                self.info(f'{shefparm_pathname} does not contain section [{section}] ({section_info[section]["name"]})')

    def set_pe_code(self, line: str) -> None :
        '''
        Update PE codes from SHEFPARM line
        '''
        key, value = line[0:2], float(line[3:23].strip())
        if key not in self._pe_conversions :
            if key  not in self._send_codes :
                self.info(f"{self._shefparm_pathname}: Adding non-standard physical element code [{key}] with conversion factor [{value}]")
        else:
            if 0.9999 <= value / self._pe_conversions[key] <= 1.001 :
                pass
            else :
                self.warning(f"{self._shefparm_pathname}: Updating standard physical element code [{key}] conversion factor from [{self._pe_conversions[key]}] to [{value}]")
        self._pe_conversions[key] = value

    def get_recognized_pe_codes(self) -> set :
        '''
        Return the set of recognized PE codes
        '''
        return set(self._pe_conversions.keys()).union(self._addional_pe_codes)

    def set_additional_pe_codes(self, additional_pe_codes: set) -> None :
        '''
        Add to the set of recognized PE codes
        '''
        recognozed_pe_codes = self.get_recognized_pe_codes()
        for additional_pe_code in [x for x in sorted(additional_pe_codes) if x not in recognozed_pe_codes] :
            self.info(f"PE code [{additional_pe_code}] is now recognized and will not generate any warning messages")
            self._addional_pe_codes.add(additional_pe_code)

    def set_duration_code(self, line: str) -> None :
        '''
        Update Duration codes from SHEFPARM line
        '''
        key, valstr = line[0], line[3:8].strip()
        try :
            value: int = int(valstr)
        except :
            self.critical(f"Cannot use non-integer value [{value}] for duration code [{key}]")
        if key not in self._duration_codes :
            self.info(f"{self._shefparm_pathname}: Adding non-standard duration code [{key}] with numerical value [{value}]")
        elif value != int(self._duration_codes[key]) :
            self.warning(f"{self._shefparm_pathname}: Updating standard duration code [{key}] numerical value from [{self._duration_codes[key]}] to [{value}]")
        self._duration_codes[key] = value

    def set_ts_code(self, line: str) -> None :
        '''
        Update TS codes from SHEFPARM line
        '''
        key, value = line[0:2], int(line[3:5].strip()) if len(line) > 3 else 0
        if value :
            if key not in self._ts_codes :
                self.info(f"{self._shefparm_pathname}: Adding non-standard type-and-source code [{key}]")
                self._ts_codes.add(key)
        else :
            if key in self._ts_codes :
                self.warning(f"{self._shefparm_pathname}: Disabling standard type-and-source code [{key}]")
                self._ts_codes.remove(key)

    def set_extremum_code(self, line: str) -> None :
        '''
        Update Extremum codes from SHEFPARM line
        '''
        key, value = line[0:1], int(line[3:5].strip()) if len(line) > 3 else 0
        if value :
            if key not in self._extremum_codes :
                self.info(f"{self._shefparm_pathname}: Adding non-standard extremum code [{key}]")
                self._extremum_codes.add(key)
        else :
            if key in self._extremum_codes :
                self.warning(f"{self._shefparm_pathname}: Disabling standard extremum code [{key}]")
                self._extremum_codes.remove(key)

    def set_probability_code(self, line: str) -> None :
        '''
        Update Probability codes from SHEFPARM line
        '''
        key, value = line[0], float(line[2:22].strip())
        if key not in self._probability_codes :
            self.info(f"{self._shefparm_pathname}: Adding non-standard probability code [{key}] with conversion factor [{value}]")
        elif value != self._probability_codes[key] :
            self.warning(f"{self._shefparm_pathname}: Updating standard probability code [{key}] conversion factor from [{self._probability_codes[key]}] to [{value}]")
        self._probability_codes[key] = value

    def set_send_code(self, line: str) -> None :
        '''
        Update Send codes from SHEFPARM line
        '''
        key, value = line[0:2], (line[3:10], len(line) > 12 and line[12] == '1')
        if key not in self._send_codes :
            self.info(f"{self._shefparm_pathname}: Adding non-standard send code [{key}] with parmameter [{value[0]}] and use-prev-0700 = [{value[1]}]")
        elif value != self._send_codes[key] :
            cur_val = self._send_codes[key]
            self.warning(
                f"{self._shefparm_pathname}: Updating standard send code [{key}] from parmameter [{cur_val[0]}] and use-prev-0700 = [{cur_val[1]}] " \
                    f"to parmameter [{value[0]}] and use-prev-0700 = [{value[1]}]")
        self._send_codes[key] = value

    def set_qualifier_code(self, line: str) -> None :
        '''
        Update Data qualifiers from SHEFPARM line
        '''
        key = line[0]
        if len(key) != 1 or not key.isalpha() or key != key.upper() or key in ("IO") :
            self.critical(f"{self._shefparm_pathname}: Invalid ata qualifier [{key}]")
        if key not in self._qualifier_codes :
            self.info(f"{self._shefparm_pathname}: Adding non-standard data qualifier code [{key}]")
            self._qualifier_codes.add(key)

    def set_max_error_count(self, line: str) -> None :
        '''
        Update Max error count from SHEFPARM line
        '''
        value = int(line[:4].replace(' ', ''))
        if value != self._max_error_count :
            self.info(f"{self._shefparm_pathname}: Maximum error count set to [{self._max_error_count}]")
        self._max_error_count = value

    def debug(self, message_text: str) -> None :
        '''
        Log info message.
        '''
        logger.debug(message_text)

    def info(self, message_text: str) -> None :
        '''
        Log info message.
        '''
        if self._raw_message is not None :
            lines = textwrap.wrap(f"{message_text} in message starting at {self._input_name}:{self._message_location}", width=self._log_line_len)
            logger.info("\n\t".join(lines))
            if self._raw_message != self._previous_raw_message :
                logger.info("Warning is for message :\n\t{}".format("\n\t".join(self._raw_message.split('\n'))))
            else :
                logger.info("Warning is for message logged above")
            self._previous_raw_message = self._raw_message
        else :
            if self._input_name is None :
                lines = textwrap.wrap(message_text, width=self._log_line_len)
            else :
                lines = textwrap.wrap(f"{message_text} at {self._input_name}:{self._line_number}", width=self._log_line_len)
            logger.info("\n\t".join(lines))

    def warning(self, message_text: str) -> None :
        '''
        Log and track warnings.
        '''
        if self._raw_message is not None :
            lines = textwrap.wrap(f"{message_text} in message starting at {self._input_name}:{self._message_location}", width=self._log_line_len)
            logger.warning("\n\t".join(lines))
            if self._raw_message != self._previous_raw_message :
                logger.info("Warning is for message :\n\t{}".format("\n\t".join(self._raw_message.split('\n'))))
            else :
                logger.info("Warning is for message logged above")
            self._previous_raw_message = self._raw_message
        else :
            if self._input_name is None :
                lines = textwrap.wrap(message_text, width=self._log_line_len)
            else :
                lines = textwrap.wrap(f"{message_text} at {self._input_name}:{self._line_number}", width=self._log_line_len)
            logger.warning("\n\t".join(lines))
        self._warning_count += 1
        if self._message != self._last_message_with_warning :
            self._messages_with_warning_count += 1
            self._last_message_with_warning = self._message

    def error(self, message_text: str, count_error: bool=True) -> None :
        '''
        Log and track errors. Abort if max errors exceeded.
        '''
        if self._raw_message is not None :
            lines = textwrap.wrap(f"{message_text} in message starting at {self._input_name}:{self._message_location}", width=self._log_line_len)
            logger.error("\n\t".join(lines))
            if self._raw_message != self._previous_raw_message :
                logger.info("Error is in message :\n\t{}".format("\n\t".join(self._raw_message.split('\n'))))
            else :
                logger.info("Error is in message logged above")
            self._previous_raw_message = self._raw_message
        else :
            if self._input_name is None :
                lines = textwrap.wrap(message_text, width=self._log_line_len)
            else :
                lines = textwrap.wrap(f"{message_text} at {self._input_name}:{self._line_number}", width=self._log_line_len)
            logger.error("\n\t".join(lines))
        if count_error :
            self._error_count += 1
            if self._message != self._last_message_with_error :
                self._messages_with_error_count += 1
                self._last_message_with_error = self._message
        if self._error_count > self._max_error_count :
            msg = f"Maximum number of errors ({self._max_error_count}) exceeded - aborting"
            logger.critical(msg)
            exit(-2)

    def critical(self, message_text: str) -> None :
        '''
        Log critical error and abort.
        '''
        if self._raw_message is not None :
            lines = textwrap.wrap(f"{message_text} in message starting at {self._input_name}:{self._message_location}, aborting parser", width=self._log_line_len)
            logger.critical("\n\t".join(lines))
            if self._raw_message != self._previous_raw_message :
                logger.info("Critical error is in message :\n\t{}".format("\n\t".join(self._raw_message.split('\n'))))
            else :
                logger.info("Critcal error is in message logged above")
            self._previous_raw_message = self._raw_message
        else :
            if self._input_name is None :
                lines = textwrap.wrap(message_text, width=self._log_line_len)
            else :
                lines = textwrap.wrap(f"{message_text} at {self._input_name}:{self._line_number}", width=self._log_line_len)
            logger.critical("\n\t".join(lines))
        self._error_count += 1
        exit(-1)

    def get_parameter_code(self, partial_parameter_code: str) -> tuple[str, bool] :
        '''
        Generate a complete parameter code from a partial parameter code and defaults
        '''
        #--------------------#
        # resolve send codes #
        #--------------------#
        value_at_prev_0700 = False
        send_code = None
        if len(partial_parameter_code.strip().split()) != 1 :
            raise ShefParser.ParseException(f"Invalid parameter code: [{partial_parameter_code}]")
        try :
            code, value_at_prev_0700 = self._send_codes[partial_parameter_code[:2]]
            if len(partial_parameter_code) != 2 and partial_parameter_code[:2] not in self._pe_conversions :
                raise ShefParser.ParseException(f"Invalid parameter code: [{partial_parameter_code}] - {partial_parameter_code[:2]} is send code for {code}")
            if len(partial_parameter_code) == 2 :
                send_code = partial_parameter_code[:2]
            else :
                code = partial_parameter_code
        except KeyError :
            code = partial_parameter_code
        length = len(code)
        if not 2 <= length <= 7 :
            raise ShefParser.ParseException(f"Parameter code [{partial_parameter_code}] must be 2-7 characters long")
        if length > 2 and code[2] == 'Z' and not send_code :
            #----------------------#
            # replace 'Z' duration #
            #----------------------#
            _code = code[:2]
            try :
                _code += ShefParser.DEFAULT_DURATION_CODES[code[:2]]
            except KeyError :
                _code += self._default_duration_code
            if length > 3 :
                _code += code[3:]
            code = _code
        if length > 3 and code[3] == 'Z' :
            #------------------#
            # replace 'Z' type #
            #------------------#
            _code = code[:3] + self._default_type_code
            if length > 4 :
                _code += code[4:]
            code = _code
        #----------------------#
        # expand partial codes #
        #----------------------#
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
        #-------------------#
        # validate portions #
        #-------------------#
        if code[2] not in self._duration_codes :
            raise ShefParser.ParseException(f"Invalid duration code [{code[2]}] in parameter_code [{code}]")
        if code[3:5] not in self._ts_codes :
            raise ShefParser.ParseException(f"Invalid type and source code [{code[3:5]}] in parameter code [{code}]")
        if code [5] not in self._extremum_codes :
            raise ShefParser.ParseException(f"Invalid extremum code [{code[5]}] in parameter_code [{code}]")
        if code [6] not in self._probability_codes :
            raise ShefParser.ParseException(f"Invalid probability code [{code[6]}] in parameter_code [{code}]")
        return code, value_at_prev_0700

    def close_input(self) -> None :
        '''
        Close and detach the message input device
        '''
        if self._input :
            self.debug(f"Closing input {self._input_name}")
            if not self._input.isatty() :
                self._input.close()
            self._input = None
        else :
            self.info("Input is already closed or was never set")

    def set_input(self, input_object: Union[TextIO, str]) -> None :
        '''
        Attach the message input device, opening if necessary
        '''
        if self._input :
            self.close_input()
        if isinstance(input_object, TextIOWrapper) :
            self._input = input_object
            self._input_name = input_object.name
        elif isinstance(input_object, str) :
            self._input = open(input_object)
            self._input_name = input_object
        else :
            raise ShefParser.InputException(f"Expected TextIOWrapper or str object, got [{input_object.__class__.__name__}]")
        self._line_number = 0
        self.debug(f"Message input set to {self._input_name}")

    def close_output(self) -> None :
        '''
        Close and detach the data output device
        '''
        if self._output :
            self.debug(f"Closing output {self._output_name}")
            if isinstance(self._output, TextIOWrapper) :
                self._output.write("\n")
            elif isinstance(self._output, BufferedRandom) :
                self._output.write("\n".encode("utf-8"))
            if not self._output.isatty() :
                self._output.close()
            self._output = None
        else :
            logger.debug("Output is already closed or was never set")

    def set_output(self, output_object: Union[TextIO, str], append: bool) -> None :
        '''
        Attach the data output device, opening if necessary
        '''
        if self._output :
            self.close_output()
        if isinstance(output_object, (BufferedRandom, TextIOWrapper)) :
            self._output = output_object
            self._output_name = output_object.name
        elif isinstance(output_object, str) :
            self._output = open(output_object, "a+b" if append else "w+b")
            self._output_name = output_object
        else :
            raise ShefParser.OutputException(f"Expected BufferedRandom or str object, got [{output_object.__class__.__name__}]")
        logger.debug(f"Data output set to {self._output_name}")

    def output(self, outrec : OutputRecord) -> None :
        '''
        Write a value to the output
        '''
        if outrec :
            if not self._output :
                raise ShefParser.OutputException("Cannot output record; output is closed or never opened")
            outstr = f"{outrec.format(self._output_format)}\n"
            if isinstance(self._output, TextIOWrapper) :
                self._output.write(outstr)
            elif isinstance(self._output, BufferedRandom) :
                self._output.write(outstr.encode("utf-8"))
            else :
                raise ShefParser.OutputException(f"Unexpected output device type: {self._output.__class__.__name__}")

    def remove_comment_fields(self, line: str) -> str :
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

    def get_next_message(self) -> str :
        '''
        Retrieve the next complete message from the message input device
        '''
        raw_message_lines: deque = deque()
        message_lines: deque = deque()
        message_type: str  = ''
        revised: bool = False
        in_header: bool = False
        while True :
            while self._input_lines :
                line = self._input_lines.popleft()
                self._line_number += 1
                self.debug(f"Removed line from input queue [{line}]")
                message_line = self.remove_comment_fields(line).rstrip('=').rstrip('&').rstrip('=')
                if not message_type :
                    #-----------------------------------#
                    # looking for first line of message #
                    #-----------------------------------#
                    if not message_line or line[0] != '.' :  continue
                    if not self._msg_start_pattern.search(message_line) :
                        self.error(f"Invalid line: [{line}]")
                        continue
                    message_type = message_line[1]
                    revised = message_line[2] == 'R'
                    raw_message_lines.append(line)
                    message_lines.append(message_line)
                    in_header = message_type == 'B'
                else :
                    #----------------------------#
                    # looking for end of message #
                    #----------------------------#
                    if message_type == 'B' :
                        raw_message_lines.append(line)
                        message_lines.append(message_line)
                        if message_line and message_line[0] == '.' :
                            if in_header and self._msg_continue_patterns[message_type][int(revised)].search(message_line) :
                                continue
                            if not message_line.startswith(".END") :
                                if self._msg_continue_patterns[message_type][int(revised)].search(message_line) :
                                    self.error(".B message has data between header lines")
                                    message_lines.pop()
                                    message_lines.pop()
                                    message_lines.append(message_line)
                                    in_header = True
                                    continue
                                self._line_number -= 1
                                self._input_lines.appendleft(line)
                                self.debug(f"Restored line to input queue  [{line}]")
                                message_lines.pop()
                                raw_message_lines.pop()
                                self._message_location = self._line_number-len(raw_message_lines)+1
                                self._message = '\n'.join(list(message_lines)+[".END"])
                                self._raw_message = '\n'.join(raw_message_lines)
                                self.error(".B message not finished before next message - missing \".END\" appended")
                                return self._message
                            in_header = False
                            message_type = ''
                            break
                        else :
                            in_header = False
                    else :
                        if self._msg_continue_patterns[message_type][int(revised)].search(message_line) :
                            raw_message_lines.append(line)
                            message_lines.append(message_line)
                        else :
                            self._line_number -= 1
                            self._input_lines.appendleft(line)
                            self.debug(f"Restored line to input queue  [{line}]")
                            message_type = ''
                            break
            if message_lines and not message_type :
                #-------------------#
                # done with message #
                #-------------------#
                break
            elif not self._input :
                if message_type == 'B' :
                    self._message_location = self._line_number-len(raw_message_lines)+1
                    self._message = '\n'.join(message_lines)
                    self._raw_message = '\n'.join(raw_message_lines)
                    self.error(".B message not finished before input exhaused - missing \".END\" appended")
                    message_lines.append(".END")
                break
            else :
                #----------------#
                # read more data #
                #----------------#
                for i in range(100) :
                    try :
                        line = self._input.readline()
                    except Exception as e:
                        self.error(f"Line read error: {exc_info(e)}")
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
                self.debug(f"Put {len(self._input_lines)} lines from {self._input_name} into input queue")
        self._message_location = self._line_number-len(raw_message_lines)+1
        self._raw_message = '\n'.join(raw_message_lines)
        self._message = '\n'.join(message_lines)
        if self._message :
            self.debug("Assembled message starting at {0}:{1}:\n\t{2}".format(
                self._input_name,
                self._message_location,
                "\n\t".join(self._raw_message.split('\n'))))
        return self._message

    def parse_header_date(self, datestr : str, time_zone: Union[timezone, ZoneInfo, str], shefit_times: bool = False) -> tuple:
        '''
        Parses the header observation date into a DateTime object.
        Returns a tuple of observation date and whether the century is specified in the date.

            datestr      = the observation date string from the header
            time_zone    = the time zone from the header
            shefit_times = whether the parser is using shefit-style times
        '''
        century_specified = False
        dt = ShefParser.DateTime.now(time_zone)
        cy, cm, cd = dt.year, dt.month, dt.day
        length = len(datestr)
        cur_date = ShefParser.DateTime(cy, cm, cd, 0, 0, 0, tzinfo=time_zone)
        if length == 4 : # mmdd
            y, m, d = cy, int(datestr[0:2]), int(datestr[2:4])
        elif length == 6 : # yymmdd
            y, m, d = int(str(cur_date.year)[0:2] + datestr[0:2]), int(datestr[2:4]), int(datestr[4:6])
            if y - cy > 10 :
                y -= 100
        elif length == 8 : # ccyymmdd
            century_specified = True
            y, m, d = int(datestr[0:4]), int(datestr[4:6]), int(datestr[6:8])
        else :
            raise ShefParser.ParseException(f"Bad date string: [{datestr}]")
        if not 1700 <= y <= 2100 or not 1 <= m <= 12 or not 1 <= d <= ShefParser.DateTime.last_day(y, m) :
            raise ShefParser.ParseException(f"Bad date string: [{datestr}]")
        try :
            if length == 4 :
                # no year specified, use closeset date
                if shefit_times :
                    y = cy
                    month_diff = cm - m
                    if   month_diff  >  6            : y += 1
                    elif month_diff  < -6            : y -= 1
                    elif month_diff == -6 and cd < d : y -= 1
                    elif month_diff ==  6 and cd > d : y += 1
                    dateval = ShefParser.DateTime(y, m, d, 0, 0, 0, tzinfo=time_zone)
                else :
                    dateval = ShefParser.DateTime(y, m, d, 0, 0, 0, tzinfo=time_zone)
                    prev_year = dateval - MonthsDelta(12)
                    cur_diff = (dateval - cur_date)
                    prev_diff = (cur_date - prev_year)
                    if not isinstance(cur_diff, timedelta) or not isinstance(prev_diff, timedelta) :
                        raise ShefParser.ParseException(f"Invalid comparison types: {prev_diff.__class__.__name__}, {cur_diff.__class__.__name__}")
                    if prev_diff < cur_diff :
                        if not isinstance(prev_year, ShefParser.DateTime) :
                            raise ShefParser.ParseException(f"Expected ShefParser.DateTime object, got {prev_year.__class__.__name__}")
                        dateval = prev_year
            else :
                dateval = ShefParser.DateTime(y, m, d, 0, 0, 0, tzinfo=time_zone)
            return dateval, century_specified
        except :
            raise ShefParser.ParseException(f"Bad date string: [{datestr}]")

    def tokenize_a_e_data_string(self, datastr: str, message_type: str, is_revised: bool) -> list :
        '''
        Common conversion of .A(R) or .E(R) data strings into tokens. Each type provides its own
        retokenization after this.

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
                    lines[i] = '/' + lines[i]
            prev = i
            # make sure retained comments are separated from values
            lines[i] = self._retained_comment_pattern.sub(r" \1", lines[i])
            # set all the whitespace in retained comments to non-whitespace
            lines[i] = ShefParser.hide_quoted_whitespace(lines[i])
            # collapse whitespace
            lines[i] = ' '.join(lines[i].split())
            # invert the whitespace/non-whitespace replacements in the entire line (swap ' ' with NUL, and '\t' with SOH)
            lines[i] = lines[i].translate({0:32,1:9,32:0,9:1})
        #------------------------------------------------------#
        # convert lines back into a single string and tokenize #
        #------------------------------------------------------#
        datastr = "".join(lines).strip('/')
        tokens: list[Any] = datastr.split('/')
        for i in range(len(tokens)) :
            # split the tokens on whitespace replacements (NUL,SOH) after stripping replacements
            tokens[i] = self._replacement_split_pattern.split(self._replacement_strip_pattern.sub("", tokens[i]))
        return tokens

    def get_observation_time(self, base_time: DateTime, token: str, century_specified: bool, dot_b: bool=False) -> tuple :
        '''
        Return the observation time from the base datetime as updated by the token. Only one of obstime and relative_time
        will be returned.

        Parameters:
            base_time         = The last explicit observation time specified (possibly the header date)
            token             = The observersation time token
            century_specified = Whether the century was specified when generating the base datetime
            dot_b             = Whether this is for a .B message

        Returned:
            obstime           = The observation time as updated by the token. If dot_b == True and the token
                                starts with "DR", this will be None
            relative_time     = The relative time if dot_b == True and token starts with "DR", else None
            century_specified = Whether the century was specified in the base_time or token
        '''
        bt = base_time
        obstime: Union[None, ShefParser.DateTime] = base_time
        relativetime: Union[None, timedelta, MonthsDelta] = None
        subtokens = token.strip('@').split('@')
        if len(subtokens) > 1 and subtokens[0][1] == 'J' :
            raise ShefParser.ParseException(f"Bad observation time: [{subtokens[0]}]/[{subtokens[1]}]")
        for subtoken in subtokens :
            try :
                cur_time = ShefParser.DateTime.now('Z' if self.shefit_times else ShefParser.UTC)
                v = subtoken[2:]
                length = len(v)
                if subtoken[1] == 'S' :
                    if length == 2 : # DSss
                        obstime = ShefParser.DateTime(bt.year, bt.month, bt.day, bt.hour, bt.minute, int(v[0:2]), tzinfo=bt.tzinfo)
                    else :
                        raise ShefParser.ParseException(f"Bad observation time: [{subtoken}]")
                elif subtoken[1] == 'N' :
                    if length == 4 : # DNnnss
                        obstime = ShefParser.DateTime(bt.year, bt.month, bt.day, bt.hour, int(v[0:2]), int(v[2:4]), tzinfo=bt.tzinfo)
                    elif length == 2 : # DNnn
                        obstime = ShefParser.DateTime(bt.year, bt.month, bt.day, bt.hour, int(v[0:2]), bt.second, tzinfo=bt.tzinfo)
                    else :
                        raise ShefParser.ParseException(f"Bad observation time: [{subtoken}]")
                elif subtoken[1] == 'H' :
                    if length == 6 : # DHhhnnss
                        obstime = ShefParser.DateTime(bt.year, bt.month, bt.day, int(v[0:2]), int(v[2:4]), int(v[4:6]), tzinfo=bt.tzinfo)
                    elif length == 4 : # DHhhnn
                        obstime = ShefParser.DateTime(bt.year, bt.month, bt.day, int(v[0:2]), int(v[2:4]), bt.second, tzinfo=bt.tzinfo)
                    elif length == 2 : # DHhh
                        obstime = ShefParser.DateTime(bt.year, bt.month, bt.day, int(v[0:2]), bt.minute, bt.second, tzinfo=bt.tzinfo)
                    else :
                        raise ShefParser.ParseException(f"Bad observation time: [{subtoken}]")
                elif subtoken[1] == 'D' :
                    if length == 8 : # DDddhhnnss
                        obstime = ShefParser.DateTime(bt.year, bt.month, int(v[0:2]), int(v[2:4]), int(v[4:6]), int(v[6:8]), tzinfo=bt.tzinfo)
                    elif length == 6 : # DDddhhnn
                        obstime = ShefParser.DateTime(bt.year, bt.month, int(v[0:2]), int(v[2:4]), int(v[4:6]), bt.second, tzinfo=bt.tzinfo)
                    elif length == 4 : # DDddhh
                        obstime = ShefParser.DateTime(bt.year, bt.month, int(v[0:2]), int(v[2:4]), bt.hour, bt.second, tzinfo=bt.tzinfo)
                    elif length == 2 : # DDdd
                        obstime = ShefParser.DateTime(bt.year, bt.month, int(v[0:2]), bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo)
                    else :
                        raise ShefParser.ParseException(f"Bad observation time: [{subtoken}]")
                elif subtoken[1] == 'M' :
                    if length == 10 : # DMmmddhhnnss
                        obstime = ShefParser.DateTime(bt.year, int(v[0:2]), int(v[2:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), tzinfo=bt.tzinfo)
                    elif length == 8 : # DMmmddhhnn
                        obstime = ShefParser.DateTime(bt.year, int(v[0:2]), int(v[2:4]), int(v[4:6]), int(v[6:8]), bt.second, tzinfo=bt.tzinfo)
                    elif length == 6 : # DMmmddhh
                        obstime = ShefParser.DateTime(bt.year, int(v[0:2]), int(v[2:4]), int(v[4:6]), bt.minute, bt.second, tzinfo=bt.tzinfo)
                    elif length == 4 : # DMmmdd
                        obstime = ShefParser.DateTime(bt.year, int(v[0:2]), int(v[2:4]), bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo)
                    elif length == 2 : # DMmm
                        obstime = ShefParser.DateTime(bt.year, int(v[0:2]), bt.day, bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo)
                    else :
                        raise ShefParser.ParseException(f"Bad observation time: [{subtoken}]")
                elif subtoken[1] == 'Y' :
                    if length > 1 :
                        if century_specified :
                            y = bt.year - bt.year % 100 + int(v[0:2])
                        else :
                            y = cur_time.year - cur_time.year % 100 + int(v[0:2])
                        if y - cur_time.year > 10 : y -= 100
                    else :
                        raise ShefParser.ParseException(f"Bad observation time: [{subtoken}]")
                    if length == 12 : # DYyymmddhhnnss
                        obstime = ShefParser.DateTime(y, int(v[2:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), int(v[10:12]), tzinfo=bt.tzinfo)
                    elif length == 10 : # DYyymmddhhnn - set date and time
                        obstime = ShefParser.DateTime(y, int(v[2:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), bt.second, tzinfo=bt.tzinfo)
                    elif length == 8 : # DYyymmddhh
                        obstime = ShefParser.DateTime(y, int(v[2:4]), int(v[4:6]), int(v[6:8]), bt.minute, bt.second, tzinfo=bt.tzinfo)
                    elif length == 6 : # DYyymmdd
                        obstime = ShefParser.DateTime(y, int(v[2:4]), int(v[4:6]), bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo)
                    elif length == 4 : # DYyymm
                        obstime = ShefParser.DateTime(y, int(v[2:4]), bt.day, bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo)
                    elif length == 2 : # DYyy
                        obstime = ShefParser.DateTime(y, bt.month, bt.day, bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo)
                    else :
                        raise ShefParser.ParseException(f"Bad observation time: [{subtoken}]")
                elif subtoken[1] == 'T' :
                    if length == 14 : #DTccyymmddhhnnss
                        obstime = ShefParser.DateTime(int(v[0:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), int(v[10:12]), int(v[12:14]), tzinfo=bt.tzinfo)
                    elif length == 12 : #DTccyymmddhhnn
                        obstime = ShefParser.DateTime(int(v[0:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), int(v[10:12]), 0, tzinfo=bt.tzinfo)
                    elif length == 10 : #DTccyymmddhh
                        obstime = ShefParser.DateTime(int(v[0:4]), int(v[4:6]), int(v[6:8]), int(v[8:10]), 0, 0, tzinfo=bt.tzinfo)
                    elif length == 8 : #DTccyymmdd
                        obstime = ShefParser.DateTime(int(v[0:4]), int(v[4:6]), int(v[6:8]), bt.hour, 0, 0, tzinfo=bt.tzinfo)
                    elif length == 6 : #DTccyymm
                        obstime = ShefParser.DateTime(int(v[0:4]), int(v[4:6]), bt.day, bt.hour, 0, 0, tzinfo=bt.tzinfo)
                    elif length == 4 : #DTccyy
                        obstime = ShefParser.DateTime(int(v[0:4]), bt.month, bt.day, bt.hour, 0, 0, tzinfo=bt.tzinfo)
                    elif length == 2 : #DTcc
                        obstime = ShefParser.DateTime(100*int(v[0:2])+bt.year%100, bt.month, bt.day, bt.hour, 0, 0, tzinfo=bt.tzinfo)
                    else :
                        raise ShefParser.ParseException(f"Bad observation time: [{subtoken}]")
                elif subtoken[1] == 'J' :
                    if length == 7 : # DJccyyddd
                        y = int(v[0:4])
                        d = int(v[4:])
                        if d > (366 if ShefParser.DateTime.is_leap(y) else 365) :
                            raise ShefParser.ParseException(f"Invalid day: [{subtoken}]")
                        obstime = ShefParser.DateTime(y, 1, 1, bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo) + timedelta(days=int(v[4:7])-1)
                    elif length == 5 : # DJyyddd
                        y = cur_time.year - cur_time.year % 100 + int(v[0:2])
                        if y - cur_time.year > 10 : y -= 100
                        d = int(v[2:])
                        if d > (366 if ShefParser.DateTime.is_leap(y) else 365) :
                            raise ShefParser.ParseException(f"Invalid day: [{subtoken}]")
                        obstime = ShefParser.DateTime(y, 1, 1, bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo) + timedelta(days=int(v[2:5])-1)
                    elif length < 4 : # DJd[d[d]]
                        d = int(v)
                        if d > (366 if ShefParser.DateTime.is_leap(bt.year) else 365) :
                            raise ShefParser.ParseException(f"Invalid day: [{subtoken}]")
                        obstime = ShefParser.DateTime(bt.year, 1, 1, bt.hour, bt.minute, bt.second, tzinfo=bt.tzinfo) + timedelta(days=int(v[0:])-1)
                    else :
                        raise ShefParser.ParseException(f"Bad observation time: [{subtoken}]")
                elif subtoken[1] == 'R' :
                    # for .B messages the relative times are kept in the parameter info objects
                    obstime = None
                    v = subtoken[3:]
                    val = int(v)
                    if abs(val) > 99 :
                        raise ShefParser.ParseException("Invalid relative time value")
                    if subtoken[2] == 'S' :
                        if dot_b :
                            relativetime = timedelta(seconds=val)
                        else :
                            obstime = bt + timedelta(seconds=val)
                    elif subtoken[2] == 'N' :
                        if dot_b :
                            relativetime = timedelta(minutes=val)
                        else :
                            obstime = bt + timedelta(minutes=val)
                    elif subtoken[2] == 'H' :
                        if dot_b :
                            relativetime = timedelta(hours=val)
                        else :
                            obstime = bt + timedelta(hours=val)
                    elif subtoken[2] == 'D' :
                        if dot_b :
                            relativetime = timedelta(days=val)
                        else :
                            obstime = bt + timedelta(days=val)
                    elif subtoken[2] == 'M' :
                        if dot_b :
                            relativetime = MonthsDelta(val)
                        else :
                            obstime = bt + MonthsDelta(val)
                    elif subtoken[2] == 'E' :
                        if dot_b :
                            relativetime = MonthsDelta(val, eom=True)
                        else :
                            obstime = bt + MonthsDelta(val, eom=True)
                    elif subtoken[2] == 'Y' :
                        if dot_b :
                            relativetime = MonthsDelta(12*val)
                        else :
                            obstime = bt + MonthsDelta(12*val)
                    else :
                        raise ShefParser.ParseException(f"Bad observation time: [{subtoken}]")
            except ShefParser.Exc :
                raise
            except :
                raise ShefParser.ParseException(f"Bad observation time: [{subtoken}]")
        return obstime, relativetime, century_specified

    def get_creation_time(self, obstime: DateTime, token: Union[None, str]) -> Union[None, DateTime] :
        '''
        Generate a creation time from an obsersation time and a token
        '''
        if not token:
            return None
        curtime = ShefParser.DateTime.now('Z' if self.shefit_times else ShefParser.UTC)
        threshold = ShefParser.DateTime(obstime.year, obstime.month, obstime.day, 0, 0, 0, tzinfo=obstime.tzinfo) + MonthsDelta(120)
        s = token
        length = len(s)
        try :
            if length == 12 :   # ccyymmddhhnn
                y, m, d, h, n = int(s[0:4]), int(s[4:6]), int(s[6:8]), int(s[8:10]), int(s[10:12])
                dt = ShefParser.DateTime(y, m, d, h, n, 0, tzinfo=obstime.tzinfo)
            elif length == 10 : # yymmddhhnn
                y = curtime.year - curtime.year % 100 + int(s[0:2])
                m, d, h, n = int(s[2:4]), int(s[4:6]), int(s[6:8]), int(s[8:10])
                dt = ShefParser.DateTime(y, m, d, h, n, 0, tzinfo=obstime.tzinfo)
                while dt > threshold :
                    dt2 = dt - MonthsDelta(1200)
                    if not isinstance(dt2, ShefParser.DateTime) :
                        raise ShefParser.ParseException(f"Expected ShefParser.DateTime object, got {dt2.__class__.__name__}")
                    dt = dt2
            elif length == 8 :  # mmddhhnn
                y, m, d, h, n = obstime.year, int(s[0:2]), int(s[2:4]), int(s[4:6]), int(s[6:8])
                dt = ShefParser.DateTime(y, m, d, h, n, 0, tzinfo=obstime.tzinfo)
                while dt > threshold :
                    dt2 = dt - MonthsDelta(1200)
                    if not isinstance(dt2, ShefParser.DateTime) :
                        raise ShefParser.ParseException(f"Expected ShefParser.DateTime object, got {dt2.__class__.__name__}")
                    dt = dt2
            elif length == 6 :  # mmddhh
                y, m, d, h, n = obstime.year, int(s[0:2]), int(s[2:4]), int(s[4:6]), 0
                dt = ShefParser.DateTime(y, m, d, h, n, 0, tzinfo=obstime.tzinfo)
                while dt > threshold :
                    dt2 = dt - MonthsDelta(1200)
                    if not isinstance(dt2, ShefParser.DateTime) :
                        raise ShefParser.ParseException(f"Expected ShefParser.DateTime object, got {dt2.__class__.__name__}")
                    dt = dt2
            elif length == 4 :  # mmdd
                hour = 12 if obstime.tzinfo in ('Z', ShefParser.UTC) else 24
                y, m, d, h, n = obstime.year, int(s[0:2]), int(s[2:4]), hour, 0
                dt = ShefParser.DateTime(y, m, d, h, n, 0, tzinfo=obstime.tzinfo)
                while dt > threshold :
                    dt2 = dt - MonthsDelta(1200)
                    if not isinstance(dt2, ShefParser.DateTime) :
                        raise ShefParser.ParseException(f"Expected ShefParser.DateTime object, got {dt2.__class__.__name__}")
                    dt = dt2
            else :
                raise ShefParser.ParseException(f"Bad creation time: [{token}]")
            return dt
        except :
            raise ShefParser.ParseException(f"Bad creation time: [{token}]")

    def parse_value_token_alt(self, token: str) -> tuple :
        '''
        Returns the numeric value and data qualifier from a token that the regex fails to match
        '''
        value = qualifier = None
        has_digit = has_decimal = has_qualifier = error = False
        for i in range(len(token)) :
            if token[i].isdigit() :
                has_digit = True
            elif token[i] in "-+" :
                if i != 0 :
                    error = True
                    break
            elif token[i] == '.' :
                if has_decimal :
                    error = True
                    break
                has_decimal = True
            elif token[i].isalpha() :
                if has_qualifier :
                    error = True
                    break
                if has_digit :
                    value = float(token[:i])
                    qualifier = token[i]
                    if i < len(token)-1 :
                        if not token[i+1].isspace() and token[i+1] not in "'\"" :
                            error = True
                    break
                else :
                    error = True
                    break
            else :
                error = True
                break
        if error :
            if self._replacement_split_pattern.sub("", token).strip() :
                raise ShefParser.ParseException(f"Invalid value: [{token}]")
            else :
                raise ShefParser.ParseException("Missing value")
        return value, qualifier

    def parse_value_token(self, token: str, pe_code: str, units: str) -> tuple :
        '''
        Returns the numeric value and data qualifier for a specified physical element and units system from a token
        '''
        m = self._value_pattern.match(self._retained_comment_pattern.sub("", token).strip())
        if not m :
            return self.parse_value_token_alt(token)
        # groups
        # 1 = value
        # 2 = numeric value
        # 3 = trace value
        # 4 = missing valule
        # 5 = value qualifier
        matched_groups = "".join(map(lambda x : 'T' if bool(x) else 'F', [m.group(i) for i in (2,3,4)]))
        qualifier = None
        if matched_groups == "TFF" :
            #------------------------------#
            # value (with or without sign) #
            #------------------------------#
            value = float(m.group(2))
            if units == "EN" and pe_code in ("PC", "PP") and '.' not in m.group(2) :
                value /= 100
            elif units == "SI" and value != -9999. :
                value = self.get_english_unit_value(value, pe_code)
            if value == 0 : value = 0 # prevent -0.000
        elif matched_groups ==  "FTF" :
            #---------------------------#
            # Precipitation trace value #
            #---------------------------#
            if pe_code not in ("PC", "PP") :
                raise ShefParser.ParseException(f"Value [{m.group(3)}] is not valid for pe_code [{pe_code}]")
            value = .001
        elif matched_groups == "FFT" :
            #-----------------------#
            # explicit missing data #
            #-----------------------#
            value = -9999.
            v = m.group(4).upper()
            if len(v) > 1 and v[-1].isalpha() and not m.group(5) :
                qualifier = v[-1]
        else :
            #---------------------------------------#
            # invalid combination of matched groups #
            #---------------------------------------#
            raise ShefParser.ParseException(f"Invalid data value: [{token}]")
        if not qualifier :
            qualifier = m.group(5).upper()
        return value, qualifier

    def get_time_zone(self, name: str) -> Union[str, timezone, ZoneInfo] :
        '''
        Create a time zone from the name
        '''
        if self.shefit_times :
            return name
        else :
            text = ShefParser.TZ_NAMES[name]
            try :
                if text.startswith("timedelta") :
                    return timezone(eval(text))
                else :
                    return ZoneInfo(text)
            except :
                raise ShefParser.ParseException(f"Cannot instantiate time zone [{name}]")

    def get_english_unit_value(self, value: float, parameter: str) -> float :
        '''
        Convert a value to english unit for a specified physical element
        '''
        key = parameter[:2].upper()
        try :
            factor = self._pe_conversions[key]
        except KeyError :
            raise ShefParser.ParseException(f"Cannot find conversion factor for phyical element [{key}]")
        if factor == -1 :
            # C to F conversion
            value = value * 1.8 + 32
        else :
            value *= factor
        return value

    def parse_message(self) -> list :
        '''
        Parse the next message on the input and return a list of OutputRecord objects
        '''
        if self._message is not None :
            if self._message.startswith(".A") :
                return self.parse_dot_a_message(self._message)
            if self._message.startswith(".B") :
                return self.parse_dot_b_message(self._message)
            if self._message.startswith(".E") :
                return self.parse_dot_e_message(self._message)
        return []

    def parse_dot_a_message(self, message: str) -> list :
        '''
        Parse a .A or .AR message and return a list of OutputRecord objects
        '''
        def retokenize(tokens: list) -> list :
            '''
            Accomodates sloppy slash usage in .A message like shefit
            '''
            new_tokens = []
            skip = False
            for i in range(len(tokens)) :
                if skip :
                    skip = False
                    continue
                if len(tokens[i]) == 1 :
                    if self._parameter_code_pattern.match(tokens[i][0]) and tokens[i][0][0] != 'D':
                        if i < len(tokens)-1 :
                            if self._parameter_code_pattern.match(tokens[i+1][0]) and tokens[i+1][0][0] != 'D':
                                new_tokens.append(tokens[i] + [chr(0)])
                            else :
                                new_tokens.append(tokens[i] + tokens[i+1])
                                skip = True
                        else :
                            new_tokens.append(tokens[i])
                    else :
                        new_tokens.append(tokens[i])
                else :
                    count = 0
                    for j in range(len(tokens[i])) :
                        if self._obs_time_pattern2.match(tokens[i][j]) or self._unit_system_pattern.match(tokens[i][j]) :
                            new_tokens.append([tokens[i][j]])
                            count += 1
                        else :
                            new_tokens.append(tokens[i][count:])
                            break
            return new_tokens

        #-----------------------------#
        # parse the positional fields #
        #-----------------------------#
        revised   = None
        location  = None
        time_zone = None
        length    = None
        m = self._positional_fields_pattern.search(message)
        if not m :
            raise ShefParser.ParseException(f"Mal-formed positional fields: [{message}]")
        #------------------------------#
        # process the positionl fields #
        #------------------------------#
        revised   = message[2].upper() == 'R'
        location  = m.group(1).upper()
        time_zone = m.group(6).upper() if m.group(6) else 'Z'
        dateval, century_specified = self.parse_header_date(m.group(2).upper(), time_zone, self.shefit_times)
        length    = m.end()
        if not time_zone :
            time_zone = 'Z'
        zi = self.get_time_zone(time_zone)
        dateval = ShefParser.DateTime(dateval.year, dateval.month, dateval.day, tzinfo=zi)
        datastr = message[length:].strip()
        tokens  = self.tokenize_a_e_data_string(datastr, 'A', revised)
        #-----------------------------#
        # set the default data values #
        #-----------------------------#
        if time_zone == 'Z' :
            obstime = ShefParser.DateTime(dateval.year, dateval.month, dateval.day, 12, 0, 0, tzinfo=zi)
        else :
            obstime = ShefParser.DateTime(dateval.year, dateval.month, dateval.day, 0, 0, 0, tzinfo=zi)
        last_explicit_time = obstime
        createtime_str     = None
        default_qualifier  = 'Z'
        units              = "EN"
        duration_unit      = 'Z'
        duration_value     = None
        outrecs:list[ShefParser.OutputRecord] = []
        #--------------------------------#
        # process the data string fields #
        #--------------------------------#
        tokens = retokenize(tokens)
        relative_specified = False
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
                        try :
                            if token[pos+1] in "JR" :
                                obstime, relativetime, century_specified = self.get_observation_time(last_explicit_time, m.group(1).upper(), century_specified, dot_b=False)
                                if token[pos+1] == 'R' :
                                    relative_specified = True
                            else :
                                obstime, relativetime, century_specified = self.get_observation_time(obstime, m.group(1).upper(), century_specified, dot_b=False)
                                last_explicit_time = obstime
                                relative_specified = False
                            pos += m.end(1)+1
                        except ShefParser.Exc as spe :
                            self.error(str(spe))
                            return [] if self._reject_problematic else outrecs
                    if token[pos:] :
                        self.error(f"Unexpected data string item: [{token}]")
                        return [] if self._reject_problematic else outrecs
                elif self._create_time_pattern.match(token) :
                    #---------------------------------------------#
                    # set the creation time for subsequent values #
                    #---------------------------------------------#
                    createtime_str = token[2:]
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
                        self.error(f"Bad data qualifier: [{default_qualifier}]")
                        return [] if self._reject_problematic else outrecs
                elif self._duration_code_pattern.match(token) :
                    #----------------------------------------------------------------#
                    # set the duration for subequent values with duration code = 'V' #
                    #----------------------------------------------------------------#
                    duration_unit = token[2].upper()
                    if duration_unit == 'Z' :
                        duration_value = None
                    else :
                        duration_value = int(token[3:])
                        if duration_value > 99 :
                            raise ShefParser.ParseException(f"Invalid duration code variable [{token}]")
                elif not token :
                    #----------------------------------#
                    # ignore NULL fields in .A message #
                    #----------------------------------#
                    pass
                else :
                    self.error(f"Unexpected data string item: [{token}]")
                    return [] if self._reject_problematic else outrecs
            else :
                #------------#
                # data value #
                #------------#
                code = tokens[i][0].upper()
                if len(code) < 2 :
                    self.error(f"Invalid PE code: [{code[:min(2, len(code))]}]")
                    return []
                elif code not in self._send_codes and code[:2] not in self._pe_conversions and code[:2] not in self._addional_pe_codes :
                    self.warning(f"Unknown PE code: [{code[:min(2, len(code))]}], value(s) will be untransformed")
                try :
                    parameter_code, use_prev_7am = self.get_parameter_code(code)
                    orig_parameter_code = code
                except ShefParser.Exc as spe :
                    self.error(str(spe))
                    if self._reject_problematic :
                        return []
                    continue
                if use_prev_7am :
                    if relative_specified :
                        self.error("Cannot use relative date/time offsets with send codes QY, HY, or PY")
                        if self._reject_problematic :
                            return []
                        continue
                    if obstime.tzinfo == ('Z' if self.shefit_times else ShefParser.UTC) :
                        self.error("Cannot use Zulu/UTC time zone with send codes QY, HY, or PY")
                        if self._reject_problematic :
                            return []
                        continue
                    t = ShefParser.DateTime(obstime.year, obstime.month, obstime.day, obstime.hour, obstime.minute, obstime.second, tzinfo=obstime.tzinfo)
                    if t.hour < 7 :
                        t2 = t - timedelta(days=1)
                        if not isinstance(t2, ShefParser.DateTime) :
                            raise ShefParser.ParseException(f"Expected ShefParser.DateTime object, got [{t2.__class__.__name__}]")
                        t = t2
                    obstime = ShefParser.DateTime(t.year, t.month, t.day, 7, 0, 0, tzinfo=t.tzinfo)
                if len(tokens[i]) == 1 :
                    continue # same as a NULL field - a parameter code with no value
                try :
                    value_token = tokens[i][1].upper()
                    value, qualifier = self.parse_value_token(value_token, parameter_code[:2], units)
                except ShefParser.Exc as spe :
                    if self._obs_time_pattern2.match(value_token) :
                        self.error(f"Expected value for parameter [{parameter_code}], got, observation time [{value_token}]")
                        if self._reject_problematic :
                            return []
                        break
                    elif self._create_time_pattern.match(value_token) :
                        self.error(f"Expected value for parameter [{parameter_code}], got, creation time [{value_token}]")
                        if self._reject_problematic :
                            return []
                        break
                    elif self._unit_system_pattern.match(value_token) :
                        self.error(f"Expected value for parameter [{parameter_code}], got, unit system [{value_token}]")
                        if self._reject_problematic :
                            return []
                        break
                    elif self._data_qualifier_pattern.match(value_token) :
                        self.error(f"Expected value for parameter [{parameter_code}], got, data qualifier [{value_token}]")
                        if self._reject_problematic :
                            return []
                        break
                    elif self._duration_code_pattern.match(value_token) :
                        self.error(f"Expected value for parameter [{parameter_code}], got, duration code [{value_token}]")
                        if self._reject_problematic :
                            return []
                        break
                    else :
                        self.error(str(spe))
                        if self._reject_problematic :
                            return []
                    continue
                if not qualifier :
                    qualifier = default_qualifier
                if qualifier not in self._qualifier_codes :
                    self.warning(f"Unknown data qualifier: [{qualifier}], qualifier set to Z")
                    qualifier = 'Z'
                comment = None
                if len(tokens[i]) > 2 :
                    comment = tokens[i][2]
                    if comment :
                        if comment[0] not in "'\"" :
                            self.error(f"Invalid retained comment [{tokens[i][2]}]")
                            comment = None

                if parameter_code[3] == 'F' and not createtime_str :
                    self.warning(f"Forecast parameter [{parameter_code}] value [{value}] does not have creation date")

                outrecs.append(ShefParser.OutputRecord(
                    self,
                    location,
                    parameter_code,
                    orig_parameter_code,
                    obstime,
                    createtime_str,
                    value,
                    qualifier,
                    revised,
                    duration_unit,
                    duration_value,
                    comment = comment))
        return outrecs

    def parse_dot_e_message(self, message: str) -> list :
        '''
        Parse a .E or .ER message and return a list of OutputRecord objects
        '''
        def retokenize(tokens: list) -> list :
            '''
            Accomodates sloppy slash usage in .E message like shefit
            '''
            new_tokens: list[Any] = []
            for token in tokens :
                for subtoken in token :
                    if subtoken and subtoken[0] in "'\"" and len(new_tokens) > 0 :
                        new_tokens[-1] += [subtoken]
                    else :
                        new_tokens.append([subtoken])
            return new_tokens

        #-----------------------------#
        # parse the positional fields #
        #-----------------------------#
        revised   = None
        location  = None
        time_zone = None
        length    = None
        m = self._positional_fields_pattern.search(message)
        if not m :
            raise ShefParser.ParseException(f"Mal-formed positional fields: [{message}]")
        #-------------------------------#
        # process the positional fields #
        #-------------------------------#
        revised   = message[2].upper() == 'R'
        location  = m.group(1).upper()
        time_zone = m.group(6).upper() if m.group(6) else 'Z'
        dateval, century_specified = self.parse_header_date(m.group(2).upper(), time_zone, self.shefit_times)
        length    = m.end()
        if not time_zone :
            time_zone = 'Z'
        zi = self.get_time_zone(time_zone)
        dateval = ShefParser.DateTime(dateval.year, dateval.month, dateval.day, tzinfo=zi)
        datastr = message[length:].strip()
        tokens  = self.tokenize_a_e_data_string(datastr, 'E', revised)
        #-----------------------------#
        # set the default data values #
        #-----------------------------#
        if time_zone == 'Z' :
            obstime = ShefParser.DateTime(dateval.year, dateval.month, dateval.day, 12, 0, 0, tzinfo=zi)
        else :
            obstime = ShefParser.DateTime(dateval.year, dateval.month, dateval.day, 0, 0, 0, tzinfo=zi)
        parameter_code     = None
        original_obstime   = obstime
        last_explicit_time = obstime
        createtime_str     = None
        interval: Union[None, timedelta, MonthsDelta] = None
        time_series_code   = 0
        default_qualifier  = 'Z'
        units              = "EN"
        duration_unit      = 'Z'
        duration_value     = None
        outrecs: list[ShefParser.OutputRecord] = []
        #--------------------------------#
        # process the data string fields #
        #--------------------------------#
        use_prev_7am = False
        tokens = retokenize(tokens)
        for i in range(len(tokens)) :
            if len(tokens[i]) > 1 : self.error(f"Invalid data string")
            token = tokens[i][0]
            value = None
            comment = None
            relative_specified = False
            if self._obs_time_pattern2.search(token) :
                #------------------------------------------------#
                # set the observation time for subsequent values #
                #------------------------------------------------#
                pos = 0
                while True :
                    m = self._obs_time_pattern2.search(token[pos:])
                    if not m : break
                    try :
                        if token[pos+1] in "JR" :
                            obstime, relativetime, century_specified = self.get_observation_time(last_explicit_time.astimezone('Z' if self.shefit_times else ShefParser.UTC), m.group(1).upper(), century_specified, dot_b=False)
                            if token[pos+1] == 'R' :
                                relative_specified = True
                                if use_prev_7am :
                                    raise ShefParser.ParseException("Cannot use relative date/time offsets with send codes QY, HY, or PY")
                        else :
                            obstime, relativetime, century_specified = self.get_observation_time(original_obstime, m.group(1).upper(), century_specified, dot_b=False)
                            last_explicit_time = obstime
                    except ShefParser.Exc as spe :
                        self.error(str(spe))
                        if self._reject_problematic :
                            return []
                        break
                    pos += m.end(1)+1
                if token[pos:] :
                    self.error(f"Unexpected data string item: [{token}]")
                    return [] if self._reject_problematic else outrecs
                time_series_code = 1
            elif self._create_time_pattern.match(token) :
                #---------------------------------------------#
                # set the creation time for subsequent values #
                #---------------------------------------------#
                createtime_str = token[2:]
                obstime = last_explicit_time
                time_series_code = 1
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
                    self.error(f"Bad data qualifier: [{default_qualifier}]")
                    return [] if self._reject_problematic else outrecs
            elif self._duration_code_pattern.match(token) :
                #----------------------------------------------------------------#
                # set the duration for subequent values with duration code = 'V' #
                #----------------------------------------------------------------#
                duration_unit = token[2].upper()
                if duration_unit == 'Z' :
                    duration_value = None
                else :
                    duration_value = int(token[3:])
                    if duration_value > 99 :
                        raise ShefParser.ParseException(f"Invalid duration code variable [{token}]")
                time_series_code = 1
            elif self._interval_pattern.match(token) :
                #-----------------------------------------#
                # set the intrerval for subsequent values #
                #-----------------------------------------#
                if parameter_code is None :
                    raise ShefParser.ParseException("Interval is specified before parameter")
                if use_prev_7am :
                    raise ShefParser.ParseException(f"Cannot use data interval [{token}] with send codes QY, HY, or PY")
                if interval :
                    self.error("Interval specified more than once")
                    return [] if self._reject_problematic else outrecs
                time_series_code = 1
                interval_unit = token[2].upper()
                interval_value = int(token[3:])
                duration_code = interval_value
                if abs(interval_value) > 99 :
                    raise ShefParser.ParseException(f"Invalid interval value: [{token}]")
                if interval_unit == 'S' :
                    interval = timedelta(seconds=interval_value)
                    duration_code += 7000
                elif interval_unit == 'N' :
                    pass
                elif interval_unit == 'H' :
                    interval = timedelta(hours=interval_value)
                    duration_code += 1000
                elif interval_unit == 'D' :
                    interval = timedelta(days=interval_value)
                    duration_code += 2000
                elif interval_unit == 'M' :
                    interval = MonthsDelta(interval_value)
                    duration_code += 3000
                elif interval_unit == 'E' :
                    interval = MonthsDelta(interval_value, eom=True)
                    duration_code += 3000
                elif interval_unit == 'Y' :
                    duration_code += 4000
                try :
                    duration_id = self._duration_ids[duration_code]
                except KeyError :
                    self.error(f"No valid duration code for time interval [{token}]")
                    return [] if self._reject_problematic else outrecs
                parameter_code = f"{parameter_code[:2]}{duration_id}{parameter_code[3:]}"
            elif self._parameter_code_pattern.match(token) :
                #-------------------------------------------------#
                # set the parameter code for the susequent values #
                #-------------------------------------------------#
                if parameter_code :
                    self.error("Parameter code specified more than once")
                    return [] if self._reject_problematic else outrecs
                code = token.upper()
                if len(code) < 2 :
                    self.error(f"Invalid PE code: [{code[:min(2, len(code))]}]")
                    return [] if self._reject_problematic else outrecs
                elif code not in self._send_codes and code[:2] not in self._pe_conversions and code[:2] not in self._addional_pe_codes :
                    self.warning(f"Unknown PE code: [{code[:2]}], value(s) will be untransformed")
                parameter_code, use_prev_7am = self.get_parameter_code(code)
                orig_parameter_code = code
                if use_prev_7am :
                    if relative_specified :
                        raise ShefParser.ParseException("Cannot use relative date/time offsets with send codes QY, HY, or PY")
                    if obstime.tzinfo == ('Z' if self.shefit_times else ShefParser.UTC) :
                        raise ShefParser.ParseException("Cannot use Zulu/UTC time zone with send codes QY, HY, or PY")
                    if interval :
                        raise ShefParser.ParseException("Cannot data interval with send codes QY, HY, or PY")
            elif self._value_pattern.match(token) :
                #------------#
                # data value #
                #------------#
                if parameter_code is None :
                    raise ShefParser.ParseException("Value encountered before parameter code")
                value, qualifier = self.parse_value_token(token.upper(), parameter_code[:2], units)
                if not qualifier :
                    qualifier = default_qualifier
                if qualifier not in self._qualifier_codes :
                    self.warning(f"Unknown data qualifier: [{qualifier}], qualifier set to Z")
                    qualifier = 'Z'
                comment = None
                if len(tokens[i]) > 1 :
                    comment = tokens[i][1]
                    if comment :
                        if comment[0] not in "'\"" :
                            self.error(f"Invalid retained comment [{tokens[i][2]}]")
                            comment = None
            elif not token :
                #------------------------------------#
                # missing value if in list of values #
                #------------------------------------#
                if not (parameter_code and interval) :
                    raise ShefParser.ParseException("Null field in data definition")
                obstime += interval
                time_series_code = 2
            elif token[0] in "\"'" :
                #------------------#
                # retained comment #
                #------------------#
                if value is None :
                    self.error("Comment encountered before value")
                    if self._reject_problematic :
                        return []
            else :
                self.error(f"Unexpected data string item: [{token}]")
                if self._reject_problematic :
                    return []
                obstime += interval
                continue

            if value is not None :
                if not parameter_code :
                    raise ShefParser.ParseException("Value encountered before parameter code")
                if not interval :
                    raise ShefParser.ParseException("Value encountered before interval")

                if parameter_code[3] == 'F' and not createtime_str :
                    self.warning(f"Forecast parameter [{parameter_code}] value [{value}] does not have creation date")

                outrec = ShefParser.OutputRecord(
                    self,
                    location,
                    parameter_code,
                    orig_parameter_code,
                    obstime,
                    createtime_str,
                    value,
                    qualifier,
                    revised,
                    duration_unit,
                    duration_value,
                    time_series_code = time_series_code,
                    comment = comment)

                outrecs.append(outrec)
                time_series_code = 2
                try :
                    obstime += interval
                except ShefParser.Exc as spe :
                    self.error(str(spe))
                    return [] if self._reject_problematic else outrecs
        return outrecs

    def parse_dot_b_message(self, message: str) -> list:
        '''
        Parses a .B or .BR message and return a list of OutputRecord objects
        '''

        def retokenize(tokens: list) -> list :
            '''
            Accomodates sloppy slash usage in .B message body like shefit
            '''
            new_tokens = []
            for i in range(len(tokens)) :
                if not tokens[i] :
                    new_tokens.append(tokens[i])
                    continue
                tokens[i] = ShefParser.hide_quoted_whitespace(tokens[i])
                temp_tokens = tokens[i].split()
                for j in range(len(temp_tokens)) :
                    if temp_tokens[j][0] in "'\"" :
                        new_tokens[-1] += ' '+temp_tokens[j]
                    else :
                        new_tokens.append(temp_tokens[j])
            for i in range(len(new_tokens)) :
                new_tokens[i] = ShefParser.unhide_quoted_whitespace(new_tokens[i])
            return new_tokens

        #------------------------------------------------------------------------------------#
        # separate the header (positional fields and parameter control) from the data string #
        #------------------------------------------------------------------------------------#
        m = self._dot_b_header_lines_pattern.search(message)
        if not m :
            raise ShefParser.ParseException(f"Invalid .B message: {message}")
        lines = m.group(0).strip().split('\n')
        lines[0] = lines[0].strip()
        for i in range(1, len(lines)) :
            lines[i] = lines[i][len(lines[i].split()[0]):].strip()
            if lines[i] and lines[0][-1] != '/' and lines[i][0] != '/' : lines[0] += '/'
            lines[0] += lines[i]
        header = lines[0]
        body = '\n'.join(message[m.end():].strip().split('\n')[:-1]).strip()
        #------------------------------------#
        # parse the header positional fields #
        #------------------------------------#
        revised    = None
        msg_source = None
        time_zone  = None
        m = self._positional_fields_pattern.search(message)
        if not m :
            raise ShefParser.ParseException(f"Mal-formed positional fields: [{message}]")
        #--------------------------------------#
        # process the header positional fields #
        #--------------------------------------#
        revised    = message[2].upper() == 'R'
        msg_source = m.group(1).upper()
        time_zone  = m.group(6).upper() if m.group(6) else 'Z'
        dateval, century_specified = self.parse_header_date(m.group(2).upper(), time_zone, self.shefit_times)
        if not time_zone : time_zone = 'Z'
        zi      = self.get_time_zone(time_zone)
        dateval = ShefParser.DateTime(dateval.year, dateval.month, dateval.day, tzinfo=zi)
        #-----------------------------#
        # set the default data values #
        #-----------------------------#
        if time_zone == 'Z' :
            default_obstime = ShefParser.DateTime(dateval.year, dateval.month, dateval.day, 12, 0, 0, tzinfo=zi)
        else :
            default_obstime = ShefParser.DateTime(dateval.year, dateval.month, dateval.day, 24, 0, 0, tzinfo=zi)
        dateval = ShefParser.DateTime(dateval.year, dateval.month, dateval.day, tzinfo=zi)
        parameter_code     = None
        obstime_specified  = False
        obstime            = default_obstime
        last_explicit_time: Union[None, ShefParser.DateTime] = default_obstime
        relativetime: Union[None, timedelta, MonthsDelta] = None
        createtime_str     = None
        createtime         = None
        qualifier          = 'Z'
        units              = "EN"
        units_override     = None
        duration_unit      = 'Z'
        duration_value: Union[None, int] = None
        use_prev_7am       = False
        hdr_param_info: list[Any] = []
        param_count        = 0
        outrecs: list[ShefParser.OutputRecord] = []
        if last_explicit_time is None :
            raise ShefParser.ParseException("No message date time")
        #--------------------------------------#
        # process the parameter control fields #
        #--------------------------------------#
        param_str = header[m.end():].strip()
        while self._multiple_obs_time_pattern.search(param_str) :
            param_str = self._multiple_obs_time_pattern.sub(r"\1@\6\7", param_str)
        param_tokens = list(map(lambda s : s.strip().strip('@'), param_str.strip('/').split('/')))
        last = None
        obstime_error = None
        for token in param_tokens :
            try :
                if self._obs_time_pattern2.search(token) :
                    #----------------------------------------------------#
                    # set the observation time for subsequent parameters #
                    #----------------------------------------------------#
                    pos = 0
                    while True :
                        m = self._obs_time_pattern2.search(token[pos:])
                        if not m :
                            self.error(f"Unexpected data string item: [{token[pos:]}]")
                            return []
                        try :
                            obstime, relativetime, century_specified = self.get_observation_time(last_explicit_time, m.group(1).upper(), century_specified, dot_b=True)
                            if relativetime is not None:
                                obstime_specified = False
                            else :
                                if obstime is None :
                                    raise ShefParser.ParseException("Bad absolute or relatieve time token: [{token}]")
                                last_explicit_time = obstime
                                obstime_specified = True
                        except ShefParser.Exc as spe :
                            obstime_error = str(spe)
                        pos += m.end()
                        if pos >= len(token) :
                            break
                elif self._create_time_pattern.match(token) :
                    #-------------------------------------------------#
                    # set the creation time for subsequent parameters #
                    #-------------------------------------------------#
                    createtime_str = token[2:]
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
                        raise ShefParser.ParseException(f"Bad data qualifier: [{qualifier}]")
                elif self._duration_code_pattern.match(token) :
                    #--------------------------------------------------------------------#
                    # set the duration for subequent parameters with duration code = 'V' #
                    #--------------------------------------------------------------------#
                    duration_unit = token[2].upper()
                    if duration_unit == 'Z' :
                        duration_value = None
                    else :
                        duration_value = int(token[3:])
                        if duration_value > 99 :
                            raise ShefParser.ParseException(f"Invalid duration code variable [{token}]")
                elif self._parameter_code_pattern.match(token) :
                    #----------------------------------------------------------#
                    # create a new parameter control object for this parameter #
                    #----------------------------------------------------------#
                    code = token.upper()
                    if len(code) < 2 :
                        raise ShefParser.ParseException(f"Invalid PE code: [{code[:min(2, len(code))]}]")
                    elif code not in self._send_codes and code[:2] not in self._pe_conversions :
                        self.warning(f"Unknown PE code: [{code[:min(2, len(code))]}], value(s) will be untransformed")
                    parameter_code, use_prev_7am = self.get_parameter_code(code)
                    orig_parameter_code = code
                    if obstime_error :
                        raise ShefParser.ParseException(obstime_error)

                    if createtime_str and not createtime :
                        hdr_param_info.append(ShefParser.DotBHeaderParameterInfo(
                            self,
                            parameter_code,
                            orig_parameter_code,
                            last_explicit_time,
                            use_prev_7am,
                            relativetime,
                            createtime_str,
                            None,
                            units,
                            qualifier,
                            duration_unit,
                            duration_value))
                        createtime = hdr_param_info[0].createtime
                    else :
                        if obstime_specified :
                            relativetime = None
                        elif relativetime is None and last is not None:
                            relativetime = hdr_param_info[last].relativetime
                        hdr_param_info.append(ShefParser.DotBHeaderParameterInfo(
                            self,
                            parameter_code,
                            orig_parameter_code,
                            last_explicit_time,
                            use_prev_7am,
                            relativetime,
                            None,
                            createtime,
                            units,
                            qualifier,
                            duration_unit,
                            duration_value))
                    param_count += 1
                    last = len(hdr_param_info) - 1
                    obstime_specified = False
                    relativetime = None
                elif not token :
                    pass
                else :
                    self.error(f"Unexpected data string item: [{token}]")
                    return []
            except ShefParser.Exc as spe :
                self.error(str(spe))
                if self._reject_problematic :
                    return []
                hdr_param_info.append(None)
        #------------------#
        # process the body #
        #------------------#
        body = body.replace(',', '\n')
        bodylines = list(map(lambda x : x.strip(), body.split('\n')))
        last = None
        for i in range(len(bodylines)) :
            p = 0
            outrec_pos = 0
            obstime_override = None
            relativetime_override = None
            createtime_override_str = None
            default_qualifier = None
            units_override = None
            last_explicit_time = None
            comment = None
            duration_unit = 'Z'
            duration_value = None
            skip_parameter = False
            time_overrides = len(hdr_param_info) * [None]
            relativetime_overrides = len(hdr_param_info) * [None]
            if not self._dot_b_body_line_pattern.match(bodylines[i]) and bodylines[i].strip() :
                self.error(f"Invalid item in body line or packed report: [{bodylines[i]}]")
                if self._reject_problematic :
                    return []
                continue
            if not bodylines[i].strip() :
                continue
            location = bodylines[i].split()[0]
            bodytokens = list(map(lambda s: s.strip(), bodylines[i][len(location):].strip().split('/')))
            bodytokens = retokenize(bodytokens)
            for token in bodytokens :
                try :
                    if p >= len(hdr_param_info) :
                        if token :
                            self.warning(f"Too many tokens in .B body line [{bodylines[i]}]. Header contains {len(hdr_param_info)} valid parameters")
                        break
                    if not token :
                        p += 1
                        continue
                    if self._obs_time_pattern.match(token) :
                        #-------------------#
                        # obs time override #
                        #-------------------#
                        try :
                            t = last_explicit_time if last_explicit_time else \
                                obstime if obstime else \
                                hdr_param_info[p].obstime
                            if token[1] == 'M' and len(token) > 6 :
                                token = token.ljust(12, '0')
                            elif token[1] == 'D' and len(token) > 4 :
                                token = token.ljust(10, '0')
                            elif token[1] == 'H' :
                                token = token.ljust(8, '0')
                            elif token[1] == 'N' and len(token) == 4:
                                token = token.ljust(6, '0')
                            obstime_override, relativetime_override, century_specified = self.get_observation_time(t, token, century_specified, dot_b=True)
                            if relativetime_override is not None :
                                relativetime_overrides[p] = relativetime_override
                            else :
                                last_explicit_time = obstime_override
                                time_overrides[p] = obstime_override
                        except ShefParser.Exc as spe :
                            skip_parameter = True
                            raise
                    elif self._create_time_pattern.match(token) :
                        #----------------------#
                        # create time override #
                        #----------------------#
                        createtime_override_str = token[2:]
                    elif self._unit_system_pattern.match(token) :
                        #----------------#
                        # units override #
                        #----------------#
                        units_override = "EN" if token[2].upper() == 'E' else "SI"
                    elif self._data_qualifier_pattern.match(token) :
                        #----------------------------#
                        # default qualifier override #
                        #----------------------------#
                        default_qualifier = token[2]
                    elif self._duration_code_pattern.match(token) :
                        #----------------------------#
                        # duration variable override #
                        #----------------------------#
                        duration_unit = token[2].upper()
                        if duration_unit == 'Z' :
                            duration_value = None
                        else :
                            duration_value = int(token[3:])
                    else :
                        #-------------------------------#
                        # value with or without comment #
                        #-------------------------------#
                        if hdr_param_info[p] :
                            try :
                                value, qualifier = self.parse_value_token(token, hdr_param_info[p].pe_code, hdr_param_info[p].units)
                            except ShefParser.Exc as spe :
                                p += 1
                                outrec_pos += 1
                                raise
                            if default_qualifier and not qualifier :
                                qualifier = default_qualifier
                            if qualifier and qualifier not in self._qualifier_codes :
                                self.warning(f"Unknown data qualifier: [{qualifier}], qualifier set to Z")
                            m = self._retained_comment_pattern.search(token)
                            if m :
                                comment = m.group(0)
                            if comment :
                                if comment[0] not in "'\"" :
                                    self.error(f"Invalid data value [{token}]")
                                    if self._reject_problematic :
                                        return []
                                    break
                            if p > 0 :
                                if not time_overrides[p] and last is not None and time_overrides[last] :
                                    time_overrides[p] = time_overrides[last]
                                if relativetime_overrides[p] is None and last is not None and relativetime_overrides[last] is not None :
                                    relativetime_overrides[p] = relativetime_overrides[last]
                            if not skip_parameter :

                                if hdr_param_info[p].parameter_code[3] == 'F' and not hdr_param_info[p].createtime :
                                    self.warning(f"Forecast parameter [{hdr_param_info[p].parameter_code}] value [{value}] does not have creation date")

                                outrecs.append(hdr_param_info[p].get_output_record(
                                    revised,
                                    msg_source,
                                    location,
                                    time_overrides[p] if time_overrides[p] else last_explicit_time,
                                    relativetime_overrides[p],
                                    createtime_override_str,
                                    units_override,
                                    duration_unit if duration_unit != 'Z' else None,
                                    duration_value if duration_unit != 'Z' else None,
                                    value,
                                    qualifier,
                                    comment))

                                outrec_pos += 1
                                last = p
                            else :
                                skip_parameter = False
                        value = None
                        comment = None
                        duration_unit = 'Z'
                        duration_value = None
                        p += 1
                except ShefParser.Exc as e :
                    self.error(exc_info(e))
                    if self._reject_problematic :
                        return []
            if outrec_pos < param_count :
                self.warning(f"Value count ({outrec_pos}) is less than parameter count ({param_count}) for location [{location}]")
        return outrecs
    
def parse(
        input_name: Optional[str],
        output_name: Optional[str],
        output_format: int,
        append_output: bool,
        log_name: Optional[str],
        log_level: str,
        append_log: bool,
        log_timestamps: bool,
        shefparm: Optional[str],
        use_defaults: bool,
        shefit_times: bool,
        reject_problematic: bool,
        loader_spec: str,
        unload: bool,) :
    '''
    Either parse incoming SHEF (optionally loading into a datastore) or unload from a datastore into SHEF text

        input               : Name of input file (SHEF text for parsing, possibly intermediate data for unloading). Use None or "" for <stdin>
        output              : Name of output file (shefit -1 or shefit -2 for parsing or possibly intermediate data for loading). Use None or "" for <stdout>
        output_format       : 1 for shefit -1 or 2 for shefit -2 (not used with a loader)
        append_output       : Whether to append to existing output if outputting to a file
        log                 : Name of log file. Use None or "" for <stderr>
        log_level           : "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"
        append_log          : Whether to append to existing log if logging to a file
        log_timestamps      : Whether to timestamp log records
        shefparm            : Name of SHEFPARM file if not in standard locations (current dir or $rfs_sys_dir)
        use_defaults        : Ignore any SHEFPARM file in standard locations (current dir or $rfs_sys_dir)
        shefit_times        : Whether to use same logic as shefit program for time zones and daylight savings transitions
        reject_problematic  : Whether to reject all data from messages that generate parsing errors
        loader_spec         : Name of loader and options for loading to data store
        unload              : Whether to use loader to unload from data store
    '''
    global logger
    start_time = datetime.now()
    #-------------------------------------------------------#
    # assign input and output streams if no filenames given #
    #-------------------------------------------------------#
    input:  Union[TextIO, str] = sys.stdin  if not input_name  else input_name
    output: Union[TextIO, str] = sys.stdout if not output_name else output_name
    log:    Union[TextIO, str] = sys.stderr if not log_name    else log_name
    #-----------------------------------------------------------------#
    # get default SHEFPARM file if exists and --default not specified #
    #-----------------------------------------------------------------#
    if not shefparm and not use_defaults :
        p = Path.joinpath(Path(os.getenv("rfs_sys_dir", Path.cwd())), Path("SHEFPARM"))
        if p.exists() and not p.is_dir() :
            shefparm = str(p)
    elif use_defaults :
        shefparm = None
    #-------------------#
    # set up the logger #
    #-------------------#
    datefmt = "%Y-%m-%d %H:%M:%S"
    if log_timestamps :
        format  = "%(asctime)s %(levelname)s: %(msg)s"
    else :
        format  = "%(levelname)s: %(msg)s"
    level  = {
        "DEBUG"    : logging.DEBUG,
        "INFO"     : logging.INFO,
        "WARNING"  : logging.WARNING,
        "ERROR"    : logging.ERROR,
        "CRITICAL" : logging.CRITICAL,
        "ALL"      : logging.NOTSET}[log_level]
    if isinstance(log, str) :
        if os.path.exists(log) :
            if not os.path.isfile(log) :
                raise Exception(f"{log} is not a regular file")
            if not append_log :
                os.remove(log)
        logging.basicConfig(filename=log, format=format, datefmt=datefmt, level=level)
        logfile_name = log
    else :
        logging.basicConfig(stream=log, format=format, datefmt=datefmt, level=level)
        logfile_name = log.name
    logger  = logging.getLogger(progname)
    #------------------#
    # log startup info #
    #------------------#
    infile_name = input if isinstance(input,  str) else input.name
    outfile_name = output if isinstance(output, str) else output.name
    if len(sys.argv) == 1 :
        logger.info("")
        logger.info(f"Use '{progname} -h' for help")
        logger.info("")
        logger.info(f"Reading from {infile_name}, press ^D (^Z+Enter on Windows) to exit")
        logger.info("")
    logger.info("----------------------------------------------------------------------")
    logger.info(f"Program {progname} version {version} ({version_date}) starting up")
    logger.info("----------------------------------------------------------------------")
    logger.debug(f"Input file set to {infile_name}")
    logger.debug(f"Output file set to {outfile_name}")
    logger.debug(f"Log file set to {logfile_name}")
    logger.debug(f"Log level set to {log_level}")
    if shefparm and not use_defaults :
        logger.debug(f"Will modify program defaults with content of file {shefparm}")
    else :
        logger.debug(f"Will use program defaults")
    if unload and not loader_spec :
        print("\nArgument --unload may only be used if argument --loader is also used")
        exit(-1)
    #--------------------------------#
    # create the loader if specified #
    #--------------------------------#
    loader = None
    if loader_spec :
        try :
            pos = loader_spec.find('[')
            if pos == -1 :
                loader_name = loader_spec
                loader_args = None
            else :
                loader_name = loader_spec[:pos]
                loader_args = loader_spec[pos:]
            if loader_name in ["base", "base_loader"] :
                raise ShefParser.ParseException("Cannot directly use the base loader")
            if loader_name in available_loaders :
                loader_info = available_loaders[loader_name]
            elif f"{loader_name}_loader" in available_loaders :
                loader_info = available_loaders[f"{loader_name}_loader"]
            else :
                logger.critical(f"No such loader: {loader_name}")
                exit(-1)
            loader = loader_info["class"](logger, output, append_output)
            loader.set_options(loader_args)
        except Exception as e :
            logger.critical(exc_info(e))
            raise
    if unload :
        #-----------------#
        # write SHEF text #
        #-----------------#
        if not loader :
            raise Exception("Cannot call unload() without a valid loader")
        try :
            loader.set_input(input)
            loader.unload()
        except Exception as e :
            logger.critical(exc_info(e))
            raise
    else :
        #----------------#
        # read SHEF text #
        #----------------#
        #-------------------#
        # create the parser #
        #-------------------#
        parser = ShefParser(output_format, shefparm, shefit_times=shefit_times, reject_problematic=reject_problematic)
        parser.set_input(input)
        parser.set_output(output, append_output)
        if loader :
            parser.set_additional_pe_codes(loader.get_additional_pe_codes(parser.get_recognized_pe_codes()))
        else :
            if output_format == 1 and isinstance(parser._output, TextIOWrapper) and parser._output.isatty():
                parser._output.write("STATION   OBSERVATION-DATE/TM  CREATION-DATE/TIME   PARM-CD     DATA-VALUE Q  PROB-CD DURTN R T  GROUP-NM  QUOTE\n")
                parser._output.write('aaaaaaaa  yyyy mm dd hh nn ss  yyyy mm dd hh nn ss  pedtsep     rrrrr.dddd a  rrr.ddd iiiii i i  aaaaaaaa  "aa..."\n\n')
        #--------------------------------------------------------------------------------#
        # parse the messages on the input and either generate output or pass to a loader #
        #--------------------------------------------------------------------------------#
        message_count = 0
        value_count   = 0
        while True :
            message = parser.get_next_message()
            if not message : break
            message_count += 1
            outrecs = None
            try :
                outrecs = parser.parse_message()
                value_count += len(outrecs)
                if outrecs :
                    for outrec in outrecs :
                        if loader :
                            format_1_str = outrec.format(ShefParser.OutputRecord.SHEFIT_TEXT_V1)
                            loader.set_shef_value(format_1_str)
                        else :
                            parser.output(outrec)
            except (ShefParser.Exc, loaders.LoaderException) as e :
                parser.error(exc_info(e))
        #-------------------#    
        # clean up and exit #
        #-------------------#    
        if loader :
            loader.done()
        else :
            parser.close_output()
            logger.info("")
            logger.info("--[Summary]-----------------------------------------------------------")
            logger.info(f"Program    = {progname} version {version} ({version_date})")
            logger.info(f"SHEFPARM   = {shefparm}")
            logger.info(f"Start Time = {str(start_time)[:-7]}")
            logger.info(f"Run Time   = {str(datetime.now() - start_time)[:-3]}")
            logger.info(f"{parser._line_number:6d} lines read from {parser._input_name}")
            logger.info(f"{message_count:6d} messages processed")
            if loader :
                logger.info(f"{value_count:6d} values passed to {loader.loader_name}")
            else :
                logger.info(f"{value_count:6d} values output to {parser._output_name}")
            logger.info(f"{parser._warning_count:6d} warnings in {parser._messages_with_warning_count} messages")
            logger.info(f"{parser._error_count:6d} errors in {parser._messages_with_error_count} messages")

def main() -> None :
    '''
    Driver routine
    '''
    #--------------------#
    # parse command line #
    #--------------------#
    argparser = argparse.ArgumentParser(
        formatter_class = argparse.RawDescriptionHelpFormatter,
        description="Parses SHEF messages into different output formats")
    group = argparser.add_mutually_exclusive_group()
    group.add_argument(
        "-s",
        "--shefparm",
        action="store",
        help="path of SHEFPARM file to use")
    argparser.add_argument(
        "-i",
        "--in",
        action="store",
        default=sys.stdin,
        metavar="input_filename",
        help="input file (defaults to <stdin>)")
    argparser.add_argument(
        "-o",
        "--out",
        action="store",
        default=sys.stdout,
        metavar="output_filename",
        help="output file (defaults to <stdout>)")
    argparser.add_argument(
        "-l",
        "--log",
        action="store",
        default=sys.stderr,
        metavar="log_filename",
        help="log file (defaults to <sterr>)")
    argparser.add_argument(
        "-f",
        "--format",
        type=int,
        action="store",
        choices=[1,2],
        default=1,
        help=f"output format (defaults to 1)")
    argparser.add_argument(
        "-v",
        "--loglevel",
        action="store",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="verbosity/logging level (defaults to INFO)")
    argparser.add_argument(
        "--loader",
        metavar="<ts_loader>",
        action="store",
        help="allows loading time series to various data stores (more info in --description)")
    group.add_argument(
        "--defaults",
        action="store_true",
        help="use program defaults (ignore default SHEFPARM)")
    argparser.add_argument(
        "--timestamps",
        action="store_true",
        help="timestamp log output")
    argparser.add_argument(
        "--shefit_times",
        action="store_true",
        help="use shefit date/time logic")
    argparser.add_argument(
        "--reject_problematic",
        action="store_true",
        help="reject all values from messages that contain errors")
    argparser.add_argument(
        "--append_out",
        action="store_true",
        help="append to output file instead of overwriting")
    argparser.add_argument(
        "--append_log",
        action="store_true",
        help="append to log file instead of overwriting")
    argparser.add_argument(
        "--unload",
        action="store_true",
        help="use loader to unload from data store to SHEF text")
    argparser.add_argument(
        "--make_shefparm",
        action="store_true",
        help="write SHEFPARM data to <stdout> and exit (exclusive to other arguments except -o/--out)")
    argparser.add_argument(
        "--description",
        action="store_true",
        help="show a more detailed program description and exit")
    args = argparser.parse_args()

    if args.make_shefparm :
        if args.shefparm or getattr(args, "in") != sys.stdin or args.log != sys.stderr or args.format != 1 or args.loglevel != "INFO" \
        or args.defaults or args.timestamps or args.reject_problematic or args.description :
            print("\nArgument --make_shefparm may not be used with any other argument except -o/--out\n")
            exit(-1)
        ShefParser.write_shefparm_data(args.out)
        exit(0)

    if args.description :
        print(f'''
{progname} is a pure Python replacement for the shefit program from NOAA/NWS.

SHEFPARM file:
    Unlike shefit, {progname} doesn't require the use of a SHEFPARM file, although one may be used.

    If --defaults is not specified, {progname} uses the same rules as shefit for locating the
    SHEFPARM file:
        1. the current directory is searched first
        2. the directory specified by "rfs_sys_dir" environment variable is searched

    However, unlike shefit which exits if no SHEFPARM file is found, {progname} will use program
    defaults instead. The program defaults have the same behavior as using the SHEFPARM file
    bundled with the latest source code for shefit.

    Also unlike shefit, the location of the SHEFPARM file can be specified the using -s/--shefparm
    option, and doesn't need to be named SHEFPARM. Using -s/--shefparm overrides searching the
    default locations for the file.

    If a SHEFPARM file is used, any modifications it makes to the program defaults are logged at
    the INFO and/or WARNING levels on program startup.

    The --defaults option may be specified to force {progname} to use program defaults if a
    SHEFPARM file exists in the current or $rfs_sys_dir directories.

    The --defaults and -s/--shefparm options are mutually exclusive.

    The --make_shefparm option may be used to output program defaults in SHEFPARM format. This may
    be useful if it is necessary to override the program defaults. Either redirect <stdout> or
    use the -o/--out option to capture the SHEFPARM data to a file in order to modify it for use.

Output format:
    Like shefit, the default output format is the shefit text version 1. The output formats
    -f/--format 1 and -f/--format 2 are equivalent to the shefit -1 and -2 options, respectively.
    There is no equivalent to the shefit -b (binary output) option.

Times and timezone processing:
    By default, {progname} uses modern date/time and time zone objects to process times and time
    zones, which do not always produce the same results as the logic used in shefit. Use the
    --shefit_times option to force {progname} to use the same date/time logic as shefit. This is
    helpful when comparing {progname} output to shefit output for a common input.

    Note that using --shefit_times causes {progname} to (like shefit) always generate incorrect UTC
    times for SHEF time zones Y, YD, YS, and ND, and to generate incorrect UTC times for SHEF time
    zone N during daylight saving time.

Messages with errors:
    In many circumstances {progname} is able to process valid portions of messages that occur
    after an erroneous portion, where shefit normally stops further processing of a message when
    it encounters an error. This usually results in parsing more valid values from problematic
    messages than shefit. However, it can result treating invalid data as valid in certain messages
    that are badly mangled. This behavior can be prevented by using the --reject_problematic option
    which discards all data from messages with errors.

Loading SHEF data to data stores:''')
        if not available_loaders :
            print("    The 'loaders' package was not found or it contained no valid loaders.")
        else :
            for loader_name in sorted(available_loaders) :
                if loader_name == "base_loader" :
                    continue
                description = "\n                    ".join(available_loaders[loader_name]["description"].split(chr(10)))
                options =     "\n                    ".join(available_loaders[loader_name]["option_format"].split(chr(10)))
                print(f"    loader        : {loader_name} v{available_loaders[loader_name]['version']}")
                print(f"    Description   : {description}")
                print(f"    Can unload    : {available_loaders[loader_name]['can_unload']}")
                print(f"    Option Format : {options}")
                print("")

        exit(0)

    input = getattr(args, "in")
    parse(
        input_name         = input if isinstance(input, str) else None,
        output_name        = args.out if isinstance(args.out, str) else None,
        output_format      = args.format,
        append_output      = args.append_out,
        log_name           = args.log if isinstance(args.log, str) else None,
        log_level          = args.loglevel,
        append_log         = args.append_log,
        log_timestamps     = args.timestamps,
        shefparm           = args.shefparm,
        use_defaults       = args.defaults,
        shefit_times       = args.shefit_times,
        reject_problematic = args.reject_problematic,
        loader_spec        = args.loader,
        unload             = args.unload,)

if __name__ == "__main__" :
    main()

