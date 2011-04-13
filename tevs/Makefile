ROOT=~/data
INCOMING=~/data/unproc
DOCS=~/tevs-docs

all: reset run docs

run: reset
	@./main.py

reset: clean
	@cp -r ${ROOT}/proc/* ${INCOMING} 2>/dev/null || true
	@rm -rf ${ROOT}/proc/*
	@rm -rf ${ROOT}/errors/*
	@rm -rf ${ROOT}/results/*
	@cat ${ROOT}/log.txt >>${ROOT}/log.old 2>/dev/null || true
	@rm -f ${ROOT}/log.txt
	@echo 1 >${ROOT}/nexttoprocess.txt

reset-templates: reset
	@rm -rf ${ROOT}/templates

clean:
	@rm -f *.pyc

docs: *.py docs/*.rst
	@PYTHONPATH=$PYTHONPATH:. sphinx-build -b html -aqE docs docs/sphinx
	@cd docs && ./mkug.sh

test: *.py
	@nosetests -q --with-doctest #--with-coverage --cover-erase --cover-html --cover-html-dir=coverage

.PHONY: clean reset reset-templates
