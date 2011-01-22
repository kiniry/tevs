# HartBallot.py implements the interface defined (well, suggested)
# in Ballot.py, in a Hart-specific way.
# The Trachtenberg Election Verification System (TEVS)
# is copyright 2009,2010 by Mitch Trachtenberg 
# and is licensed under the GNU General Public License version 2.
# (see LICENSE file for details.)

import os
import sys
import subprocess
import xml.dom.minidom
import time

from PILB import Image, ImageStat
from Ballot import Ballot, BallotException, BtRegion, VoteData
import const
import util
from ocr import ocr
from adjust import rotate_pt_by

class HartBallot(Ballot):
    """Class representing ballots from Hart Intersystems.

    Each Hart ballot has dark rectangles around voting areas,
    and voting areas are grouped in boxed contests.
    """

    def __init__(self, im1, im2=None, flipped=False):
        im1 = self.Flip(im1)
        if im2 is not None:
            im2 = self.Flip(im2)
        super(HartBallot, self).__init__(im1, im2, flipped)
        self.brand = "Hart"
        self.vote_box_images = {}

    def Flip(self, im):
        # crop the upper bar code possibilities,
        # UL and UR run from y = .8" to beyond 1.5"
        # (try relying on only first two)
        # U/LL from 1/3" to 2/3", U/LR 1/3" to 2/3" inch in from right
        # ballot is rightside up if the missing bar code
        # is the upper right, upside down if the missing
        # barcode is lower left.

        # if we get even a third of a bar code, 
        # it should darken crop by more than 1/8

        # Not added: ambiguous results could be tested with OCR

        cannot_be_barcode_above = 224
        ul = im.crop((int(0.4*const.ballot_dpi),
                  int(0.8*const.ballot_dpi),
                  int(0.6*const.ballot_dpi),
                  int(1.5*const.ballot_dpi)))
    
        ul2 = im.crop((int(0.3*const.ballot_dpi),
                  int(0.8*const.ballot_dpi),
                  int(0.5*const.ballot_dpi),
                  int(1.5*const.ballot_dpi)))
    
        ur = im.crop((int(im.size[0] - (0.6*const.ballot_dpi)),
                  int(0.8*const.ballot_dpi),
                  int(im.size[0] - (0.4*const.ballot_dpi)),
                  int(1.5*const.ballot_dpi)))
    
        uls = ImageStat.Stat(ul).mean[0]
        ul2s = ImageStat.Stat(ul2).mean[0]
        urs = ImageStat.Stat(ur).mean[0]
        if uls < cannot_be_barcode_above or ul2s < cannot_be_barcode_above:
            if urs > cannot_be_barcode_above:
                pass #return 1
            elif urs < cannot_be_barcode_above:
                im.rotate(180)
        return im

    def GetLandmarks(self):
        """ retrieve landmarks for Hart images, set tang, xref, yref

        Landmarks for the Hart Ballot will be the ulc, urc, lrc, llc 
        (x,y) pairs marking the four corners of the main surrounding box."""

        # zero'th entry for image 1, first for image 2
        self.tiltinfo = [0, 0]
        self.tang = [0, 0]
        self.xref = [0, 0]
        self.yref = [0, 0]

        # It turns out to be a mistake to set the dpi based on the
        # observed ballot size in pixels, because when the ballots
        # are skewed, the scanner may increase the output width.
        # We are forced to rely on the specified dpi in tevs.cfg,
        # or else punt.
        self.dpi = int(round( #XXX below code repeated in multiple places with different values, should be handled elsewhere
                self.im1.size[0]/const.ballot_width_inches))
        if self.dpi >= 148 and self.dpi <= 152:
            self.dpi = 150
        elif self.dpi >= 296 and self.dpi <= 304:
            self.dpi = 300
        else:
            const.logger.warning(
                "Image file %s has DPI %d from pixel width %d, forcing %d from tevs.cfg" %
                (
                    self.im1.filename,
                    self.dpi,
                    self.im1.size[0],
                    const.ballot_dpi
                    )
                )

        self.dpi = const.ballot_dpi
        self.dpi_y = self.dpi
        if self.im1.mode == 'L':
            fn = self.im1.filename
            self.im1 = self.im1.convert("RGB")
            self.im1.filename = fn
            
        self.tiltinfo[0] = self.im1.gethartlandmarks(self.dpi,0)
        try:
            if self.im2 is not None:
                fn = self.im2.filename
                self.im2 = self.im2.convert("RGB")
                self.im2.filename = fn
                self.tiltinfo[1] = self.im2.gethartlandmarks(self.dpi,0)
            else:
                self.tiltinfo[1] = None
        except:
            self.tiltinfo[1] = None
        # ballots are duplex only when
        # gethartlandmarks can find a tilt on both sides;
        # (ballots with a blank side are not duplex)
        if (self.tiltinfo[1] is None) or (self.tiltinfo[0] is None):
            self.duplex = False
        else:
            self.duplex = self.tiltinfo[1][1] == 0 and self.tiltinfo[1][2] == 0
        
        # flunk ballots with more than 
        # allowed_corner_black_inches of black in corner
        # to avoid dealing with severely skewed ballots

        testwidth = self.dpi * const.allowed_corner_black_inches
        testheight = testwidth
        testcrop = self.im1.crop( (0, 0, testwidth, testheight) )
        teststat = ImageStat.Stat(testcrop)
        if teststat.mean[0] < 16:
            const.logger.error("Dark upper left corner on %s, code %d" % (
                    self.im1.filename,1))
            raise BallotException("dark upper left corner")
        testcrop = self.im1.crop((self.im1.size[0] - testwidth,
                                  0,
                                  self.im1.size[0] - 1,
                                  testheight))
        teststat = ImageStat.Stat(testcrop)
        if teststat.mean[0] < 16:
            const.logger.error("Dark upper right` corner on %s, code %d" % (
                    self.im1.filename,2))
            raise BallotException("dark upper right corner")
        testcrop = self.im1.crop((self.im1.size[0] - testwidth,
                                  self.im1.size[1] - testheight,
                                  self.im1.size[0] - 1,
                                  self.im1.size[1] - 1))
        teststat = ImageStat.Stat(testcrop)
        if teststat.mean[0] < 16:
            const.logger.error("Dark lower right corner on %s, code %d" % (
                    self.im1.filename,3))
            raise BallotException("dark lower right corner") #XXX bad message, doesn't explain why this is an issue
        testcrop = self.im1.crop((0,
                                  self.im1.size[1] - testheight,
                                  testwidth,
                                  self.im1.size[1] - 1))
        teststat = ImageStat.Stat(testcrop)
        if teststat.mean[0] < 16:
            const.logger.error("Dark lower left corner on %s, code %d" % (
                    self.im1.filename,4))
            raise BallotException("dark lower left corner") #XXX see above

        if not self.duplex:
            toprange = 1
        else:
            toprange = 2

        for n in range(toprange):
            # tiltinfo is vestigial, get more understandable names
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
                if abs(self.tang[n])>const.allowed_tangent:
                    const.logger.error("Bad tilt calculation on %s" % 
                                 self.imagefilenames[n])
                    const.logger.error("n%d tiltinfo[%d] = %s, short%d, long%d" % 
                         (n, n, self.tiltinfo[n], shortdiff, longdiff)
                         )
                const.logger.debug("shortdiff %d longdiff %d tangent %f\n"%(
                        shortdiff, 
                        longdiff, 
                        self.tang[n])
                             )
                if abs(self.tang[n]) > const.allowed_tangent: 
                    raise BallotException("tangent %f exceeds %f" % (
                        self.tang[n], const.allowed_tangent))

            except Exception as e:
                print e
                const.logger.error(e)
                self.tang[n] = 0.
                raise

        # Switch front and back if necessary; 
        # unfortunately, this is probably site-dependent

        const.logger.debug("TANG %s XREF %s YREF %s " 
                           % (self.tang,self.xref,self.yref))

        return self.tiltinfo
        

    def TestLayoutCode(self,code_string):
        """check code for obvious flaws"""
        barcode_good = True
        if len(code_string) != 14:
            barcode_good = False
        elif not (code_string.startswith("100") 
                  or code_string.startswith("200")):
            # disqualify if not a sheet 1 or a sheet 2
            barcode_good = False
        elif code_string[7] != "0":
            # disqualify if eighth digit is not zero
            barcode_good = False
        if barcode_good:
            # ninth digit is side count, must be four or below
            # and everything should be decimal digits as well
            try:
                csi = int(code_string[8])
                remaining = int(code_string[8:])
                if csi > 4:
                    barcode_good = False
            except:
                barcode_good = False
        return barcode_good

    def GetLayoutCode(self):
        """ Determine the layout code(s) from the ulc barcode(s) """
        self.layout_code = [0, 0]
        if self.duplex is False:
            toprange = 1
        else:
            toprange = 2
        # barcode zones to search are from 1/3" to 1/6" to left of ulc
        # and from 1/8" above ulc down to 2 5/8" below ulc.
        n = 0
        for im in (self.im1, self.im2):
            if n>0 and not self.duplex:
                break
            # don't pass negative x,y into getbarcode
            if self.xref[n] < (self.dpi/3):
                raise BallotException("bad xref")
            if self.yref[n] < (self.dpi/8):
                raise BallotException("bad yref")
            if im is not None:
                bc_startx = self.xref[n] - (self.dpi/3)
                bc_starty = self.yref[n] - (self.dpi/8)
                bc_endx = self.dpi/6
                bc_endy = (3*self.dpi) - ((3*self.dpi)/8)
                self.layout_code[n] = im.getbarcode(
                    bc_startx, bc_starty, bc_endx, bc_endy)
            n = n+1
        im = self.im1
 
        code_string = "".join(
            ("%07d" % el) for el in self.layout_code[0] if el > 0
        )

        # Note that the Ballot framework provides for 
        # calling registered functions
        # to test barcode validity;
        # we are not implementing that yet.

        # try validating the barcode number, first as read off barcode,
        # then, if failure to validate, try validating OCR'd version
        barcode_good = True
        orig_code_string = code_string
        self.code_string = code_string
        barcode_good = self.TestLayoutCode(code_string)

        # barcodes starting with 1 should be duplex, warn if not
        if code_string.startswith("1") and not self.duplex:
            const.logger.warning("Sheet 1 but not duplex, check %s" % (self.im1.filename,))

        # If barcode passed validation,
        # we might be requiring that it match an already generated template.
        # See if it is already in the front dictionary;
        # if we should already have all ballot templates, the entry
        # should be present; if we are looking for new ballot templates,
        # the entry should NOT be present.
        
        # Stubbed for alternate behavior if rejecting new code_string
        if barcode_good: 
             try:
                 self.precinct = self.code_string
                 self.front_layout = BallotSideFromXML(
                     im.filename,
                     0,
                     Ballot.front_dict[code_string])
             except:
                 pass#barcode_good = False
             return self.layout_code

        # end Reminder Stub
        
        # If we did not find the entry and we need for the entry
        # to be present, we continue to search via OCR'ing the nearby
        # text version.
        # 

        self.code_string = code_string
        if barcode_good == False:
             const.logger.warning("Bad barcode %s at %s" % (
                       code_string, im.filename))
             # try getting bar code from ocr of region beneath
             # try opening a file in "templates" named with code_string
             # and retrieving the text to serve as an alternate source
             zone = im.crop((
                       self.xref[0]- int(self.dpi/3) - int(self.dpi*0.05),
                       self.yref[0] + int(2.5 * self.dpi)  ,
                       self.xref[0] - int(self.dpi/24),
                       self.yref[0] + int(4.5*self.dpi) ))
             zone = zone.rotate(-90)
             zone.save("/tmp/barcode.tif") #XXX really needs to be in one and only one place
             p = subprocess.Popen(["/usr/local/bin/tesseract", 
                                  "/tmp/barcode.tif", 
                                  "/tmp/barcode"],
                                 stdout = subprocess.PIPE,
                                 stderr = subprocess.PIPE
                                 )
             errstuff = p.stderr.read()
             outstuff = p.stdout.read()
             sts = os.waitpid(p.pid,0)[1]
             if not (errstuff.startswith(
                     "Tesseract Open Source OCR Engine") and len(errstuff) < 36):
                 const.logger.error(errstuff)

             barcode_text = util.readfrom("/tmp/barcode.txt")
             #XXX these corrections should also be in one and only one place
             barcode_text = barcode_text.replace("\n","").replace(" ","")
             barcode_text = barcode_text.replace("O","0").replace("o","0")
             barcode_text = barcode_text.replace("l","1")
             barcode_text = barcode_text.replace("I","1").replace("B","8")
             barcode_text = barcode_text.replace("Z","2").replace("U","0")
             barcode_text = barcode_text.replace("]","1").replace("[","1")
             barcode_text = barcode_text.replace(".","").replace(",","")
             barcode_good = True
             code_string = barcode_text
             barcode_good = self.TestLayoutCode(code_string)
             if barcode_good:
                 const.logger.warning(
                     "Barcode %s replaced with OCRd value %s for %s" % (
                         orig_code_string, code_string, im.filename))
                 print "WAS %s NOW %s" % (orig_code_string,code_string)
                 self.code_string = code_string
             else:
                 const.logger.error("Bad barcode %s, then %s for %s" % (
                         self.code_string, code_string, im.filename)
                                    )
                 raise BallotException("bad bar code")

        self.precinct = self.code_string
        return self.layout_code

    #About distinguishing front and back layouts.  
    #Hart ballots give a unique identifying code to each front and each back
    #but Diebold, at least, uses a common code for all backs.
    #So although it appears we can distinguish between all backs in Hart,
    #we'll still rely on the front layout code to grab the appropriate back.

    def GetFrontLayout(self):
        """ Retrieve front template from dict if present, or call Build func.

        If front layout is not in dictionary, generate it 
        from the current front image, and store it in file 
        and in dictionary.
        """
        try:
            self.front_layout = BallotSideFromXML(
                self.im1.filename,
                0,
                Ballot.front_dict[self.code_string])
            return self.front_layout
        except: #XXX what can BallotSideFromXML throw?
            print "On new layout: '%s'" % (const.on_new_layout,)
            if const.on_new_layout.startswith("reject"):
                return None #XXX should this raise instead?
            return self.BuildFrontLayout()



    def GetBackLayout(self):
        """ Retrieve back template from dict or call Build func.

        If back layout is not in dictionary, generate it 
        from the current back image, and store it in file 
        and in dictionary, keyed by FRONT.
        """
        try:
            self.back_layout = BallotSideFromXML(
                self.im2.filename,
                1,
                Ballot.back_dict[self.code_string])
            return self.back_layout
        except:
            return self.BuildBackLayout()


    def BuildFrontLayout(self):
        self.regionlists = [[], []]
        self.need_to_pickle = True
        self.front_layout = []

        # for gethartdetails to operate properly, we need to 
        # cancel out rotation to get vertical and horizontal lines
        rot_angle = self.tang[0] * 57.2957795 #180/pi
        filename = self.im1.filename
        self.im1 = self.im1.rotate(-rot_angle)
        self.im1 = self.im1.convert("RGB")
        self.im1.filename = filename
        if self.im2 is not None:
            filename = self.im2.filename
            self.im2 = self.im2.rotate(rot_angle)
            self.im2 = self.im2.convert("RGB")
            self.im2.filename = filename
        self.tang[0] = 0.0
        self.tang[1] = 0.0
        # we also update our landmark and tilt information,
        # for the rotated image
        self.GetLandmarks()

        print "New layout bar code: ", self.code_string
        print "Running Tesseract Open Source OCR "
        print "to retrieve text for front and back of new layout."
        print "This may take up to a minute or two, depending on your system."

        self.gethartdetails(self.im1, self.regionlists[0])

        self.front_layout = BallotSide(
            self,
            0,
            precinct=self.precinct,
            dpi=self.dpi)

        front_xml = self.front_layout.toXML(self.code_string)
        
        Ballot.front_dict[self.code_string] = front_xml

        # save each template, named by code_string, for future use
        template_filename = os.path.join(const.templates_path, self.code_string)
        util.writeto(template_filename, front_xml)
        const.logger.info("Created layout template %s at %s" % (template_filename, time.asctime()))
        # if you need to build the front layout, you need to build
        # the back layout as well

        self.BuildBackLayout()

        # if you've just built the layouts, you must reload
        # the original images, because you may have rotated your images
        # You must then retrieve the landmarks again.
        # If IsAHart returned 2, the images were flipped and the
        # ballot was created with flipped True.  If this is the case,
        # when we reopen the images, we need to flip them again.
        self.im1 = Image.open(self.im1.filename)
        if self.flipped:
            self.im1 = self.im1.rotate(180.)
            self.im1 = self.im1.convert("RGB")
        if self.im2 is not None:
            self.im2 = Image.open(self.im2.filename)
            if self.flipped:
                self.im2 = self.im2.rotate(180.)
                self.im2 = self.im2.convert("RGB")
        self.GetLandmarks()
        return self.front_layout

    def BuildBackLayout(self):
        try:
            self.regionlists[1] = []
        except:
            self.regionlists = [[], []]
        self.back_layout = []

        if not self.duplex:
            return None
        self.gethartdetails(self.im2, self.regionlists[1])
        self.back_layout = BallotSide(
            self,
            1,
            precinct=self.precinct,
            dpi=self.dpi)

        back_xml = self.back_layout.toXML(self.code_string)
        Ballot.back_dict[self.code_string] = back_xml
        template_filename = os.path.join(const.backtemplates_path, self.code_string)
        util.writeto(template_filename, back_xml)
        print "Length of self.regionlists[1]", len(self.regionlists[1])

        return self.back_layout

    # gethartdetails remains ugly and is a candidate for DO OVER.
    # it gets the column dividers, then finds
    # presumed horizontal lines across each column,
    # confirms them, calls gethartvoteboxes to determine
    # how the contests should be divided into bands for
    # contest description and vote boxes,
    # and calls ocr to analyze the bands. 
    # vop is short for vote op. conf_hll is confirmed horizontal line list
    def gethartdetails(self, im, br):
        """ get layout and ocr information """
        dpi = self.dpi
        vline_list = im.getcolumnvlines(0, im.size[1]/4, im.size[0]-20)
        const.logger.debug(str(vline_list))
        lastx = 0
        #For each hlinelist that is separated from the previous by 
        #a reasonable amount (more than dpi/4 pixels), we want to line up
        #the negative values from the new hlinelist with the positive values
        #from the old one
        hlinelistlist = []
        columnstart_list = []
        vop_list = []
        for x in vline_list:
            if (x - lastx) > (dpi/4):
                columnstart_list.append(x)
                pot_hlines = im.getpotentialhlines(x, 1, dpi)
                hlinelistlist.append(pot_hlines)
            lastx = x
        lastel2 = 0

        # an hline is confirmed by matching a positive hline in sublist n
        # against a negative hline in sublist n+1; if no sublist n+1, no hlines
        conf_hll = []
        for col in range(len(hlinelistlist)-1): #XXX simplify
            conf_hll.append([])
            for entrynum in range(len(hlinelistlist[col])):
                yval1 = hlinelistlist[col][entrynum]
                for entrynum2 in range(len(hlinelistlist[col+1])):
                    yval2 = hlinelistlist[col+1][entrynum2]
                    if (yval1 > 0) and (abs(yval1 + yval2) < (dpi/16)):
                        conf_hll[col].append(yval1)
                        break
        for i, el in enumerate(conf_hll):
            conf_hll[i] = [ [e, "h"] for e in el ]
        vboxes = []
        for startx in columnstart_list:
             if (startx <= 0):
                  const.logger.info(
                      "Negative startx passed to gethartvoteboxes")
             xss = im.gethartvoteboxes(startx, dpi/2, dpi)
             vboxes.append([ [xs[1], "v"] for xs in xss])


        for x in range(len(conf_hll)):
            conf_hll[x].extend(vboxes[x])
            conf_hll[x].sort()
            # now pass conf_hll[x] and the corresponding column start and end
            # into a function which will do OCR on vote and above-vote 
            # subregions
            endx = 0
            try:
                endx = columnstart_list[x+1]
            except:
                endx = im.size[0] - (dpi/2)
            text = ocr(im,br,dpi,columnstart_list[x],endx,conf_hll[x])

    def CaptureVoteInfo(self):
        """CaptureVoteInfo just calls CaptureSideInfo for each side"""
        self.CaptureSideInfo(side="Front")
        if self.duplex:
            self.CaptureSideInfo(side="Back")


    def CaptureSideInfo(self, side):
        """CaptureVoteInfo captures votes off the images in a HartBallot
        
        Each HartBallot instance has one or two images representing the
        sides of the ballot, and points to one or two "BallotSide" 
        template instances, representing the layout of votes on images
        representing ballots of the target ballot's precinct.

        CaptureVoteInfo goes through the templates item by item and
        examines the equivalent regions of the ballot instance to
        determine which vote opportunities have been marked by the voter.
        """
        #first, the front
        sidenum = 0
        if side == "Front":
            layout = self.front_layout
            im = self.im1
            sidenum = 0
        else:
            layout = self.back_layout
            im = self.im2
            sidenum = 1

        # For saving vote box images, create directory per file
        print "CaptureSideInfo", side
        if im is None:
            return None
        seq = 0
        margin = int(round(self.dpi * 0.03))
        boxes_filename = im.filename
        try: #XXX everything here is suspect
            if im.filename.startswith("/"):
                boxes_filename = im.filename[1:]
            if im.filename.startswith("./"):
                boxes_filename = im.filename[2:]                
            util.mkdirp(const.boxes_root, boxes_filename)
        except:
            pass
        region_valid = True
        for region in layout.regionlist:
            if region.purpose == BtRegion.JURISDICTION:
                self.current_jurisdiction = region.text

            elif region.purpose == BtRegion.CONTEST:
                self.current_contest = region.text

                # if the current_contest is less than 
                # const.minimum_contest_height_inches,
                # set contest invalid and skip votes;
                # else set contest valid
                if (int(region.bbox[3]) - int(region.bbox[1])) < (const.minimum_contest_height_inches * self.dpi):
                    region_valid = False
                else:
                    region_valid = True
                if self.current_contest.find("Count")>=0:
                    self.current_jurisdiction = self.current_contest
                if self.current_contest.find("State")>=0:
                    self.current_jurisdiction = self.current_contest
                if self.current_contest.find("School")>=0:
                    self.current_jurisdiction = self.current_contest
                if self.current_contest.find("Meas")>=0:
                    self.current_prop = self.current_contest[:40]
                else:
                    self.current_prop = None

            elif region.purpose == BtRegion.CHOICE:
                self.current_choice = region.text

            elif region.purpose == BtRegion.PROP:
                self.current_contest = region.text
                self.current_prop = "(Prop)"
                
            else:
                # skip over items in a contest that's not valid
                # because it is too short 
                # (settable via minimum_contest_height_inches in tevs.cfg)
                if not region_valid:
                    continue
                # anything else is a vote op, with the y offset stored
                # in place of the purpose
                self.current_oval = region.text
                self.current_coords = region.coord
                scalefactor = float(self.dpi)/float(layout.dpi)
                xoffset = self.xref[sidenum] - (layout.xref*scalefactor)
                yoffset = self.yref[sidenum] - (layout.yref*scalefactor)

                # the ballot region's dpi will typically be 300,
                # while individual ballots will typically have 150
                scalefactor = float(self.dpi)/float(layout.dpi)
                # adjust oval location given in template 
                # for tilt and offset of this ballot
                startx = int(self.current_coords[0])
                starty = int(self.current_coords[1])
                startx = startx + int(round(xoffset))
                starty = starty + int(round(yoffset))
                startx, starty = rotate_pt_by(startx,starty,self.tang[sidenum],
                                              self.xref[sidenum],
                                              self.yref[sidenum])
                # add in end points for oval
                startx = int(round(startx * scalefactor))
                starty = int(round(starty * scalefactor))
                ow = int(round(const.oval_width_inches * self.dpi ))
                oh = int(round(const.oval_height_inches * self.dpi)) 
                endx = startx + ow
                endy = starty + oh
                cs = im.cropstats( #XXX throwing a deprecation warning, mustfix
                    self.dpi,
                    int(round(const.vote_target_horiz_offset_inches * self.dpi)),
                    int(round(startx)),
                    int(round(starty)),
                    int(round(ow)),
                    int(round(oh)),
                    1)
                if const.save_vops:
                    cropx = int(round(cs[-3]))
                    cropy = int(round(cs[-2]))
                    cropendx = cropx + ow
                    cropendy = cropy + oh
                    # the statistics have been gathered before the photo 
                    # is taken; let's give the photo some margins
                    crop = im.crop((int(round(cropx))- margin,
                                    int(round(cropy))- margin,
                                    int(round(cropendx))+ margin,
                                    int(round(cropendy))+ margin
                                    ))
                    redintensity = cs[0]
                    greenintensity = cs[5]
                    blueintensity = cs[10]
                    self.vote_box_images[(side,cropx,cropy)] = crop
                    seq += 1
                maxv = 1
                try:
                    #maxv = get_maxv_from_text(self.current_contest)
                    self.current_contest = self.current_contest[:40]
                except:
                    pass
                if self.current_prop is None:
                    self.current_prop = "No"
                vd = VoteData(filename = im.filename,
                              precinct = layout.precinct,
                              jurisdiction = self.current_jurisdiction[:40],
                              contest = self.current_contest[:40],
                              choice = self.current_choice[:40],
                              prop = self.current_prop[:40],
                              oval = self.current_oval,
                              coords = [startx, starty],
                              stats = cs,
                              maxv = maxv)
                self.results.append(vd)

                if vd.suspicious and not vd.was_voted:
                    const.logger.warning("Suspicious mark in nonvoted box %s %s %s\n" % (self.current_contest[:40],self.current_oval[:40],im.filename))

                # deal with write-ins; this should be refactored out
                if vd.was_voted and (self.current_oval.find("Write")>-1 
                                   or self.current_oval.find("vrit")>-1 
                                   or self.current_oval.find("Vrit")>-1):
                   # crop the coords for three inches of horizontal
                   # and three times the oval height
                   if self.current_oval.find("riter") <= -1:
                        wincrop = im.crop(
                             (startx,
                              starty,
                              startx+int(2.5*self.dpi),
                              starty+int(0.6*self.dpi)
                              )
                             )
                        if not os.path.exists(const.writeins): #XXX need to refactor out mkdir -p into a utility func (in tev_normal)
                            util.mkdirp(const.writeins)
 
                        savename = "writeins/%s_%s.jpg" % ( #XXX path not from config, cannot assume positions are constant
                            im.filename[-10:-4].replace("/","").replace(" ","_"),
                            self.current_contest[:20].replace(
                                "/","").replace(" ","_")
                            )
                        wincrop.save(savename)
                        const.logger.info("Writein saved %s\n",savename)

    def WriteVoteInfo(self):
        return "\n".join(vd.toString() for vd in self.results) + "\n"

class BallotSide(object):
    """Representing a ballot side as a list of meaningful regions,
    plus sufficient information about the current ballot to scale,
    offset, and rotate information from the template regions."""

    def __init__(self, ballot, side, precinct="?",
                 dpi=150 
                 ):
        self.ballot = ballot
        self.side = side
        self.dpi = dpi
        self.precinct = self.ballot.precinct
        self.regionlists = [[], []]
        if side == 0:
            self.name = self.ballot.im1.filename
        else:
            self.name = self.ballot.im2.filename
        self.xref = self.ballot.xref[self.side]
        self.yref = self.ballot.yref[self.side]
        self.tang = self.ballot.tang[self.side]
        self.regionlist = self.ballot.regionlists[self.side]
        self.codelist = [None, None]
        self.columnlist = [None, None]
        self.br = [None, None]
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
        return "BallotSide %s regionlist length %s  tangent %f, precinct %s" % (
            self.name,
            len(self.regionlist),
            self.tang, 
            self.precinct)

    def append(self,region):
        if type(region) != BtRegion:
            raise TypeError(type(region) + " is not BtRegion")
        # don't append regions with (0,0) location, they're artifacts
        if (region.coord[0] != 0) and (region.coord[1] != 0):
            self.regionlist.append(region)


    def toXML(self, precinct="?"):
        contestlist = []
        if precinct == "?":
            precinct = self.precinct
        retlist = ["<BallotSide",
                   "dpi='%d' precinct='%s' lx='%d' ly='%d' rot='%f'>" % (
                  self.dpi,
                  precinct,
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
                                  region.bbox[0], region.bbox[1],
                                  region.bbox[2], region.bbox[3],
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
                               % region.text.replace("'", ""))
                
                self.current_contest = region.text
                # open new
                self.current_prop = "(Prop)"
                
            else:
                # anything above 3 is an oval, with the y offset stored
                # in place of the purpose
                self.current_oval = region.text
                contest_ovalcount += 1
                self.current_coords = region.coord
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
        return "\n".join(retlist)



class BallotSideFromXML(BallotSide):
    """BallotSide created from an xml string"""


    def toXML(self,precinct="?"):
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
        except Exception as e:
            const.logger.error("problem parsing")
            const.logger.error(e)
            for line in myxml.split("\n"):
                const.logger.error(line)
            print e
        self.regionlist = []
        bs = doc.getElementsByTagName("BallotSide")
        self.dpi = bs[0].getAttribute('dpi')
        self.dpi = int(self.dpi)
        self.precinct = bs[0].getAttribute('precinct')
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

        self.im = None
        contest_x = contest.getAttribute('x')
        self.xref = int(bs[0].getAttribute('lx')) #from the xml
        self.yref = int(bs[0].getAttribute('ly')) #from the xml
        self.tang = float(bs[0].getAttribute('rot')) #from the xml
        self.codelist = [None, None]
        self.columnlist = [None, None]
        self.br = [None, None]
        self.current_jurisdiction = "No info"
        self.current_contest = "No info"
        self.current_choice = "No info"
        self.current_prop = "No info"
        self.current_oval = "No info"
        self.current_coords = "No info"
        self.oval_width = const.oval_width_inches * self.dpi
        self.oval_height = const.oval_height_inches * self.dpi
        self.results = []

