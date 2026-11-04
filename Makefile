# Thin wrapper; the real logic is in tasks.py so Windows works without make.
PY ?= python

.PHONY: setup check demo live eval extract record
setup check demo live eval extract record:
	$(PY) tasks.py $@
