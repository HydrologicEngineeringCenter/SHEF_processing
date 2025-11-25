Using The DssLoader Class
=========================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   dss_sensors+parameters

.. role:: py(code)
    :language: python

This page does not cover unloading with the ``--unload`` command line option, which is covered in the :doc:`using-dss-exporter` page.

Command Line
------------

To use the :py:`DssLoader` class, specify ``--loader dss[<dss_filename>][<sensor_filename>][<parameter_filename>]`` on the command line,
where

* ``<dss_filename>`` is the absolue or relative path to the HEC-DSS file
* ``<sensor_filename>`` is the absolute or relative path to the sensor file
* ``<parameter_filename>`` is the absolute or relative path to the parameter file

Loading Configuration
----------------------

The configuration information for loading SHEF data into an HEC-DSS file is contained in sensor and paramter files as described in
:doc:`dss_sensors+parameters`

Notes
-----

The loader uses the environment variable ``DSS_MESSAGE_LEVEL`` to control the output level from the HEC-DSS library it uses. Valid levels
are:

* ``0``: No output
* ``1``: Critcal output only
* ``2``: Terse (includes file open and close)
* ``4``: General (default - includes read and write)
* ``5``: User Diagnostic
* ``11``: Internal Diagnostic
* ``13``: Internal Debug


Examples
--------

The example loads SHEF data from a source (Oklahoma Mesonet) that reports multiple parameters for a single time in each report. The
natural way to encode each report into SHEF is to use ``.A`` messages. As can be seen in the command line session below, the
:py:`DssLoader` loads each of the 120 reports individually, resulting in 720 stores to 6 separate time series. Pre-processing the SHEF
into 6 reports would improve the loading efficiency.

.. dropdown:: mesonet.shef file

   ::

      .A TNSO2 20240630 DH0000
      .A00 PCIRRZZ   0.00Z"15:OKMN"
      .A01 XRCRRZZ  56.00Z"15:OKMN"
      .A02 YWCRRZZ 105.00Z"15:OKMN"
      .A03 TACRRZZ  94.28Z"15:OKMN"
      .A04 UDCRRZZ 178.00Z"15:OKMN"
      .A05 USCRRZZ   8.95Z"15:OKMN"
      ...
      ...
      .A TNSO2 20240630 DH2245
      .A00 PCIRRZZ   0.03Z"15:OKMN"
      .A01 XRCRRZZ  63.00Z"15:OKMN"
      .A02 YWCRRZZ 398.00Z"15:OKMN"
      .A03 TACRRZZ  87.98Z"15:OKMN"
      .A04 UDCRRZZ  61.00Z"15:OKMN"
      .A05 USCRRZZ   8.95Z"15:OKMN"

   [1]_

.. dropdown:: sensors.csv file

   ::

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
      TNSO2,PC,,,TULSA,OK Meosnet
      TNSO2,TA,*,,TULSA,OK Meosnet
      TNSO2,UD,*,,TULSA,OK Meosnet
      TNSO2,US,*,,TULSA,OK Meosnet
      TNSO2,XR,*,,TULSA,OK Meosnet
      TNSO2,YW,*,,TULSA,OK Meosnet

   [2]_

.. dropdown:: parameters.csv file

   ::

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
      PC,Precip,in,*,
      TA,Temp-Air,F,*,
      UD,Dir-Wind,deg,*,
      US,Speed-Wind,mph,*,
      XR,%-Relative Humidity,%,*,
      YW,Irrad-Total,W/m2,*,

.. dropdown:: command line session

   ::

      U:\Devl\git\SHEF_processing>set DSS_MESSAGE_LEVEL=1

      U:\Devl\git\SHEF_processing>run_shef_parser -i mesonet.shef --loader dss[mesonet.dss][sensors.csv][parameters.csv]
      INFO: ----------------------------------------------------------------------
      INFO: Program shef_parser version 1.6.0 (19Nov2025) starting up
      INFO: ----------------------------------------------------------------------
      INFO: DssLoader v1.0.0 instatiated

      INFO: DssLoader v1.0.0 initialized with:
            sensor file    : sensors.csv
            parameter file : parameters.csv
      INFO: Set HEC-DSS message level to 1
      INFO: U:\Devl\git\SHEF_processing\SHEFPARM: Maximum error count set to [500]
      INFO: PE code [YW] is now recognized and will not generate any warning messages at mesonet.shef:0
      INFO: Outputting [1] values to be stored to [//TULSA/Precip//IR-Month/OK Meosnet/]
      INFO: Outputting [1] values to be stored to [//TULSA/%-Relative Humidity//15Minute/OK Meosnet/]
      INFO: Outputting [1] values to be stored to [//TULSA/Irrad-Total//15Minute/OK Meosnet/]
      INFO: Outputting [1] values to be stored to [//TULSA/Temp-Air//15Minute/OK Meosnet/]
      INFO: Outputting [1] values to be stored to [//TULSA/Dir-Wind//15Minute/OK Meosnet/]
      INFO: Outputting [1] values to be stored to [//TULSA/Speed-Wind//15Minute/OK Meosnet/]
      ...
      ...
      INFO: Outputting [1] values to be stored to [//TULSA/Precip//IR-Month/OK Meosnet/]
      INFO: Outputting [1] values to be stored to [//TULSA/%-Relative Humidity//15Minute/OK Meosnet/]
      INFO: Outputting [1] values to be stored to [//TULSA/Irrad-Total//15Minute/OK Meosnet/]
      INFO: Outputting [1] values to be stored to [//TULSA/Temp-Air//15Minute/OK Meosnet/]
      INFO: Outputting [1] values to be stored to [//TULSA/Dir-Wind//15Minute/OK Meosnet/]
      INFO: Outputting [1] values to be stored to [//TULSA/Speed-Wind//15Minute/OK Meosnet/]
      INFO: --[Summary]-----------------------------------------------------------
      INFO: 720 values output in 720 time series

      U:\Devl\git\SHEF_processing>python
      Python 3.9.19 (main, May  6 2024, 20:12:36) [MSC v.1916 64 bit (AMD64)] on win32
      >>> from hec import DssDataStore
      >>> DssDataStore.set_message_level(1)

      >>> dss = DssDataStore.open("mesonet.dss")
      >>> for pathname in sorted(dss.catalog()):
      ...     print(dss.retrieve(pathname))
      ...
      //TULSA/%-Relative Humidity//15Minute/OK Meosnet/ 97 values in %
      //TULSA/Dir-Wind//15Minute/OK Meosnet/ 97 values in deg
      //TULSA/Irrad-Total//15Minute/OK Meosnet/ 97 values in W/m2
      //TULSA/Precip//IR-Month/OK Meosnet/ 96 values in in
      //TULSA/Speed-Wind//15Minute/OK Meosnet/ 97 values in mph
      //TULSA/Temp-Air//15Minute/OK Meosnet/ 97 values in F
      >>>
      >>> exit()

      U:\Devl\git\SHEF_processing>

.. [1] The ``"15:OKMN"`` in this SHEF text is a retained comment. To enhance human readability, SHEF text can have interspersed
   comments, toggled on and off by the ``:`` character, but hese comments are stripped during SHEF parsing, whild retained comments are
   preserved in the parsed output. The :py:`DssLoader` ignores retained comments, but a legacy database loader for this data used
   these comments to track the data source and interval.
.. [2] The omission of the ``*`` character in field 3 of the ``TNSO2,PC`` sensor line is inadvertent, but you can see how it
   causes the resulting time series to be irregular-interval instead of 15 minutes.