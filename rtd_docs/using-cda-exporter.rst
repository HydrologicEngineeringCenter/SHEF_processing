Using the CdaExporter Class
===========================

.. toctree::
   :maxdepth: 1
   :caption: Contents:

.. role:: py(code)
    :language: python

Exporting Configuration
-----------------------

The configuration information for exporting SHEF data from a CWMS database is stored much like the SHEF loading configuration.
However, instead of having one import time series group, you can create as many time series groups as necessary under the 
``SHEF Export`` time series category, and assign the time series to be exported to the groups. Note that this allows for a single time
series to be a member of more than one export group.

.. dropdown:: Why use sparate time series categoreies & groups for loading and unloading?

    1. It allows for SHEF text for a specific location and parameter to be loaded into one time series and unloaded from another one.
       This allows loading into a "raw" (not screened or validated) time series and unloading from a "revised" (screeened and validiated)
       time series.

    2. Using multiple groups for export allows the :py:`CdaExporter` to export by group name instead of having to export multiple time series
       identifiers to unload SHEF text for specific purposes

As in the SHEF loading configuration, assigned time series use the ``Alias`` field to hold the SHEF unloading configuration. The information must be of the format
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

An exmple configuration and a Python script using it to unload data is shown below. Note that some non-standard SHEF PE
codes are used, so an annotated SHEF file is created that has extra information.

.. figure:: images/cda_exporter_config.png
   :alt: Application screenshot
   :width: 100%
   :align: left

   CWMS-Vue with SHEF unloading configuration info (double-click to see larger image).

.. code-block:: python

    # export_arbuckle.py

    import os
    from datetime import datetime, timedelta
    from shef.exporters import CdaExporter

    exporter = CdaExporter(os.getenv("cda_url_root"), "SWT")
    exporter.start_time = datetime.now() - timedelta(hours=6)
    exporter.end_time = datetime.now()

    # ------------------------------------------------------------------ #
    # Generate SHEF data for time series in group "ARBU" (Arbuckle Lake) #
    # ------------------------------------------------------------------ #
    # Create a file with just SHEF data (no indication of missing data)  #
    # ------------------------------------------------------------------ #
    with open("Arbuckle.shef", "w") as f:
        exporter.set_output(f)
        exporter.export("ARBU")
    # -------------------------------------------- #
    # Create an annotated SHEF file that includes: #
    # 1. Source time series IDs                    #
    # 2. SHEF units                                #
    # 3. Indication of missing data                #
    # -------------------------------------------- #
    with open("Arbuckle-annotated.shef", "w") as f:
        exporter.set_output(f)
        for tsid in exporter.get_time_series("ARBU"):
            f.write(f":\n: {tsid}, unit={exporter.get_unit(tsid)}\n:\n")
            shef = exporter.get_export(tsid)
            f.write(shef if shef else "<No data in time window>\n\n")


.. dropdown:: Arbuckle.shef

    ::

        .E ARBO2 20251124 Z DH060000/LSHPZZ/DIH01
        .E1 73.3261/73.3737/73.3499/73.3737/73.3737/73.3737/

        .E ARBO2 20251124 Z DH060000/PCHPZZ/DIH01
        .E1 38.85/38.99/39.05/39.06/39.06/39.08/

        .E ARBO2 20251124 Z DH060000/HPHPZZ/DIH01
        .E1 872.39/872.41/872.4/872.41/872.41/872.41/

        .E ARBO2 20251124 Z DH060000/VBHPZZ/DIH01
        .E1 13.05/13.05/13.05/13.05/13.05/13.05/

        .E ARBO2 20251124 Z DH060000/YHHPZZ/DIH01
        .E1 12.97/12.97/12.97/12.97/12.97/12.97/

        .E ARBO2 20251124 Z DH060000/YLHPZZ/DIH01
        .E1 100/100/100/100/100/100/

        .E ARBO2 20251124 Z DH060000/YDHPZZ/DIH01
        .E1 62.571/62.571/62.571/62.571/62.571/62.571/

        .E ARBO2 20251124 Z DH060000/YMHPZZ/DIH01
        .E1 2.54375/2.67419/2.609/2.67419/2.67419/2.67419/

        .E ARBO2 20251124 Z DH060000/YEHPZZ/DIH01
        .E1 0.92712/0.97466/0.9509/0.97466/0.97466/0.97466/



.. dropdown:: Arbuckle-annotated.shef

    ::

        :
        : ARBU.Stor.Inst.1Hour.0.Ccp-Rev, unit=kaf
        :
        .E ARBO2 20251124 Z DH060000/LSHPZZ/DIH01
        .E1 73.3261/73.3737/73.3499/73.3737/73.3737/73.3737/

        :
        : ARBU.Precip-Cuml.Inst.1Hour.0.Ccp-Rev, unit=in
        :
        .E ARBO2 20251124 Z DH060000/PCHPZZ/DIH01
        .E1 38.85/38.99/39.05/39.06/39.06/39.08/

        :
        : ARBU.Elev.Inst.1Hour.0.Ccp-Rev, unit=ft
        :
        .E ARBO2 20251124 Z DH060000/HPHPZZ/DIH01
        .E1 872.39/872.41/872.4/872.41/872.41/872.41/

        :
        : ARBU.Volt-Battery.Inst.1Hour.0.Ccp-Rev, unit=volt
        :
        .E ARBO2 20251124 Z DH060000/VBHPZZ/DIH01
        .E1 13.05/13.05/13.05/13.05/13.05/13.05/

        :
        : ARBU.Volt-Battery Load.Inst.1Hour.0.Ccp-Rev, unit=volt
        :
        .E ARBO2 20251124 Z DH060000/YHHPZZ/DIH01
        .E1 12.97/12.97/12.97/12.97/12.97/12.97/

        :
        : ARBU.Precip-Cuml Alt.Inst.1Hour.0.Ccp-Rev, unit=in
        :
        <No data in time window>

        :
        : ARBU.%-Conservation Pool Full.Inst.1Hour.0.Ccp-Rev, unit=%
        :
        .E ARBO2 20251124 Z DH060000/YLHPZZ/DIH01
        .E1 100/100/100/100/100/100/

        :
        : ARBU.Stor-Conservation Pool.Inst.1Hour.0.Ccp-Rev, unit=kaf
        :
        .E ARBO2 20251124 Z DH060000/YDHPZZ/DIH01
        .E1 62.571/62.571/62.571/62.571/62.571/62.571/

        :
        : ARBU.%-Flood Pool Full.Inst.1Hour.0.Ccp-Rev, unit=%
        :
        .E ARBO2 20251124 Z DH060000/YMHPZZ/DIH01
        .E1 2.54375/2.67419/2.609/2.67419/2.67419/2.67419/

        :
        : ARBU.Stor-Flood Pool.Inst.1Hour.0.Ccp-Rev, unit=kaf
        :
        .E ARBO2 20251124 Z DH060000/YEHPZZ/DIH01
        .E1 0.92712/0.97466/0.9509/0.97466/0.97466/0.97466/



.. [1] Use ``Z`` unless you know the values represent some extremum (min or max over a time period), in which case consult the
       `SHEF Code Manual <https://www.google.com/url?sa=t&rct=j&q=&esrc=s&source=web&cd=&ved=2ahUKEwiqkISqkvqQAxXyQjABHdeoE9QQFnoECBkQAQ&url=https%3A%2F%2Fwww.weather.gov%2Fmedia%2Fmdl%2FSHEF_CodeManual_5July2012.pdf&usg=AOvVaw0k3t5QKxjiMX1oPJXSOR3K&opi=89978449>`_.