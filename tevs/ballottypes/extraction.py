# extraction.py provides the ability to completely analyze an ESS ballot image
# (ignore the name, which will change) by creating Ballot instances, 
#or a Hart ballot image by creating HartBallot instances.
# TODO: now that we are using python2.6 and Imaging-1.1.7, 
# bring PIL modifications over to 1.1.7 and rebuild it.
# investigate y offset variations
# todo: mode that allows you to specify bar code manually, 
# either interactive or from file;
# also: need to check whether box-less sides cause problems
import sys
import os
imaging_dir = os.path.expanduser("~/Imaging-1.1.7")
sys.path = [imaging_dir]+sys.path[:]
from PIL import Image, ImageStat
import getopt
import const
import ConfigParser
import ImageChops
import ImageDraw
import ImageEnhance
import ImageFont
import ImageOps
import gc
import logging
import math
import pickle
import pdb
import os
import string
import subprocess
import time
import xml.dom
import xml.dom.minidom
from datetime import datetime
import re
from string import atoi
import logging

class BallotException(Exception):
     def __init__(self, value):
         self.value = value
     def __str__(self):
         return repr(self.value)


# useful for getting unlimited serial numbers
indices = xrange(sys.maxint)

global process_list

# for clamping dark to black
threshold48table = [
0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255, # end of first band
0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255, # end of second band
0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255,
255,255,255,255,255,255,255,255] # end of third band



def process_list(im,br,list,header_x, endx):
    """Process a list of column breaks and ovals, returning text for each."""
    # modes 0,1,2 represent encounter with black, gray, white region
    # mode 3 represents a white region that spans the entire col width
    # modes above 3 are really the x_offset of an encountered oval
    #print "PROCESS LIST"
    #pdb.set_trace()
    textlist = []
    next_mode_or_x = 0
    current_mode_or_x = 0
    last_y = 0
    new_y = 0
    dpi = 150
    ovalheight = dpi/10
    this_mode_or_x = 0
    prev_mode_or_x = 0
    next_mode_or_x = 0
    startx = 0
    starty = 0
    endy = 0
    texttype = ["JURISDICTION0","CONTEST1","BLACKONWHITE2","BLACKONWHITE3"]
    for n in range(len(list)):
        this_mode_or_x = list[n][0]
        try:
            prev_mode_or_x = list[n-1][0]
        except:
            prev_mode_or_x = 0
        try: 
            next_mode_or_x = list[n+1][0]
        except:
            next_mode_or_x = 0
        # starting x only depends on current mode
        if this_mode_or_x <= 3:
            startx = header_x - (dpi/2)#((9*dpi)/20)
        else:
            startx = header_x
        #if (startx > 300) and (startx < 340) and (list[n][1]>2000):
        #    pdb.set_trace()
        # starting y depends on current mode and previous mode
        # if this is non-oval, begin at current item's y
        if this_mode_or_x <=3:
            starty = list[n][1]
        # if this is oval and prev is non-special non-oval, 
        # then begin at prev item's y
        elif prev_mode_or_x < 3:
            try:
                starty = list[n-1][1]
            except:
                pass
        # if this is oval and previous is special insert, 
        # begin at an oval's height above the oval
        elif prev_mode_or_x == 3:
            starty = list[n][1] - ovalheight
        # if this is oval and prev is oval, calculate beginning
        # halfway between oval bottoms
        else:
            starty = ((list[n-1][1]+list[n][1])/2)+ovalheight
        # ending y depends on current mode and next mode
        # if next is non-oval, end where next begins
        if next_mode_or_x <= 3:
            try:
                endy = list[n+1][1]
            except:
                endy = im.size[1] - (2*dpi/3)
        # if next is oval and we are non-oval, end 1/10" up from next
        # to prevent any oval from being read
        elif this_mode_or_x <=3:
            try:
                endy = list[n+1][1] - (dpi/10)
            except:
                endy = im.size[1] - (2*dpi/3)
        # if next is oval and we are oval, end halfway between oval bottoms
        else:
            try:
                endy = ((list[n][1]+list[n+1][1])/2)+ovalheight
            except:
                endy = im.size[1] - (2*dpi/3)
        if this_mode_or_x <= 3:
            modestring = texttype[this_mode_or_x]
        else:
            modestring = "OVAL"
        textlist.append("%s bounding box (%d %d %d %d)" % 
                        (modestring,
                         startx,
                         starty,
                         endx,
                         endy
                         )
                        )
        regiontext = get_region_text(im,startx,starty,endx,endy)
        if modestring.startswith("JUR"):
            purpose = BtRegion.JURISDICTION
            br.append(BtRegion(bbox=(startx,starty,endx,endy),
                               purpose=purpose,
                               coord=(startx,starty),
                               text=regiontext))
        elif modestring.startswith("CON"):
            purpose = BtRegion.CONTEST
            br.append(BtRegion(bbox=(startx,starty,endx,endy),
                               purpose=purpose,
                               coord=(startx,starty),
                               text=regiontext))

        elif modestring.startswith("BLACKONWHITE3"):
            purpose = BtRegion.PROP
            br.append(BtRegion(bbox=(startx,starty,endx,endy),
                               purpose=purpose,
                               coord=(startx,starty),
                               text=regiontext))
            br.append(BtRegion())
        elif modestring.startswith("CHOICE"):
            purpose = BtRegion.OVAL
            br.append(BtRegion(bbox=(startx,starty,endx,endy),
                               purpose=purpose,
                               coord=(startx,starty),
                               text=regiontext))
        elif modestring.startswith("OVAL"):
            purpose = BtRegion.OVAL
            br.append(BtRegion(bbox=(startx,starty,endx,endy),
                               purpose=purpose,
                               coord=[list[n][0],list[n][1]],
                               text=regiontext))
        textlist.append(regiontext)
    return "\n".join(textlist)

# 
def ocr(im,br,dpi,x1,x2,splits):
    """ ocr runs ocr and assembles appends to the list of BtRegions"""
    const.logger.debug("ocr handed x1 = %d, dpi = %d" % (x1,dpi))
    box_type = ""
    for n in range(len(splits)-1):
        text = ""
        # for votes, we need to step past the vote area
        if splits[n][1]=="v":
            startx = x1 + int(round(const.candidate_text_inches*dpi))
            box_type = "v"
        # while for other text, we just step past the border line
        else:
            startx = x1 + (dpi/40)
            box_type = "h"

        croplist = (startx+1,splits[n][0]+1,x2-2,splits[n+1][0]-2)
        text = "("+box_type+")"

        if croplist[3]<=croplist[1]:
            const.logger.debug( "Negative height to croplist")
            continue
        crop = im.crop(croplist)
        gaps = crop.gethgaps((128,1))
        # we now need to split line by line at the gaps:
        # first, discard the first gap if it starts from 0
        if len(gaps)==0:
            pass
        elif gaps[0][1] == 0:
            gaps = gaps[1:]
        # then, take from the start to the first gap start
        if len(gaps)==0:
            # just use crop
            zone = crop
        else:
            zone_croplist = (0,0,crop.size[0]-1, gaps[0][1])
            #print "Zone croplist",zone_croplist
            if zone_croplist[3]<=zone_croplist[1]:
                #print "Negative height to zone_croplist"
                continue
            zone = crop.crop(zone_croplist)
        zone.save("/tmp/region.tif")
        p = subprocess.Popen(["/usr/local/bin/tesseract", 
                              "/tmp/region.tif", 
                              "/tmp/region"]
                             )
        sts = os.waitpid(p.pid,0)[1]
        tempf = open("/tmp/region.txt")
        text += tempf.read()
        tempf.close()
        # then, take from the first gap end to the next gap start
        for m in range(len(gaps)):
            end_of_this_gap = gaps[m][3]-2
            try:
                start_of_next_gap = gaps[m+1][1]
            except:
                start_of_next_gap = crop.size[1]-2
            zone_croplist = (0,
                             end_of_this_gap,
                             crop.size[0]-1,
                             start_of_next_gap)
            if (start_of_next_gap - end_of_this_gap) < (dpi/16):
                continue
            zone = crop.crop(zone_croplist)
            #enhancer = ImageEnhance.Sharpness(zone)
            #enhancer.enhance(2.0).save("region.tif")
            zone.save("/tmp/region.tif")
            p = subprocess.Popen(["/usr/local/bin/tesseract", 
                                  "/tmp/region.tif", 
                                  "/tmp/region"]
                                 )
            sts = os.waitpid(p.pid,0)[1]
            tempf = open("/tmp/region.txt")
            text += tempf.read()
            tempf.close()
        text = text.replace("\n","/").replace(",","comma")
        text = text.replace("'",'squot')
        text = text.replace('"','dquot')
        text = text.replace('\/','(M)').replace("IVI","(M)IVI")
        text = text.replace("|(M)","(M)").replace("I(M)","(M)")
        text = text.replace("(M)|","M").replace("(M)I","M")
        text = text.replace("|","I")
        text = re.sub(r'[^a-zA-Z0-9_ /]+', '', text)
        # now create a BTRegion from the item
        if box_type == "v":
            purpose = BtRegion.OVAL
            coord = (croplist[0] - ((3*dpi)/8),croplist[1]-(dpi/50))
        else:
            purpose = BtRegion.CONTEST
            coord = (croplist[0],croplist[1])
        
        br.append(BtRegion(bbox=croplist,
                           purpose=purpose,
                           coord = coord,
                           text = text))
    return(text)

def getdetails(dpi,im,br):
        """ get layout and ocr information """
        vline_list = im.getcolumnvlines(0,im.size[1]/4,im.size[0]-20)
        const.logger.debug("%s" % vline_list)
        lastx = 0
        """
        For each hlinelist that is separated from the previous by 
        a reasonable amount (more than dpi/4 pixels), we want to line up
        the negative values from the new hlinelist with the positive values
        from the old one
        """
        hlinelistlist = []
        columnstart_list = []
        vop_list = []
        for x in vline_list:
            if (x - lastx) > (dpi/4):
                columnstart_list.append(x)
                pot_hlines = im.getpotentialhlines(x,1,dpi)
                #print x,pot_hlines
                hlinelistlist.append( pot_hlines)
                #print "TO",x,len(hlinelistlist)
            lastx = x
        lastel2 = 0
        #for col in range(len(hlinelistlist)):
        #    print col,hlinelistlist[col]

        # an hline is confirmed by matching a positive hline in sublist n
        # against a negative hline in sublist n+1; if no sublist n+1, no hlines
        conf_hll = []
        for col in range(len(hlinelistlist)-1):
            conf_hll.append([])
            #print col, len(hlinelistlist[col])
            for entrynum in range(len(hlinelistlist[col])):
                yval1 = hlinelistlist[col][entrynum]
                for entrynum2 in range(len(hlinelistlist[col+1])):
                    yval2 = hlinelistlist[col+1][entrynum2]
                    if (yval1 > 0) and (abs(yval1 + yval2) < (dpi/16)):
                        conf_hll[col].append(yval1)
                        break
        #print conf_hll
        for x in range(len(conf_hll)):
            conf_hll[x] = map(lambda el: [el,"h"],conf_hll[x])
        #print conf_hll

        vboxes = []
        for startx in columnstart_list:
             if (startx <= 0):
                  const.logger.info("Negative startx passed to gethartvoteboxes")
                  
             vboxes.append([])
             vboxes[-1] = im.gethartvoteboxes(startx,dpi/2,dpi)
             vboxes[-1] = map(lambda el: [el[1],"v"],vboxes[-1])

        for x in range(len(conf_hll)):
            conf_hll[x].extend(vboxes[x])
            conf_hll[x].sort()
            #print columnstart_list[x],conf_hll[x]
            # now pass conf_hll[x] and the corresponding column start and end
            # into a function which will do OCR on vote and above-vote 
            # subregions
            endx = 0
            try:
                endx = columnstart_list[x+1]
            except:
                endx = im.size[0] - (dpi/2)
            text = ocr(im,br,dpi,columnstart_list[x],endx,conf_hll[x])
            #print len(br)
            #for btr in br:
            #    print btr




class VoteData(object):
    # for ess:
    # vote_threshold = 224
    # for hart:
    #vote_threshold = const.vote_intensity_threshold
    def __init__(self,filename="filename",
                 precinct="precinct",
                 jurisdiction="jurisdiction", 
                 contest="contest",
                 choice = "choice", 
                 prop="prop",
                 oval="oval",
                 coords="coords",
                 maxv=1,
                 stats=None):
        VoteData.vote_threshold = const.vote_intensity_threshold
        self.filename = filename
        self.precinct = precinct
        self.jurisdiction=jurisdiction
        self.contest = contest
        self.choice = choice
        self.prop = prop
        self.oval = oval
        self.coords = coords
        self.maxv = maxv # max votes allowed in contest
        try:
            self.stats = stats[:]
            if stats is None:
                print "No stats while creating vote data"
        except:
            print "No stats while creating vote data"
        self.was_voted = stats[0] < VoteData.vote_threshold
    def __repr__(self):
        return "%s,%s,%s,%s,%s,%d,%d,%s,%s,%s" % (
            self.filename,
            self.precinct,
            self.contest,
            self.prop,
            self.oval,
            self.coords[0],self.coords[1],
            str(self.stats)[1:-1],
            self.maxv,
            self.was_voted
            )
    def toString(self):
        return "%s,%s,%s,%s,%s,%d,%d,%s,%s,%s" % (
            self.filename,
            self.precinct,
            self.contest,
            self.prop,
            self.oval,
            self.coords[0],self.coords[1],
            str(self.stats)[1:-1],
            self.maxv,
            self.was_voted
            )
    

class BtRegion(object):
    """ Representing a rectangular region of a ballot. """
    JURISDICTION = 0
    CONTEST = 1
    CHOICE = 2
    PROP = 3
    OVAL = 4
    purposelist = ["JUR","CONTEST","CHOICE","PROP","OVAL"]
    def __init__(self,bbox=(),purpose=None,coord=(0,0),text=None):
        self.bbox = bbox
        self.purpose = purpose
        self.text = text
        self.coord = coord

    def __repr__(self):
        purposetext = ""
        try:
            if self.purpose < 5: 
                purposetext = BtRegion.purposelist[self.purpose]
            else: 
                purposetext = "OVAL"
        except:
            purposetext = "OVAL"
        return "BtRegion with purpose %s, bbox %s coord %s\ntext %s" % (
            purposetext,self.bbox,self.coord,self.text)



class BallotSide(object):
    """Representing a ballot side as a list of meaningful regions,
    plus sufficient information about the current ballot to scale,
    offset, and rotate information from the template regions."""

    def __init__(self, ballot,side, 
                 dpi=150 
                 ):
        self.ballot = ballot
        self.side = side
        self.dpi = dpi
        self.name = self.ballot.imagefilenames[self.side]

        # we don't really need the image, we just need to know it's not none,
        # and images cannot be pickled, so just save 1 if image provided
        if ballot.im[side] is not None:
            self.im = 1
        else:
            self.im = None
        #self.landmarklist = self.ballot.landmarklist[self.side]
        self.xref = self.ballot.xref[self.side]
        self.yref = self.ballot.yref[self.side]
        self.tang = self.ballot.tang[self.side]
        self.regionlist = self.ballot.regionlists[self.side]
        self.codelist = [None,None]
        self.columnlist = [None,None]
        self.br = [None,None]
        self.current_jurisdiction = "No info"
        self.current_contest = "No info"
        self.current_choice = "No info"
        self.current_prop = "No info"
        self.current_oval = "No info"
        self.current_coords = "No info"
        self.oval_width = const.oval_width_inches * dpi
        self.oval_height = const.oval_height_inches * dpi
        self.results = []

    def __repr__(self):
        return "BallotSide %s regionlist length %s  tangent %f" % (
            self.name,
            len(self.regionlist),
            self.tang)

    def append(self,region):
        if type(region)<>BtRegion:
            raise Exception
        # don't append regions with (0,0) location, they're artifacts
        if (region.coord[0] <> 0) and (region.coord[1] <> 0):
            self.regionlist.append(region)

    def oval_result(self,
                    image,
                    scalefactor,
                    precinct,
                    xoffset,yoffset,
                    tang,
                    rot_about_x=0,
                    rot_about_y=0):
         """Adjust the template coordinates for this ballot's tilt and offset, 
         and get the intensities associated with the adjusted coordinates."""
         
         # Scale to this image
         dpi = self.dpi * scalefactor
         startx = int(self.current_coords[0])
         starty = int(self.current_coords[1]) 
         startx *= scalefactor
         starty *= scalefactor
         startx += xoffset
         starty += yoffset
         refptx = int(round(self.xref * scalefactor))
         refpty = int(round(self.yref * scalefactor))
         
         deltatang = tang - self.tang
         const.logger.debug("%s imagetang %f referencetang %f " % (
                   self.name,
                   tang,
                   self.tang
                   )
                      )
         
         const.logger.debug( "Startingxy (%d,%d) land (%d,%d), deltatang %f" 
                       % (startx,
                          starty,
                          refptx,
                          refpty,
                          deltatang))
         
         (startx,starty) = rotate_pt_by(
              startx,starty,
              deltatang,
              refptx,refpty)
         
         startx = int(round(startx))
         starty = int(round(starty))
         
         # for reasons unknown, the templates all came out 
         # about 1/30" high so we'll compensate
         starty += int(round(dpi/30))

         endx = startx + (self.oval_width * scalefactor)
         endy = starty + (self.oval_height * scalefactor)
         
         # instead of the if False below, we've added fine adjustment
         # to cropstats in imaging's imaging.c
         # sanity check and adjustment:
         # the oval/rectangle should appear at a particular offset from 
         # the black column border line
         # so examine the eighth inch before and after the startx 
         # to find the line
         # there should be a black pixel approx 1/32" behind startx
         
         const.logger.debug(
              "requesting stats on (%d %d, %d, %d)" % (startx,
                                                       starty,
                                                       2+endx-startx,
                                                       2+endy-starty))
         
         # 1 at the end indicates use fine adjustment (for hart vote oval)
         cs = image.cropstats(int(round(startx)),
                              int(round(starty)),
                              int(round(self.oval_width * scalefactor)),
                              int(round(self.oval_height * scalefactor)), 1)
         
         # TODO: sometimes, the fine adjustment in cropstats may be "tricked"
         # by a long line in the preceding column; if the un-fine-adjusted
         # box is darker, consider using it. (Also, check for large change
         # in y from the original.)
         
         # subtract at least two lines worth from cs[1] and cs[2]
         # to account for the oval lines
         darkish = cs[1]+cs[2]
         darkish -= (2 * (const.oval_width_inches * dpi))
         
         
         # for ess, require at least 1/16 coverage of the oval 
         # with darkish pixels,
         # (after taking away the two lines worth)
         # that would mean 1/4 the height and 1/4 the width
         ovalarea =  (self.oval_width * self.oval_height)
         was_voted = (darkish > (ovalarea/16))
         
         # for hart, require average intensity below 140
         # was_voted = (cs[0]<140)
         
        # trim fields to 40 characters, enough to identify
         try:
              self.current_jurisdiction = self.current_jurisdiction[:40]
         except:
              pass
         
         maxv = 1
         try:
              maxv = get_maxv_from_text(self.current_contest)
              self.current_contest = self.current_contest[:40]
         except:
              pass
         try:
              if self.current_jurisdiction.startswith("(h)"):
                   self.current_jurisdiction = self.current_jurisdiction[3:]
              if self.current_contest.startswith("(h)"):
                   self.current_contest = self.current_contest[3:]
              if self.current_choice.startswith("(v)"):
                   self.current_choice = self.current_choice[3:]
              if self.current_oval.startswith("(v)"):
                   self.current_oval = self.current_oval[3:]
         except:
              pass
         
         try:
              self.current_choice = self.current_choice[:40]
         except:
              pass
         
         try:
              self.current_prop = self.current_prop[:40]
         except:
              pass
         
         try:
              self.current_oval = self.current_oval[:40]
         except:
              pass
         
         
         vd = VoteData(filename=self.name,
                       precinct=precinct,
                       jurisdiction=self.current_jurisdiction,
                       contest = self.current_contest,
                       choice = self.current_choice,
                       prop = self.current_prop,
                       oval = self.current_oval,
                       coords = [startx,starty],
                       stats = cs,
                       maxv = maxv)
         try:
              # check to see if the current choice is darkened and
              # also includes "Write-in" or a variant text and, if so,
              # write out the region to a file
              if vd.was_voted and (self.current_oval.find("Write")>-1 
                                   or self.current_oval.find("vrit")>-1 
                                   or self.current_oval.find("Vrit")>-1):
                   # crop the coords for three inches of horizontal
                   # and three times the oval height
                   if (self.current_oval.find("riter")>-1):
                        pass
                   else:
                        wincrop = image.crop(
                             (startx,
                              starty,
                              startx+int(2.5*dpi),
                              starty+int(0.6*dpi)
                              )
                             )
                   if not os.path.exists("./writeins"):
                        try:
                             os.makedirs("./writeins")
                        except Exception, e:
                             print "Could not create directory %s\n%s" % (
                                  "./writeins",e)
                             const.logger.error("Could not create directory %s\n%s" % 
                                          ("./writeins",e))
                             
                   savename = "writeins/%s_%s.jpg" % (
                        self.name[-10:-4].replace("/","").replace(" ","_"),
                        self.current_contest[:20].replace(
                             "/","").replace(" ","_")
                        )
                   wincrop.save(savename)
                   print "Saved",savename
                   const.logger.info("Saved %s\n",savename)

         except Exception, e:
              print e
              const.logger.debug(e)

         return vd

    def toXML(self):
        contestlist = []
        retlist = ["<BallotSide",
                   "dpi='%d' precinct='?' lx='%d' ly='%d' rot='%f'>" % (
                  self.dpi,
                  self.xref,
                  self.yref,
                  self.tang)
                   ]
        jurisdiction_open = False
        contest_open = False
        
        const.logger.debug(
            "BSide.toXML imname %s dpi %d newxy %d %d tang %f" % (
                self.name,
                self.dpi,
                self.xref,
                self.yref,
                self.tang)
            )
        self.results = []
        self.current_jurisdiction = "No info"
        self.current_contest = "No info"
        self.current_choice =  "No info"
        self.current_prop = "No info"
        # walk through the regionlist in sequence, creating potential
        # contest nodes and adding them to the ballotside if the potential
        # contest includes at least one oval (choice).
        contest_ovalcount = 0
        for region in self.regionlist:
            if region.text.startswith("(v)") or region.text.startswith("(h)"):
                region.text = region.text[3:]
            if region.purpose == BtRegion.JURISDICTION:
                # close existing jurisdiction
                if jurisdiction_open:
                    retlist.append("</Jurisdiction>")
                self.current_jurisdiction = region.text
                # open new jurisdiction
                retlist.append("<Jurisdiction text='%s'>" 
                               % region.text.replace("'",""))
            elif region.purpose == BtRegion.CONTEST:
                # close existing contest
                if contest_open:
                    contestlist.append("</Contest>")
                if contest_ovalcount > 0:
                    retlist.extend(contestlist)
                contestlist = []
                contest_ovalcount = 0
                self.current_contest = region.text
                # open new contest
                contest_open = True
                contestlist.append(
       "<Contest prop='False' \ntext='%s' x='%d' y='%d' x2='%d' y2='%d'>"
                               % (region.text.replace("'",""),
                                  region.bbox[0],region.bbox[1],
                                  region.bbox[2],region.bbox[3],
                                  )
                )
                if self.current_contest.find("Count")>=0:
                    self.current_jurisdiction = self.current_contest
                if self.current_contest.find("State")>=0:
                    self.current_jurisdiction = self.current_contest
                if self.current_contest.find("School")>=0:
                    self.current_jurisdiction = self.current_contest
                if self.current_contest.find("Meas")>=0:
                    self.current_prop = self.current_contest
                else:
                    self.current_prop = None

            elif region.purpose == BtRegion.CHOICE:
                self.current_choice = region.text

            elif region.purpose == BtRegion.PROP:
                # close existing
                # close existing contest
                if contest_open:
                    contestlist.append("</Contest>")
                if contest_ovalcount > 0:
                    retlist.extend(contestlist)
                contestlist = []
                contest_ovalcount = 0
                self.current_contest = region.text


                contestlist.append("<Contest prop='True' \ntext='%s'>"
                               % region.text.replace("'",""))
                
                self.current_contest = region.text
                # open new
                self.current_prop = "(Prop)"
                
            else:
                # anything above 3 is an oval, with the y offset stored
                # in place of the purpose
                self.current_oval = region.text
                contest_ovalcount += 1
                self.current_coords = region.coord
                #pdb.set_trace()
                contestlist.append("<oval x='%d' y='%d' text='%s' />" 
                               % (self.current_coords[0], 
                                  self.current_coords[1], 
                                  region.text.replace("'","")
                                  )
                               )
                # if additional result functions are provided,
                # call them here and accumulate their results
        if contest_open and contest_ovalcount > 0:
            retlist.extend(contestlist)
            retlist.append("</Contest>")
        if jurisdiction_open:
            retlist.append("</Jurisdiction>")
        retlist.append("</BallotSide>")
        return retlist

    def vote(self, image, dpi, precinct, newx, newy, tang):
        if (tang > 0.05):
            const.logger.info("Tang of %f on %s is too high, clamping at 0.05" % (
                    self.tang,self.name))
            self.tang = 0.05

        if (tang < -0.05):
            const.logger.info("Tang of %f on %s is too low, clamping at -0.05" % (
                    self.tang,self.name))
            self.tang = -0.05
        
        const.logger.debug(
            "BSide.vote imname %s dpi %d newxy %d %d tang self.tang %f %f" % (
                self.name,
                dpi,
                newx,
                newy,
                tang,
                self.tang)
            )
        if image is None:
            print "Attempting to vote ballot side with no image"
        self.results = []
        self.current_jurisdiction = "No info"
        self.current_contest = "No info"
        self.current_choice =  "No info"
        self.current_prop = "No info"
        # walk through the regionlist in sequence, setting jurisdiction
        # and contest as they are changed, and determining intensity of
        # vote ovals by calls to oval_result
        for region in self.regionlist:
            if region.purpose == BtRegion.JURISDICTION:
                self.current_jurisdiction = region.text

            elif region.purpose == BtRegion.CONTEST:
                self.current_contest = region.text
                #if self.current_contest.find("SHER")>-1:
                #     pdb.set_trace()
                if self.current_contest.find("Count")>=0:
                    self.current_jurisdiction = self.current_contest
                if self.current_contest.find("State")>=0:
                    self.current_jurisdiction = self.current_contest
                if self.current_contest.find("School")>=0:
                    self.current_jurisdiction = self.current_contest
                if self.current_contest.find("Meas")>=0:
                    self.current_prop = self.current_contest
                else:
                    self.current_prop = None

            elif region.purpose == BtRegion.CHOICE:
                self.current_choice = region.text

            elif region.purpose == BtRegion.PROP:
                self.current_contest = region.text
                self.current_prop = "(Prop)"
                
            else:
                # anything above 3 is an oval, with the y offset stored
                # in place of the purpose
                self.current_oval = region.text
                self.current_coords = region.coord
                scalefactor = float(dpi)/float(self.dpi)
                xoffset = newx - (self.xref*scalefactor)
                yoffset = newy - (self.yref*scalefactor)
                # the ballot region's dpi will typically be 300,
                # while individual ballots will typically have 150
                
                scalefactor = float(dpi)/float(self.dpi)
                try:
                    ovalresult = self.oval_result(image,
         scalefactor,
         precinct,
         xoffset,
         yoffset,
         tang,
         rot_about_x=int(scalefactor*self.xref),
         rot_about_y=int(scalefactor*self.yref)
         )
                    self.results.append(ovalresult)
                except TypeError, e:
                    print "TypeError",e
                # if additional result functions are provided,
                # call them here and accumulate their results


class BallotSideFromXML(BallotSide):
    """BallotSide created from an xml string"""


    def toXML(self):
        """If a BallotSide is from xml string, toXML just returns the string"""
        return self.myxml

    def __init__(self, name,side,myxml):
        """Create a BallotSide from an XML string, so editing is possible"""
        self.ballot = None
        self.name = name
        self.side = side
        self.myxml = """<?xml version="1.0"?>"""+myxml
        try:
            doc = xml.dom.minidom.parseString(self.myxml)
        except Exception, e:
            const.logger.error("problem parsing")
            const.logger.error(e)
            for line in myxml.split("\n"):
                const.logger.error(line)
            print e
        self.regionlist = []
        bs = doc.getElementsByTagName("BallotSide")
        self.dpi = bs[0].getAttribute('dpi')
        self.dpi = int(self.dpi)
#       "dpi='%d' precinct='?' lx='%d' ly='%d' rot='%f'
        contests = doc.getElementsByTagName("Contest")
        for contest in contests:
            contest_x = contest.getAttribute('x')
            contest_y = contest.getAttribute('y')
            contest_x2 = contest.getAttribute('x2')
            contest_y2 = contest.getAttribute('y2')
            contest_text = contest.getAttribute('text')
            purpose = BtRegion.CONTEST
            contest_x = int(contest_x)
            contest_y = int(contest_y)
            bbox = (contest_x,contest_y,contest_x2,contest_y2)
            coord = (contest_x,contest_y)
            self.regionlist.append(BtRegion(bbox,purpose,coord,contest_text))
            choices = contest.getElementsByTagName("oval")
            for choice in choices:
                choice_x = choice.getAttribute('x')
                choice_y = choice.getAttribute('y')
                choice_text = choice.getAttribute('text')
                purpose = BtRegion.OVAL
                bbox = (choice_x,choice_y,choice_x,choice_y)
                coord = (choice_x,choice_y,choice_x,choice_y)
                self.regionlist.append(BtRegion(bbox,purpose,coord,choice_text))
                """
                try:
                    print "Contest %s choice %s coord %s" % (
                        contest.getAttribute('text')[:40],
                        choice.getAttribute('text')[:40],
                        coord
                        )
                except Exception, e:
                    const.logger.error("pdb.set_trace()")
                """

        self.im = None
        #self.landmarklist = self.ballot.landmarklist[self.side]
        contest_x = contest.getAttribute('x')
        self.xref = int(bs[0].getAttribute('lx')) #from the xml
        self.yref = int(bs[0].getAttribute('ly')) #from the xml
        self.tang = float(bs[0].getAttribute('rot')) #from the xml
        self.codelist = [None,None]
        self.columnlist = [None,None]
        self.br = [None,None]
        self.current_jurisdiction = "No info"
        self.current_contest = "No info"
        self.current_choice = "No info"
        self.current_prop = "No info"
        self.current_oval = "No info"
        self.current_coords = "No info"
        self.oval_width = const.oval_width_inches * self.dpi
        self.oval_height = const.oval_height_inches * self.dpi
        self.results = []

        pass

class Ballot(object):
    front_dict = {}
    back_dict = {}
    precinct_dict = {}

    def register(self, n):
         """Add this ballot's number and code(s) to ballotcodes.csv file"""
         print self.code_string
         pdb.set_trace()
         f = open("ballotcodes.csv","a")
         f.write("%06d,%s\n" % (n,self.code_string))
         f.close()

    def toString(self):
         # any result that does not include a minimum 
         # of two ovals for a contest is not output
         # because it is either an artifact or write-in only
         stringarray = []
         tempstringarray = []
         thiscontest = ""
         lastcontest = ""
         num_in_contest = 0

         # if new contest, 
         #   if num_in_contest > 1:
         #     put stored buffer into output
         #   clear stored buffer
         # set num_in_contest to 1 and store in buffer
         # if matches last contest, inc num_in_contest and store in buffer
         for vd in self.br[0].results:
              thiscontest = vd.contest
              if thiscontest <> lastcontest:
                   if num_in_contest > 1:
                        stringarray.extend(tempstringarray)
                   tempstringarray = []
                   num_in_contest = 1
              else:
                   num_in_contest += 1
              tempstringarray.append(vd.toString())
              lastcontest = thiscontest
         stringarray.extend(tempstringarray)
         tempstringarray = []
         if self.duplex:
              for vd in self.br[1].results:
                   thiscontest = vd.contest
                   if thiscontest <> lastcontest:
                        if num_in_contest > 1:
                             stringarray.extend(tempstringarray)
                        tempstringarray = []
                        num_in_contest = 1
                   else:
                        num_in_contest += 1
                   tempstringarray.append(vd.toString())
                   lastcontest = thiscontest
              stringarray.extend(tempstringarray)

         return "\n".join(stringarray)

    def do_pickle(self):
         """ Save the precinct dictionary."""
         # There's no longer any need to save the front and back
         # layout dictionaries, as the individual layouts
         # are now saved in the templates folder.
         try:
              precinctdictfile = open("precincts.dct","w")
              pickle.dump(Ballot.precinct_dict,precinctdictfile)
              precinctdictfile.close()
         except Exception, e:
              print "Could not pickle the precinct_dict to precincts.dct"
              print e


    def build_regionlist(self,im,br,ovallist,headers,columns):
        global process_list
        newovallist = [[],[],[],[],[]]
        changelist = [[],[],[],[],[]]
        for ov in ovallist:
            bestmatch = -1
            lowdiff = 10000
            for n in range(columns):
                diff = abs(headers[n][0] - ov[0])
                if diff < lowdiff:
                    lowdiff = diff
                    bestmatch = n
            newovallist[bestmatch].append(ov)


        for n in range(columns):
            topx = headers[n][0]-(self.dpi/10) 
            bottomx = headers[n+columns][0]-(self.dpi/10)
            changelist[n] = im.getchanges(topx, bottomx, self.dpi)
        # for each column, 
        # 1) combine and sort the change and oval lists
        # using [1] (y) as the sort value, 
        # 2) adjust list for text in oval zone
        # 3) recombine and resort
        addovallist = [[],[],[],[],[]]
        rettext = ["","","","",""]
        #const.logger.debug(datetime.now().isoformat())
        for n in range(columns):
            # merge the two lists
            newovallist[n].extend(changelist[n])
            # sort the result in place
            newovallist[n].sort(cmp = lambda a,b: a[1]-b[1])
            #print n, newovallist[n]

            # FURTHER REQUIRED ADJUSTMENT TO RESULTING LIST:
            # if an entry is called an oval,
            # we have to examine the region above -- 
            # typically white or including a prior oval --
            # for any other darkness in the oval's x channel.
            # If encountered, we have to split the region
            # at the highest and lowest nonoval dark pixels.
            # This is due to descriptive text 
            # sometimes found in the oval channel.

            # strategy: if list[n][1]>3 
            # examine oval channel list[n][0]...list[n][0+10] for dark pixels 
            # from list[n-1][1]+ovalheight
            # to list[n][1] - "a bit"
            # crop((list[n][0],list[n-1][1]+ovalheight,
            #      list[n][0]+10,list[n][1]-5))

            clear_tilt = self.dpi/36
            clear_oval = self.dpi/4
            check_zone_width = self.dpi/3
            just_added = 0
            for m in range(len(newovallist[n])):
                # if you added a new entry in the last pass,
                # you will not want to add a new entry before the next oval
                if just_added:
                    just_added = 0
                    continue
                miny = 0
                maxy = 0
                if newovallist[n][m][0]>3:
                    startx = newovallist[n][m][0]
                    try:
                        # if the preceding entry was an oval, clear it
                        # but if the preceding entry was black or gray, 
                        # just clear a possible tilt
                        if newovallist[n][m-1][0] > 3:
                            starty = newovallist[n][m-1][1]+clear_oval
                        else:
                            starty = newovallist[n][m-1][1]+clear_tilt

                    except:
                        starty = 1
                    endx = newovallist[n][m][0]+check_zone_width
                    endy = newovallist[n][m][1] - clear_tilt
                    for y in range(starty,endy):
                        # 0 at the end means no fine adjustment (not vote oval)
                        cs = im.cropstats(startx,y,endx-startx,1,0)
                        if ((miny==0) and (cs[1] > 1)):
                            miny = y
                        if ((y>maxy) and (cs[1] > 1)):
                            maxy = y

                    (miny,maxy) = im.getdarkextents(startx,starty,endx,endy)

                    # We require that we found at least 2 dark pixels in rows
                    # which are separated by at least 1/12" 
                    # (avoiding the case of
                    # just one dark row near one edge)
                    if ((miny>0) and (maxy>0)):
                        miny -= (self.dpi/72)
                        maxy += (self.dpi/72)
                        # the new entry will be merged at the end of the loop
                        addovallist[n].append([3,miny])
                        just_added = 1
                        #print "Addovallist[n]",n,addovallist
                        # the old entry starting y 
                        # moves to the new entry's ending y
                        #print "Oval at",n,m,"was",newovallist[n][m]
                        #newovallist[n][m][1] = maxy
                        #print "Oval at",n,m,"now is",newovallist[n][m]
                        #print "New region starts at %d  precedes 
                        #            oval (%d,%d)\n" % (
                        #    miny, 
                        #    newovallist[n][m][0],
                        #    newovallist[n][m][1])
                    miny = 0
                    maxy = 0

            # add the new entries to newovallist, and re-sort in place
            newovallist[n].extend(addovallist[n])
            newovallist[n].sort(cmp = lambda a,b: a[1]-b[1])

            try:
                next_x = headers[n+1][0] - (self.dpi/4)
                if next_x < (headers[n][0] - (self.dpi/4)):
                    raise Exception
            except:
                next_x = im.size[1] - ((2*self.dpi)/3)

            rettext[n] = process_list(im,br,newovallist[n],headers[n][1],next_x)

    def toXML(self):
        retlist = ["<Ballot name='%s'>" % self.imagefilenames[0]]
        if self.br[0] is not None:
            retlist.extend(self.br[0].toXML())
        if self.br[1] is not None:
            retlist.extend(self.br[1].toXML())
        retlist.append("</Ballot>")
        return retlist
    
    def vote(self):
        """ Voting is delegated to the BallotRegion lists"""
        """In order to vote the ovals, you need to compare each ballot
        image's tiltinfo with that in the stored BallotRegion that has
        unadjusted (x,y) for ovals, shifting and rotating as appropriate."""
        if self.br[0] is not None:
            if self.im[0] is None:
                print "No image found for ",self.imagefilenames[0]
                raise Exception
            else:
                const.logger.info(
                    "Ballot calling br[0].vote with %s, %d" % (
                        self.imagefilenames[0],
                        self.dpi)
                    )
                try:
                    self.br[0].vote(self.im[0],
                                    self.dpi,
                                    self.precinct,
                                    self.xref[0],
                                    self.yref[0],
                                    self.tang[0]
                                    )
                except Exception, e:
                    print e
                    const.logger.error("%s" % e )
                    self.im[0] = None


        if self.duplex and self.br[1] is not None:
            if self.im[1] is None:
                print "No image found for ",self.imagefilenames[1]
                raise Exception
            else:
                const.logger.info(
                    "Ballot calling br[1].vote with %s, %d" % (
                        self.imagefilenames[1],
                        self.dpi)
                    )
                try:
                    self.br[1].vote(self.im[1],
                                    self.dpi,
                                    self.precinct,
                                    self.xref[1],
                                    self.yref[1],
                                    self.tang[1]
                                    )
                except Exception, e:
                    print e
                    const.logger.error(e)
                    const.logger.debug("pdb.set_trace()")
                    self.im[1] = None


class TemplateBallot(Ballot):
    """A ballot built from XML.
    The idea being that once the system has generated ballot sides,
    they can be written out as XML entries in a dictionary, 
    the text can be corrected by humans, and the corrected template
    can be imported back."""
    pass

class DieboldBallot(Ballot):
     """A DieboldBallot uses Diebold analysis."""
     def getdiebolddetails(self,im,br):
          """ get layout and ocr information """
          dpi = self.dpi
          """ pull stuff in from diebold.py !!! """
          return None

    def gethartdetails(self,im,br):
        """ get layout and ocr information """
        dpi = self.dpi
        vline_list = im.getcolumnvlines(0,im.size[1]/4,im.size[0]-20)
        const.logger.debug("%s" % vline_list)
        lastx = 0
        """
        For each hlinelist that is separated from the previous by 
        a reasonable amount (more than dpi/4 pixels), we want to line up
        the negative values from the new hlinelist with the positive values
        from the old one
        """
        hlinelistlist = []
        columnstart_list = []
        vop_list = []
        for x in vline_list:
            if (x - lastx) > (dpi/4):
                columnstart_list.append(x)
                pot_hlines = im.getpotentialhlines(x,1,dpi)
                #print x,pot_hlines
                hlinelistlist.append( pot_hlines)
                #print "TO",x,len(hlinelistlist)
            lastx = x
        lastel2 = 0
        #for col in range(len(hlinelistlist)):
        #    print col,hlinelistlist[col]

        # an hline is confirmed by matching a positive hline in sublist n
        # against a negative hline in sublist n+1; if no sublist n+1, no hlines
        conf_hll = []
        for col in range(len(hlinelistlist)-1):
            conf_hll.append([])
            #print col, len(hlinelistlist[col])
            for entrynum in range(len(hlinelistlist[col])):
                yval1 = hlinelistlist[col][entrynum]
                for entrynum2 in range(len(hlinelistlist[col+1])):
                    yval2 = hlinelistlist[col+1][entrynum2]
                    if (yval1 > 0) and (abs(yval1 + yval2) < (dpi/16)):
                        conf_hll[col].append(yval1)
                        break
        #print conf_hll
        for x in range(len(conf_hll)):
            conf_hll[x] = map(lambda el: [el,"h"],conf_hll[x])
        #print conf_hll

        vboxes = []
        for startx in columnstart_list:
             if (startx <= 0):
                  const.logger.info("Negative startx passed to gethartvoteboxes")
                  
             vboxes.append([])
             vboxes[-1] = im.gethartvoteboxes(startx,dpi/2,dpi)
             vboxes[-1] = map(lambda el: [el[1],"v"],vboxes[-1])

        for x in range(len(conf_hll)):
            conf_hll[x].extend(vboxes[x])
            conf_hll[x].sort()
            #print columnstart_list[x],conf_hll[x]
            # now pass conf_hll[x] and the corresponding column start and end
            # into a function which will do OCR on vote and above-vote 
            # subregions
            endx = 0
            try:
                endx = columnstart_list[x+1]
            except:
                endx = im.size[0] - (dpi/2)
            text = ocr(im,br,dpi,columnstart_list[x],endx,conf_hll[x])
            #print len(br)
            #for btr in br:
            #    print btr

     def __init__(self, imagefilenames=None):
          print "New Diebold Ballot",imagefilenames
          self.imagefilenames = imagefilenames
        #self.dpi = 150
        #self.dpi_y = 150
          self.need_to_pickle = False
          self.tiltinfo = [None,None]
          self.im = [None,None]
          self.xref = [0,0]
          self.yref = [0,0]
          self.tang = [0,0]
          self.codelist = [None,None]
          self.columnlist = [None,None]
          self.br = [None,None]
          self.precinct = ""
          self.regionlists = [[],[]]
          self.duplex = False
          self.frontfirst = True
          self.results = []
          
          if len(self.imagefilenames)>1:
               self.duplex = True
          if len(self.imagefilenames)>2:
               raise Exception
        # get images, dpi, and tilts
          self.imagecount = len(imagefilenames)

        # The following "if" is present to catch the one sided ballots;
        # they will have no lines at top or bottom and therefore will
        # return None from gethartlandmarks.
        # If it is the first of the pair, the imagefilename pair is 
        # replaced with the second; if it is the second of the pair,
        # the imagefilename pair is replaced with the first.

          first_was_removed = False
          
          if self.imagecount > 1:
             try:
                  self.im[0] = Image.open(self.imagefilenames[0])
                  self.im[0] = self.im[0].convert("RGB")
                  self.dpi = int(round(
                            self.im[0].size[0]/const.ballot_width_inches)
                                 )
                  if self.dpi > 148 and self.dpi < 152:
                       self.dpi = 150
                  self.dpi_y = self.dpi

                  self.tiltinfo[0] = self.im[0].getdieboldlandmarks(
                       self.dpi,
                       False)
                  if self.tiltinfo[0] is None:
                       self.imagefilenames = [self.imagefilenames[1]]
                       first_was_removed = True
                       self.duplex = False
             except Exception, e:
                  const.logger.error(e)

          if self.imagecount > 1 or first_was_removed:
             n = 1
             if first_was_removed:
                  n = 0
             try:
                  self.im[n] = Image.open(self.imagefilenames[n])
                  self.im[n] = self.im[n].convert("RGB")
                  self.dpi = int(round(
                            self.im[n].size[0]/const.ballot_width_inches)
                                 )
                  self.dpi_y = self.dpi
                  if self.dpi > 148 and self.dpi < 152:
                       self.dpi = 150
                  self.dpi_y = self.dpi

                  self.tiltinfo[n] = self.im[n].getdieboldlandmarks(
                       self.dpi,
                       False)
                  if self.tiltinfo[n] is None:
                       if not first_was_removed:
                            self.imagefilenames = [self.imagefilenames[0]]
                            self.duplex = False
                       else:
                            raise BallotException
             except Exception, e:
                  const.logger.error(e)

          self.imagecount = len(self.imagefilenames)
          
          for n in range(self.imagecount):
            try:
                self.im[n] = Image.open(self.imagefilenames[n])
                self.im[n] = self.im[n].convert("RGB")
                self.dpi = int(round(
                          self.im[n].size[0]/const.ballot_width_inches)
                               )
                if self.dpi > 148 and self.dpi < 152:
                     self.dpi = 150
                     self.dpi_y = self.dpi
                const.logger.debug("DPI %d on file %s" % (self.dpi,
                                                    self.imagefilenames[n]))

                # don't worry for now about oddball case 
                # with y resolution <> x resolution
                self.dpi_y = self.dpi

                #  tiltinfo = (blocktype,blockx,blocky,linediff1,ydiff);
                # blocktype 2 is front, 4 is back
                try:
                    self.tiltinfo[n] = self.im[n].getdieboldlandmarks(
                         self.dpi,
                         False)
                    if self.tiltinfo[n] is None:
                         if (n == 1):
                              self.imagefilenames = (self.imagefilenames[0])
                    if self.tiltinfo[n][0] == 0:
                        raise Exception
                except Exception, e:
                    print "Problem in getdieboldlandmarks ",
                    print "creating ballot from image %s" % (
                        self.imagefilenames[n])
                    print e
                    const.logger.error(e)
                    self.im[n] = None
                    raise Exception
                #print self.tiltinfo

                # we will be calling functions that require 
                # tiltinfo to be in the style of ESS tiltinfo:
                #  tiltinfo = (blocktype,blockx,blocky,linediff1,ydiff);
                # 
                self.xref[n] = self.tiltinfo[n][0][0]
                self.yref[n] = self.tiltinfo[n][0][1]
                xdiff = self.tiltinfo[n][1][0]- self.tiltinfo[n][0][0]
                ydiff = self.tiltinfo[n][1][1]- self.tiltinfo[n][0][1]
                # Try using longest line instead
                # note that tiltinfo[n][3][0] is not set!!!
                shortdiff = self.tiltinfo[n][2][0] - self.tiltinfo[n][1][0]
                longdiff = self.tiltinfo[n][2][1] - self.tiltinfo[n][1][1]
                const.logger.debug("n %d tiltinfo[%d] = %s, short %d, long %d" % 
                             (n,n,self.tiltinfo[n],shortdiff,longdiff)
                             )
                self.tiltinfo[n] = [2,
                                    self.xref[n],
                                    self.yref[n],
                                    longdiff,
                                    shortdiff]
                try:
                    self.tang[n] = float(shortdiff)/float(longdiff)
                    if abs(self.tang[n])>0.05:
                        const.logger.error("Bad tilt calculation on %s" % 
                                     self.imagefilenames[n])
                        const.logger.error("n %d tiltinfo[%d]=%s, short%d, long%d" % 
                             (n,n,self.tiltinfo[n],shortdiff,longdiff)
                             )
                    const.logger.debug("shortdiff %d longdiff %d tangent %f\n"%(
                            shortdiff, 
                            longdiff, 
                            self.tang[n])
                                 )
                except Exception, e:
                    print e
                    const.logger.error(e)
                    self.tang[n] = 0.
                    raise Exception
            except:
                self.im[n] = None
                raise BallotException
          dashcode = self.im[0].diebolddashcode(self.im[0].size[1]-1,False)
        # check for "reverse" dash code (!!! this may vary)
          reverse_dash_code = 0xFF;
          if ((dashcode & 0x7FFF) == reverse_dash_code) :
             #pdb.set_trace()
             correct_order_of_images = False
             # switch the first and second
             const.logger.info("Switching images %s and %s"  % 
                         (self.imagefilenames[0],self.imagefilenames[1]))
             self.tiltinfo[0],self.tiltinfo[1] = (
                  self.tiltinfo[1],self.tiltinfo[0])
             self.im[0],self.im[1] = (self.im[1],self.im[0])
             self.xref[0], self.xref[1] = (self.xref[1],self.xref[0])
             self.yref[0], self.yref[1] = (self.yref[1],self.yref[0])
             self.tang[0], self.tang[1] = (self.tang[1],self.tang[0])
             self.codelist[0], self.codelist[1] = (
                  self.codelist[1], self.codelist[0])
             self.columnlist[0], self.columnlist[1] = (
                  self.columnlist[1], self.columnlist[0])
             self.imagefilenames[0],self.imagefilenames[1] = (
                  self.imagefilenames[1],self.imagefilenames[0])
             self.frontfirst = True

          for n in range(self.imagecount):
             try:
                  # now get the code and header columns from the images
                #print "self.xref[n]",n,self.xref[n]
                #print "self.yref[n]",n,self.yref[n]
                #print "self.tang[n]",n,self.tang[n]
                #print "height: ",(3*self.dpi) - ((3*self.dpi)/8)
                  
                  print n,self.xref[n],self.yref[n],self.dpi/3,self.dpi/8
                  
                  if (self.xref[n] - (self.dpi/3))<0:
                       raise BallotException
                  if (self.yref[n] - (self.dpi/8))<0:
                       raise BallotException
                  self.codelist[n] = self.im[n].diebolddashcode(128,self.dpi,0)
             except Exception, e:
                  const.logger.error("Problem in gethartbarcode for %s"% (
                            self.imagefilenames[n],)
                               ) 
                  const.logger.error(e)
                  self.im[n] = None
                  raise BallotException
        # if the front code is not yet in the dictionary, 
        # build front and back BallotSide and store 
        # using front code as key in both cases
          code_string = "%08x" % self.codelist[0]        
          try:
            # we must reset the name to avoid using the 
            # dictionary version's ballot name for all votes
            self.br[0] = BallotSideFromXML(
                 self.imagefilenames[0],
                 0,
                 "\n".join(Ballot.front_dict[code_string]))
            if self.duplex:
                 self.br[1] = BallotSideFromXML(
                      self.imagefilenames[1],
                      1,
                      "\n".join(Ballot.back_dict[code_string]))
            #self.br[1].name = self.imagefilenames[1]
            self.precinct = Ballot.precinct_dict[code_string]
          except:
            # EVERYTHING IN THIS EXCEPTION IS GETTING NEW LAYOUT

            # the landmarklist will be the x,y linediff1 and ydiff 
            # from getesstilt, where (x,y) are coordinates of the first box
            # of the ballots box column (front left or back right)
            # and linediff1 is the dx for ydiff dy
            # calculated by looking at the drift of the boxes in that column 

            #pdb.set_trace()
            const.logger.info("New code string %s at image %s" % (
                       code_string,
                       self.imagefilenames[0])
                        )
            self.need_to_pickle = True
            self.br[0] = []

            self.getdiebolddetails(self.im[0],self.regionlists[0])
            #self.gethartdetails(self.im[0],self.regionlists[0])
            self.br[0] = BallotSide(
                self,0,
                dpi=self.dpi)
            #print self.br[0]
            Ballot.front_dict[code_string] = self.br[0].toXML()
            if self.duplex:
                self.br[1] = []
                self.getdiebolddetails(self.im[1],self.regionlists[1])
                self.br[1] = BallotSide(
                    self,1,
                    dpi=self.dpi)
                Ballot.back_dict[code_string] = self.br[1].toXML()
            for n in range(self.imagecount):
                if (n==0):
                    self.precinct = " "
                    Ballot.precinct_dict[code_string] = self.precinct




class HartBallot(Ballot):
    """A HartBallot uses Hart analysis to build new layouts"""

    def gethartdetails(self,im,br):
        """ get layout and ocr information """
        dpi = self.dpi
        vline_list = im.getcolumnvlines(0,im.size[1]/4,im.size[0]-20)
        const.logger.debug("%s" % vline_list)
        lastx = 0
        """
        For each hlinelist that is separated from the previous by 
        a reasonable amount (more than dpi/4 pixels), we want to line up
        the negative values from the new hlinelist with the positive values
        from the old one
        """
        hlinelistlist = []
        columnstart_list = []
        vop_list = []
        for x in vline_list:
            if (x - lastx) > (dpi/4):
                columnstart_list.append(x)
                pot_hlines = im.getpotentialhlines(x,1,dpi)
                #print x,pot_hlines
                hlinelistlist.append( pot_hlines)
                #print "TO",x,len(hlinelistlist)
            lastx = x
        lastel2 = 0
        #for col in range(len(hlinelistlist)):
        #    print col,hlinelistlist[col]

        # an hline is confirmed by matching a positive hline in sublist n
        # against a negative hline in sublist n+1; if no sublist n+1, no hlines
        conf_hll = []
        for col in range(len(hlinelistlist)-1):
            conf_hll.append([])
            #print col, len(hlinelistlist[col])
            for entrynum in range(len(hlinelistlist[col])):
                yval1 = hlinelistlist[col][entrynum]
                for entrynum2 in range(len(hlinelistlist[col+1])):
                    yval2 = hlinelistlist[col+1][entrynum2]
                    if (yval1 > 0) and (abs(yval1 + yval2) < (dpi/16)):
                        conf_hll[col].append(yval1)
                        break
        #print conf_hll
        for x in range(len(conf_hll)):
            conf_hll[x] = map(lambda el: [el,"h"],conf_hll[x])
        #print conf_hll

        vboxes = []
        for startx in columnstart_list:
             if (startx <= 0):
                  const.logger.info("Negative startx passed to gethartvoteboxes")
                  
             vboxes.append([])
             vboxes[-1] = im.gethartvoteboxes(startx,dpi/2,dpi)
             vboxes[-1] = map(lambda el: [el[1],"v"],vboxes[-1])

        for x in range(len(conf_hll)):
            conf_hll[x].extend(vboxes[x])
            conf_hll[x].sort()
            #print columnstart_list[x],conf_hll[x]
            # now pass conf_hll[x] and the corresponding column start and end
            # into a function which will do OCR on vote and above-vote 
            # subregions
            endx = 0
            try:
                endx = columnstart_list[x+1]
            except:
                endx = im.size[0] - (dpi/2)
            text = ocr(im,br,dpi,columnstart_list[x],endx,conf_hll[x])
            #print len(br)
            #for btr in br:
            #    print btr

    def register(self,arg):
         super(HartBallot,self).register(arg)

    def __init__(self, imagefilenames=None):
        #pdb.set_trace()
        print "New Hart Ballot",imagefilenames
        self.imagefilenames = imagefilenames
        #self.dpi = 150
        #self.dpi_y = 150
        self.need_to_pickle = False
        self.tiltinfo = [None,None]
        self.im = [None,None]
        self.xref = [0,0]
        self.yref = [0,0]
        self.tang = [0,0]
        self.codelist = [None,None]
        self.code_string = ""
        self.columnlist = [None,None]
        self.br = [None,None]
        self.precinct = ""
        self.regionlists = [[],[]]
        self.duplex = False
        self.frontfirst = True
        self.results = []

        if len(self.imagefilenames)>1:
            self.duplex = True
        if len(self.imagefilenames)>2:
            raise Exception
        # get images, dpi, and tilts
        self.imagecount = len(imagefilenames)

        # The following "if" is present to catch the one sided ballots;
        # they will have no lines at top or bottom and therefore will
        # return None from gethartlandmarks.
        # If it is the first of the pair, the imagefilename pair is 
        # replaced with the second; if it is the second of the pair,
        # the imagefilename pair is replaced with the first.

        first_was_removed = False

        if self.imagecount > 1:
             try:
                  self.im[0] = Image.open(self.imagefilenames[0])
                  self.im[0] = self.im[0].convert("RGB")
                  self.dpi = int(round(
                            self.im[0].size[0]/const.ballot_width_inches)
                                 )
                  if self.dpi > 148 and self.dpi < 152:
                       self.dpi = 150
                  self.dpi_y = self.dpi

                  self.tiltinfo[0] = self.im[0].gethartlandmarks(self.dpi,False)
                  if self.tiltinfo[0] is None:
                       self.imagefilenames = [self.imagefilenames[1]]
                       first_was_removed = True
                       self.duplex = False
             except Exception, e:
                  const.logger.error(e)

        if self.imagecount > 1 or first_was_removed:
             n = 1
             if first_was_removed:
                  n = 0
             try:
                  self.im[n] = Image.open(self.imagefilenames[n])
                  self.im[n] = self.im[n].convert("RGB")
                  self.dpi = int(round(
                            self.im[n].size[0]/const.ballot_width_inches)
                                 )
                  self.dpi_y = self.dpi
                  if self.dpi > 148 and self.dpi < 152:
                       self.dpi = 150
                  self.dpi_y = self.dpi

                  self.tiltinfo[n] = self.im[n].gethartlandmarks(self.dpi,False)
                  if self.tiltinfo[n] is None:
                       if not first_was_removed:
                            self.imagefilenames = [self.imagefilenames[0]]
                            self.duplex = False
                       else:
                            raise BallotException
             except Exception, e:
                  const.logger.error(e)
                  raise BallotException

        self.imagecount = len(self.imagefilenames)

        for n in range(self.imagecount):
            try:
                self.im[n] = Image.open(self.imagefilenames[n])
                self.im[n] = self.im[n].convert("RGB")
                self.dpi = int(round(
                          self.im[n].size[0]/const.ballot_width_inches)
                               )
                if self.dpi > 148 and self.dpi < 152:
                     self.dpi = 150
                     self.dpi_y = self.dpi
                const.logger.debug("DPI %d on file %s" % (self.dpi,
                                                    self.imagefilenames[n]))

                # don't worry for now about oddball case 
                # with y resolution <> x resolution
                self.dpi_y = self.dpi

                # yolo, mjt 7/21 flunk ballots with 3/16" of black in corner
                
                testwidth = (self.dpi * 3) / 16
                testheight = testwidth
                testcrop = self.im[n].crop((0,0,testwidth,testheight))
                teststat = ImageStat.Stat(testcrop)
                """
                if teststat.mean[0] < 16:
                     const.logger.error("Dark upper left corner on %s, code %d" % (
                     self.imagefilenames[n],1))
                     raise BallotException
                testcrop = self.im[n].crop((self.im[n].size[0] - testwidth,
                                            0,
                                            self.im[n].size[0] - 1,
                                            testheight))
                teststat = ImageStat.Stat(testcrop)
                if teststat.mean[0] < 16:
                     const.logger.error("Dark upper right corner on %s, code %d" % (
                     self.imagefilenames[n],2))
                     raise BallotException
                testcrop = self.im[n].crop((self.im[n].size[0] - testwidth,
                                            self.im[n].size[1] - testheight,
                                            self.im[n].size[0] - 1,
                                            self.im[n].size[1] - 1))
                teststat = ImageStat.Stat(testcrop)
                if teststat.mean[0] < 16:
                     const.logger.error("Dark lower right corner on %s, code %d" % (
                     self.imagefilenames[n],3))
                     raise BallotException
                testcrop = self.im[n].crop((0,
                                            self.im[n].size[1] - testheight,
                                            testwidth,
                                            self.im[n].size[1] - 1))
                teststat = ImageStat.Stat(testcrop)
                if teststat.mean[0] < 16:
                     const.logger.error("Dark lower left corner on %s, code %d" % (
                     self.imagefilenames[n],4))
                     raise BallotException
"""

                #  tiltinfo = (blocktype,blockx,blocky,linediff1,ydiff);
                # blocktype 2 is front, 4 is back
                try:
                    self.tiltinfo[n] = self.im[n].gethartlandmarks(
                         self.dpi,
                         False
                         )
                    if self.tiltinfo[n] is None:
                         if (n == 1):
                              self.imagefilenames = (self.imagefilenames[0])
                    if self.tiltinfo[n][0] == 0:
                        raise Exception
                except Exception, e:
                    print "Problem in gethartlandmarks ",
                    print "creating ballot from image %s" % (
                        self.imagefilenames[n])
                    print e
                    const.logger.error(e)
                    self.im[n] = None
                    raise Exception
                #print self.tiltinfo

                # we will be calling functions that require 
                # tiltinfo to be in the style of ESS tiltinfo:
                #  tiltinfo = (blocktype,blockx,blocky,linediff1,ydiff);
                # 
                self.xref[n] = self.tiltinfo[n][0][0]
                self.yref[n] = self.tiltinfo[n][0][1]
                xdiff = self.tiltinfo[n][1][0]- self.tiltinfo[n][0][0]
                ydiff = self.tiltinfo[n][1][1]- self.tiltinfo[n][0][1]
                # Try using longest line instead
                # note that tiltinfo[n][3][0] is not set!!!
                shortdiff = self.tiltinfo[n][2][0] - self.tiltinfo[n][1][0]
                longdiff = self.tiltinfo[n][2][1] - self.tiltinfo[n][1][1]
                const.logger.debug("n %d tiltinfo[%d] = %s, short %d, long %d" % 
                             (n,n,self.tiltinfo[n],shortdiff,longdiff)
                             )
                self.tiltinfo[n] = [2,
                                    self.xref[n],
                                    self.yref[n],
                                    longdiff,
                                    shortdiff]
                try:
                    self.tang[n] = float(shortdiff)/float(longdiff)
                    if abs(self.tang[n])>0.05:
                        const.logger.error("Bad tilt calculation on %s" % 
                                     self.imagefilenames[n])
                        const.logger.error("n%d tiltinfo[%d] = %s, short%d, long%d" % 
                             (n,n,self.tiltinfo[n],shortdiff,longdiff)
                             )
                    const.logger.debug("shortdiff %d longdiff %d tangent %f\n"%(
                            shortdiff, 
                            longdiff, 
                            self.tang[n])
                                 )
                except Exception, e:
                    print e
                    const.logger.error(e)
                    self.tang[n] = 0.
                    raise Exception
            except:
                self.im[n] = None
                raise BallotException


        for n in range(self.imagecount):
             if abs(self.tang[n])>0.05:
                  raise BallotException

        correct_order_of_images = True
        # for this set of ballots, we can look for the gray area
        # used as a background in the instructions.  The area 
        # starts at 1.9 inches in and runs to 2.5 inches in from the left,
        # an runs from 3.6" down to 3.8" down and 4" down to 4.2" down,
        # and will be of an average intensity between 128 and 220 on fronts.
        # The backs may have black text falling in the area lowering the
        # average intensity, but this shoul dnot get it below 220, and it
        # can be further identified by counting black pixels versus medium
        # pixels
        # cropstats takes x,y,w,h
        print self.xref[0],self.yref[0]
        # 0 at end means no fine_adj (not working with Hart vote oval)
        cs = self.im[0].cropstats(int(self.dpi*2.0),
                                  int(self.dpi*3.65),
                                  int(self.dpi/10),
                                  int(self.dpi/10),
                                  0)
        # let's see if there's a tint in the second image 
        # which would require that we switch first and second
        cs2 = self.im[1].cropstats(int(self.dpi), 
                                   int(self.dpi/2), 
                                   int(self.dpi/10),
                                   int(self.dpi/10)
                                   ,0)
        # we want avg intensity between 128 and 224, and few pixels in black
        #if (cs[0]>128) and (cs[0]<224) and ((cs[1]*20)<cs[4]):
        #     self.frontfirst = True
        # but will allow a higher average if there are only 4 black pixels
        #elif (cs[0]>=224) and (cs[0]<240) and (cs[1]<5):
        #     self.frontfirst = True
        #elif 
        #elif (self.imagecount>1):
        #     const.logger.error("Images MAY NOT BE IN ORDER %s and %s "  % (
        #          self.imagefilenames[0],self.imagefilenames[1]))
        # images 0 should have gray region in instructions,
        # and most images 1 will have tinted areas at top
        # check for lack of gray average in cs of image 0
        # or tinted average in cs2 of image 1;
        # switch if either condition is found
        """
        if (self.imagecount>1) and (
             (abs(cs2[0] - cs2[5])>3) or 
             (abs(cs2[5]-cs2[10])>3) or
             (not ((cs[0]>128) and (cs[0]<232) and ((cs[1]*20)<cs[4])))):
             #pdb.set_trace()
             correct_order_of_images = False
             # switch the first and second
             const.logger.info("Switching images %s and %s"  % (
             self.imagefilenames[0],self.imagefilenames[1]))
             self.tiltinfo[0],self.tiltinfo[1] = (
                  self.tiltinfo[1],self.tiltinfo[0])
             self.im[0],self.im[1] = (self.im[1],self.im[0])
             self.xref[0], self.xref[1] = (self.xref[1],self.xref[0])
             self.yref[0], self.yref[1] = (self.yref[1],self.yref[0])
             self.tang[0], self.tang[1] = (self.tang[1],self.tang[0])
             self.codelist[0], self.codelist[1] = (
                  self.codelist[1], self.codelist[0])
             self.columnlist[0], self.columnlist[1] = (
                  self.columnlist[1], self.columnlist[0])
             self.imagefilenames[0],self.imagefilenames[1] = (
                  self.imagefilenames[1],self.imagefilenames[0])
             self.frontfirst = True

        """
        for n in range(self.imagecount):
             try:
                  # now get the code and header columns from the images
                #print "self.xref[n]",n,self.xref[n]
                #print "self.yref[n]",n,self.yref[n]
                #print "self.tang[n]",n,self.tang[n]
                #print "height: ",(3*self.dpi) - ((3*self.dpi)/8)
                  
                  print n,self.xref[n],self.yref[n],self.dpi/3,self.dpi/8
                  
                  if (self.xref[n] - (self.dpi/3))<0:
                       raise BallotException
                  if (self.yref[n] - (self.dpi/8))<0:
                       raise BallotException
                  self.codelist[n] = self.im[n].getbarcode(
                       self.xref[n]-(self.dpi/3),
                       self.yref[n] - (self.dpi/8),
                       self.dpi/6,
                       (3*self.dpi) - ((3*self.dpi)/8) )
             except Exception, e:
                  const.logger.error("Problem in gethartbarcode for %s" % (
                            self.imagefilenames[n],)) 
                  const.logger.error(e)
                  self.im[n] = None
                  raise BallotException
        # if the front code is not yet in the dictionary, 
        # build front and back BallotSide and store 
        # using front code as key in both cases
        code_tuple = tuple(self.codelist[0])
        # if the latter half of the code begins with a 2 instead of a 1,
        # we have a back-side instead of a front and need to switch info
        if code_tuple[1]>200000 and code_tuple[1]<300000:
             # switch the first and second
             const.logger.info("Switching images %s and %s"  % (
                       self.imagefilenames[0],self.imagefilenames[1]))
             self.tiltinfo[0],self.tiltinfo[1] = (
                  self.tiltinfo[1],self.tiltinfo[0])
             self.im[0],self.im[1] = (self.im[1],self.im[0])
             self.xref[0], self.xref[1] = (self.xref[1],self.xref[0])
             self.yref[0], self.yref[1] = (self.yref[1],self.yref[0])
             self.tang[0], self.tang[1] = (self.tang[1],self.tang[0])
             self.codelist[0], self.codelist[1] = (
                  self.codelist[1], self.codelist[0])
             self.columnlist[0], self.columnlist[1] = (
                  self.columnlist[1], self.columnlist[0])
             self.imagefilenames[0],self.imagefilenames[1] = (
                  self.imagefilenames[1],self.imagefilenames[0])
             self.frontfirst = True
             code_tuple = tuple(self.codelist[0])
             
        code_string = ""
        for el in code_tuple:
            if el>0:
                code_string += ("%d" % el)
        # code_string must conform to these rules, or is bad:
        # rules for bar codes:
        # must begin 1000
        # must follow first four digits with three digit number
        # below maximum precinct number
        # must follow three digit precinct section with
        # (0)100 and three digit number, where the (0)
        # is excluded from the codestring and the filename
        # if does not match rules, try OCR on the text beneath the bar code
        print code_string
        orig_code_string = code_string

        barcode_good = True

        # Set all barcodes to bad if you want to force new templates
        #barcode_good = False
        #pdb.set_trace()

        if len(code_string) <> 13:
             barcode_good = False
        elif not code_string.startswith("1000"):
             barcode_good = False
        else:
             code_position567 = code_string[4:7]
             if not int(code_position567)<170:
                  barcode_good = False
             code_position89A = code_string[7:10]
             if not int(code_position89A) == 100:
                  barcode_good = False
        if barcode_good:
             try:
                  Ballot.front_dict[code_string]
             except:
                  barcode_good = False

        self.code_string = code_string
        if barcode_good == False:
             const.logger.warning("Bad barcode %s at %s" % (
                       code_string, self.imagefilenames[0]))
             # try getting bar code from ocr of region beneath
             # try opening a file in "templates" named with code_string
             # and retrieving the text to serve as an alternate source
             zone = self.im[0].crop((
                       self.xref[0]- int(self.dpi/3) - int(self.dpi*0.05),
                       self.yref[0] + int(2.5 * self.dpi)  ,
                       self.xref[0] - int(self.dpi/24),
                       self.yref[0] + int(4.5*self.dpi) ))
             zone = zone.rotate(-90)
             zone.save("/tmp/barcode.tif")
             p = subprocess.Popen(["/usr/local/bin/tesseract", 
                                   "/tmp/barcode.tif", "/tmp/barcode"])
             sts = os.waitpid(p.pid,0)[1]
        #os.system("/usr/local/bin/tesseract region.tif region 2>/dev/null")
             tempf = open("/tmp/barcode.txt")
             barcode_text = tempf.read()
             tempf.close()
             barcode_text = barcode_text.replace("\n","").replace(" ","")
             barcode_text = barcode_text.replace("O","0").replace("o","0")
             barcode_text = barcode_text.replace("l","1")
             barcode_text = barcode_text.replace("I","1").replace("B","8")
             barcode_text = barcode_text.replace("Z","2").replace("U","0")
             barcode_text = barcode_text.replace("]","1").replace("[","1")
             barcode_text = barcode_text.replace(".","").replace(",","")
             barcode_text = barcode_text[:7]+barcode_text[8:]
             const.logger.warning("Barcode %s replaced with ocr'd value %s at %s" % (
                       code_string, barcode_text, self.imagefilenames[0]))
             code_string = barcode_text
             const.logger.warning( "WAS %s NOW %s" % (orig_code_string,code_string))
             print "WAS %s NOW %s" % (orig_code_string,code_string)
             self.code_string = code_string
             try:
                  Ballot.front_dict[code_string]
                  raise Exception
             except:
                  #const.logger.error("Code string failure %s" % 
                  # self.imagefilenames[0])
                  #try manual input
                  #code_string = raw_input("Enter code string: ")
                  #or flag and punt
                  #raise BallotException
                  self.need_to_pickle = True
                  self.br[0] = []

                  self.gethartdetails(self.im[0],self.regionlists[0])
                  self.br[0] = BallotSide(
                       self,0,
                       dpi=self.dpi)
                  #print self.br[0]
                  pdb.set_trace()
                  Ballot.front_dict[code_tuple] = self.br[0].toXML()
                  template_outfile = open("templates/"+code_string,"w")
                  template_outfile.write("\n".join(self.br[0].toXML()))#!!!
                  template_outfile.close()
                  if self.duplex:
                       self.br[1] = []
                       self.gethartdetails(self.im[1],self.regionlists[1])
                       self.br[1] = BallotSide(
                            self,1,
                            dpi=self.dpi)
                       Ballot.back_dict[code_tuple] = self.br[1].toXML()
                       template_outfile = open("backtemplates/"+code_string,"w")
                       template_outfile.write("\n".join(self.br[1].toXML()))#!!!
                       template_outfile.close()

                  for n in range(self.imagecount):
                       if (n==0):
                            self.precinct = "%07d%07d" % (
                                 self.codelist[0][0],self.codelist[0][1])
                            Ballot.precinct_dict[code_tuple] = self.precinct
             
             #pdb.set_trace()
        try:
            self.br[0] = BallotSideFromXML(
                 self.imagefilenames[0],
                 0,
#                 "\n".join(Ballot.front_dict[code_string]))
                 Ballot.front_dict[code_string])
            if self.duplex:
                 self.br[1] = BallotSideFromXML(
                      self.imagefilenames[1],
                      1,
#                      "\n".join(Ballot.back_dict[code_string]))
                      Ballot.back_dict[code_string])
            #self.br[1].name = self.imagefilenames[1]
            self.precinct = code_string#Ballot.precinct_dict[code_string]
        except:
            # EVERYTHING IN THIS EXCEPTION IS GETTING NEW LAYOUT

            # the landmarklist will be the x,y linediff1 and ydiff 
            # from getesstilt, where (x,y) are coordinates of the first box
            # of the ballots box column (front left or back right)
            # and linediff1 is the dx for ydiff dy
            # calculated by looking at the drift of the boxes in that column 

            #pdb.set_trace()
            ##const.logger.warning("New code string %s at image %s; rejecting" % (
            ##           code_string,
            ##           self.imagefilenames[0])
            ##            )
            # For yolo, rejecting because we have all valid templates
            # DON'T REJECT UNLESS YOU ALREADY HAVE ALL VALID TEMPLATES
            ##raise BallotException

            self.need_to_pickle = True
            self.br[0] = []

            self.gethartdetails(self.im[0],self.regionlists[0])
            self.br[0] = BallotSide(
                self,0,
                dpi=self.dpi)
            #print self.br[0]
            Ballot.front_dict[code_tuple] = self.br[0].toXML()
            template_outfile = open("templates/"+code_string,"w")
            template_outfile.write("\n".join(self.br[0].toXML()))#!!!
            template_outfile.close()
            if self.duplex:
                self.br[1] = []
                self.gethartdetails(self.im[1],self.regionlists[1])
                self.br[1] = BallotSide(
                    self,1,
                    dpi=self.dpi)
                Ballot.back_dict[code_tuple] = self.br[1].toXML()
                template_outfile = open("backtemplates/"+code_string,"w")
                template_outfile.write("\n".join(self.br[1].toXML()))#!!!
                template_outfile.close()

            for n in range(self.imagecount):
                if (n==0):
                    self.precinct = "%07d%07d" % (
                         self.codelist[0][0],self.codelist[0][1])
                    Ballot.precinct_dict[code_tuple] = self.precinct


def get_args():
     """Get command line arguments"""
     try:
          opts, args = getopt.getopt(sys.argv[1:],
                                     "tdrq",
                                     [ "templates",
                                       "debug",
                                       "retry-on-missing",
                                       "question-user"
                                       ]
                                     ) 
     except getopt.GetoptError:
          print "usage:"
          sys.exit(2)
     templates_only = False
     debug = False
     retry = False
     question = False
     for opt, arg in opts:
          if opt in ("-t", "--templates"):
               templates_only = True
          if opt in ("-d", "--debug"):
               debug = True
          if opt in ("-r", "--retry-on-missing"):
               retry = True
          if opt in ("-q", "--question-user"):
               question = True
               
     const.templates_only = templates_only
     const.debug = debug
     const.retry = retry
     const.question = question
     print "OPTS", opts
     print "ARGS", args

def get_config():
     config = ConfigParser.ConfigParser()
     config.read("tevs.cfg")

     # first, get log file name so log can be opened
     const.logfilename = config.get("Paths","logfilename")
     if const.debug:
          logging.basicConfig(filename=const.logfilename,level=logging.DEBUG)
     else:
          logging.basicConfig(filename=const.logfilename,level=logging.INFO)

     const.logger = logging.getConst.Logger("extraction")

     # then both log and print other config info for this run
     bwi = config.get("Sizes","ballot_width_inches")
     cti = config.get("Sizes","candidate_text_inches")
     bhi = config.get("Sizes","ballot_height_inches")
     owi = config.get("Sizes","oval_width_inches")
     ohi = config.get("Sizes","oval_height_inches")
     vit = config.get("Sizes","vote_intensity_threshold")
     const.ballot_width_inches = float(bwi)
     const.candidate_text_inches = float(cti)
     const.ballot_height_inches = float(bhi)
     const.oval_width_inches = float(owi)
     const.oval_height_inches = float(ohi)
     const.vote_intensity_threshold = float(vit)
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

     print "Log file", const.logfilename
     print "Ballot width in inches", const.ballot_width_inches
     print "Ballot height in inches", const.ballot_height_inches
     print "Voteop width in inches", const.oval_width_inches
     print "Voteop height in inches", const.oval_height_inches
     print "Format string for processed files:", const.procformatstring
     print "substituted with 123456", const.procformatstring % (
          123456/1000,123456)
     print "Format string for unprocessed, results, and masks files:"
     print const.unprocformatstring
     print const.unprocformatstring % (123456/1000,123456)
     print const.resultsformatstring
     print const.resultsformatstring % (123456/1000,123456)
     print const.masksformatstring
     print const.masksformatstring % (123456/1000,123456)
     const.logger.info( "Ballot width in inches %f"%const.ballot_width_inches)
     const.logger.info( "Ballot height in inches %f"%const.ballot_height_inches)
     const.logger.info( "Voteop width in inches %f"%const.oval_width_inches)
     const.logger.info( "Voteop height in inches %f"%const.oval_height_inches)
     const.logger.info( "Format string for processed files: %s" 
                  % const.procformatstring)
     const.logger.info( "substituted with 123456: %s" 
                  % (const.procformatstring % (123456/1000,123456)))
     const.logger.info( "Format strings for unprocessed, results, masks files:")
     const.logger.info( const.unprocformatstring)
     const.logger.info( const.unprocformatstring % (123456/1000,123456))
     const.logger.info( const.resultsformatstring)
     const.logger.info( const.resultsformatstring % (123456/1000,123456))
     const.logger.info( const.masksformatstring)
     const.logger.info( const.masksformatstring % (123456/1000,123456))
     print const.logger
     return const.logger

def initialize_from_templates():
     """Read layout info from templates directory."""
     try:
          # for each file in templates directory, 
          # add contents to fronts dictionary,
          # keyed by name; create None entry in backs dictionary
          for f in os.listdir("templates"):
               print "Reading",f
               ff = open("templates/"+f,"r")
               template_text = ff.read()
               Ballot.front_dict[f] = template_text
               Ballot.precinct_dict[f] = "1"
               try:
                    ff = open("backtemplates/"+f,"r")
                    template_text = ff.read()
                    Ballot.back_dict[f] = template_text
               except: 
                    pass
        
     except Exception, e:
          const.logger.info("Could not load existing template entries.")
          const.logger.debug(e)


def save_nextnum(n):
     """Save number in nexttoprocess.txt"""
     try:
          n = n+2
          hw = open("nexttoprocess.txt","w")
          hw.write("%d"%n)
          hw.close()
     except Exception, e:
          const.logger.debug("Could not write %d to nexttoprocess.txt %s\n" % 
                       (n,e))
     return n

def get_nextnum(numlist):
     if len(numlist)>0:
          n = numlist[0]
          numlist = numlist[1:]
     else:
          try:
               hw = open("nexttoprocess.txt","r")
               hwline = hw.readline()
               hw.close()
               n = atoi(hwline)
               const.logger.info("Processing %d"%n)
          except:
               const.logger.error( 
                    "Could not read nexttoprocess.txt, setting n to 1")
               n = 1
     return n

def handle_overvotes(bstr):
     """ Read the votes into a dictionary to mark overvotes."""
     outstr = ""
     try:
          cd = {}
          voutdict = {}
          for line in bstr.split("\n"):
               field = line.split(",")
               try:
                    if field[2] in voutdict:
                         voutdict[field[2]] = voutdict[field[2]]+line+"\n"
                    else:
                         voutdict[field[2]] = line+"\n"
                    # if you find 2 entries for field2 
                    # containing intensities at or below vote intensity thresh
                    # replace candidate with overvote+candidate
                    if int(field[7]) <= const.vote_intensity_threshold:
                         if field[2] in cd:
                              ovoutstr = ""
                              for line2 in voutdict[field[2]].split("\n"):
                                   line2fields = line2.split(",")
                                # handle blank lines
                                   try:
                                        line2fields[4] = ("vOVERVOTE"+
                                                          line2fields[4])
                                        ovoutstr += ",".join(line2fields)+"\n"
                                   except:
                                        pass
                              voutdict[field[2]] = ovoutstr
                         else:
                              cd[field[2]] = 1

               except Exception,e:
                    print "Problem checking for overvote."
                    print e
                    pdb.set_trace()
               # write notes to log file for potential ambiguous
               cvit = const.vote_intensity_threshold
               less5pct = int(round(cvit * .95))
               plus5pct = int(round(cvit * 1.05))
               if int(field[7])>less5pct and int(field[7])<=cvit:
                    const.logger.info("LIGHT")
                    const.logger.info(line)
               if int(field[7])>cvit and int(field[7])<plus5pct:
                    const.logger.info("VLIGHT")
                    const.logger.info(line)

          for key in voutdict:
               outstr += voutdict[key]

     except Exception, e:
          print "Problem scanning for light lines;", e
          const.logger.info("Problem scanning for light lines.")
          const.logger.info(e)
          pdb.set_trace()

     return outstr


if __name__ == "__main__":

     # get command line arguments
     get_args()

     # read configuration from tevs.cfg and set constants for this run
     const.logger = get_config()

     # try to initialize the front and back layout dictionaries 
     initialize_from_templates()

     # if there is a file named numlist.txt, 
     # use it for a list of numbers to process,
     # instead of using nexttoprocess.txt
     numlist = []
     try:
          numlistfile = open("numlist.txt","r")
          for numline in numlistfile.readlines():
               num = int(numline)
               numlist.append(num)
     except:
          pass

     # main process loop
     while(1):
          n = get_nextnum(numlist)
          const.logger.info("Creating ballot %d,%s: " % (
                    n,datetime.now().isoformat()))

          # generate filenames using the new image number(s)
          # create additional subdirectories as needed 
          # in proc, results, masks directories
          name1 = const.unprocformatstring % (n/1000,n)
          name2 = const.unprocformatstring % ((n+1)/1000,(n+1))
          procname1 = const.procformatstring % (n/1000,n)
          procname2 = const.procformatstring % ((n+1)/1000,(n+1))
          resultsfilename = const.resultsformatstring % (n/1000,n)
          masksfilename1 = const.masksformatstring % (n/1000,n)
          masksfilename2 = const.masksformatstring % ((n+1)/1000,(n+1))
          resultspath = os.path.split(resultsfilename)[0]
          maskspath = os.path.split(masksfilename1)[0]
          procpath = os.path.split(procname1)[0]
          procpath2 = os.path.split(procname2)[0]
          for item in (name1,
                       name2,
                       procname1,
                       procname2,
                       resultsfilename, 
                       masksfilename1,
                       masksfilename2):
               this_path = os.path.split(item)[0]
               if not os.path.exists(this_path):
                    try:
                         os.makedirs(this_path)
                    except Exception, e:
                         print "Could not create directory %s; %s" % (
                              this_path,e)
                         const.logger.error("Could not create directory %s; %s" % 
                                      (this_path,e))

          try:
               f = open(name1,"r")
          except Exception, e:
               const.logger.error("Could not open %s, %s" % (name1,e))
               if const.retry:
                    # place number back in queue, if queue exists
                    if len(numlist)>0:
                         numlist.insert(0,n)
                    sleep(5)
                    continue
               else:
                    break

          # create an appropriate ballot instance
          b = None
          try:
               if const.layout_brand == "Hart":
                    b = HartBallot(imagefilenames=[name1,name2])
               elif const.layout_brand == "Diebold":
                    b = DieboldBallot(imagefilenames=[name1,name2])
               else:
                    print "WARNING: ESS might not be changed "
                    print "to work with dictionary XML"
                    b = Ballot(imagefilenames=[name1,name2])
          except Exception, e:
               const.logger.error("Could not create ballot using names %s %s; %s" 
                            % (name1,name2,e))
               n = save_nextnum(n)
               continue

          try:
               b.register(n)
          except Exception, e:
               const.logger.error("Could not register ballot %s; %s" % (b,e))
               n = save_nextnum(n)
               continue
          # vote the ballot instance, generating results
          try:
               b.vote()
          except Exception, e:
               const.logger.error("Could not vote ballot %s; %s" % (b,e))
               n = save_nextnum(n)
               continue

          # write the results
          try:
               bstr = b.toString()
               #overvote and light line handling (move to Ballot toString)
               outstr = handle_overvotes(bstr)

               # open the results file and write the results
               resultsfile = open(resultsfilename,"w+")
               resultsfile.write(outstr.encode('utf-8'))
               resultsfile.close()

               # move the images from unproc to proc
               try:
                    os.rename(name1,procname1)
               except:
                    const.logger.error("Could not rename %s" % name1)
               try:
                    os.rename(name2,procname2)
               except:
                    const.logger.error("Could not rename %s" % name2)

               # need to pickle is set true only for ballots 
               # that generated new templates

               if b.need_to_pickle:
                    const.logger.info("PICKLING ballot for %s" % name1)
                    # prior to pickling, save a scaled down thickened version
                    # of the ballot images
                    scaledown = 2.
                    newsize1 = (int(round(b.im[0].size[0]/scaledown)),
                                int(round(b.im[0].size[1]/scaledown)))
                    scaled_image = b.im[0].resize(newsize1,
                                                  Image.BILINEAR).convert(
                         "L")
                    scaled_image.thicken().save(masksfilename1)
                    if b.duplex:
                         newsize2 = (int(round(b.im[1].size[0]/scaledown)),
                                     int(round(b.im[1].size[1]/scaledown)))
                         scaled_image = b.im[1].resize(newsize2,
                                                       Image.BILINEAR).convert(
                              "L")
                         scaled_image.thicken().save(masksfilename2)
                    b.do_pickle()
                
          except Exception, e:
               const.logger.debug("Unhandled exception %s in main loop, n=%d." % (
                         e,n)
                            )
          finally:
               # IMPORTANT TO GARBAGE COLLECT AS TEMPLATES ARE BUILT!
               gc.collect()
               # remove this if you don't want to increment
               # to the next file after encountering problem with a file.
               n = save_nextnum(n)
          continue

"""END"""
