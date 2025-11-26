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

from .abstract_exporter import AbstractExporter
from .cda_exporter import CdaExporter
from .dss_exporter import DssExporter

error_modules = []
try:
    from shef.exporters import abstract_exporter
except:
    raise Exception("ERROR|Cannot import abstract_exporter")

try:
    from shef.exporters import cda_exporter
except:
    error_modules.append("cda_exporter")

try:
    from shef.exporters import dss_exporter
except:
    error_modules.append("dss_exporter")
