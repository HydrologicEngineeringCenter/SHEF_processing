"""
Contains routines to convert SHEFDSS column-based sensor and parameter files to CSV format

make_sensor_csv(col_filename: str, csv_filename: Optional[str] = None) -> int

    Converts a shefdss-style sensor file from columnar form to CSV form to allow longer A, B, and F
    pathname parts.

    Arguments:
        col_filename (required) The path to the sensor or parameter file to convert
        csv_filename (optional) The path to the resulting CSV file. If not specified, the output will
                                be written to a file with the same name as col_filename but with any
                                extension replaced with ".csv"

    Returns:
        zero on success
        non-zero on error

make_parameter_csv(col_filename: str, csv_filename: Optional[str] = None) -> int

    Converts a shefdss-style parameter file from columnar form to CSV form to allow a longer C
    pathname part.

    Arguments:
        col_filename (required) The path to the sensor or parameter file to convert
        csv_filename (optional) The path to the resulting CSV file. If not specified, the output will
                                be written to a file with the same name as col_filename but with any
                                extension replaced with ".csv"

    Returns:
        zero on success
        non-zero on error

"""

import os
import sys
from typing import Optional, TextIO


def _open_files_(
    col_filename: str, csv_filename: Optional[str] = None
) -> tuple[TextIO, TextIO]:
    """
    Opens a columnar file for reading and a CSV file for writing and returns them
    """
    col_file = None
    csv_file = None
    if not os.path.exists(col_filename):
        raise Exception(f"ERROR: Specified text file [{col_filename}] does not exist")
    if not os.path.isfile(col_filename):
        raise Exception(
            f"\nERROR: Specified text file [{col_filename}] is not a regular file"
        )
    try:
        col_file = open(col_filename, "r")
    except:
        raise Exception(
            f"ERROR: Could not open specified text file [{col_filename}] for reading"
        )
    if csv_filename:
        if os.path.exists(csv_filename) and not os.path.isfile(csv_filename):
            col_file.close()
            raise Exception(
                f"ERROR: Specified CSV file [{csv_filename}] is not a regular file"
            )
    else:
        csv_filename = f"{os.path.splitext(col_filename)[0]}.csv"
    try:
        csv_file = open(csv_filename, "w")
    except:
        col_file.close()
        raise Exception(f"ERROR: Could not open CSV file [{csv_filename}] for writing")
    return col_file, csv_file


def _make_csv_record_(items: tuple[str, ...]) -> str:
    """
    returns a string of comma-separated items, quoting any items that contain a comma
    """
    return ",".join(
        map(lambda x: f"{str(x)}" if str(x).find(",") == -1 else f'"{str(x)}"', items)
    )


def make_sensor_csv(col_filename: str, csv_filename: Optional[str] = None) -> int:
    """
    Converts a shefdss-style sensor file from columnar form to CSV form to allow longer A, B, and F
    pathname parts.

    Arguments:
        col_filename (required) The path to the sensor or parameter file to convert
        csv_filename (optional) The path to the resulting CSV file. If not specified, the output will
                                be written to a file with the same name as col_filename but with any
                                extension replaced with ".csv"

    Returns:
        zero on success
        non-zero on error
    """
    # ----------------#
    # open the files #
    # ----------------#
    try:
        col_file, csv_file = _open_files_(col_filename, csv_filename)
    except Exception as e:
        sys.stderr.write(f"\n{str(e)}\n\n")
        return -1
    try:
        # ---------------------------#
        # output field descriptions #
        # ---------------------------#
        for line in """
            * SHEF ID  (required),,,,,
            * PE Code  (required),,,,,
            * Interval (optional),,,,,
            *          blank=irregular,,,,,
            *          * = use SHEF duration,,,,,
            *          nU where n = number and U in (M H D L Y),,,,,
            *              5M = 5Minutes,,,,,
            *              6H = 6Hours,,,,,
            *              1D = 1Day,,,,,
            *              1L = 1Month,,,,,
            *              1Y = 1Year,,,,,
            * A Part (optional) defaults to blank,,,,,
            * B Part (optional) defaults to SHEF ID,,,,,
            * F Part (optional) set to * for forecast time,,,,,
            ***********************************************,,,,,
            * SHEF ID,PE_Code,Interval,A Part,B Part,F Part
        """.strip().split(
            "\n"
        ):
            csv_file.write(f"{line.strip()}\n")
        # ---------------------------#
        # convert columns to fields #
        # ---------------------------#
        for line in col_file.readlines():
            line = line.strip()
            if not line:
                csv_file.write("\n")
                continue
            elif line[0] == "*" or not line[:10].strip():
                continue
            location = line[:8].strip()
            pe_code = line[8:10].strip()
            interval = line[10:15].strip()
            a_part = line[16:33].strip()
            b_part = line[33:50].strip()
            f_part = line[50:67].strip()
            csv_file.write(
                f"{_make_csv_record_((location, pe_code, interval, a_part, b_part, f_part))}\n"
            )
        return 0
    except Exception as e:
        sys.stderr.write(f"\n{str(e)}\n\n")
        return -1
    finally:
        col_file.close()
        csv_file.close()


def make_parameter_csv(col_filename: str, csv_filename: Optional[str] = None) -> int:
    """
    Converts a shefdss-style parameter file from columnar form to CSV form to allow a longer C
    pathname part.

    Arguments:
        col_filename (required) The path to the sensor or parameter file to convert
        csv_filename (optional) The path to the resulting CSV file. If not specified, the output will
                                be written to a file with the same name as col_filename but with any
                                extension replaced with ".csv"

    Returns:
        zero on success
        non-zero on error
    """
    # ----------------#
    # open the files #
    # ----------------#
    try:
        col_file, csv_file = _open_files_(col_filename, csv_filename)
    except Exception as e:
        sys.stderr.write(f"\n{str(e)}\n\n")
        return -1
    try:
        # ---------------------------#
        # output field descriptions #
        # ---------------------------#
        for line in """
            * PE code,,,,
            * C Part, (optional),,,
            *     blank = SHEF PE code,,,,
            * Data Unit (required),,,,
            * Data Type (required),,,,
            *     * = infer data type from SHEF parameter,,,,
            * Conversion (optional),,,,
            *     number = numerical factor,,,,
            *     hm2h = hhmm->decimal h,,,,
            *     dur2h = MW<duration> -> MWh for (VK VL VM VR),,,,
            *********************************************************,,,,
            *PE Code,C Part,Data Unit,Data Type,Conversion
        """.strip().split(
            "\n"
        ):
            csv_file.write(f"{line.strip()}\n")
        # ---------------------------#
        # convert columns to fields #
        # ---------------------------#
        for line in col_file.readlines():
            line = line.strip()
            if not line:
                csv_file.write("\n")
                continue
            elif line[0] == "*" or not line[:2].strip():
                continue
            pe_code = line[:2].strip()
            c_part = line[3:29].strip()
            unit = line[29:36].strip()
            data_type = line[38:45].strip()
            transform = line[47:56].strip()
            csv_file.write(
                f"{_make_csv_record_((pe_code, c_part, unit, data_type, transform))}\n"
            )
        return 0
    except Exception as e:
        sys.stderr.write(f"\n{str(e)}\n\n")
        return -1
    finally:
        col_file.close()
        csv_file.close()
