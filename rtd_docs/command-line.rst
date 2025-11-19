Command Line Options
====================

.. toctree::
   :maxdepth: 1
   :caption: Contents:

::

   python shef/shef_parser.py --help

   usage: shef_parser.py [-h]
                         [-s SHEFPARM]
                         [-i input_filename]
                         [-o output_filename]
                         [-l log_filename]
                         [-f {1,2}]
                         [-v {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                         [--loader <ts_loader>]
                         [--processed]
                         [--defaults]
                         [--timestamps]
                         [--shefit_times]
                         [--reject_problematic]
                         [--append_out]
                         [--append_log]
                         [--unload]
                         [--make_shefparm]
                         [--description]
                         [--version]

   -h
   --help                show this help message and exit

   -s SHEFPARM
   --shefparm SHEFPARM   path of SHEFPARM file to use

   -i input_filename
   --in input_filename   input file (defaults to <stdin>)

   -o output_filename
   --out output_filename output file (defaults to <stdout>)

   -l log_filename
   --log log_filename    log file (defaults to <sterr>)

   -f {1,2}
   --format {1,2}        output format (defaults to 1)

   -v {DEBUG,INFO,WARNING,ERROR,CRITICAL}
   --loglevel {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                         verbosity/logging level (defaults to INFO)

   --loader <ts_loader>  allows loading time series to various data stores
                         (more info in --description)

   --processed           input is pre-processed (format 1 or 2) instead of
                         SHEF text

   --defaults            use program defaults (ignore default SHEFPARM)

   --timestamps          timestamp log output

   --shefit_times        use shefit date/time logic

   --reject_problematic  reject all values from messages that contain errors

   --append_out          append to output file instead of overwriting

   --append_log          append to log file instead of overwriting

   --unload              use loader to unload from data store to SHEF text

   --make_shefparm       write SHEFPARM data to output file and exit

   --description         show a more detailed program description and exit

   --version             print the version info and exit

