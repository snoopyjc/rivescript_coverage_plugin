#!/usr/bin/env python

import os
import sys

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


if sys.argv[-1] == 'publish':
    os.system('python setup.py sdist upload')
    sys.exit()

readme = open('README.rst').read()
doclink = """
Documentation
-------------

The full documentation is at http://rivescript_coverage_plugin.rtfd.org."""
history = open('HISTORY.rst').read().replace('.. :changelog:', '')

setup(
    name='rivescript_coverage_plugin',
    version='0.2.2',                    # Fix Issues #1-#4, #5, #6
    description='A plug-in to measure code coverage in RiveScript with python',
    long_description=readme + '\n\n' + doclink + '\n\n' + history,
    author='Joe Cool',
    author_email='snoopyjc@gmail.com',
    url='https://github.com/snoopyjc/rivescript_coverage_plugin',
    packages=[
        'rivescript_coverage_plugin',
    ],
    package_dir={'rivescript_coverage_plugin': 'rivescript_coverage_plugin'},
    include_package_data=True,
    install_requires=[
        'coverage >= 5.0',              # v0.2.0: Issue #1
        'rivescript >= 1.14.9',         # v0.2.0: Issue #1
    ],
    license='MIT',
    zip_safe=False,
    keywords='rivescript_coverage_plugin',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
)
