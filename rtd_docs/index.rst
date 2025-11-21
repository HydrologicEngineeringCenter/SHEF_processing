.. shef-parser documentation master file, created by
   sphinx-quickstart on Wed Nov 19 09:02:39 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

User Guide for Package shef-parser |release| 
=============================================

.. toctree::
   :maxdepth: 1
   :caption: Contents:

   helper-script
   command-line
   description
   loaders
   exporters
   shefit

.. role:: py(code)
    :language: python
    
Overview
---------

This package proviedes the capability to:

* Parse SHEF text
* Load parsed text into data stores as time series
* Generate SHEF text from time series stored in data stores

.. dropdown:: What is SHEF?

   SHEF is an acronym for Standard Hydrometeorologic Exhchange Format, created in the early 1980s
   by NOAA/NWS, with major participation from USACE, USGS, and other agencies, to provide a standard
   format for exchanging hydromet observations and forecasts that is both human readable and machine parsable.

   SHEF provides multiple ways of encoding information and has been extended over time to provide more
   capabilities. The current standard is version 2.2, dated July 5, 2012, available
   `here <https://www.google.com/url?sa=t&rct=j&q=&esrc=s&source=web&cd=&ved=2ahUKEwiqkISqkvqQAxXyQjABHdeoE9QQFnoECBkQAQ&url=https%3A%2F%2Fwww.weather.gov%2Fmedia%2Fmdl%2FSHEF_CodeManual_5July2012.pdf&usg=AOvVaw0k3t5QKxjiMX1oPJXSOR3K&opi=89978449>`_.

   Although SHEF is no longer actively supported by NWS and was intended to be replaced by newer standards
   such as WaterML, it is still widely used.

Parsing
-------

Parsing SHEF text includes the following steps:

1. Reading the SHEF-formatted text
2. Identifying individual messages within the text
3. Validating messages and logging errors
4. Outputting the parsed text using one of two rigid output formats.

So the SHEF parser is really just a fancy text format converter. However, it is a necessary one because while SHEF
text must adhere to a standard, in order to meet the goal of human readability the standard is very flexible with regard to:

* unit system
* time zone
* use of whitespace
* order of information
* assumed defaults
* intermingling of SHEF and non-SHEF content

Having a dedicated parser to convert SHEF text into a not-so-human-readable format that is much simpler to parse by
machine allows downstream programs to employ much simpler parsing code.

In this package SHEF parser is the :py:`shef.shef_parser` module; it is assumed you will execute it using ``run_shef_parser``.

.. dropdown:: Format Examples

   SHEF Text::

      .E KEYO2 20251107 Z DH1400/HT/DIH01/637.74/637.73/637.72/637.71/637.71/637.7/637.7/637.38
      .E00 641.01/641.11/641.15/641.11/638.93/638.32/638.06/637.93/637.85/637.81/637.78/637.76
      .E01 637.74/637.74/637.35/640.99/641.08/641.13/638.9/638.31/637.7/641.01/641.11/641.15

   Output Format 1::

      KEYO2     2025-11-07 14:00:00  0000-00-00 00:00:00  HTIRZZ        637.7400 Z   -1.000  0000 0 1            " "
      KEYO2     2025-11-07 15:00:00  0000-00-00 00:00:00  HTIRZZ        637.7300 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-07 16:00:00  0000-00-00 00:00:00  HTIRZZ        637.7200 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-07 17:00:00  0000-00-00 00:00:00  HTIRZZ        637.7100 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-07 18:00:00  0000-00-00 00:00:00  HTIRZZ        637.7100 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-07 19:00:00  0000-00-00 00:00:00  HTIRZZ        637.7000 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-07 20:00:00  0000-00-00 00:00:00  HTIRZZ        637.7000 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-07 21:00:00  0000-00-00 00:00:00  HTIRZZ        637.3800 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-07 22:00:00  0000-00-00 00:00:00  HTIRZZ        641.0100 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-07 23:00:00  0000-00-00 00:00:00  HTIRZZ        641.1100 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 00:00:00  0000-00-00 00:00:00  HTIRZZ        641.1500 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 01:00:00  0000-00-00 00:00:00  HTIRZZ        641.1100 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 02:00:00  0000-00-00 00:00:00  HTIRZZ        638.9300 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 03:00:00  0000-00-00 00:00:00  HTIRZZ        638.3200 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 04:00:00  0000-00-00 00:00:00  HTIRZZ        638.0600 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 05:00:00  0000-00-00 00:00:00  HTIRZZ        637.9300 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 06:00:00  0000-00-00 00:00:00  HTIRZZ        637.8500 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 07:00:00  0000-00-00 00:00:00  HTIRZZ        637.8100 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 08:00:00  0000-00-00 00:00:00  HTIRZZ        637.7800 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 09:00:00  0000-00-00 00:00:00  HTIRZZ        637.7600 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 10:00:00  0000-00-00 00:00:00  HTIRZZ        637.7400 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 11:00:00  0000-00-00 00:00:00  HTIRZZ        637.7400 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 12:00:00  0000-00-00 00:00:00  HTIRZZ        637.3500 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 13:00:00  0000-00-00 00:00:00  HTIRZZ        640.9900 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 14:00:00  0000-00-00 00:00:00  HTIRZZ        641.0800 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 15:00:00  0000-00-00 00:00:00  HTIRZZ        641.1300 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 16:00:00  0000-00-00 00:00:00  HTIRZZ        638.9000 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 17:00:00  0000-00-00 00:00:00  HTIRZZ        638.3100 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 18:00:00  0000-00-00 00:00:00  HTIRZZ        637.7000 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 19:00:00  0000-00-00 00:00:00  HTIRZZ        641.0100 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 20:00:00  0000-00-00 00:00:00  HTIRZZ        641.1100 Z   -1.000  0000 0 2            " "
      KEYO2     2025-11-08 21:00:00  0000-00-00 00:00:00  HTIRZZ        641.1500 Z   -1.000  0000 0 2            " "

   Output Format 2::

      KEYO2   202511 714 0 0    0 0 0 0 0 0 HT RZZ   637.740 Z -1.00    0 0         1
      KEYO2   202511 715 0 0    0 0 0 0 0 0 HT RZZ   637.730 Z -1.00    0 0         2
      KEYO2   202511 716 0 0    0 0 0 0 0 0 HT RZZ   637.720 Z -1.00    0 0         2
      KEYO2   202511 717 0 0    0 0 0 0 0 0 HT RZZ   637.710 Z -1.00    0 0         2
      KEYO2   202511 718 0 0    0 0 0 0 0 0 HT RZZ   637.710 Z -1.00    0 0         2
      KEYO2   202511 719 0 0    0 0 0 0 0 0 HT RZZ   637.700 Z -1.00    0 0         2
      KEYO2   202511 720 0 0    0 0 0 0 0 0 HT RZZ   637.700 Z -1.00    0 0         2
      KEYO2   202511 721 0 0    0 0 0 0 0 0 HT RZZ   637.380 Z -1.00    0 0         2
      KEYO2   202511 722 0 0    0 0 0 0 0 0 HT RZZ   641.010 Z -1.00    0 0         2
      KEYO2   202511 723 0 0    0 0 0 0 0 0 HT RZZ   641.110 Z -1.00    0 0         2
      KEYO2   202511 8 0 0 0    0 0 0 0 0 0 HT RZZ   641.150 Z -1.00    0 0         2
      KEYO2   202511 8 1 0 0    0 0 0 0 0 0 HT RZZ   641.110 Z -1.00    0 0         2
      KEYO2   202511 8 2 0 0    0 0 0 0 0 0 HT RZZ   638.930 Z -1.00    0 0         2
      KEYO2   202511 8 3 0 0    0 0 0 0 0 0 HT RZZ   638.320 Z -1.00    0 0         2
      KEYO2   202511 8 4 0 0    0 0 0 0 0 0 HT RZZ   638.060 Z -1.00    0 0         2
      KEYO2   202511 8 5 0 0    0 0 0 0 0 0 HT RZZ   637.930 Z -1.00    0 0         2
      KEYO2   202511 8 6 0 0    0 0 0 0 0 0 HT RZZ   637.850 Z -1.00    0 0         2
      KEYO2   202511 8 7 0 0    0 0 0 0 0 0 HT RZZ   637.810 Z -1.00    0 0         2
      KEYO2   202511 8 8 0 0    0 0 0 0 0 0 HT RZZ   637.780 Z -1.00    0 0         2
      KEYO2   202511 8 9 0 0    0 0 0 0 0 0 HT RZZ   637.760 Z -1.00    0 0         2
      KEYO2   202511 810 0 0    0 0 0 0 0 0 HT RZZ   637.740 Z -1.00    0 0         2
      KEYO2   202511 811 0 0    0 0 0 0 0 0 HT RZZ   637.740 Z -1.00    0 0         2
      KEYO2   202511 812 0 0    0 0 0 0 0 0 HT RZZ   637.350 Z -1.00    0 0         2
      KEYO2   202511 813 0 0    0 0 0 0 0 0 HT RZZ   640.990 Z -1.00    0 0         2
      KEYO2   202511 814 0 0    0 0 0 0 0 0 HT RZZ   641.080 Z -1.00    0 0         2
      KEYO2   202511 815 0 0    0 0 0 0 0 0 HT RZZ   641.130 Z -1.00    0 0         2
      KEYO2   202511 816 0 0    0 0 0 0 0 0 HT RZZ   638.900 Z -1.00    0 0         2
      KEYO2   202511 817 0 0    0 0 0 0 0 0 HT RZZ   638.310 Z -1.00    0 0         2
      KEYO2   202511 818 0 0    0 0 0 0 0 0 HT RZZ   637.700 Z -1.00    0 0         2
      KEYO2   202511 819 0 0    0 0 0 0 0 0 HT RZZ   641.010 Z -1.00    0 0         2
      KEYO2   202511 820 0 0    0 0 0 0 0 0 HT RZZ   641.110 Z -1.00    0 0         2
      KEYO2   202511 821 0 0    0 0 0 0 0 0 HT RZZ   641.150 Z -1.00    0 0         2  

Loading
-------

Loading is the process of reading the output of the SHEF parser and loading the data into a data store.
While the SHEF parser can be agnostic of any specific data store, a loading program must be intimately
tied to the datastore's structure, API, etc....

In this package, loaders are not stand-alone programs but are sub-modules of the :py:`shef.loaders` module written to an API that allows 
:py:`shef.shef_parser` to pass its output directly to them to be loaded to the desired data store. To tell
:py:`shef.shef_parser` to use a specific loader you use the ``--loader`` command line switch follwed by loader-specific
arguments. The arguments required by each loader are specified on the command line in one or more bracketed
text strings (e.g., ``[arg1][arg2]...``) and can be displayed by running ``run_shef_parser --description``.

In the event that one has on hand not the SHEF text but parsed text, :py:`shef.shef_parser` can pass the processed text
through to an attached loader by using the ``--processed`` command line argument.

Information on how loaders interact with shef_parser and the API they are required to implement is detailed on the
:doc:`loader-requirements` page.

Command line information is shown in the :doc:`command-line` page.

Exporting/Unloading
-------------------

As described on the :doc:`loader-requirements` page, each loader module is required to have a public boolean variable named
:py:`can_unload` that specifies whether its loader class contains an :py:`unload()` method. If provided, the :py:`unload()`
method reads time series data on the loader's input and generates one or more SHEF messages for each time series read.
Typically, one ``.E`` message or multiple ``.A`` messages for each time series depending on whether the time series
has a regular or irregular interval.

While a loader's loading input (parsed SHEF text) can be generated by :py:`shef.shef_parser`, there is no way for it to
generate a loader's unloading input (loader-specific-formatted time series). This is the role of exporters. This
requires each loader to have its own exporter.

Exporters are sub-modules of the :py:`shef.exporters` module.

The role of an exporter is to retrieve time series from a data store and write them to the loader's input in the correct
format for unloading. This normally involves:

* choosing a data store
* setting a time window
* selecting and retrieving time series
* writing time series in the loader's format

While exporters may define their own methods to allow them to be executed from the command line, there is no
requirement for them to do so. The API they are required to implement is detailed on the :doc:`exporter-requirements` page.

