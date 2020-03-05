#!/bin/bash
if [[ `pwd` != *test ]]; then
	cd test
fi
pytest "$@"
coverage report| tr "\\\\" "/" >coverage_report.out
diff -sq coverage_report.out coverage_report.good
if [[ $? -ne 0 ]]; then
	echo "testrcp: Test failed!"
	exit 1
else
	V1=`grep "^VERSION" ../rivescript_coverage_plugin/plugin.py|sed -e s/VERSION=// -e s/\"//g`
	V2=`grep "    version=" ../setup.py|sed -e "s/    version=//" -e s/\'//g -e s/,//`
	if [[ "$V1" != "$V2" ]]; then
		echo "testrcp: Test failed: VERSION $V1 != $V2 (plugin.py vs setup.py)"
	else
		echo "testrcp: Test passed!"
	fi
fi
