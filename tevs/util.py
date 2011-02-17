import sys
import os
import errno
import const
from Ballot import Ballot

def root(*dir):
    "convert a dir to a root relative path"
    dir = (const.root,) + dir
    return os.path.join(*dir)

def fatal(msg, *p):
    "log fatal messages and exit"
    if len(p) != 0:
        msg = msg % p
    const.logger.exception(msg)
    sys.exit(1)

def writeto(fname, data):
    "save data into fname"
    try:
        with open(fname, "w") as f:
            f.write(str(data))
    except OSError as e:
        const.logger.exception("Could not write to %s" % fname)
        sys.exit(1)

def genwriteto(fname, gen):
    "save data into fname"
    try:
        with open(fname, "w") as f:
            f.writelines(gen)
    except OSError as e:
        const.logger.exception("Could not write to %s" % fname)
        sys.exit(1)
def readfrom(fname, default=None):
    "return contents of fname as string, if we can't read: returns default if not None, otherwise shuts down"
    try:
        with open(fname, "r") as f:
            return f.read()
    except Exception as e:
        if default is not None:
            return default
        const.logger.exception("Could not read from %s" % fname)
        sys.exit(1) 

def mkdirp(*path):
     "Copy of mkdir -p, joins all arguments as path elements"
     if len(path) == 0:
         return
     path = os.path.join(*path)
     try:
         os.makedirs(path)
     except Exception as e:
         if e.errno == errno.EEXIST:
            return # an ignorable error, dir already exists
         const.logger.exception("Could not create directory %s" % path)
         sys.exit(1)

def rmf(*path):
    "Copy of rm -f, joins all arguments as path elements"
    if len(path) == 0:
        return
    path = os.path.join(*path)
    try:
        os.unlink(path)
    except OSError as e:
        if e.errno == errno.ENOENT:
            return
        const.logger.exception("Could not remove file " + path)
        sys.exit(1)

def pairs(list):
    """walk through list returning two elements at a time.
     Assumes len(list) is even."""
    for i in range(0, len(list), 2):
        yield list[i:i+2]


def get_maxv_from_text(text):
     """Look for hint about maximum votes allowed in contest"""
     maxv = 1
     if (text.find("to 2") > 1):
          maxv = 2
     elif (text.find("to 3") > 1):
          maxv = 3
     elif (text.find("to 4") > 1):
          maxv = 4
     elif (text.find("to 5") > 1):
          maxv = 5
     if (text.find("Two") > 1):
          maxv = 2
     elif (text.find("Thre") > 1):
          maxv = 3
     elif (text.find("Four") > 1):
          maxv = 4
     elif (text.find("Five") > 1):
          maxv = 5
     return maxv

# Remove punctuation and special chars from text, except for space
def alnumify(instring):
     return filter(lambda x: (x.isalnum() or x.isspace()) and x, instring)

# Reasonable text assumptions
def clean_text(instring):
    """Make reasonable guesses about known common OCR failures"""
    # letter I surrounded by lower case letters is really letter ell
    # united States is United States, etc...
    # vvnte VVnte is Write
    # MO_ is NO_
    # l\/l is M
    instring = instring.replace("united States", "United States")
    instring = instring.replace("MO ", "NO ")
    instring = instring.replace("l\/l", "M")
    instring = instring.replace("VVnte", "Write")
    instring = instring.replace("Wnte", "Write")
    instring = instring.replace("vv", "W")
    return instring

def get_region_text(im, x1, y1, x2, y2):
     """ read text from image (may no longer be in use"""
     # return text within provided bounds
     if x1<1:x1=1
     if y1<1:y1=1
     if x2>=im.size[0]:x2=im.size[0]-1
     if y2>=im.size[1]:y2=im.size[1]-1
     if y1>=y2:
          return("")
     const.logger.debug("Cropping %d %d %d %d" % (x1,y1,x2,y2))
     crop = im.crop((x1,y1,x2,y2))
     contrast = crop.point(threshold48table)
     crop.save("regionorig.tif")
     contrast.save("region.tif")
     p = subprocess.Popen(["/usr/local/bin/tesseract", "region.tif", "region"])
     sts = os.waitpid(p.pid,0)[1]
     #os.system("/usr/local/bin/tesseract region.tif region 2>/dev/null")
     tempf = open("region.txt")
     text = tempf.read()
     tempf.close()
     return clean_text(text.replace("\n","/").replace(",",";"))


