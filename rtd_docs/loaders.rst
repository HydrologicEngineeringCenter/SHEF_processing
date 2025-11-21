Loaders
=======

.. toctree::
   :maxdepth: 1
   :caption: Contents:

   loader-requirements
   using-cda-loader
   using-dss-loader

.. role:: py(code)
    :language: python

Without the ``--loader`` command line option, :py:`shef.shef_parser` simply outputs the parsed text in one of the
formats described on the :doc:`index` page. With the ``--loader`` command line option, the format is:

``--loader <loader_name><loader_options>``

where:

* ``<loader_name>`` is the name of the loader module without the ``_loader`` portion (e.g., ``abc`` for the module ``abc_loader``)
* ``<loader_options>`` is zero or more loader options, each in square brackets (e.g., ``[opt1][opt2]``)

An example would be ``run_shef_parser --loader abc[opt1][opt2]``

Workflow Using a Loader
-----------------------

When using a loader, the following happens instead:

1. The parser constructs a new loader object based on the loader name passed on the command line, passing 3 arguments:

   * the parser's logger
   * the parser's output object (used if unloading)
   * whether to append to the output object (used if unloading)
2. The parser calls the loader's :py:`set_options(...)` method, passing the loader options specified on the command line
3. If ``--unload`` is specified on the command line

   a. The parser calls the loader's :py:`unload()` method and exits

   If ``--unload`` is *not* specified on the command line

   b. For each SHEF value [1]_, the parser calls the loader's :py:`set_shef_value(value_str: str)` method [2]_, which then:

   * Uses the loader's :py:`time_series_name` property to compare the loader-specific time seies identifier of the SHEF value
     with that of the previous SHEF value (if any).
   * If there was a previous SHEF value and the time series identifier is different, calls the loader's :py:`load_time_series()` method. [3]_
   * Appends the SHEF value into the loader's :py:`_time_series` variable

   c. Calls the loader's :py:`done()` method and exits. [4]_

.. [1] A single SHEF message may contain multiple values, each of which is parsed into a single line in the output
.. [2] The :py:`set_shef_value(value_str: str)` is not normally overridden in a loader, instead using the version in :py:`shef.loaders.abstract_loader.AbstractLoader`
.. [3] :py:`shef.loaders.abstract_loader.AbstractLoader.load_time_series()` is abstract, so it must be implemented by the loader, and it must leave its :py:`_time_series` value empty
.. [4] :py:`shef.loaders.abstract_loader.AbstractLoader.done()` call's the loader's :py:`load_time_series()` method. If additional code is necessary to clean up resources, the loader
       should override the :py:`done()` method and implement its additional code after calling :py:`super().done()`