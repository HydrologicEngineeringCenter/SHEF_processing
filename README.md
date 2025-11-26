# Package SHEF Parser

A python based package to parse SHEF files and optionally load them into various data stores. It also provides functionality for generating SHEF
text from various data stores.

Parsing and loading can be performed by using module in python or through command line. Generating SHEF text from a data store is currenly limited
to using the module in python.

See User Guide at https://shef-parser.readthedocs.io/en/latest/

See API Documentation at https://hydrologicengineeringcenter.github.io/shef-parser/index.html

## Install

```sh
pip install shef-parser
```

## Loading via command line
```sh
#CWMS CDA loader
shefParser -i input_filename --loader cda[$API_ROOT][$API_KEY]
```

```sh
#HEC-DSS loader
shefParser -i input_filename --loader dss[<dss_file>][<sensors_file>][<parameters_file>]
```

## Loading via module
```python
#CWMS CDA loader
import os
from shef import shef_parser

cda_url: str = os.getenv("CDA_API_ROOT")
cda_api_key: str = os.getenv("CDA_API_KEY")

shef_parser.parse(
    input_name=input_filename,
    loader_spec=f"cda[{cda_url}][{cda_api_key}]",
)
```

```python
#HEC-DSS loader
from shef import shef_parser

dss_filename: str = "/path/to/dss_file"
sensors_filename: str = "/path/to/sensors_file"
parameters_filename: str = "/path/to/parameters_file"

shef_parser.parse(
    input_name=input_filename,
    loader_spec=f"dss[{dss_filename}][{sensors_filename}][{parameters_filename}]",
)
```

## Generating SHEF Text
```python
#CWMS CDA loader
import os
from datetime import datetime, timedelta
from shef.exporters import cda_exporter

cda_url: str = os.getenv("CDA_API_ROOT")
office_id: str = os.getenv("CDA_OFFICE_ID")
tsids: list[str] = [
    ...
]

exporter = cda_exporter.CdaExporter(cda_url, office_id)
exporter.start_time = datetime.now() - timedelta(days=1)
exporter.end_time = datetime.now()
with open("/path/to/output_file", "w") as f:
    exporter.set_output(f)
    for (tsid in tsids):
        exporter.export(tsid)
```

```python
#HEC-DSS loader
from datetime import datetime, timedelta
from shef.exporters import dss_exporter

dss_filename: str = "/path_to_dss_file"
sensors_filename: str = "/path/to/sensors_file"
parameters_filename: str = "/path/to/parameters_file"
pathnames: list[str] = [
    ...
]

exporter = dss_exporter.DssExporter(
    dss_filename,
    sensors_filename,
    parameters_filename
)
exporter.start_time = datetime.now() - timedelta(days=1)
exporter.end_time = datetime.now()
with open("/path/to/output_file", "w") as f:
    exporter.set_output(f)
    for (pathname in pathnames):
        exporter.export(pathname)
```
