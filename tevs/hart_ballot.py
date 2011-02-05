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
import Ballot
import const
import util
from ocr import ocr
from adjust import rotator

class HartBallot(Ballot.Ballot):
    """Class representing ballots from Hart Intersystems.

    Each Hart ballot has dark rectangles around voting areas,
    and voting areas are grouped in boxed contests.
    """

    brand = "Hart"
    transformer = rotator

    def __init__(self, im1, im2=None, flipped=False):
        im1 = self.Flip(im1)
        if im2 is not None:
            im2 = self.Flip(im2)
        super(HartBallot, self).__init__(im1, im2, flipped)
        self.dpi = const.ballot_dpi
        self.vote_box_images = {}

        #convert all our constants to locally correct values
        adj = lambda f: int(round(self.dpi * f))
        self.oval_size = (
            adj(const.oval_width_inches),
            adj(const.oval_height_inches)
        )
        self.oval_margin = adj(.03) #XXX length should be in config or metadata
        self.min_contest_height = adj(const.minimum_contest_height_inches)
        self.vote_target_horiz_inches = adj(const.vote_target_horiz_offset_inches)
        self.writein_xoff = adj(2.5) #XXX
        self.writein_yoff = adj(.6)

        self.pages = [Page(self.dpi, 0, 0, 0, im1)]
        if im2 is not None:
            self.pages.append(Page(self.dpi, 0, 0, 0, im2))


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
        ul = im.crop((int(0.4*const.ballot_dpi), #XXX magic number should be inconfig
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

        self.dpi = const.ballot_dpi
        self.dpi_y = self.dpi
           
        self.tiltinfo[0] = self.im1.gethartlandmarks(self.dpi,0)
        self.tiltinfo[1] = None
        try:
            self.tiltinfo[1] = self.im2.gethartlandmarks(self.dpi,0)
        except AttributeError:
            pass
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
            raise Ballot.BallotException("Dark upper left corner on %s, code %d" % (
                    self.im1.filename,1))
        testcrop = self.im1.crop((self.im1.size[0] - testwidth,
                                  0,
                                  self.im1.size[0] - 1,
                                  testheight))
        teststat = ImageStat.Stat(testcrop)
        if teststat.mean[0] < 16:
            raise Ballot.BallotallotException("Dark upper right corner on %s, code %d" % (
                    self.im1.filename,2))
        testcrop = self.im1.crop((self.im1.size[0] - testwidth,
                                  self.im1.size[1] - testheight,
                                  self.im1.size[0] - 1,
                                  self.im1.size[1] - 1))
        teststat = ImageStat.Stat(testcrop)
        if teststat.mean[0] < 16:
            raise Ballot.BallotException("Dark lower right corner on %s, code %d" % (
                    self.im1.filename,3))
        testcrop = self.im1.crop((0,
                                  self.im1.size[1] - testheight,
                                  testwidth,
                                  self.im1.size[1] - 1))
        teststat = ImageStat.Stat(testcrop)
        if teststat.mean[0] < 16:
            raise Ballot.BallotException("Dark lower left corner on %s, code %d" % (
                    self.im1.filename,4))

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
            self.tang[n] = float(shortdiff)/float(longdiff)
            if abs(self.tang[n])>const.allowed_tangent:
                raise Ballot.BallotException(("Bad tilt calculation on %s" % 
                             self.imagefilenames[n])
                + ("\nn%d tiltinfo[%d] = %s, short%d, long%d" % 
                     (n, n, self.tiltinfo[n], shortdiff, longdiff)
                     ))
            if abs(self.tang[n]) > const.allowed_tangent: 
                raise Ballot.BallotException("tangent %f exceeds %f" % (
                    self.tang[n], const.allowed_tangent))
        return self.tiltinfo
        

    def TestLayoutCode(self,code_string):
        """check code for obvious flaws"""
        if len(code_string) != 14:
            return False
        elif not (code_string.startswith("100") 
                  or code_string.startswith("200")):
            # disqualify if not a sheet 1 or a sheet 2
            return False
        elif code_string[7] != "0":
            # disqualify if eighth digit is not zero
            return False
        # ninth digit is side count, must be four or below
        # and everything should be decimal digits as well
        try:
            csi = int(code_string[8])
            remaining = int(code_string[8:])
        except IndexError:
            return False
        return csi <= 4

    def GetLayoutCode(self):
        """ Determine the layout code(s) from the ulc barcode(s) """
        self.layout_code = [0, 0]
        if self.duplex is False:
            toprange = 1
        else:
            toprange = 2
        # barcode zones to search are from 1/3" to 1/6" to left of ulc
        # and from 1/8" above ulc down to 2 5/8" below ulc.
        for n, im in enumerate((self.im1, self.im2)):
            if n>0 and not self.duplex:
                break
            # don't pass negative x,y into getbarcode
            if self.xref[n] < (self.dpi/3):
                raise Ballot.BallotException("bad xref")
            if self.yref[n] < (self.dpi/8):
                raise Ballot.BallotException("bad yref")
            if im is not None:
                bc_startx = self.xref[n] - (self.dpi/3)
                bc_starty = self.yref[n] - (self.dpi/8)
                bc_endx = self.dpi/6
                bc_endy = (3*self.dpi) - ((3*self.dpi)/8)
                self.layout_code[n] = im.getbarcode(
                    bc_startx, bc_starty, bc_endx, bc_endy)
        im = self.im1
 
        code_string = "".join(
        )

        # Note that the Ballot framework provides for 
        # calling registered functions
        # to test barcode validity;
        # we are not implementing that yet.

        # try validating the barcode number, first as read off barcode,
        # then, if failure to validate, try validating OCR'd version
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
                     Ballot.Ballot.front_dict[code_string])
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
                 raise Ballot.BallotException("bad bar code")

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
                Ballot.Ballot.front_dict[self.code_string])
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
                Ballot.Ballot.back_dict[self.code_string])
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

        front_xml = self.front_layout.XML(self.code_string)
        
        Ballot.Ballot.front_dict[self.code_string] = front_xml

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

        back_xml = self.back_layout.XML(self.code_string)
        Ballot.Ballot.back_dict[self.code_string] = back_xml
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
             if startx <= 0:
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
                endx = im.size[0] - dpi/2
            text = ocr(im,br,dpi,columnstart_list[x],endx,conf_hll[x])

    def CaptureVoteInfo(self):
        """CaptureVoteInfo just calls CaptureSideInfo for each side"""
        self.CaptureSideInfo(side="Front")
        self.CaptureSideInfo(side="Back")
        #replace this with:
        #for page in pages:
        #    self.captureSideInfo(page)

    def captureSideInfo(self, page):
        T = self.transformer(self.rot, page.template.xoff, page.template.yoff)
        scale = page.dpi / page.template.dpi #should be in rotator--which should just be in Page?

        results = []
        def append(contest, choice, x=-1, y=-1, stats=None, oval=None, writein=None, voted=None, ambiguous=None):
            results.append(Ballot.VoteData(
                filename     = page.filename,
                precinct     = page.template.precinct,
                contest      = contest,
                choice       = choice,
                coords       = (x, y),
                stats        = stats,
                is_writein   = writein,
                voted        = voted,
                ambiguous    = ambiguous,
                image        = oval,
            ))

        for contest in page.template.contests:
            if int(contest.h) - int(contest.y) < self.min_contest_height:
                for choice in contest.choices:
                     append(contest, choice) #mark all bad
                continue

            for choice in contest.choices:
                x, y, stats, crop, writein, voted, ambiguous = self.ExtractOval(
                    page, T, scale, choice
                )
                append(contest, choice, x, y, stats, crop, writein, voted, ambiguous)

        return results

    def ExtractOval(self, page, rotate, scale, choice):
        """Extract a single oval, or writein box, from the specified ballot"""
        x, y = choice.coords()
        iround = lambda x: int(round(x))

        #XXX BEGIN move into transformer
        xoff = page.xoff - iround(page.template.xoff*scale)
        yoff = page.yoff - iround(page.template.yoff*scale)

        x, y = rotate(xoff + x, yoff + y)
        x = iround(x * scale)
        y = iround(y * scale)
        #XXX end move into transformer (which should now just take a page obj)

        ow, oh = self.oval_size
        stats = Stats(im.cropstats( #XXX throwing a deprecation warning, mustfix, but looks good . . .
            page.dpi,
            self.vote_target_horiz_offset,
            x, y,
            ow, oh,
            1
        ))

        cropx = cs.adjusted.x
        cropy = cs.adjusted.y
        crop = im.crop((
            cropx - margin,
            cropy - margin,
            cropx + margin + ow, 
            cropy + margin + oh
        ))

        voted, ambiguous = self.IsVoted(crop, stats, choice)
        writein = False
        if voted:
           writein = self.IsWriteIn(crop, stats, choice)
        if writein:
            crop = im.crop(( #XXX choice of coordinates inconsistient with above?
                 cropx  - margin,
                 cropy  - margin,
                 cropx  + self.writein_xoff + margin,
                 cropyy + self.writein_yoff + margin
            ))

        return cropx, cropy, stats, crop, voted, writein, ambiguous

    def IsVoted(self, im, stats, choice): #should this be somewhere separate that's "plugged into" the Ballot object?
        """determine if a box is checked
        and if so whether it is ambiguous"""
        intensity_test = stats.mean_intensity() < const.vote_intensity_threshold
        darkness_test  = stats.mean_darkness()  > const.dark_pixel_threshold
        voted = intensity_test or darkness_test  
        ambiguous = intensity_test != darkness_test
        return voted, ambiguous

    def IsWriteIn(self, im, stats, choice):
        """determine if box is actually a write in"""
        d = choice.description.tolower().find
        if d("write") != -1 or d("vrit") != -1:
            return d("riter") == -1
        return False 

