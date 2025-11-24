Using The CdaLoader Class
=========================

.. toctree::
   :maxdepth: 1
   :caption: Contents:

This page does not cover unloading with the ``--unload`` command line option, which is covered in the :doc:`using-cda-exporter` page.

Command Line
------------

To use the CdaLoader class, specify ``--loader cda[<cda_url_root>][<cda_api_key>]`` on the command line, where

* ``<cda_url_root>`` is the URL to the Cwms Data API (e.g., ``https://cwms-data-test.cwbi.us/cwms-data/`` for the CWBI test database)
* ``<cda_api_key>`` is your personal authentication key for the database referenced by the URL

It is recommended to use environment variables to hold the URL root and API key so that your command line would look 
something like ``run_shef_parser  --loader cda[%CDA_URL_ROOT%][%CDA_API_KEY%]`` on Windows or ``run_shef_parser --loader cda[$CDA_URL_ROOT][$CDA_API_KEY]``
on Linux

Loading Configuration
----------------------

The configuration information for loading SHEF data into a CWMS database is specified by assigning time series to be loaded
to the ``SHEF Data Acquisition`` time series group under the ``Data Acquisition`` time series category. If no ``SHEF Data Acquisition``
time series group exists for your office in the CWMS database, you may create it under the ``Data Acquisition`` time series category.
You can use CWMS-Vue to both create the time series group and assign individual time series to it.

The assigned time series use the ``Alias`` field to hold the SHEF loading configuration. The information must be of the format
``<shef-loc>.<shef-pe-code>.<shef-ts+ext-code>.<shef-dur-value>:Units=<shef-unit>``
where:

* ``<shef-loc>`` is the location identifer in the SHEF text
* ``<shef-pe-code>`` is the SHEF phyical element code in the SHEF text
* ``<shef-ts+ext-code>`` is the SHEF type and source code concatenated with the SHEF extremum code [1]_ in the SHEF text
* ``<shef-dur-value>`` is the SHEF duration numeric value corresponding to the duration code in the SHEF text
* ``<shef-unit>`` is the unit of the values in the SHEF text

For information on SHEF codes, see the `SHEF Code Manual <https://www.google.com/url?sa=t&rct=j&q=&esrc=s&source=web&cd=&ved=2ahUKEwiqkISqkvqQAxXyQjABHdeoE9QQFnoECBkQAQ&url=https%3A%2F%2Fwww.weather.gov%2Fmedia%2Fmdl%2FSHEF_CodeManual_5July2012.pdf&usg=AOvVaw0k3t5QKxjiMX1oPJXSOR3K&opi=89978449>`_

Examples
--------

It is important to note that the alias field value must *match the actual SHEF text*, so if non-standard SHEF text is being received, the
alias field may have to have values that disagree with the SHEF standard for the time series.

An exmple (non-standard) configuration and a command line session using it to load data is shown below.

.. figure:: images/cda_loader_config.png
   :alt: Application screenshot
   :width: 100%
   :align: left

   CWMS-Vue with SHEF loading configuration info (double-click to see larger image).

::

    U:\Devl\git\SHEF_processing>run_shef_parser -i testing/cda_test.shef --loader cda[%cda_url_root%][%cda_api_key%]
    INFO: ----------------------------------------------------------------------
    INFO: Program shef_parser version 1.6.0 (19Nov2025) starting up
    INFO: ----------------------------------------------------------------------
    INFO: CdaLoader v0.5 instatiated
    INFO: Beginning CWMS-Data-API POST tasks...
    INFO: Stored 168 values in TestLoc.Elev.Inst.1Hour.0.Test
    INFO: Stored 168 values in TestLoc.Stor.Inst.1Hour.0.Test
    INFO: CWMS-Data-API POST tasks complete (0.62 seconds)
    INFO: --[Summary]-----------------------------------------------------------
    INFO: 336 values posted in 2 time series

    U:\Devl\git\SHEF_processing>

.. [1] The extremum code is almost never in the SHEF text (although it *is* in the processed text). If absent, it defaults to ``Z`` (not an extremum).