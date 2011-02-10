# HartBallot.py implements the interface defined (well, suggested)
# in Ballot.py, in a Hart-specific way.
# The Trachtenberg Election Verification System (TEVS)
# is copyright 2009,2010 by Mitch Trachtenberg 
# and is licensed under the GNU General Public License version 2.
# (see LICENSE file for details.)

import os
import sys
import subprocess
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

    def __init__(self, images, extensions):
        super(HartBallot, self).__init__(images, extensions)
        #convert all our constants to locally correct values
        adj = lambda f: int(round(const.dpi * f))
        self.oval_size = (
            adj(const.oval_width_inches),
            adj(const.oval_height_inches)
        )
        self.oval_margin = adj(.03) #XXX length should be in config or metadata
        self.min_contest_height = adj(const.minimum_contest_height_inches)
        self.vote_target_horiz_inches = adj(const.vote_target_horiz_offset_inches)
        self.writein_xoff = adj(2.5) #XXX
        self.writein_yoff = adj(.6)
        self.allowed_corner_black = adj(const.allowed_corner_black_inches)

    def flip(self, im):
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

        adj = lambda x: int(round(x * const.ballot_dpi))
        mean = lambda i: ImageStat(i).mean[0]
        box = lambda a, b, c, d: \
            mean(im.crop(adj(a), adj(b), adj(c), adj(d)))

        uls = box(.4, .8, .6, 1.5)
        ul2s = box(.3, .8, .5, 1.5)        
        urs = mean(im.crop(
            im.size[0] - adj(0.6), adj(0.8),
            im.size[0] - adj(0.4), adj(1.5)
        ))
    
        bar_cutoff = 224
        if uls < bar_cutoff or ul2s < bar_cutoff:
            if urs < bar_cutoff:
                im.rotate(180)
        return im

    def find_landmarks(self, page): #make so it takes a page, rename find_landmarks
        """ retrieve landmarks for Hart images, set tang, xref, yref

        Landmarks for the Hart Ballot will be the ulc, urc, lrc, llc 
        (x,y) pairs marking the four corners of the main surrounding box."""

        #[(x,y),(x,y),(x,y),(x,y)] | None //from upper left hand corner, clockwise
        tiltinfo = self.im1.gethartlandmarks(const.dpi,0)
        if tiltinfo is None:
            raise Ballot.BallotException("Could not find landmarks")
        
        # flunk ballots with more than 
        # allowed_corner_black_inches of black in corner
        # to avoid dealing with severely skewed ballots

        errmsg = "Dark %s corner on %s"
        testlen = self.allowed_corner_black
        xs, ys = page.image.size

        ul = (0,             0,           
              testlen,       testlen)
 
        ur = (xs - testlen,  0,           
              xs - 1,        testlen)

        lr = (xs - testlen,  ys - testlen,
              xs - 1,        ys - 1)
 
        ll = (0,             ys - testlen,
              testlen,       ys - 1)

        for area, corner in ((ul, "upper left"),
                             (ur, "upper right"),
                             (lr, "lower right"),
                             (ll, "lower left")):
            if ImageStat(page.image.crop(area)).mean[0] < 16:
                raise Ballot.BallotException(errmsg % (corner, page.filename))

        xoff = self.tiltinfo[0][0]
        yoff = self.tiltinfo[0][1]

        # note that tiltinfo[3][0] is not set!!!
        shortdiff = self.tiltinfo[2][0] - self.tiltinfo[1][0]
        longdiff  = self.tiltinfo[2][1]  - self.tiltinfo[1][1]

        self.tiltinfo = [2, #XXX only keeping as reference, to be removed
                         self.xref,
                         self.yref,
                         longdiff,
                         shortdiff]

        rot = shortdiff/float(longdiff)
        if abs(rot) > const.allowed_tangent:
            raise Ballot.BallotException(
                "Tilt %f of %s exceeds %f" % (rot, page.filename, const.allowed_tanget)
            )

        return rot, xoff, yoff 

    def get_layout_code(self, page):
        """ Determine the layout code(s) from the ulc barcode(s) """
        # barcode zones to search are from 1/3" to 1/6" to left of ulc
        # and from 1/8" above ulc down to 2 5/8" below ulc.

        adj = lambda x: int(round(const.dpi/x))
        dpi3, dpi6, dpi8 = adj(3.), adj(6.), adj(8.)

        # don't pass negative x,y into getbarcode
        if page.xoff < dpi3:
            raise Ballot.BallotException("bad xref")
        if page.yoff < dpi8:
            raise Ballot.BallotException("bad yref")

        codestr = page.image.getbarcode(
            page.xoff - dpi3,
            page.yoff - dpi8,
            dpi6,
            3*const.dpi - int(round((3*const.dpi)/8.))
        )
        barcode = None
        if codestr is not None:
            barcode = "".join(("%07d" % el) for el in codestr if el > 0)

        if not good_barcode(barcode):
             # try getting bar code from ocr of region beneath
             madj = lambda x: int(round(x*const.dpi))
             zone = page.image.crop((
                       page.xoff - dpi3 - madj(.05),
                       page.yoff + madj(2.5),
                       page.xoff - adj(24),
                       page.yoff + madj(4.5)
             ))
             zone = zone.rotate(-90) #make it left to right
             barcode = self.extensions.ocr(zone)

             #remove OCR errors specific to text guranteed numeric
             for bad, good in (("\n", ""),  (" ", ""),  ("O", "0"), ("o", "0"),
                               ("l",  "1"), ("I", "1"), ("B", "8"), ("Z", "2"),
                               ("]",  "1"), ("[", "1"), (".", ""),  (",", "")):
                 barcode = barcode.replace(bad, good)

             if not good_barcode(barcode):
                 raise Ballot.BallotException("bad bar code")

        return barcode

    def extract_VOP(self, page, rotate, scale, choice):
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
        stats = Ballot.IStats(im.cropstats( #XXX throwing a deprecation warning, mustfix, but looks good . . .
            page.dpi,
            self.vote_target_horiz_offset, #XXX is this the only part that can't be pulled out of this specific ballot kind?!
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

        voted, ambiguous = self.extensions.IsVoted(crop, stats, choice)
        writein = False
        if voted:
           writein = self.extensions.IsWriteIn(crop, stats, choice)
        if writein:
            crop = im.crop((
                 cropx  - margin,
                 cropy  - margin,
                 cropx  + self.writein_xoff + margin,
                 cropyy + self.writein_yoff + margin
            ))

        return cropx, cropy, stats, crop, voted, writein, ambiguous

    def BuildFrontLayout(self): #merge next two into build_layout(page)
        self.regionlists = [[], []]
        self.need_to_pickle = True
        self.front_layout = []

        # for gethartdetails to operate properly, we need to 
        # cancel out rotation to get vertical and horizontal lines,
        # duplicate the original images so we can dispose of the
        # modified ones when we're done with them
        oldim1 = self.im1.copy()
        oldim1.filename = self.im1.filename
        oldim2 = None
        if self.im2 is not None:
            oldim2 = self.im2.copy()
            oldim2.filename = self.im2.filename

        rot_angle = self.tang[0] * 57.2957795 #180/pi
        self.tang[0] = 0.0
        self.tang[1] = 0.0
        # we also update our landmark and tilt information,
        # for the rotated image
        self.GetLandmarks()

        print "New layout bar code: ", self.code_string
        print "Running Tesseract Open Source OCR "
        print "to retrieve text for front and back of new layout."
        print "This may take up to a minute or two, depending on your system."

        self.gethartdetails(self.im1, self.regionlists[0]) #XXX should be factored out

        self.front_layout = BallotSide( #XXX change to page
            self,
            0,
            precinct=self.precinct,
            dpi=const.dpi)

        front_xml = self.front_layout.XML(self.code_string) #XXX deprecated
        
        Ballot.Ballot.front_dict[self.code_string] = front_xml #XXX depracated

        #XXX needs to be somewhere else
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
        self.im1, self.im2 = oldim1, oldim2
        self.GetLandmarks() #XXX cache old landmarks and restore, like we did with images
        return self.front_layout

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
        dpi = const.dpi
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
        conf_hll = [] #confirmed hll
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
             xss = im.gethartvoteboxes(startx, dpi/2, dpi) #column_start, half inch down, dpi
             vboxes.append([ [xs[1], "v"] for xs in xss])

        for x, hll in enumerate(conf_hll):
            hll.extend(vboxes[x])
            hll.sort()
            try:
                endx = columnstart_list[x+1]
            except:
                endx = im.size[0] - dpi/2
            ocr(im, br, dpi, columnstart_list[x], endx, hll, self.extensions)

def good_barcode(code_string):
    """check code for obvious flaws"""
    if code_string is None:
        return False
    if len(code_string) != 14:
        return False
    elif not (code_string.startswith("100") 
              or code_string.startswith("200")):
        # disqualify if not a sheet 1 or a sheet 2
        return False
    elif code_string[7] != "0":
        return False

    # ninth digit is side count, must be four or below
    # and everything should be decimal digits as well
    try:
        csi = int(code_string[8])
        _ = int(code_string[8:])
    except IndexError:
        return False
    return csi <= 4
