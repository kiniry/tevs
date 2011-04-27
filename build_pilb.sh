#!/bin/sh

cd ~/tevs/Imaging-1.1.7
python setup.py build_ext -i
cp -a PILB ..
