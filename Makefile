# Thin wrapper; the real logic is in tasks.py so Windows works without make.
PY ?= python

.PHONY: setup check demo live eval
setup check demo live eval:
	$(PY) tasks.py $@
