Comparison to Shefit
====================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

The ``shefit`` program - a Fortran 77 program developed by the NWS - is the reference SHEF parser.

Executing ``shefit -h`` generates the following output.::

    Shefit is a UNIX filter program to decode shef messages.
    It can be used by piping messages into it and redirecting
    output to a file; or by giving it filename arguments for
    input, output, and errors.

    One of the following options may be given as the first
    argument:

    -1 .. Text output as one long line, full quotes (default)
    -2 .. Text output as two lines, quotes limited to 66 chars
    -b .. Binary output if output is to a file
    -h .. Output a help message on how to run shefit (stdout)

    General forms:

    shefit  [option]  input_file  [output_file]  [error_file]
    cmd-mesg  |  shefit  [option]  [> out_file]  [2> err_file]

    Examples:

    shefit  shef_messg_in
    shefit  -b  shef_messg_in  decode_out  err_out
    shefit  -2  shef_messg_in  >  decode_out
    print ".A STA 971205 Z DH08/HG 2"  |  shefit  2>&-
    cat  shef_messg_in  |  shefit  >  decode_out  2>  err_out

SHEFPARM file
--------------

What the output above doesn't show is that ``shefit`` requires a file named ``SHEFPARM`` located either in
the current working directory or in a directory named in the ``rfs_sys_dir`` environment variable.

The ``SHEFPARM`` file is a parsing configuration file that contains sections labeled as follows:

1. PE Codes And Conversion Factors
2. Duration Codes And Associated Values
3. TS Codes
4. Extremum Codes
5. Probility Codes And Associated Values
6. Send Codes Or Duration Defaults Other Than I
7. Data Qualifier Codes
8. Max Number Of Errors

Using a file for the parsing configuration enables customization for certain situations, but it also
allows files to proliferate without knowing which, if any, contain the canonical information.

The ``shef.shef_parser`` module contains all canonical parsing configuration in code and thus does not
need a ``SHEFPARM`` file unless specific customization is required. In this case a ``SHEFPARM`` file
containing canonical information can be created by running ``python shef/shef_parser.py --make_shefparm``.
The file can then be edited as necessary and used with ``shef.shef_parser`` by
by:

1. Running ``shef.shef_parser`` with the ``-s`` or ``--shefparm`` option (recommended)
2. Placing the ``SHEFPARM`` file in the current working directory
3. Placing the ``SHEFPARM`` file in a directory specified by the ``rfs_sys_dir``

When using option 2 or 3 above, the ``SHEFPARM`` file can be ignored by running ``shef.shef_parser`` with the ``--defaults`` option

Output Formats
--------------

The ``shef.shef_parser`` output options ``-f 1`` (or ``--format 1``) and ``-f 2`` (or ``--format 2``) are equivalent to the  ``shefit`` output options ``-1`` and ``-2``, respectively

The ``shef.shef_parser`` module does not contain the equivalent of the ``shefit -b`` option

Times
-----

By default, shef_parser uses modern date/time and time zone objects to process times and time zones, which do not always produce the same
results as the logic used in shefit. Use the ``--shefit_times`` option to force ``shef.shef_parser`` to use the same date/time logic as ``shefit``.

Note that using ``--shefit_times`` causes ``shef.shef_parser`` to (like ``shefit``) always generate incorrect UTC times for SHEF time zones Y, YD, YS, and
ND, and to generate incorrect UTC times for SHEF time zone N during daylight saving time.

Garbled SHEF Messages
---------------------

In many circumstances ``shef.shef_parser`` is able to process valid portions of messages that occur after an erroneous portion, where ``shefit``
normally stops further processing of a message when it encounters an error. This usually results in parsing more valid values from problematic
messages than ``shefit``. However, it can result in treating invalid data as valid in certain messages that are badly mangled. This behavior
can be prevented by using the ``--reject_problematic`` option which discards all data from messages with errors.