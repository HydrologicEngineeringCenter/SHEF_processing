"""
# Module shef.exporters

This module includes modules to be used for exporting SHEF data from specific data stores, using the `unload()` methods of loaders from the shef.loaders module

See the [User Guide](https://shef-parser.readthedocs.io/en/latest/)
"""

__all__: list[str] = [
    "abstract_exporter",
    "cda_exporter",
    "dss_exporter",
]

error_modules = [] # used only when shef_parser.py is executed
import_errors = {} # caches exporter import errors until someone tries to execute 'from shef.exporters import XxxExporter'
try:
    from shef.exporters import abstract_exporter
    from .abstract_exporter import AbstractExporter
except:
    raise Exception("ERROR|Cannot import abstract_exporter")

try:
    from shef.exporters import cda_exporter
    from .cda_exporter import CdaExporter
except Exception as e:
    error_modules.append("cda_exporter")
    import_errors["CdaExporter"] = e

try:
    from shef.exporters import dss_exporter
    from .dss_exporter import DssExporter
except Exception as e:
    error_modules.append("dss_exporter")
    import_errors["DssExporter"] = e

def __getattr__(name: str) :
    if name in globals():
        return globals()[name]
    raise import_errors[name]
