"""
# Module shef

This package provides the capability to:
* Parse SHEF text
* Load parsed text into data stores as time series
* Generate SHEF text from time series stored in data stores

See the [User Guide](https://shef-parser.readthedocs.io/en/latest/)
"""

__all__: list[str] = [
    "shef_parser",
    "loaders",
    "exporters",
]

from . import import_validator

import_validator.install()
from shef import shef_parser
