ROOT=~/data

all: reset run

run: reset
	@./main.py

reset: clean
	@cp -r ${ROOT}/proc/* ~/data/unproc 2>/dev/null || true
	@rm -rf ${ROOT}/proc/*
	@rm -rf ${ROOT}/errors/*
	@cat ${ROOT}/tevs_log.txt >>${ROOT}/tevs_log.txt.old 2>/dev/null || true
	@rm -f ${ROOT}/tevs_log.txt
	@echo 1 >${ROOT}/nexttoprocess.txt

reset-templates: reset
	@rm -f ${ROOT}/templates

clean:
	@rm -f *.pyc

test: *.py
	@nosetests -q --with-doctest #--with-coverage --cover-erase --cover-html --cover-html-dir=coverage

.PHONY: reset clean reset-templates
