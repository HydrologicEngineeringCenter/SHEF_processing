Exporters
=========

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   exporter-requirements
   using-cda-exporter
   using-dss-exporter

.. role:: py(code)
    :language: python

Exporters are for use with loaders that have an :py:`unload()` method, and are used to deliver time series
to the loaders' input for unloading (generating SHEF text from the time series).

Loaders can unload time series without exporters, but the time series to unload must be available on the
SHEF parser's (and thus the loader's) input device in the format used by the loader. If the time series are
available in this format, the using ``run_shef_parser --loader <loader-spec> --unload`` will suffice. However,
in most contexts, some extra functionality is needed to retrieve the desired time series (with the desired 
time window) from the data store, and format it appropriately for the loader.

Workflow Using an Exporter
--------------------------
Instead of running from a command line, exporters are used from within Python - either in scripts or
in interactive sessions. The workflow generally follows the following process:

1. Import the exporter
2. Instantiate the exporter with its specific parameters
3. Specify or connect to a data store (if not already done in previous step)
4. Set the exporter's time window by assigning :py:`Optional[datetime.dateime]` objects to its
   :py:`start_time` and :py:`end_time` properties
5. Set the exporter's output to a file or other ouptut using the exporter's :py:`set_output(...)` method
6. Call the exporter's :py:`export(...)` method, passing a time series identifier (or a group identifier
   if the exporter supports groups)
7. Repeat steps 3-6 as necessary
8. Delete the exporter (possibly by exiting the script). The exporter should release any resources is has.

A work flow might look like:

.. code-block:: python

   from datetime import datetime, timedelta
   from shef.exporters.abc_exporter import AbcExporter
   exporter = AbcExporter(<abc-data-store>, <user-credentials>)
   exporter.end_time = datetime.now()
   exporter.start_time = exporter.end_time - timedelta(days=7)
   exporter.set_output("/path/to/output_file.shef")
   with open("time_series_to_output.txt") as f:
      for time_series in [line.strip() for line in f]:
         exporter.export(time_series)
   exit()