import const
import ConfigParser
import logging
import sane
import time
import sys
import getopt
import os
import pdb
from string import atoi
from datetime import datetime

# scanloop.py: scan files into the unproc directory tree
# the -s argument gives the starting number 
# to assign to scans and the -e argument gives the number which,
# once assigned, should terminate scanning
# If no start number is specified, or the start is 0,
# the program pulls the next number from nexttoscan.txt in the current
# directory.

# Note that when extraction.py processes files in the unproc directory tree
# it moves each processed file to the proc directory tree.

# Note that when scanning in duplex, you have to start, snap(no cancel), 
# then start, snap to get the second side
if __name__ == "__main__":
    # read configuration from tevs.cfg and set constants for this run
    config = ConfigParser.ConfigParser()
    config.read("tevs.cfg")

    # first, get log file name so log can be opened
    #const.logfilename = config.get("Paths","logfilename")
    # or, in this case, set it to /tmp/scan_log.txt
    const.logfilename ="/tmp/scan_log.txt"
    logging.basicConfig(filename=const.logfilename,level=logging.DEBUG)
    logger = logging.getLogger("scanloop")
    print const.logfilename
    # then both log and print other config info for this run
    bwi = config.get("Sizes","ballot_width_inches")
    bhi = config.get("Sizes","ballot_height_inches")
    owi = config.get("Sizes","oval_width_inches")
    ohi = config.get("Sizes","oval_height_inches")
    const.ballot_width_inches = float(bwi)
    const.ballot_height_inches = float(bhi)
    const.oval_width_inches = float(owi)
    const.oval_height_inches = float(ohi)
    const.layout_brand = config.get("Layout","brand")
    const.proc = config.get("Paths","proc")
    const.unproc = config.get("Paths","unproc")
    const.results = config.get("Paths","results")
    pfs = config.get("Paths","procformatstring")
    ufs = config.get("Paths","unprocformatstring")
    rfs = config.get("Paths","resultsformatstring")
    mfs = config.get("Paths","masksformatstring")
    const.procformatstring = pfs.replace(
        "thousands","%03d").replace("units","%06d")
    const.unprocformatstring = ufs.replace(
        "thousands","%03d").replace("units","%06d") 
    const.resultsformatstring = rfs.replace(
        "thousands","%03d").replace("units","%06d")
    const.masksformatstring = mfs.replace(
        "thousands","%03d").replace("units","%06d")



    counter = 0
    #endcounter = 99
    inches_to_mm = 25.4
    inches = 11
    resolution = 300
    duplex = False
    comment = ""
    try:
        opts,args = getopt.getopt(sys.argv[1:],"s:e:d:l:r:c:",["start=","end=","duplex=","length=","resolution=","comment="])
    except getopt.GetoptError:
        print "Usage: scanloop [-s #] [-e #] [-d True|False] [-l <length in inches>] [-r <dpi>][-c <comment>]"
        sys.exit(0)
    for opt, arg in opts:
        #print opt, arg
        if opt in ("-s","--start"):
            counter = int(arg)
        #if opt in ("-e","--end"):
        #    endcounter = int(arg)
        if opt in ("-d","--duplex"):
            if arg.find("True")>-1:
                duplex = 1
            else:
                duplex = 0
        if opt in ("-c","--comment"):
            comment = arg
        if opt in ("-l","--length"):
            inches = int(arg)
        if opt in ("-r","--resolution"):
            resolution = int(arg)
    print counter
    hwnum = counter
    if (counter == 0):
        try:
            hw = open("nexttoscan.txt","r")
            hwline = hw.readline()
            hw.close()
            hwnum = atoi(hwline)
            print hwnum
            counter = hwnum
        except:
            print "Could not read nexttoscan.txt"
            
    bigcount = 0
    sane.init()
    s = sane.open(sane.get_devices()[0][0])
    if duplex:
        s.source = 'ADF Duplex'
    else:
        s.source = 'ADF Front'
    s.endorser = True
    s.endorser_string = '%08ud'
    s.endorser_val = counter
    print s.endorser_string, s.endorser_val
    #s.opt['endorser_string'] = '%06ud'
    pdb.set_trace()
    s.page_height = int(inches * inches_to_mm)
    s.br_y = int(inches * inches_to_mm)
    s.mode = 'Color'
    s.resolution = resolution # at 300, took six seconds per 14" duplex
    s.y_resolution = resolution
    # be ready to remove this if it does not properly set reported dpi
    #s.density = resolution
    s.swdeskew = 0 # software deskew might cause problems with our line recog
    # Gray at 140 took 3.1 sec
    # at 150 took 3.2 sec
    # at 200 took 4.0
    # at 220 took 5.1
    # at 240 took 3.2 sec
    # at 270 will not process properly
    # at 249 will not process properly


    first_time = True
    while(1):
        s.endorser_val = counter
        try:
            s.start()
        except:
            # CHANGE THIS TO EXIT, IF YOU DON'T WANT 
            # AUTOMATIC RESTARTING (perhaps the 5900 tray should stay down) 
            # when start fails, you've either run out of paper
            # or encountered another problem, so you should
            # treat the next scan as a "first scan", which means
            # you number it in mode "number first scan only"
            first_time = True
            # Note that we can read button state, possibly state of doublefeed 
            #print "Send to pressed:",s.email #state of "send to" button
            time.sleep(2)
            continue
        imagename = const.unprocformatstring % (counter/1000,counter)
        if duplex:
            img1 = s.snap(no_cancel=True)
            imagename = const.unprocformatstring % (counter/1000,counter)
            imagepath = os.path.split(imagename)[0]
            if not os.path.exists(imagepath):
                try:
                    os.makedirs(imagepath)
                except Exception, e:
                    print e
                    logger.error("Could not create directory %s\n%s" % 
                                 (imagepath,e))

            img1.save(imagename)
            print imagename
            logger.info("Saving,%s,%s,%s" % (
                    imagename, 
                    datetime.now().isoformat(),
                    comment))
            #if first_time:
            #    print "FIRST TIME",
            #print "Saved image", imagename
            counter += 1
            try:
                hw = open("nexttoscan.txt","w")
                hw.write("%d"%(counter,))
                hw.close()
            except:
                print "Could not write to nexttoscan.txt"
            # did not get image in img2 when no second call to s.start()
            s.start()

        
        img2 = s.snap()
        imagename = const.unprocformatstring % (counter/1000,counter)
        imagepath = os.path.split(imagename)[0]
        if not os.path.exists(imagepath):
            try:
                os.makedirs(imagepath)
            except Exception, e:
                print e
                logger.error("Could not create directory %s\n%s" % 
                             (imagepath,e))


        print imagename[-10:-4]
        img2.save(imagename)
        if not duplex:
            print "Saving,%s,%s,%s" % (
                    imagename, 
                    datetime.now().isoformat(),
                    comment)
            logger.info("Saving,%s,%s,%s" % (
                    imagename, 
                    datetime.now().isoformat(),
                    comment))
        else:
            logger.info("Saving %s,%s, " % (imagename, 
                                          datetime.now().isoformat()))
        counter += 1
        first_time = False
        try:
            hw = open("nexttoscan.txt","w")
            hw.write("%d"%(counter,))
            hw.close()
        except:
            print "Could not write to nexttoscan.txt"
            logger.critical("Could not write to nexttoscan.txt")
