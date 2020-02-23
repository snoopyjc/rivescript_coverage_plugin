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
	echo "testrcp: Test passed!"
fi
