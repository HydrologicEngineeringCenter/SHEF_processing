Exporter Requirements
=====================

.. toctree::
   :maxdepth: 1
   :caption: Contents:

.. role:: py(code)
    :language: python

As stated in the main page, exporters are modules within the :py:`shef.exporters` module.

Exporter Module Requirements
----------------------------

Any exporter that fails to meet all of these requirements will raise and :py:`ImportError` on import.

* An exporter module must be named ``<exporter-name>_exporter.py`` where <exporter-name> is the loader name of the loader module it uses.

* An exporter module must have the following global variables in order to be imported. Multi-line strings are acceptable

  * :py:`exporter_parameters` - A description of the parameters required for the exporter class's initializer (:py:`__init__` method)
  * :py:`exporter_description: str` - A description of what the exporter is used for
  * :py:`exporter_version: str` - The version number of the exporter as a string
  * :py:`exporter_class: class` - The class that is the exporter. This class must be defined in the module and must be a subclass of :py:`shef.loaders.AbstractExporter`
  * :py:`loader_class: class` - The loader class that the exporter uses.
  
  .. code-block:: python
  
      # abc_exporter.py
      from shef import loaders
      from shef.exporters import AbstractExporter
      class AbcExporter(AbstractExporter):
          ...
      ...
        exporter_description = "Outputs SHEF text from time series in ABC data stores"
        exporter_parameters = "abc_filename: str, user_credentials: str"
        exporter_version = "1.0.0"
        exporter_class = AbcExporter
        loader_class = loaders.abc_lodader.AbcLoader

Exporter Class Requirements
---------------------------

As stated above, the loader class must be a subclass of :py:`shef.loaders.AbstracExporter`. As such it *must*:

* call the :py:`AbstractExporter.__init__()` method from its own :py:`__init__(self, ...)` method.
    .. code-block:: python

        #abc_exporter.py
      class AbcLoader(abstract_loader.AbstractLoader):
          """
          Loads/unloads to/from ABC data stores.
          """

        def __init__(self, data_store: str, user_credentials: str) -> None:
            super().__init__()

* implement the method :py:`export(self, identifier: str) -> None`
  This method should:
  
  * retrieve the time series (or multiple time series if the exporter supports groups and :py:`identifer` is a group name)
  * format the time series as expected by the loader's :py:`unload()` method
  * write the formatted time series to a file-like object (can be a :py:`io.StringIO` object or a file)
  * set the loader's input to the same file-like object
  * optionally set the loader's output to the desired location
  * call the loader's :py:`unload()` method

  Note that :py:`AbstractExporter` has a :py:`get_export(self., identifier: str) -> str` method that will call
  this exporter's :py:`export(self, identifier: str)` method and return the resulting SHEF text in a string

AbstractExporter Class
-----------------------

The :py:`AbstractExporter` class provides the following properties and methods that can/should be used directly by exporter subclasses:

* properties

  * :py:`start_time: datetime.datetime` (get/set): The start of the export time window. Initially set to :py:`None`, which may have 
    different meanings for different exporters
  * :py:`end_time: datetime.datetime` (get/set): The end of the export time window. Initially set to :py:`None`, which may have 
    different meanings for different exporters
  * :py:`logger: logging.Logger` (get only): A logger for use by exporters. Initially configured to level :py:`logging.WARNING`

* methods

  * :py:`set_output(output: Optional[Union[io.BufferedRandom, typing.TextIO, io.StringIO]]) -> None`: Used to set the exporter's output
    to a file-like object or None (which may have different meanings for different exporters)
  * :py:`get_export(identifier: str) -> str`: calls the current exporter's :py:`export(identifier)` method and returns the results in a string.
    While :py:`AbstractExporter` has no concept of groups, it can be used from exporters that do to collect the output of exporting the
    group in a string.