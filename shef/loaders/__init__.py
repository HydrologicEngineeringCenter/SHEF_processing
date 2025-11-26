"""
# Module shef.loaders

This module includes modules to be used for loading (storing) SHEF data (as parsed by the `shefParser` program) to specific data stores,
and optionally unloading (generating SHEF text) from specific data stores. Each module is responsible for one data store type.

See the [User Guide](https://shef-parser.readthedocs.io/en/latest/)
"""

__all__: list[str] = [
    "LoaderException",
    "abstract_loader",
    "cda_loader",
    "dss_loader",
]

from shef.loaders.shared import LoaderException

error_modules = []
try:
    from shef.loaders import abstract_loader
except:
    raise Exception("ERROR|Cannot import abstract_loader")

try:
    from shef.loaders import cda_loader
except:
    error_modules.append("cda_loader")

try:
    from shef.loaders import dss_loader
except:
    error_modules.append("dss_loader")
