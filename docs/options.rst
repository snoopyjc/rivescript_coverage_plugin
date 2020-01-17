========
Options
========

The options provided by the RiveScript Coverage Plugin are designed to help troubleshoot the plugin itself and should not be needed by normal users.  For completeness, they are documented here.  The options go in your ``.coveragerc`` file and are specified as follows::

  [rivescript_coverage_plugin]
  show_startup = True
  show_parsing = True
  show_tracing = True
  clean_rs_objects = False

The default values are the opposite of what I show above.  The options are defined as follows:

show_startup
  Show information about the plugin's startup sequence is shown, including version information and command line arguments.  This is False by default.

show_parsing
  Show information about which lines of the RiveScript files are executable and which are not.  This is False by default.

show_tracing
  Generate a complete trace of the execution of the RiveScript interpreter, including which lines are being marked as executed as we interpret the Debug output of the RiveScript interpreter.  This is False by default.

clean_rs_objects
  Preserve the ``_rs_objects_`` temporary directory, where the RiveScript Coverage Plug creates files representing each ``< object NAME python`` in the RiveScript in order to trace it's execution.  This directory will contain a ``rs_obj_NAME.py`` file for each object named ``NAME`` in your RiveScript.  This is True by default, which means this directory will be removed after analysis.
  


  

