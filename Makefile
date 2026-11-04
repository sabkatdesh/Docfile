# Thin wrapper; the real logic is in tasks.py so Windows works without make.
PY ?= python

.PHONY: setup check demo live eval extract record run
setup check demo live eval extract record run:
	$(PY) tasks.py $@
