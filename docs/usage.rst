========
Usage
========

To use RiveScript Coverage Plugin in a project, create or edit your ``.coveragerc`` file and add this::

    [run]
    plugins = rivescript_coverage_plugin

Now run the ``coverage`` command or ``pytest`` with the ``--cov`` option and your RiveScript files will automatically be included in the coverage analysis and subsequent report generation.

Note that just like with Python coverage, RiveScript files that are not executed at all will not be part of your coverage report.  To add them, use the ``source = .`` or other more specific source specifier in the ``[run]`` section of your ``.coveragerc`` file or the ``--source`` command line option.  See the `Coverage Documentation` section "Specifying source files" for more information on this.

.. _Coverage Documentation: https://coverage.readthedocs.io/
