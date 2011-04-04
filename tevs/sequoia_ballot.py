# sequoia_ballot.py implements the interface 
# in Ballot.py, as a guide to those extending TEVS to new ballot types.
# The Trachtenberg Election Verification System (TEVS)
# is copyright 2009, 2010 by Mitch Trachtenberg 
# and is licensed under the GNU General Public License version 2.
# (see LICENSE file for details.)

import Ballot
import const
from adjust import rotator
from PILB import Image,ImageStat
from demo_utils import *
import pdb
import ocr


def get_offsets_and_tangent_from_blocks(im,dpi,dash_sep_in_pixels):
    """ locate marks at top left, right of image"""
    croptop = int(round(0.4 * dpi))
    cropbottom = int(round(1.1 * dpi))
    leftstart = 0
    leftend = int(round(0.8 * dpi))
    rightstart = im.size[0] - int(round(0.8*dpi))
    rightend = im.size[0] - 1
    vertical_dist_top_dashes = dash_sep_in_pixels
    vertical_dist_block_dashes = int(round(dpi * .17))
    
    leftstart, croptop, leftend, cropbottom = int(round(leftstart)), int(round(croptop)), int(round(leftend)), int(round(cropbottom))
    leftcrop = im.crop((leftstart,croptop,leftend,cropbottom))
    rightcrop = im.crop((rightstart,croptop,rightend,cropbottom))
    # scan down left 1/3 of leftcrop 
    # and right 1/3 of rightcrop, looking for 
    # first stretch of black lasting dpi * .05
    contig = 0
    leftstarty = 0
    rightstarty = 0
    scanx = int(round(dpi*.1))
    for n in range(dpi/2):
        pix1 = leftcrop.getpixel((0+scanx,n))
        pix2 = leftcrop.getpixel((0+scanx*2,n))
        pix3 = leftcrop.getpixel((0+scanx,n+vertical_dist_top_dashes))
        pix4 = leftcrop.getpixel((0+scanx*2,n+vertical_dist_top_dashes))
        if (pix1[0]<128 or pix2[0]<128)and (pix3[0]<128 or pix4[0]<128):
            contig = contig + 1
            if contig > (dpi * 0.05):
                leftstarty = n - (dpi * 0.05)
                break
        else:
            contig = 0
    contig = 0
    scanx1 = rightcrop.size[0] - int(round(dpi*.1)) 
    scanx2 = rightcrop.size[0] - int(round(dpi*.3))
    for n in range(dpi/2):
        pix1 = rightcrop.getpixel((scanx1,n))
        pix2 = rightcrop.getpixel((scanx2,n))
        pix3 = rightcrop.getpixel((scanx1,n+vertical_dist_top_dashes))
        pix4 = rightcrop.getpixel((scanx2,n+vertical_dist_top_dashes))
        if (pix1[0]<128 or pix2[0]<128) and (pix1[0]<128 or pix2[0]<128):
            contig = contig + 1
            if contig > (dpi * 0.05):
                rightstarty = n - (dpi * 0.05)
                break
        else:
            contig = 0
    leftdashcentery = leftstarty + (0.03 * dpi)
    rightdashcentery = rightstarty + (0.03 * dpi)
    leftdashcentery, rightdashcentery = int(round(leftdashcentery)),int(round(rightdashcentery))
    # now go leftward from scanx
    # along the center of the top dash until white or off edge
    leftstartx = 0
    scanx = int(0.2 * dpi)
    for n in range(scanx):
        pix = leftcrop.getpixel(((scanx - n),
                                 leftdashcentery+ vertical_dist_top_dashes))
        if pix[0]>128:
            leftstartx = scanx - n
            break
    scanx = int(0.3 * dpi)
    return( leftstartx,
            leftstarty+croptop,
            rightstart,
            rightstarty+croptop,
            (rightstarty-leftstarty)/(im.size[0]-(0.6*dpi)))        

def get_code_from_blocks(im,dpi,leftstartx,leftstarty,rightstartx,rightstarty,tilt):
    """read dash blocks at top left,right of image and return encoded int"""
    leftstartx = int(round(leftstartx))
    leftstarty = int(round(leftstarty))
    rightstartx = int(round(rightstartx))
    rightstarty = int(round(rightstarty))
    leftcrop = im.crop(
        (leftstartx,
         leftstarty,
         int(round(leftstartx+(dpi*0.8))),
         int(round(leftstarty+(2*dpi)))))

    rightcrop = im.crop(
        (rightstartx,
         rightstarty,
         im.size[0]-1,
         int(rightstarty+(2*dpi))))
    leftdashcentery = (0.03 * dpi)
    rightdashcentery = (0.03 * dpi)
    leftdashcentery, rightdashcentery = int(round(leftdashcentery)),int(round(rightdashcentery))
    # now go leftward from scanx
    # along the center of the top dash until white or off edge
    leftstartx = 0
    scanx = int(round(dpi*0.4))
    for n in range(scanx):
        pix = leftcrop.getpixel(((scanx - n),leftdashcentery))
        if pix[0]>128:
            leftstartx = scanx - n
            break
    for n in range(scanx):
        pix = rightcrop.getpixel(((scanx - n),rightdashcentery))
        if pix[0]>128:
            rightstartx = scanx - n
            break
    # to capture code, check the eight possible code zones of each crop
    # starting with left, continuing to right
    accum = 0
    for n in range(1,9):
        accum = accum * 2
        testspot = ((int(round(0.3 * dpi)),
                     int(round(.045 * dpi) + (n * 0.17 * dpi))))

        pix = leftcrop.getpixel(testspot)
        if pix[0]<128:
            accum = accum + 1

    for n in range(1,9):
        accum = accum * 2
        testspot = (int(round(rightstartx + (0.3 * dpi))),
                    int(round((.045 * dpi) + (n * 0.17 * dpi))))

        pix = rightcrop.getpixel(testspot)
        if pix[0]<128:
            accum = accum + 1

    return ("%d" % (accum,))

def build_template(im,dpi,code,xoff,yoff,tilt,front=True):
    """build template of arrow locations"""
    # find the locations of the arrow columns 
    # relative to xoff, yoff, and taking tilt into account
    #location_list = [(dpi,xoff,yoff,tilt)]
    # first set will be at just under 3" to right of xoff
    # next set will be at 6" to right of xoff.  
    # Both sets will be at least 0.08" tall after 0.1 inches.
    regionlist = []
    n = 0
    for x in (xoff+int(2.95*dpi),xoff+int(6.*dpi)):
        # skip the code block if you're on a front
        if n==0 and front:
            starty = int(yoff + int(1.5*dpi))
        else:
            starty = int(yoff - 1)
        adjx,adjy = x,starty # XXX assuming ballot derotated by here
        #print "Starty initially",starty,"adjxy",adjx,adjy
        # turn search on only when 0.6" of thick black line encountered
        #adjx = int(adjx)
        #adjy = int(adjy)
        
        contig = 0
        for y in range(adjy,im.size[1]):
            all_black_line = True
            for x2 in range(int(adjx+(dpi*0.1)),int(adjx+(dpi*0.5))):
                pix = im.getpixel((x2,y))
                if pix[0]>128:
                    all_black_line = False
                    break
            if all_black_line:
                contig = contig + 1
            else:
                contig = 0
            if contig > (0.05 * dpi):
                if n==0:starty = y
                break
        if n==0:starty = starty + int(0.2 * dpi)
        # starty is now 0.2 inches below the first 0.6" dash of first column; 
        # arrows may be encountered from here until the column's height less
        # less 1.1 inches
        contig = 0
        searchx1 = x + int(0.15 * dpi)
        searchx2 = x + int(0.55 * dpi)
        #print "Starty",starty
        skip = 0
        contest_x = 0
        contest_y = 0
        for y in range(int(starty),int(im.size[1]-(dpi*1.2))):
            if skip > 0:
                skip = skip - 1
                continue
            pix1 = im.getpixel((searchx1,y))
            pix2 = im.getpixel((searchx2,y))
            if pix1[0]<128 and pix2[0]<128:
                contig = contig + 1
                if contig > (dpi * 0.05):
                    # this is an arrow
                    ll_x,ll_y = ((x,y))

                    if ll_x > (im.size[0] - 5):
                        ll_x = (im.size[0] - 5)
                    if ll_y > (im.size[1] - (dpi/2)):
                        ll_y = (im.size[1] - (dpi/2))
                    if ll_x < int(2.5*dpi):
                        ll_x = int(2.5*dpi)
                    if ll_y < int(dpi/2):
                        ll_y = int(dpi/2)
                    text,contest_text,contest_loc = get_text_for_arrow_at(im,ll_x,ll_y-contig-(0.04*dpi),const.dpi)
                    pdb.set_trace()
                    print text,contest_text,contest_loc
                    # new contest location? append contest, store new location
                    if ((contest_x != contest_loc[0]) 
                        and contest_y != contest_loc[1]):
                        regionlist.append(Ballot.Contest(contest_x,contest_y,199,5*const.dpi,0,contest_text))
                        contest_x = contest_loc[0]
                        contest_y = contest_loc[1]
                    regionlist[-1].append(Ballot.Choice(ll_x, ll_y, text))
                    

                    # skip past arrow
                    #y = y + (0.2 * dpi)
                    skip = (dpi * 0.2)
                    # reset contig
                    contig = 0
    print regionlist
    pdb.set_trace()
    return regionlist

def get_text_for_arrow_at(im,x,y,global_dpi):
    """use tesseract to retrieve text corresponding to left of arrow"""
    # find center of arrow
    fortieth = int(global_dpi/40.)
    topline = int(y - fortieth)
    bottomline = int(y + int(global_dpi * .22))
    startx = int(x - global_dpi)
    starty = int(y + int(global_dpi * .07))
    for up in range(global_dpi/4):
        solid_line = True
        for xadj in range(global_dpi/4):
            pix = im.getpixel((startx+xadj,starty-up))
            if pix[0]>128:
                solid_line = False
                break
        if solid_line:
            topline = starty-up+1
            break

    for down in range(global_dpi/3):
        solid_line = True
        for xadj in range(global_dpi/4):
            pix = im.getpixel((startx+xadj,starty+down))
            if pix[0]>128:
                solid_line = False
                break
        if solid_line:
            bottomline = starty+down-1
            break
    # add one to accomodate rough top line
    topline += 1
    # need to back up to beginning of column, now using 2.25 inches
    crop_x = x - (global_dpi*2.25)
    crop_x = int(round(crop_x))
    if crop_x<0:crop_x = 0

    if topline < 0: topline = 0
    if bottomline <= topline: bottomline = topline + 1
    if bottomline >= im.size[1]: bottomline = im.size[1]-1
    
    if crop_x < 0: crop_x = 0
    if x <= crop_x: x = crop_x + 1
    if x >= im.size[0]: x = im.size[0] - 1
    crop = im.crop((int(crop_x),
                    int(topline),
                    int(x),
                    int(bottomline)))
    text = ocr.tesseract(crop)
    # now repeat process but going up until thicker black; 
    # that will be the top of the contest
    contig = 0
    for up in range(global_dpi*3):
        solid_line = True
        for xadj in range(global_dpi/4):
            pix = im.getpixel((startx+xadj,topline-up))
            if pix[0]>128:
                solid_line = False
                contig = 0
                break
        if solid_line:
            contig = contig + 1
            if contig >= int(global_dpi/60.):
                topline = topline-up+1
                break
    contest_croplist = (int(crop_x),
                        int(topline),
                        int(x),
                        int(topline + ( (2*global_dpi)/3 ) ) 
                        )
    crop = im.crop(contest_croplist)
    contest_text = ocr.tesseract(crop)
    text = text.replace("\n"," ").strip()
    contest_text = contest_text.replace("\n"," ").strip()

    return text, contest_text, contest_croplist



class SequoiaBallot(Ballot.Ballot):
    """Class representing demonstration ballots.

    Each demonstration ballot's layout code, and contest and choice locations
    are entered by the user through a text interface.

    Precinct code can be any number from 1 to 100.

    The file name demo_ballot.py and the class name SequoiaBallot
    correspond to the brand entry in tevs.cfg (demo.cfg), 
    the configuration file.
    """

    def __init__(self, images, extensions):
        #convert all our constants to locally correct values
        # many of these conversions will go to Ballot.py,
        # extenders will need to handle any new const values here, however
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
        super(SequoiaBallot, self).__init__(images, extensions)

    # Extenders do not need to supply even a stub flip
    # because flip in Ballot.py will print a stub message in the absence
    # of a subclass implementation
    #def flip(self, im):
    #    # not implemented for Demo
    #    print "Flip not implemented for Demo."
    #    return im

    def find_landmarks(self, page):
        """ retrieve landmarks for a demo template, set tang, xref, yref

        Landmarks for the demo ballot are normally at 1/2" down and
        1" in from the top left and top right corners.

        The "image" you are using as a template may be offset or 
        tilted, in which case that information will be recorded
        so it may be taken into account when future images are
        examined.
        """
        dash_sep_in_pixels = int(round(const.dpi * 0.17))
        (a,b,c,d,tilt) = get_offsets_and_tangent_from_blocks(
            page.image,
            const.dpi,
            dash_sep_in_pixels)
        if -1 in (a, b, c, d):
            raise Ballot.BallotException("Could not find landmarks")

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
            cropped = page.image.crop(area)
            area_stat = ImageStat.Stat(cropped)
            if area_stat.mean[0] < 16:
                raise Ballot.BallotException(errmsg % (corner, page.filename))

        xoff = a
        yoff = b

        shortdiff = d - b
        longdiff = c - a
        rot = -shortdiff/float(longdiff)
        if abs(rot) > const.allowed_tangent:
            raise Ballot.BallotException(
                "Tilt %f of %s exceeds %f" % (rot, page.filename, const.allowed_tanget)
            )

        return rot, xoff, yoff 

    def get_layout_code(self, page):
        """ Determine the layout code by getting it from the user

        The layout code must be determined on a vendor specific basis;
        it is usually a series of dashes or a bar code at a particular
        location on the ballot.
        """
        barcode = get_code_from_blocks(page.image,
                                       const.dpi,
                                       page.xoff,
                                       page.yoff,
                                       page.image.size[0] - int(round(const.dpi * 0.8)),
                                       page.yoff,0) # XXX use rotation to recalc?
        # If this is a back page, need different arguments
        # to timing marks call; so have failure on front test
        # trigger a back page test
        if barcode == -1:
            barcode = "BACK" + self.pages[0].barcode
        page.barcode = barcode
        return barcode

    def extract_VOP(self, page, rotate, scale, choice):
        """Extract a single oval, or writein box, from the specified ballot.
        We'll tell you the coordinates, you tell us the stats
        """
        x, y = choice.coords()
        x = int(x)
        y = int(y)
        iround = lambda x: int(round(x))
        margin = iround(.03 * const.dpi)

        #XXX BEGIN move into transformer
        xoff = page.xoff - iround(page.template.xoff*scale)
        yoff = page.yoff - iround(page.template.yoff*scale)
        x, y = rotate(xoff + x, yoff + y)
        x = iround(x * scale)
        y = iround(y * scale)
        #XXX end move into transformer (which should now just take a page obj)

        ow, oh = self.oval_size
        print """At %d dpi, on a scale of 0 to 255, 
tell us the average intensity from (%d, %d) for width %d height %d, 
given an offset from the specified x of %d
""" % (const.dpi, x, y, ow, oh, self.vote_target_horiz_offset)
        intensity = ask("Intensity", IntIn(0, 255))
        lowest = ask("Lowest count", IntIn(0, 1000))
        low = ask("Low count", IntIn(0, 1000))
        high = ask("High count", IntIn(0, 1000))
        highest = ask("Highest count", IntIn(0, 1000))
        suspicious = ask("Value of suspicious", int)
        ari, agi, abi  = intensity, intensity, intensity
        lowestr, lowestg, lowestb = lowest, lowest, lowest
        lowr, lowg, lowb = low, low, low
        highestr, highestg, highestb = highest, highest, highest
        highr, highg, highb = high, high, high
        stats = Ballot.IStats(
(ari, lowestr, lowr, highr, highestr,
agi, lowestg, lowg, highg, highestg,
abi, lowestb, lowb, highb, highestb, x, y, 0)
        )

        #can be in separate func?
        cropx = stats.adjusted.x
        cropy = stats.adjusted.y
        crop = page.image.crop((
            cropx - margin,
            cropy - margin,
            cropx + margin + ow, 
            cropy + margin + oh
        ))

        #can be in separate func?
        
        voted, ambiguous = self.extensions.IsVoted(crop, stats, choice)
        writein = False
        if voted:
           writein = self.extensions.IsWriteIn(crop, stats, choice)
        if writein:
            tell_us_about_writein_at((
                 cropx - margin,
                 cropy - margin,
                 cropx + self.writein_xoff + margin,
                 cropy + self.writein_yoff + margin
            ))

        return cropx, cropy, stats, crop, voted, writein, ambiguous

    def build_layout(self, page):
        """ get layout and ocr information from Demo ballot

        Building the layout will be the largest task for registering
        a new ballot brand which uses a different layout style.

        Here, we'll ask the user to enter column x-offsets, 
        then contests and their regions,
        and choices belonging to the contest.
        """
        regionlist = build_template(page.image,
                                    const.dpi,
                                    page.barcode,
                                    page.xoff,
                                    page.yoff,
                                    page.rot)
        return regionlist

