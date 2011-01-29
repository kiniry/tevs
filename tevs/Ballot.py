import sys
import os
import time

from PILB import Image, ImageStat
import const

class BallotException(Exception):
     pass

def LoadBallotType(name):
    name = name.lower().strip()
    try:
        module = __import__(
             name + "_ballot",
             globals(),
        )
    except ImportError as e:
        raise ValueError(str(e))
    return getattr(module,
        name[0].upper() + name[1:] + "Ballot")

class BtRegion(object):
    """ Representing a rectangular region of a ballot. """
    JURISDICTION = 0
    CONTEST = 1
    CHOICE = 2
    PROP = 3
    OVAL = 4
    purposelist = ["JUR","CONTEST","CHOICE","PROP","OVAL"]
    def __init__(self, bbox=(), purpose=None, coord=(0,0), text=None):
        self.bbox = bbox
        self.purpose = purpose
        self.text = text
        self.coord = coord

    def __repr__(self):
        purposetext = "OVAL"
        if self.purpose in BtRegion.purposelist: 
            purposetext = BtRegion.purposelist[self.purpose]
        return "BtRegion with purpose %s, bbox %s coord %s\ntext %s" % (
            purposetext, self.bbox, self.coord, self.text)


class Ballot(object):
    """Ballot contains routines to get vote info off one or two images.

    Ballot treats one or two images as the front and, optionally, the back
    of a ballot.  Ballot is an abstract class; real Ballot instances will
    be instances of Ballot subclasses.  

    Ballot defines:

    GetLandmarks for retrieving orienting information

    GetLayoutCode for getting information from the images 
    that allow it to look up the appropriate layout;

    ValidateLayoutCode to optionally test a given layout code to determine
    if it is acceptable for this election.  A false return can trigger
    an additional call to GetLayoutCode, with added optional arguments
    indicating the number of prior calls to GetLayoutCode for this image,
    the prior layout codes returned, and the reasons for prior rejection(s).
    Different levels of implementation of GetLayoutCode may simply fail
    if ValidateLayoutCode sends back a rejection, or may call upon 
    different strategies for locating an acceptable layout code.

    GetFrontLayout and GetBackLayout to retrieve previously stored layout
    information corresponding to a layout code; the layouts must contain
    sufficient information to allow a vote gathering function to locate
    all vote opportunities on the layout and merge statistics from each
    image with jurisdiction/contest/candidate information from the layout.

    BuildFrontLayout and BuildBackLayout to construct and store layout
    information for newly encountered layout codes;

    FineAdjustVote for taking coordinates provided by the layout, as
    adjusted by translation and rotation of the individual image, and
    returning further adjusted versions of the coordinates that precisely
    line up based on local landmarks.  This function is optional, called if 
    registered, and can be chained in a list.  The function returns None
    if there appears to be a problem in locating the vote target.

    CaptureVoteInfo for using layout information to process the ballot
    image and extract vote information;

    WriteVoteInfo for writing the extracted vote information to a file and,
    optionally, for calling registered output functions to save vote
    information using alternative mechanisms.
    """
    # dictionaries of front and back templates encountered 
    # are attributes of Ballot class
    front_dict = {}
    back_dict = {}
    precinct_dict = {}
    valid_front_list = [] # may contain strings or functions
    invalid_front_list = [] # may contain strings or functions
    valid_back_list = [] # may contain strings or functions
    invalid_back_list = [] # may contain strings or functions
    def __init__(self, im1, im2=None, flipped=False):
        self.im1 = im1
        self.im2 = im2
        self.flipped = flipped
        self.duplex = False
        self.layout_code = "default layout code" 
        self.code_string = "default code string"
        self.precinct = "default precinct"
        self.front_layout = "default front layout"
        self.back_layout = "default back layout"
        self.brand = "default brand"
        self.current_jurisdiction = ""
        self.current_contest = ""
        self.current_oval = ""
        self.current_prop = ""
        self.current_choice = ""
        self.current_coords = None
        self.results = []

    def GetLayoutCode(self):
        print "In %s GetLayoutCode from instance of %s" % ("Ballot", 
                                                           self.__class__)
        self.layout_code = "default layout"
        return self.layout_code

    def GetFrontLayout(self):
        print "In %s GetFrontLayout with layout %s" % ("Ballot", 
                                                       self.layout_code)
        self.front_layout = "FRONT"
        return self.front_layout

    def GetBackLayout(self):
        print "In %s GetBackLayout with layout %s" % ("Ballot", 
                                                       self.layout_code)
        self.back_layout = "BACK"
        return self.back_layout

    def BuildFrontLayout(self):
        print "In %s BuildFrontLayout with layout_code %s" % ("Ballot", 
                                                    self.layout_code)

    def BuildBackLayout(self):
        print "In %s BuildBackLayout with layout_code %s" % ("Ballot", 
                                                    self.layout_code)
            
    def GetLandmarks(self):
        print "In %s GetLandmarks" % ("Ballot",) 

    def CaptureVoteInfo(self):
        print "In %s CaptureVoteInfo" % ("Ballot",) 

    def WriteVoteInfo(self):
        print "In %s WriteVoteInfo" % ("Ballot",) 

    def __str__(self):
        return "BALLOT:%s %s %s" % (self.brand, self.im1, self.im2)

    def __repr__(self):
        return "BALLOT:%s %s %s" % (self.brand, self.im1, self.im2)

class VoteData(object):
    def __init__(self, filename="filename",
                 precinct="precinct",
                 jurisdiction="jurisdiction", 
                 contest="contest",
                 choice="choice", 
                 prop="prop",
                 oval="oval",
                 coords="coords",
                 maxv=1,
                 stats=None):
        self.filename = filename
        self.precinct = precinct
        self.jurisdiction = jurisdiction
        self.contest = contest
        self.choice = choice
        self.prop = prop
        self.oval = oval
        self.coords = coords
        self.maxv = maxv # max votes allowed in contest
        self.was_voted = False

        if len(stats) != 18:
            raise BallotException("Attempted to create voting data with invalid stats")

        self.stats = stats[:]

        (self.red_intensity,
        self.red_darkestfourth,
        self.red_secondfourth,
        self.red_thirdfourth,
        self.red_lightestfourth,

        self.green_intensity,
        self.green_darkestfourth,
        self.green_secondfourth,
        self.green_thirdfourth,
        self.green_lightestfourth,

        self.blue_intensity,
        self.blue_darkestfourth,
        self.blue_secondfourth,
        self.blue_thirdfourth,
        self.blue_lightestfourth,

        self.adjusted_x,
        self.adjusted_y,
        self.suspicious) = stats
        
        # stats 0, 5, 10 represent mean intensity on R,G,B,
        # test average against vote threshold and set was_voted true
        # if value is below

        # stats 1,2 and 6,7 and 10,11 represent darkest/darker pixel counts
        # on R, G, B; test average sum against dark_pixel threshold and
        # set was_voted true if value is below

        voted_intensity = False
        voted_count = False
        vote_intense = int((stats[0]+stats[5]+stats[10])/3)
        if vote_intense < const.vote_intensity_threshold:
             voted_intensity = True
             self.was_voted = True
        if vote_intense >= const.problem_intensity_threshold: #XXX need to flag bad input, put in a "problem directory"?
             const.logger.error("Image %s too light at %s: %s %s %s" 
                                % (filename, oval,stats[0],stats[5],stats[10]))
        if int((stats[1]+stats[2]
                +stats[6]+stats[7]
                +stats[11]+stats[12])/3 > const.dark_pixel_threshold):
             voted_count = True
             self.was_voted = True
        if voted_intensity != voted_count: #XXX same as above
             print "AMBIG VOTE", self
             const.logger.info("AMBIG: voted intensity %s voted count %s" 
                               % (voted_intensity, voted_count))
             const.logger.info("AMBIG: %s" 
                               % (self,))
                      
    def __repr__(self):
        return "%s,%s,%s,%s,%s,%d,%d,%s,%s,%s" % (
            self.filename,
            self.precinct,
            self.contest,
            self.prop,
            self.oval,
            self.coords[0],
            self.coords[1],
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
            self.coords[0],
            self.coords[1],
            str(self.stats)[1:-1],
            self.maxv,
            self.was_voted
            )

class Contest(object): #placeholder
     def __init__(self, **kw):
         self.__dict__.update(kw)
 
