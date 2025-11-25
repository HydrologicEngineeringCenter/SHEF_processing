Option Descriptions
===================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

::

    run_shef_parser --description
    
    shef_parser is a pure Python replacement for the shefit program from
    NOAA/NWS.

    SHEFPARM file:
        Unlike shefit, shef_parser doesn't require the use of a SHEFPARM file,
        although one may be used.

        If --defaults is not specified, shef_parser uses the same rules as
        shefit for locating the SHEFPARM file:
            1. the current directory is searched first
            2. the directory specified by "rfs_sys_dir" environment variable
            is searched

        However, unlike shefit which exits if no SHEFPARM file is found,
        shef_parser will use program defaults instead. The program defaults
        have the same behavior as using the SHEFPARM file bundled with the
        latest source code for shefit.

        Also unlike shefit, the location of the SHEFPARM file can be specified
        the using -s/--shefparm option, and doesn't need to be named SHEFPARM.
        Using -s/--shefparm overrides searching the default locations for the
        file.

        If a SHEFPARM file is used, any modifications it makes to the program
        defaults are logged at the INFO and/or WARNING levels on program
        startup.

        The --defaults option may be specified to force shef_parser to use
        program defaults if a SHEFPARM file exists in the current or
        $rfs_sys_dir directories.

        The --defaults and -s/--shefparm options are mutually exclusive.

        The --make_shefparm option may be used to output program defaults in
        SHEFPARM format. This may be useful if it is necessary to override the
        program defaults. Either redirect <stdout> or use the -o/--out option
        to capture the SHEFPARM data to a file in order to modify it for use.

    Input format:
        Unless --processed is specified, the program reads SHEF text and
        processes it into the (default or specified) output format, optionally
        passing the output to a loader. If --processed is specified, the
        program reads pre-processed data in either output format 1 or 2 and
        outputs it in the (default or specified) format. It can thus be used
        to change the format of a pre-processed file or to pass pre-processed
        data to a loader.

    Output format:
        Like shefit, the default output format is the shefit text version 1.
        The output formats -f/--format 1 and -f/--format 2 are equivalent to
        the shefit -1 and -2 options, respectively. There is no equivalent to
        the shefit -b (binary output) option.

    Times and timezone processing:
        By default, shef_parser uses modern date/time and time zone objects to
        process times and time zones, which do not always produce the same
        results as the logic used in shefit. Use the --shefit_times option to
        force shef_parser to use the same date/time logic as shefit. This is
        helpful when comparing shef_parser output to shefit output for a
        common input.

        Note that using --shefit_times causes shef_parser to (like shefit)
        always generate incorrect UTC times for SHEF time zones Y, YD, YS, and
        ND, and to generate incorrect UTC times for SHEF time zone N during
        daylight saving time.

    Messages with errors:
        In many circumstances shef_parser is able to process valid portions
        of messages that occur after an erroneous portion, where shefit
        normally stops further processing of a message when it encounters an
        error. This usually results in parsing more valid values from
        problematic messages than shefit. However, it can result treating
        invalid data as valid in certain messages that are badly mangled. This
        behavior can be prevented by using the --reject_problematic option
        which discards all data from messages with errors.

    Loading SHEF data to data stores:
        ======================================================================
        Loader        : cda_loader.CdaLoader v0.5
        Description   : Used to import and export SHEF data through cwms-
                        data-api.
                        For unloading, input a list of CDA /timeseries
                        responses.
                        Requires cwms-python v0.6.3 or greater.
        Option Format : --loader cda[cda_url][cda_api_key]
                        * cda_url = the url of the CDA instance to be
                        used, e.g. https://cwms-data.usace.army.mil/cwms-
                        data/
                        * cda_api_key = the api_key to use for CDA POST
                        requests
        Can unload    : True
        Exporter      : cda_exporter.CdaExporter v1.0.0
                        Outputs SHEF text from time series in CWMS
                        database via CDA
                        CdaExporter(cda_url: str, office: str)
        ======================================================================
        Loader        : dss_loader.DssLoader v1.0.0
        Description   : Used to import/export SHEF data to/from HEC-DSS
                        files. Uses ShefDss-style configuration.
                        Can use .csv sensor and parameter files to handle
                        long pathname parts.
        Option Format : --loader
                        dss[dss_file_path][sensor_file_path][parameter_file_path]
                        * dss_file_path = the name of the HEC-DSS file to
                        use
                        * sensor_file_path = the name of the ShefDss-style
                        sensor file to use
                        * parameter_file_path = the name of the ShefDss-
                        style parameter file to use
        Can unload    : True
        Exporter      : dss_exporter.DssExporter v1.0.0
                        Outputs SHEF text from time series in HEC-DSS
                        Files
                        DssExporter(dss_filename: str, sensor_filename:
                        str, parameter_filename: str)
        ======================================================================
        Loader        : dssvue_loader.DSSVueLoader v1.4.1
        Description   : Used by HEC-DSSVue to import/export SHEF data.
                        Uses ShefDss-style configuration.
                        As of v1.2 .csv sensor and parameter files can be
                        used to handle long pathname parts.
        Option Format : --loader
                        dssvue[sensor_file_path][parameter_file_path]
                        * sensor_file_path = the name of the ShefDss-style
                        sensor file to use
                        * parameter_file_path = the name of the ShefDss-
                        style parameter file to use
        Can unload    : True
        Exporter      : <None>
