# Thin wrapper; the real logic is in tasks.py so Windows works without make.
PY ?= python

.PHONY: setup check demo live eval extract record run serve openapi mutation-report
setup check demo live eval extract record run serve openapi mutation-report:
	$(PY) tasks.py $@
