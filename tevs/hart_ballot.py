# HartBallot.py implements the interface defined (well, suggested)
# in Ballot.py, in a Hart-specific way.
# The Trachtenberg Election Verification System (TEVS)
# is copyright 2009,2010 by Mitch Trachtenberg 
# and is licensed under the GNU General Public License version 2.
# (see LICENSE file for details.)

import os
import pdb
import sys
import subprocess
import time
import math

import site; site.addsitedir(os.path.expanduser("~/tevs")) #XXX
import Image, ImageStat
from line_util import *
from hart_util import *
from hart_build_contests import *
from hart_barcode import *
import Ballot
import const

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
        TOP=True
        BOT=False
        LEFT=True
        RIGHT=False
        #tiltinfo, from upperleft clockwise:
        #[(x,y),(x,y),(x,y),(x,y)] or None
        tiltinfo = []
        hline = scan_strips_for_horiz_line_y(page.image, 
                                             const.dpi, 
                                             2*const.dpi, 
                                             const.dpi/2, const.dpi/2,
                                             TOP)
        tiltinfo.append(follow_hline_to_corner(page.image, 
                                               const.dpi, 
                                               2*const.dpi, 
                                               hline, LEFT))
        hline = scan_strips_for_horiz_line_y(page.image, 
                                             const.dpi, 
                                             6*const.dpi, 
                                             const.dpi/2, const.dpi/2, 
                                             TOP)
        tiltinfo.append(follow_hline_to_corner(page.image, 
                                               const.dpi, 
                                               6*const.dpi,
                                               hline, RIGHT))
        hline=scan_strips_for_horiz_line_y(page.image, 
                                           const.dpi, 
                                           6*const.dpi, 
                                           const.dpi/2, const.dpi/2, 
                                           BOT)
        tiltinfo.append(follow_hline_to_corner(page.image, 
                                               const.dpi, 
                                               6*const.dpi,
                                               hline, RIGHT))
        hline=scan_strips_for_horiz_line_y(page.image, 
                                           const.dpi, 
                                           2*const.dpi, 
                                           const.dpi/2, const.dpi/2, 
                                           BOT)
        tiltinfo.append(follow_hline_to_corner(page.image, 
                                               const.dpi, 
                                               2*const.dpi,
                                               hline, LEFT))
        # removing PILB call
        #tiltinfo = page.image.gethartlandmarks(const.dpi, 0)
        if tiltinfo is None or tiltinfo[0][0] == 0 or tiltinfo[1][0] == 0:
            page.blank = True #needs to ensure it is a page somehow
            return 0.0, 0, 0, 0
        
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

        shortdiff = tiltinfo[3][0] - tiltinfo[0][0]
        longdiff  = tiltinfo[3][1] - tiltinfo[0][1]
        hypot = math.sqrt(shortdiff*shortdiff + longdiff*longdiff)
        if longdiff != 0:
            rot = shortdiff/float(longdiff)
        else:
            rot = 0
        if abs(rot) > const.allowed_tangent:
            raise Ballot.BallotException(
                "Tilt %f of %s exceeds %f" % (rot, page.filename, const.allowed_tangent)
            )
        page.tiltinfo = tiltinfo
        return rot, xoff, yoff, hypot

    def get_layout_code(self, page):
        """ Determine the layout code(s) from the ulc barcode(s) """
        # barcode zones to search are from 1/3" to 1/6" to left of ulc
        # and from 1/8" above ulc down to 2 5/8" below ulc.

        adj = lambda x: int(round(const.dpi*x))
        third_inch, sixth_inch, eighth_inch = adj(.3333), adj(.1667), adj(.125)

        # don't pass negative x,y into getbarcode
        if page.xoff < third_inch:
            raise Ballot.BallotException("bad xref")
        if page.yoff < eighth_inch:
            raise Ballot.BallotException("bad yref")
        # pass image, x,y,w,h
        barcode = hart_barcode(page.image,
            page.xoff - third_inch,
            page.yoff - eighth_inch,
            sixth_inch,
            eighth_inch + int(round((7.*const.dpi)/3.)) # bar code 2 1/3"
        )

        if not good_barcode(barcode):
             # try getting bar code from ocr of region beneath
             zone = page.image.crop((
                       page.xoff - third_inch - adj(.05),
                       page.yoff + adj(2.5),
                       page.xoff - adj(.04),
                       page.yoff + adj(4.5)
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

    def build_layout(self, page):
        """ get layout and ocr information """
        image = page.image
        dpi = const.dpi
        first_line = page.tiltinfo[0][0]
        last_line =  page.tiltinfo[1][0]
        width = last_line - first_line
        first_third = first_line + width/3
        second_third = first_line + (2*width)/3
        print "Warning: assuming three columns"
        print first_line,first_third,second_third,last_line
        vlines = [first_line,first_third,second_third,last_line]
        column_width = width/3
        vthop = int(round(const.vote_target_horiz_offset_inches * const.dpi))
        contests = []
        for vline in vlines:
            croplist = (vline,0,vline+column_width,image.size[1])
            crop = image.crop(croplist)
            pot_hlines = find_all_horiz_lines(crop,dpi)
            # normally, pull the .07 from config.vote_box_horiz_offset_inches
            vboxes = gethartvoteboxes(image,vline+vthop,dpi/2,dpi)
            column_contests = hart_build_contests(page.image,
                                                  pot_hlines,
                                                  vboxes,
                                                  vline,
                                                  column_width,
                                                  dpi)
            contests.extend(column_contests)
        for contest in contests:
            self.log.debug("%d,%d, %s" % (contest.x,contest.y,contest.description))
            #print contest.x, contest.y, contest.description
            for choice in contest.choices:
                self.log.debug(" %d,%d, %s" % (choice.x,choice.y,choice.description))
                #print " ", choice.x, choice.y, choice.description


        return contests


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
