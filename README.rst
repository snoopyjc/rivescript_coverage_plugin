=============================
RiveScript Coverage Plugin
=============================

.. image:: https://badge.fury.io/py/rivescript_coverage_plugin.png
    :target: http://badge.fury.io/py/rivescript_coverage_plugin

.. image:: https://travis-ci.org/snoopyjc/rivescript_coverage_plugin.png?branch=master
    :target: https://travis-ci.org/snoopyjc/rivescript_coverage_plugin

A plug-in to measure code coverage in RiveScript with python


Features
--------

The RiveScript Coverage Plugin is a plugin for Coverage.py which extends that package to measure code coverage for RiveScript files.  It uses code analysis tools and debug hooks provided by the RiveScript interpreter to determine which lines are executable, and which have been executed.  It supports CPython version 3.6 and above and plugs into Coverage.py version 5.0 and above.  It requires RiveScript 1.14.9 or above.

Documentation is on `Read The Docs`_. Code repository and issue tracker are on
`GitHub`_.

.. _Read The Docs: https://rivescript-coverage-plugin.readthedocs.io/
.. _GitHub: https://github.com/snoopyjc/rivescript_coverage_plugin

Getting Started
---------------

#. Use pip to install::

          $ pip install rivescript_coverage_plugin

#. Create or edit your ``.coveragerc`` file and add this::

    [run]
    plugins = rivescript_coverage_plugin

#. Run the ``coverage`` command or ``pytest`` with the ``--cov`` option and your RiveScript files will automatically be included in the coverage analysis and subsequent report generation.

Note that just like with Python coverage, RiveScript files that are not executed at all will not be part of your coverage report.  To add them, use the ``source = .`` or other more specific source specifier in the ``[run]`` section of your ``.coveragerc`` file or the ``--source`` command line option.  See the `Coverage Documentation`_ section "Specifying source files" for more information on this.

.. _Coverage Documentation: https://coverage.readthedocs.io/
