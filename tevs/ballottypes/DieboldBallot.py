import os
import sys
import subprocess
import xml.dom.minidom
import pdb
imaging_dir = os.path.expanduser("~/Imaging-1.1.7")
sys.path = [imaging_dir]+sys.path[:]
from PILB import Image, ImageStat
from Ballot import Ballot, BallotHatchery, BallotException, BtRegion, VoteData
import const
from tevs.utils.ocr import ocr
from tevs.utils.adjust import rotate_pt_by
from tevs.utils.util import alnumify
# "IsA" function, registered below with BallotHatchery,
# must return 1 if the image is a usable representation 
# of this module's ballot type, rightside up,
# must return 2 if the image is a usable representation
# of this module's ballot type, upside down,
# or must return 0 otherwise
def IsADiebold(im):
    print "Called IsADiebold with image",im
    # A diebold image will have registration marks on either side
    # and will have a series of dashes across the top if rightside up
    # or the bottom if upside down
    # Crop the left quarter inch for the full height as leftcrop
    # Crop the right quarter inch for the full height as rightcrop
    # Insist on a dark light pattern repeating every quarter inch;
    # Find the uppermost and lowermost dashes of the repeating pattern
    # Scan the line between the two uppermost and get intensity
    # Scan the line between the two lowermost and get intensity
    # If uppermost is darker line, rightside up; else upside down
    dpi = im.size[0]/const.ballot_width_inches
    if dpi > 148 and dpi < 152: dpi = 150
    if dpi > 296 and dpi < 304: dpi = 300
    quarter_inch = dpi/4
    thirtysecond_inch = dpi/32.
    sixtyfourth_inch = dpi/64.

    left = im.crop((0,0,quarter_inch,im.size[1]))
    right = im.crop((im.size[0]-(quarter_inch),0,im.size[0],im.size[1]))
    # on left and right
    # find the first y from top where things go dark for dpi/16, then light
    # if no pattern in first 120/64, not a Diebold
    for img in (left,right):
        for n in range(120):
            pix1 = img.getpixel((img.size[0]/2,(n*sixtyfourth_inch)))
            pix2 = img.getpixel((img.size[0]/2,((n+1)*sixtyfourth_inch)))
            pix3 = img.getpixel((img.size[0]/2,((n+8)*sixtyfourth_inch)))
            pix4 = img.getpixel((img.size[0]/2,((n+16)*sixtyfourth_inch)))
            if pix1[0]<128 and pix2[0]<128 and pix3[0]>128 and pix4[0]<128:
                img.starty = n*sixtyfourth_inch
                break
            if n==119: 
                return 0
        imght = img.size[1] - 1
        # find the last y from bottom where things enter pattern
        # if no pattern in first 120/64, not a diebold
        for n in range(120):
            pix1 = img.getpixel((img.size[0]/2,imght-((n*sixtyfourth_inch))))
            pix2 = img.getpixel((img.size[0]/2,imght-((n+1)*sixtyfourth_inch)))
            pix3 = img.getpixel((img.size[0]/2,imght-((n+8)*sixtyfourth_inch)))
            pix4 = img.getpixel((img.size[0]/2,imght-((n+16)*sixtyfourth_inch)))
            if pix1[0]<128 and pix2[0]<128 and pix3[0]>128 and pix4[0]<128:
                img.endy = n*sixtyfourth_inch
                break
            if n==119: 
                return 0

    # refuse ballots with more than 1/4 inch tilt from left to right
    if math.abs(left.starty - right.starty) > quarter_inch:
        const.logger.error("Too much tilt on likely Diebold image %s" % (im.filename,))
        return 0
    avgstarty = (left.starty + right.starty)/2
    avgcentery = avgstarty + (thirtysecond_inch)
    topcrop = im.crop((im.size[0]/3,avgcentery,(2*im.size[0])/3,avgcentery +1))
    avgstarty = im.size[1] - ((left.endy + right.endy)/2) - 1
    avgcentery = avgstarty - thirtysecond_inch
    bottomcrop = im.crop((im.size[0]/3,avgcentery-1,(2*im.size[0])/3,avgcentery))
    topstat = ImageStat.Stat(topcrop)
    bottomstat = ImageStat.Stat(bottomcrop)
    print topstat.mean, bottomstat.mean
    if topstat.mean[0] < bottomstat.mean[0]:
        return 1
    else:
        return 2



class DieboldBallot(Ballot):
    """Class representing ballots from Diebold/Premier/OwnerOfTheDay.

    Each Diebold ballot has ovals around voting areas,
    and voting areas are grouped in boxed contests.
    """

    def __init__(self,im1,im2=None):
        super(DieboldBallot,self).__init__(im1,im2)
        self.brand = "Diebold"

    def __repr__(self):
        return "%s: %s; %s" % (self.brand, self.im1, self.im2)

    def __str__(self):
        return "%s: %s, %s" % (self.brand, self.im1, self.im2)

    def GetLandmarks(self):
        """ retrieve landmarks for Diebold,

        Landmarks for the Diebold Ballot will be the ulc, urc, lrc, llc 
        (x,y) pairs marking the interior corners of the outermost dashes."""

        self.tiltinfo = [0,0]
        self.tang = [0,0]
        self.xref = [0,0]
        self.yref = [0,0]
        self.dpi = int(round(
                self.im1.size[0]/const.ballot_width_inches))
        if self.dpi > 148 and self.dpi < 152:
            self.dpi = 150
        self.dpi_y = self.dpi

        #self.dpi = 150
        self.tiltinfo[0] = self.im1.getdieboldlandmarks(self.dpi,0)
        print self.tiltinfo[0]
        try:
            if self.im2 is not None:
                self.tiltinfo[1] = self.im2.getdieboldlandmarks(self.dpi,0)
            else:
                self.tiltinfo[1] = None
        except:
            self.tiltinfo[1] = None
        # ballots are duplex only when
        # getdieboldlandmarks can find a tilt on both sides;
        # (ballots with a blank side are not duplex)
        if (self.tiltinfo[1] is None) or (self.tiltinfo[0] is None):
            self.duplex = False
        else:
            self.duplex = True

        # flunk ballots with 3/16" of black in corner
        # to avoid dealing with severely skewed ballots

        testwidth = (self.dpi * 3) / 16
        testheight = testwidth
        testcrop = self.im1.crop((0,0,testwidth,testheight))
        teststat = ImageStat.Stat(testcrop)
        if teststat.mean[0] < 16:
            const.logger.error("Dark upper left corner on %s, code %d" % (
                    self.im1.filename,1))
            raise BallotException
        testcrop = self.im1.crop((self.im1.size[0] - testwidth,
                                  0,
                                  self.im1.size[0] - 1,
                                  testheight))
        teststat = ImageStat.Stat(testcrop)
        if teststat.mean[0] < 16:
            const.logger.error("Dark upper right` corner on %s, code %d" % (
                    self.im1.filename,2))
            raise BallotException
        testcrop = self.im1.crop((self.im1.size[0] - testwidth,
                                    self.im1.size[1] - testheight,
                                    self.im1.size[0] - 1,
                                    self.im1.size[1] - 1))
        teststat = ImageStat.Stat(testcrop)
        if teststat.mean[0] < 16:
            const.logger.error("Dark lower right corner on %s, code %d" % (
                    self.im1.filename,3))
            raise BallotException
        testcrop = self.im1.crop((0,
                                    self.im1.size[1] - testheight,
                                    testwidth,
                                    self.im1.size[1] - 1))
        teststat = ImageStat.Stat(testcrop)
        if teststat.mean[0] < 16:
            const.logger.error("Dark lower left corner on %s, code %d" % (
                    self.im1.filename,4))
            raise BallotException

        if self.duplex is False:
            toprange = 1
        else:
            toprange = 2
        for n in range(toprange):
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
                if abs(self.tang[n]) > 0.05: raise BallotException

            except Exception, e:
                print e
                const.logger.error(e)
                self.tang[n] = 0.
                raise Exception

        # Switch front and back if necessary; 
        # unfortunately, this is probably site-dependent


        try:
            # back tangent will be opposite that of front
            self.tang[1] = -self.tang[0] 
            self.xref[1] = self.xref[0]
            self.yref[1] = self.yref[0]
        except:
            pass

        print "TANG",self.tang
        print "XREF",self.xref
        print "YREF",self.yref
        print "TILTINFO 2 xref yref longdiff shortdiff",self.tiltinfo

        return self.tiltinfo
        

    def GetLayoutCode(self):
        """ Determine the layout code(s) from the bottom dashcode(s) """
        self.layout_code = [0,0]
        if self.duplex is False:
            toprange = 1
        else:
            toprange = 2
        # barcode zones to search are from 1/3" to 1/6" to left of ulc
        # and from 1/8" above ulc down to 2 5/8" below ulc.
        n = 0
        for im in (self.im1, self.im2):
            # don't pass negative x,y into getbarcode
            if im is not None:
                ddc = im.diebolddashcode(128,
                                         self.dpi,
                                         im.size[1]-(self.dpi*0.3))
                ddc = "%x" % ddc 
                self.layout_code[n] = ddc.replace("-","0") 
            n = n+1
        im = self.im1
        code_string = self.layout_code[0]
        barcode_good = True
        if barcode_good: # and we expect to have all templates by now:
             try:
                  self.front_layout = BallotSideFromXML(
                      self.im.filename,
                      0,
                      Ballot.front_dict[code_string])
             except:
                  barcode_good = False

        self.code_string = code_string
        print self.code_string
        if barcode_good == False:
             const.logger.warning("Bad barcode %s at %s" % (
                       code_string, im.filename))

        print "SETTING PRECINCT FROM CODE STRING",self.code_string
        self.precinct = self.code_string
        return self.layout_code

    def GetFrontLayout(self):
        """ Retrieve front template from dictionary, if it exists.

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
        except Exception, e:
            print e
            print "On new layout: '%s'" % (const.on_new_layout,)
            if const.on_new_layout.startswith("reject"):
                return None
            return self.BuildFrontLayout()


    def GetBackLayout(self):
        """ Retrieve back template from dictionary, if it exists.

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


        pass

    def BuildFrontLayout(self):
        self.regionlists = [[],[]]
        self.need_to_pickle = True
        self.front_layout = []
        # for getdiebolddetails to operate properly, we need to 
        # cancel the rotation to get vertical and horizontal lines
        filename = self.im1.filename
        self.im1 = self.im1.rotate(-self.tang[0] * (180./3.14))
        self.im1.filename = filename
        self.tang[0] = 0.0

        self.getdiebolddetails(self.im1,self.regionlists[0])
        self.front_layout = BallotSide(
            self,
            0,
            precinct=self.precinct,
            dpi=self.dpi)

        front_xml = self.front_layout.toXML(self.code_string)
        Ballot.front_dict[self.layout_code[0]] = front_xml
        template_outfile = open("templates/"+self.code_string,"w")
        template_outfile.write(front_xml)
        template_outfile.close()
        # if you need to build the front layout, you need to build
        # the back layout as well
        self.BuildBackLayout()
        return self.front_layout

    def BuildBackLayout(self):
        if self.im2 is None: return None
        try:
            self.regionlists[1] = []
            print "Length of self.regionlists[1]",len(self.regionlists[1])
            print "Setting to empty list"
            print "Length of self.regionlists[1]",len(self.regionlists[1])
        except:
            self.regionlists = [ [],[] ]
            print "Length of self.regionlists[1]",len(self.regionlists[1])
            print "Setting to empty list"
            print "Length of self.regionlists[1]",len(self.regionlists[1])
        self.back_layout = []
        try:filename = self.im2.filename
        except: filename = "UNKNOWN"
        self.im2 = self.im2.rotate(-self.tang[1] * (180./3.14))
        self.im2.filename = filename
        self.tang[1] = 0.0
        self.getdiebolddetails(self.im2,self.regionlists[1])
        self.back_layout = BallotSide(
            self,
            1,
            precinct=self.precinct,
            dpi=self.dpi)

        back_xml = self.back_layout.toXML(self.code_string)
        Ballot.back_dict[self.layout_code[0]] = back_xml
        template_outfile = open("backtemplates/"+self.code_string,"w")
        template_outfile.write(back_xml)
        template_outfile.close()
        print "Length of self.regionlists[1]",len(self.regionlists[1])

        return self.back_layout

    def getdiebolddetails(self,im,br):
        """ get layout and ocr information """
        dpi = self.dpi
        margin = dpi/8
        oval_topline_width = dpi/8
        oval_height = dpi/8
        oval_gap = dpi/16
        vline_list = im.getcolumnvlines(0,im.size[1]/2,im.size[0]-20)
        const.logger.debug("%s" % vline_list)
        lastx = -(dpi/4)
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
                hlinelistlist.append( pot_hlines)
            lastx = x
        lastel2 = 0

        # an hline is confirmed by matching a positive hline in sublist n
        # against a negative hline in sublist n+1; if no sublist n+1, no hlines
        conf_hll = []

        for col in range(len(hlinelistlist)-1):
            conf_hll.append([])
            for entrynum in range(len(hlinelistlist[col])):
                yval1 = hlinelistlist[col][entrynum]
                for entrynum2 in range(len(hlinelistlist[col+1])):
                    yval2 = hlinelistlist[col+1][entrynum2]
                    if (yval1 > 0) and (abs(yval1 + yval2) < (dpi/16)):
                        conf_hll[col].append(yval1)
                        break
        for x in range(len(conf_hll)):
            conf_hll[x] = map(lambda el: [el,"h"],conf_hll[x])

        print conf_hll
        contest_boxes = []
        vboxes = []
        for n in range(len(columnstart_list)-1):
            #print "PASS",n,"of",len(columnstart_list),columnstart_list
            try:
                for m in range(len(conf_hll[n])-1):
                    x1 = columnstart_list[n]
                    y1 = conf_hll[n][m][0]
                    try:
                        #print "Endxy",columnstart_list[n+1],conf_hll[n][m+1]
                        try:
                            x2 = columnstart_list[n+1]
                        except:
                            x2 = im.size[0]-(2*margin)
                        try:
                            y2 = conf_hll[n][m+1][0]
                        except:
                            y2 = im.size[1]-(2*margin)
                        if y2 > (y1+(2*margin)):
                            w = x2 - x1;
                            h = y2 - y1;
                            #print "Box",x1,y1,w,h
                            # x,y,w,h followed by oval width, oval height
                            tb = im.getdieboldvoteovals(x1,
                                                        y1,
                                                        w - margin,
                                                        h -margin,
                                                        oval_topline_width,
                                                        oval_height)

                            contest_boxes.append([x1,y1,w,h,tb])
                            # extend the ballot region list with, 
                            # first, the contest, 
                            try:
                                if len(tb)==0:
                                    continue
                                #print "Cropping to ",x1,y1,x1+w,tb[0][1]
                                crop = im.crop((x1,y1,x1+w,tb[0][1]))
                                gaps = crop.gethgaps((128,1))
                                #print "Gaps are",gaps
                                try:
                                    gaps = gaps[1:]
                                except:
                                    pass
                                try:
                                    zone_croplist = (dpi/16,dpi/16,(crop.size[0]),(gaps[0][3]))
                                except:
                                    zone_croplist = (dpi/16,dpi/16,(crop.size[0]),crop.size[1])            
                                if zone_croplist[2]<=0:
                                    continue
                                if zone_croplist[3]<=0:
                                    continue
                                zone = crop.crop(zone_croplist)
                                print zone_croplist

                                zone.save("/tmp/region.tif")
                                p = subprocess.Popen(["/usr/local/bin/tesseract", 
                                                      "/tmp/region.tif", 
                                                      "/tmp/region"]
                                                     )
                                sts = os.waitpid(p.pid,0)[1]
                                tempf = open("/tmp/region.txt")
                                text = alnumify(tempf.read())
                                tempf.close()
                                if text.strip().startswith("PROP"):
                                    isProp = True
                                else: 
                                    isProp = False

                            except Exception, e:
                                print e
                                text = "CONTEST"

                            text = text.split("\n")[0]
                            if isProp:
                                purpose = BtRegion.PROP
                            else:
                                purpose = BtRegion.CONTEST
                            br.append(BtRegion(bbox=(x1,y1,x2-x1,y2-y1),
                                                    purpose = purpose,
                                                    coord = (x1,y1),
                                                    text = text))
                            # and then, the vote ops
                            for ovalcoord in tb:
                                isWriteIn = False
                                crop = im.crop((ovalcoord[0]+(dpi/4),
                                                ovalcoord[1]-(margin/2),
                                                ovalcoord[0]+(2*dpi),
                                                ovalcoord[1]+(dpi/6)))
                                # does the crop contain a long horizontal line?
                                # if it does, it's a writein
                                contig = 0
                                for pix in crop.getdata():
                                    if pix[0]<128:
                                        contig = contig + 1
                                        if contig > dpi:
                                            isWriteIn = True
                                            br.append(BtRegion(purpose=BtRegion.OVAL,
                                                               coord = ovalcoord,
                                                               text = "Write-in"
                                                               ))
                                            break
                                    else: contig = 0
                                if isWriteIn: continue    
                                # if it's not a write-in, read the text
                                crop.save("/tmp/region.tif")
                                p = subprocess.Popen(["/usr/local/bin/tesseract", 
                                                      "/tmp/region.tif", 
                                                      "/tmp/region"]
                                                     )
                                sts = os.waitpid(p.pid,0)[1]
                                tempf = open("/tmp/region.txt")
                                text = alnumify(tempf.read())
                                text = text.split("\n")[0]
                                if isProp:
                                    text = text[:9].strip()
                                    if text.find("YE")>-1:
                                        text = "YES"
                                    elif text.find("NO")>-1 or text.find("N0")>-1:
                                        text = "NO"
                                tempf.close()
                                br.append(BtRegion(purpose=BtRegion.OVAL,
                                                   coord = ovalcoord,
                                                   text = text.split("\n")[0]
                                                   ))
                    except Exception, e:
                        print e
                        pdb.set_trace()
            except Exception, e:
                print e
                pdb.set_trace()
        print br

        return br

    def CaptureVoteInfo(self):
        self.CaptureSideInfo(side="Front")
        self.CaptureSideInfo(side="Back")


    def CaptureSideInfo(self,side):
        """CaptureVoteInfo captures votes off the images in a DieboldBallot
        
        Each DieboldBallot instance has one or two images representing the
        sides of the ballot, and points to one or two "BallotSide" 
        template instances, representing the layout of votes on images
        representing ballots of the target ballot's precinct.

        CaptureVoteInfo goes through the templates item by item and
        examines the equivalent regions of the ballot instance to
        determine which vote opportunities have been marked by the voter.
        """
        #first, the front
        if side == "Front":
            layout = self.front_layout
            im = self.im1
        elif self.duplex:
            layout = self.back_layout
            im = self.im2
        else:
            return
        print layout.dpi
        print self.dpi
        for region in layout.regionlist:
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
                self.current_contest = "(Prop) " + region.text
                self.current_prop = "(Prop) " + region.text
                
            else:
                # anything else is a vote op, with the y offset stored
                # in place of the purpose
                self.current_oval = region.text
                self.current_coords = region.coord
                scalefactor = float(self.dpi)/float(layout.dpi)
                xoffset = self.xref[0] - (layout.xref*scalefactor)
                yoffset = self.yref[0] - (layout.yref*scalefactor)
                print self.current_oval, self.current_coords
                print self.xref[0], self.yref[0], layout.xref*scalefactor, layout.yref*scalefactor

                # the ballot region's dpi will typically be 300,
                # while individual ballots will typically have 150
                #print "Jurisdiction",self.current_jurisdiction
                #print "Contest",self.current_contest
                #print "VOP",self.current_oval,self.current_coords
                #print "xoffset",xoffset,"yoffset",yoffset
                #print "DPI",self.dpi,"LAYOUT DPI",layout.dpi
                scalefactor = float(self.dpi)/float(layout.dpi)
                # adjust oval location given in template 
                # for tilt and offset of this ballot
                startx = int(self.current_coords[0])
                starty = int(self.current_coords[1])
                #print "Startx,starty before offset",startx,starty
                startx = startx + int(round(xoffset))
                starty = starty + int(round(yoffset))
                #print "Startx,starty before rotate",startx,starty
                (startx,starty)=rotate_pt_by(startx,starty,self.tang[0],
                                             self.xref[0],
                                             self.yref[0])
                #print "Startx,starty after offset,rotate", startx, starty
                # add in end points for oval
                #pdb.set_trace()
                startx = int(round(startx * scalefactor))
                starty = int(round(starty * scalefactor))
                ow = int(round(const.oval_width_inches * self.dpi ))
                oh = int(round(const.oval_height_inches * self.dpi)) 
                endx = startx + ow
                endy = starty + oh
                cs = im.cropstats(
                    int(round(startx)),
                    int(round(starty)),
                    int(round(ow)),
                    int(round(oh)),
                    1)
                maxv = 1
                try:
                    maxv = get_maxv_from_text(self.current_contest)
                    self.current_contest = self.current_contest[:40]
                except:
                    pass
                vd = VoteData(filename = im.filename,
                              precinct = layout.precinct,
                              jurisdiction = self.current_jurisdiction[:40],
                              contest = self.current_contest[:40],
                              choice = self.current_choice,
                              prop = self.current_prop,
                              oval = self.current_oval,
                              coords = [startx,starty],
                              stats = cs,
                              maxv = maxv)
                self.results.append(vd)

                # deal with write-ins; this should be refactored out
                if vd.was_voted and (self.current_oval.find("Write")>-1 
                                   or self.current_oval.find("vrit")>-1 
                                   or self.current_oval.find("Vrit")>-1):
                   # crop the coords for three inches of horizontal
                   # and three times the oval height
                   if (self.current_oval.find("riter")>-1):
                        pass
                   else:
                        wincrop = im.crop(
                             (startx,
                              starty,
                              startx+int(2.5*self.dpi),
                              starty+int(0.6*self.dpi)
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
                        im.filename[-10:-4].replace("/","").replace(" ","_"),
                        self.current_contest[:20].replace(
                             "/","").replace(" ","_")
                        )
                   wincrop.save(savename)
                   print "Saved",savename
                   const.logger.info("Saved %s\n",savename)

    def WriteVoteInfo(self):
        retstr = ""
        for vd in self.results:
            try:
                retstr = retstr + vd.toString()
                retstr = retstr + "\n"
            except Exception, e:
                print e
                pdb.set_trace()
        return retstr

class BallotSide(object):
    """Representing a ballot side as a list of meaningful regions,
    plus sufficient information about the current ballot to scale,
    offset, and rotate information from the template regions."""

    def __init__(self, ballot,side,precinct="?",
                 dpi=150 
                 ):
        self.ballot = ballot
        self.side = side
        self.dpi = dpi
        self.precinct = precinct
        self.regionlists = [ [],[] ]
        if side==0:
            self.name = self.ballot.im1.filename
        else:
            self.name = self.ballot.im2.filename
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
        return "BallotSide %s regionlist length %s  tangent %f, precinct %s" % (
            self.name,
            len(self.regionlist),
            self.tang, 
            self.precinct)

    def append(self,region):
        if type(region)<>BtRegion:
            raise Exception
        # don't append regions with (0,0) location, they're artifacts
        if (region.coord[0] <> 0) and (region.coord[1] <> 0):
            self.regionlist.append(region)


    def toXML(self,precinct="?"):
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

                contestlist.append(
                    "<Contest prop='True' \ntext='%s' x='%d' y='%d' x2='%d' y2='%d'>"
                               % (region.text.replace("'",""),
                                  region.bbox[0],region.bbox[1],
                                  region.bbox[2],region.bbox[3],
                                  )
                )
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
        self.precinct = bs[0].getAttribute('precinct')
        print self.precinct
#       "dpi='%d' precinct='?' lx='%d' ly='%d' rot='%f'
        contests = doc.getElementsByTagName("Contest")
        for contest in contests:
            try:
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
            except Exception, e:
                print e
                pdb.set_trace()
        self.im = None
        #self.landmarklist = self.ballot.landmarklist[self.side]
        try:
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
        except Exception, e:
            print e
            pdb.set_trace()
# Every Ballot subclass module must register its IsA function and
# itself with the BallotHatchery.  The BallotHatchery can then go
# pair by pair down its "ImageIs" to "Ballot" pair list, 
# and create an appropriate subclass instance 
# for the first satisfactory type.
BallotHatchery.ImageIsToBallotList.append((IsADiebold,DieboldBallot))


if __name__ == "__main__":
    bh = BallotHatchery()
    newballot = bh.ballotfrom("/home/mitch/aug10/ocrtest2.jpg",
                        "/home/mitch/aug10/rot90.jpg")
    print "Hatchery returned",newballot
    print "Layout code",newballot.layout_code
    print "Brand",newballot.brand


    hb = DieboldBallot("a","b")
    print hb

