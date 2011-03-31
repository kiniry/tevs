
all: reset test run

run: reset
	@./main.py

reset: clean
	@cp -r ~/sagdata/proc/* ~/sagdata/unproc 2>/dev/null || true
	@rm -rf ~/sagdata/proc/*
	@cat ~/sagdata/tevs_log.txt >>~/sagdata/tevs_log.txt.old 2>/dev/null || true
	@rm -f ~/sagdata/tevs_log.txt
	@echo 1 >nexttoprocess.txt

clean:
	@rm -f *.pyc

test: *.py
	@nosetests -q --with-doctest #--with-coverage --cover-erase --cover-html --cover-html-dir=coverage

bundle:
	@hg bundle --base `cat lasttip.txt` ~/tevs.bz2
	@hg tags | sed 's/tip.*:\(.*\)/\1/g' > lasttip.txt

.PHONY: reset clean bundle
