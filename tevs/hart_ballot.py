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
from ocr import ocr

from cropstats import cropstats

class HartBallot(Ballot.Ballot):
    """Class representing ballots from Hart Intersystems.

    Each Hart ballot has dark rectangles around voting areas,
    and voting areas are grouped in boxed contests.
    """

    brand = "Hart"

    def __init__(self, images, extensions):
        #convert all our constants to locally correct values
        adj = lambda f: int(round(const.dpi * f))
        self.oval_size = (
            adj(const.oval_width_inches),
            adj(const.oval_height_inches)
        )
        self.oval_margin = adj(.03) #XXX length should be in config or metadata
        self.min_contest_height = adj(const.minimum_contest_height_inches)
        self.vote_target_horiz_offset = adj(const.vote_target_horiz_offset_inches)
        self.writein_xoff = adj(2.5) #XXX
        self.writein_yoff = adj(.6)
        self.allowed_corner_black = adj(const.allowed_corner_black_inches)
        super(HartBallot, self).__init__(images, extensions)

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
        mean = lambda i: ImageStat.Stat(i).mean[0]
        box = lambda a, b, c, d: \
            mean(im.crop((adj(a), adj(b), adj(c), adj(d))))

        uls = box(.4, .8, .6, 1.5)
        ul2s = box(.3, .8, .5, 1.5)        
        urs = mean(im.crop((
            im.size[0] - adj(0.6), adj(0.8),
            im.size[0] - adj(0.4), adj(1.5)
        )))
    
        bar_cutoff = 224 #XXX should be in config
        if uls < bar_cutoff or ul2s < bar_cutoff:
            if urs < bar_cutoff:
                im = im.rotate(180)
        return im

    def find_landmarks(self, page):
        """ retrieve landmarks for Hart images, set tang, xref, yref

        Landmarks for the Hart Ballot will be the ulc, urc, lrc, llc 
        (x,y) pairs marking the four corners of the main surrounding box."""

        #tiltinfo, from upperleft clockwise:
        #[(x,y),(x,y),(x,y),(x,y)] or None
        tiltinfo = page.image.gethartlandmarks(const.dpi, 0)
        if tiltinfo is None:
            page.blank = True #needs to ensure it is a page somehow
            return 0.0, 0, 0
        
        # flunk ballots with more than 
        # allowed_corner_black_inches of black in corner
        # to avoid dealing with severely skewed ballots

        errmsg = "Dark %s corner on %s"
        testlen = self.allowed_corner_black
        xs, ys = page.image.size

        #boxes to test
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
            if ImageStat.Stat(page.image.crop(area)).mean[0] < 16:
                raise Ballot.BallotException(errmsg % (corner, page.filename))

        xoff = tiltinfo[0][0]
        yoff = tiltinfo[0][1]

        # note that tiltinfo[3][0] is not set!!!
        shortdiff = tiltinfo[2][0] - tiltinfo[1][0]
        longdiff  = tiltinfo[2][1] - tiltinfo[1][1]

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
             barcode = self.extensions.ocr_engine(zone)

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
        margin = iround(.03 * const.dpi) #XXX should be in config file? class attr?

        #XXX BEGIN move into transformer
        xoff = page.xoff - iround(page.template.xoff*scale)
        yoff = page.yoff - iround(page.template.yoff*scale)

        x, y = rotate(xoff + x, yoff + y)
        x = iround(x * scale)
        y = iround(y * scale)
        #XXX end move into transformer (which should now just take a page obj)

        ow, oh = self.oval_size
        #begin pilb cropstats
        stats = Ballot.IStats(page.image.cropstats(
            const.dpi,
            self.vote_target_horiz_offset, #XXX is this the only part that can't be pulled out of this specific ballot kind?!
            x, y,
            ow, oh,
            1
        ))

        #can be in separate func?
        cropx = stats.adjusted.x
        cropy = stats.adjusted.y
        crop = page.image.crop((
            cropx - margin,
            cropy - margin,
            cropx + margin + ow, 
            cropy + margin + oh
        ))
        #end pilb cropstats


        # Below is using the pure python cropstats:
        #cropx, cropy = x, y #not adjusted like in PILB cropstats
        #crop = page.image.crop((
        #    cropx - margin,
        #    cropy - margin,
        #    cropx + margin + ow,
        #    cropy + margin + oh
        #))
        #stats = Ballot.IStats(cropstats(crop, x, y))
        # end pure python cropstats


        #XXX writeins always voted?!
        voted, ambiguous = self.extensions.IsVoted(crop, stats, choice)
        writein = self.extensions.IsWriteIn(crop, stats, choice)
        if writein:
            crop = page.image.crop((
                 cropx - margin,
                 cropy - margin,
                 cropx - margin + self.writein_xoff,
                 cropy - margin + self.writein_yoff
            ))

        return cropx, cropy, stats, crop, voted, writein, ambiguous

    # gethartdetails remains ugly and is the candidate for DO OVER.
    # it gets the column dividers, then finds
    # presumed horizontal lines across each column,
    # confirms them, calls gethartvoteboxes to determine
    # how the contests should be divided into bands for
    # contest description and vote boxes,
    # and calls ocr to analyze the bands. 
    # vop is short for vote op. hlines is confirmed horizontal line list
    def build_layout(self, page):
        """ get layout and ocr information """
        dpi = const.dpi
        dpi2, dpi4, dpi16 = dpi/2, dpi/4, dpi/16
        xend, yend = page.image.size[0], page.image.size[1]
        vlines = page.image.getcolumnvlines(0, yend/4, xend-20)

        #For each hlinelist that is separated from the previous by 
        #a reasonable amount (more than dpi/4 pixels), we want to line up
        #the negative values from the new hlinelist with the positive values
        #from the old one
        hlinelists = []
        columnstarts = []
        lastx = 0
        for vline in vlines:
            if vline - lastx > dpi4:
                columnstarts.append(vline)
                pot_hlines = page.image.getpotentialhlines(vline, 1, dpi)
                hlinelists.append(pot_hlines)
            lastx = vline

        # an hline is confirmed by matching a positive hline in sublist n
        # against a negative hline in sublist n+1; if no sublist n+1, no hlines
        hlines = [] #confirmed hll
        for col in range(len(hlinelists)-1): #XXX simplify
            hlines.append([])
            for entrynum in range(len(hlinelists[col])):
                yval1 = hlinelists[col][entrynum]
                for entrynum2 in range(len(hlinelists[col+1])):
                    yval2 = hlinelists[col+1][entrynum2]
                    if yval1 > 0 and abs(yval1 + yval2) < dpi16:
                        hlines[col].append(yval1)
                        break

        for i, el in enumerate(hlines):
            hlines[i] = [ [e, "h"] for e in el ]

        vboxes = []
        for startx in columnstarts:
             if startx <= 0:
                  self.log.info("Negative startx passed to gethartvoteboxes")
             xss = page.image.gethartvoteboxes(startx, dpi2, dpi) #column_start, half inch down, dpi
             vboxes.append([ [xs[1], "v"] for xs in xss])

        br = []
        for x, hll in enumerate(hlines):
            hll.extend(vboxes[x])
            hll.sort()
            try:
                endx = columnstarts[x+1]
            except IndexError:
                endx = xend - dpi2
            ocr(page.image, br, dpi, columnstarts[x], endx, hll, self.extensions)
        return br

def ocr(im, contests, dpi, x1, x2, splits, xtnz):
    """ ocr runs ocr and assembles appends to the list of BtRegions"""
    box_type = ""
    nexty = None
    cand_horiz_off = int(round(
        const.candidate_text_horiz_offset_inches*dpi
    ))
    vote_target_off = int(round(
        const.vote_target_horiz_offset_inches*dpi
    ))
    dpi16 = dpi/16
    dpi40 = dpi/40
    dpi_02 = int(round(dpi*0.02))
    invalid = lambda region: region[3] <= region[1]

    for n, split in enumerate(splits[:-1]):
        # for votes, we need to step past the vote area
        oval = False
        if split[1] == "v":
            startx = x1 + cand_horiz_off
            oval = True
        else:
            # while for other text, we just step past the border line
            startx = x1 + dpi40
            for y, dir in splits[n+1:]:
                if dir == 'h':
                    nexty = y
                    break

        croplist = (startx+1, split[0]+1, x2-2, splits[n+1][0]-2)
        if invalid(croplist):
            continue #XXX is this an error from somewhere?
        crop = im.crop(croplist)
        gaps = crop.gethgaps((128, 1))

        # we now need to split line by line at the gaps:
        # first, discard the first gap if it starts from 0
        if len(gaps) > 0 and gaps[0][1] == 0:
            gaps = gaps[1:]

        zone = crop

        # then, take from the start to the first gap start
        if len(gaps) != 0:
            zcroplist = (0, 0, crop.size[0]-1, gaps[0][1])
            if invalid(zcroplist):
                continue
            zone = crop.crop(zcroplist)

        text = xtnz.ocr_engine(zone)

        # then, take from the first gap end to the next gap start
        for m, gap in enumerate(gaps):
            end_of_this_gap = gap[3] - 2
            try:
                start_of_next_gap = gaps[m+1][1]
            except IndexError:
                start_of_next_gap = crop.size[1] - 2
            zone_croplist = (0,
                             end_of_this_gap,
                             crop.size[0]-1,
                             start_of_next_gap)
            if start_of_next_gap - end_of_this_gap < dpi16:
                continue #XXX is this not an error?
            zone = crop.crop(zone_croplist)
            text += xtnz.ocr_engine(zone)

        text = xtnz.ocr_cleaner(text)

        x, y, w = croplist[:3]
        if oval:
            # vote boxes begin 1/10" in from edge of contest box
            C = Ballot.Choice(
                x1 + vote_target_off,
                croplist[1] - dpi_02,
                #TODO add lower right point, remove text
                text
            )
            contests[-1].append(C)
        else:
            contests.append(Ballot.Contest(x, y, w, nexty, None, text))

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
    except ValueError:
        return False
    return csi <= 4
