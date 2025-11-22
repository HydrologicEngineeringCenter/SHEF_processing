Loader Requirements
===================

.. toctree::
   :maxdepth: 1
   :caption: Contents:

.. role:: py(code)
    :language: python

As stated in the main page, loaders are modules within the :py:`shef.loaders` module.

Loader Module Requirements
--------------------------

Any loader that fails to meet all of these requirements will raise and :py:`ImportError` on import.

* A loader module must be named ``<loader-name>_loader.py`` where <loader-name> will be used in the ``--loader`` command line option

* A loader module must have the following global variables in order to be imported. Multi-line strings are acceptable

  * :py:`loader_options: str` - The first line of this string should indicate the format of the ``--loader`` command line option.
    Subsequent lines may document the loader arguments
  * :py:`loader_description: str` - A description of what the loader is used for
  * :py:`loader_version: str` - The version number of the loader as a string
  * :py:`loader_class: class` - The class that is the loader. This class must be defined in the module and must be a subclass of :py:`shef.loaders.AbstractLoader`
  * :py:`can_unload: bool` - Specifies whether :py:`loader_class` has an :py:`unload()` method
  
  .. code-block:: python
  
      # abc_loader.py
      from shef.loaders import AbstractLoader
      class AbcLoader(AbstractLoader):
          ...
      ...
      loader_options = "--loader abc[ds_name][usr_cred]\n"
                       "* ds_name is the name of the ABC data store\n"
                       "* usr_cred is the ABC user credential string"
      loader_description = "Loads SHEF data to the specifed ABC data store\n"
                           "Allows only encoded user credential string"
      loader_version = "1.0.3"                         
      loader_class = AbcLoader
      can_unload = True

Loader Class Requirements
-------------------------

As stated above, the loader class must be a subclass of :py:`shef.loaders.AbstractLoader`. As such it *must*:

* call the :py:`AbstractLoader.__init__(...)` method from its own :py:`__init__(...)` method.
    .. code-block:: python

        #abc_loader.py

        from io import BufferedRandom
        from logging import Logger
        from typing import Optional, TextIO, Union


      class AbcLoader(abstract_loader.AbstractLoader):
          """
          Loads/unloads to/from ABC data stores.
          """

        def __init__(
            self,
            logger: Optional[Logger],
            output_object: Optional[Union[BufferedRandom, TextIO, str]] = None,
            append: bool = False,
        ) -> None:
            super().__init__(logger, output_object, append)

    where :py:`append: bool` specifies whether to append to the output if it is a file-like object

* implement the method :py:`load_time_series(self) -> None`
    :py:`shef.loaders.AbstractLoader` has the following variables that are used in this method:

    .. code-block:: python

        self._time_series: list[list[str]] = []
        self._value_count: int = 0
        self._time_series_count: int = 0

    The :py:`self._time_series` variable contains a list of lists, with each inner list containing
    
    .. code-block:: python

        [
            str,        # date_time
            str | None, # value
            str | None, # data_qualifier
            str | None  # forecast date_time
        ]

    At the conclusion of the method, the variables :py:`self._value_count` and :py:`self._time_series_count` should be incremented
    by the total number of values stored and the number of store operations, respectively

In addition to implementing :py:`load_time_series(self) -> None` method, a loader will likely *want* to override the
following methods of :py:`shef.loaders.AbstractLoader`:

* :py:`done(self) -> None`: You may want to close the data store and log summary information

    .. code-block:: python

        #dss_loader.py
        def done(self) -> None:
            """
            Load any remaining time series and close the output if necessary
            """
            super().done()
            if self._dss_file:
                self._dss_file.close()
            if self._logger:
                self._logger.info(
                    "--[Summary]-----------------------------------------------------------"
                )
                self._logger.info(
                    f"{self._value_count} values output in {self._time_series_count} time series"
                )

* :py:`get_additional_pe_codes(self, parser_recognized_pe_code: set[str]) -> set[str]`: This is used by :py:`shef.shef_parser` when loading
  to prevent warning messages on PE codes recognized by the loader that aren't recognized by the parser

  The default behavior returns an empyt set
* :py:`get_time_series_name(self, shef_value: Optional[shared.ShefValue]) -> str`: Returns a loader-specific time series identifier
  for the specified :py:`shared.ShefValue`.

  The default behavior returns the SHEF location identifier and parameter code separated by a "."
* :py:`loading_info(self) -> dict[str, Any]`: Returns any info required for loading that can't be determined by the time series identifier.

  The default behavoir returns an empty dictionary
* :py:`location(self) -> str`: Returns a loader-specific location identifier.

  The default behavior returns the SHEF location and full parameter
* :py:`parameter(self) -> str`: Returns a location specific parameter identifier.

  The default behavior returns the SHEF parameter code
* :py:`set_options(self, options_str: Optional[str]) -> None`: Sets the loader options from the options string.

  The default behavior simply logs the options at INFO level
* :py:`use_value(self) -> bool`: Returns whether the current :py:`ShefValue` should be loader_description

  The default behavior always returns :py:`True`
* :py:`value(self) -> Any`: Returns a loader-specific data value of the current :py:`ShefValue`

  The default behavior returns the current :py:`ShefValue.value`
