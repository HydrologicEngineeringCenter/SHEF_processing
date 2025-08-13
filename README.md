# Package SHEF Parser

A python based package to parser SHEF files and then loads them into various file formats based on the loader applied.  This package can be run as a module in python or through command line

## Install

```sh
pip install git+https://github.com/HydrologicEngineeringCenter/SHEF_processing.git@master
```

## Command line implementation
'''sh
#base loader
shefParser -i input_filename -o output_filename

#CWMS cda loader
shefParser -i input_filename --loader cda[$API_ROOT][$API_KEY]
'''

## Module implementation
'''python
from shef import shef_parser

#base loader
shef_parser.parse(
    input_name=input_filename,
    output_name=output_filename
)

#CWMS CDA loader
shef_parser.parse(
    input_name=input_filename,
    loader_spec=f"cda[{CDA_URL}][{CDA_API_KEY}]",
)
'''
