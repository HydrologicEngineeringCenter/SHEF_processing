The shefdss_util Module
=======================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

.. role:: py(code)
    :language: python

This module contains functions for converting tabular sensor and parameter files to .csv format.

* .. code-block:: python

    make_sensor_csv(
      col_filename: str, 
      csv_filename: Optional[str] = None
    ) -> int

  Reads a columnar sensor file and generates an eqivalent .csv sensor file. If :py:`csv_filename` is not specified, it will be
  the same as :py:`col_filename`, with the extension of ``.csv``.

* .. code-block:: python

    make_parameter_csv(
      col_filename: str, 
      csv_filename: Optional[str] = None
    ) -> int

  Reads a columnar parameter file and generates an eqivalent .csv parameter file. If :py:`csv_filename` is not specified, it will be
  the same as :py:`col_filename`, with the extension of ``.csv``.

Both functions return ``0`` on success an another value on failure.

Example
-------

.. code-block:: python

    from shef.util.shefdss_util import make_sensor_csv, make_parameter_csv

    # generate /path/to/sensor_file.csv
    make_sensor_csv("/path/to/sensor_file.txt")
    # generate /path/to/parameter_file.csv
    make_parameter_csv("/path/to_parameter_file.txt")
