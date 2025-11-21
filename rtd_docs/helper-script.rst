run_shef_parser Script
======================

.. toctree::
   :maxdepth: 1
   :caption: Contents:

.. role:: py(code)
    :language: python

.. role:: bat(code)
    :language: batch

.. role:: pwsh(code)
    :language: pwsh

.. role:: sh(code)
    :language: sh

Executing :py:`shef.shef_parser.main()` from the command line can be tricky since you need to know
the exact location of the package in your installation.

Inspecting/Updating Execution Path
----------------------------------
The easiest way is to use a helper script that is placed somewhere referenced by your PATH environment variable. You can inspect and 
set this variable from the command line in the following manner.

**Windows**

* From Command Prompt
    * inspect: :bat:`echo %Path%`
    * set: :bat:`set Path=%Path%;<another_directory>`
* From PowerShell
    * inspect: :pwsh:`$Env:Path` or :pwsh:`$Env:Path -split ';'`
    * set: :pwsh:`$Env:Path += <another_directory>`
* From Windows UI
    * type ``envvar`` in the Windows search bar and open "Edit environment variables for your account"

      .. dropdown:: Windows UI
        
        .. image:: images/windows-env-vars.png

**Linux**

* inspect: :sh:`echo $PATH`
* set: :sh:`export PATH=$PATH:<another_directory>`

Helper Script
-------------
Once you know which directory to put your helper script in, create a helper script file as follows:

* Windows
    ``run_shef_parser.bat``

    .. code-block:: batch

        @python -c "import sys; import shef; import subprocess; subprocess.run([sys.executable, shef.shef_parser.__file__]+sys.argv[1:], check=True)" %*

* Linux
    ``run_shef_parser``

    .. code-block:: bash

        #!/usr/bin/env bash
        python -c "import sys; import shef; import subprocess; subprocess.run([sys.executable, shef.shef_parser.__file__]+sys.argv[1:], check=True)" "$*"

    Don't forget to make the script executable: 
    
    .. code-block:: bash
        
        chmod u+x /path/to/run_shef_parser

Note that you may need to have your script use ``python3 -c`` instead of ``python -c``, depending on your python installation.

Now from any command line you can simply execute ``run_shef_parser <options>`` to execute the SHEF parser.

