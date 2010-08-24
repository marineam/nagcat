PREFIX  = /ita/installs/polthon
PYTHON 	= $(PREFIX)/bin/python
CY_SRC	= python/nagcat/_object_parser_c.pyx
CY_TMP	= $(CY_SRC:.pyx=.c)
CY_HTML = $(CY_SRC:.pyx=.html)
PY_EXT  = $(CY_SRC:.pyx=.so)

export PATH := $(PREFIX)/bin:$(PATH)

.PHONY: build_ext
build_ext:
	$(PYTHON) setup.py build_ext --inplace

.PHONY: report
report: $(CY_HTML)

$(CY_HTML): %.html: %.pyx
	echo $$PATH
	cython -a -o $*.tmp $<
	$(RM) $*.tmp
	firefox file://$(CURDIR)/$@

clean:
	$(RM) $(PY_EXT) $(CY_TMP) $(CY_HTML)
