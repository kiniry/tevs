import sys
import os
#XXX suspect
imaging_dir = os.path.expanduser("~/Imaging-1.1.7")
sys.path = [imaging_dir]+sys.path[:]
import time
import pdb
from PILB import Image, ImageStat
import const

class BallotException(Exception):
     def __init__(self, value):
         self.value = value
     def __str__(self):
         return repr(self.value)


class BallotHatchery(object):
    """A ballot hatchery handles images until they can be categorized by vendor,
    then creates a ballot corresponding to the appropriate vendor.
    """
    # each new ballot module must append (TestFunc,Class) pair to this list
    # where TestFunc takes a PIL Image 
    # and returns 1 if it is a picture of a Class type ballot rightside up,
    # or 2 if it is a picture of a Class type ballot upside down,
    # or 0 if it is neither
    ImageIsToBallotList = []

    def __init__(self):
        pass

    def ballotfrom(self,im1,im2):
        """ballotfrom opens image files, creates Ballot for size and brand
        
        It discovers size directly, then discovers brand by passing the 
        first image to each registered IsA function until one returns True,
        then creates a ballot instance of the corresponding ballot type.
        """
        self.im1 = Image.open(im1).convert("RGB")
        self.im1.filename = im1
        try: 
            self.im2 = Image.open(im2).convert("RGB")
            self.im2.filename = im2
        except:
            self.im2 = None
        for func, cls in BallotHatchery.ImageIsToBallotList:
            isa = func(self.im1)
            try:
                 fn1 = self.im1.filename
                 fn2 = self.im2.filename
            except AttributeError:
                 fn2 = None
            if isa==1: 
                 const.logger.info(
                      "Creating ballot object %s from %s %s at %s" % 
                                   (cls,
                                    fn1,
                                    fn2,
                                    time.asctime()))
                 return cls(self.im1,self.im2,flipped=False)
            elif isa==2:
                 const.logger.info("Creating ballot object %s from FLIPPED %s and %s at %s" % 
                                   (cls,
                                    fn1,
                                    fn2,
                                    time.asctime()))
                 const.logger.debug("Flipping %s" % self.im1.filename)
                 self.im1 = self.im1.rotate(180)
                 self.im1.filename = im1
                 try:
                      self.im2 = self.im2.rotate(180)
                      self.im2.filename = im2
                      const.logger.debug("Flipping %s" % self.im2.filename)
                 except:
                      pass
                 return cls(self.im1,self.im2,flipped=True)
        return None

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
    def __init__(self, im1, im2 = None,flipped=False):
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
        if self.front_layout is None:
            self.front_layout = self.BuildFrontLayout()
            self.back_layout = self.BuildBackLayout()
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
        return "BALLOT %s %s" % (self.im1,self.im2)

    def printme(self):
        return "BALLOT %s %s" % (self.im1,self.im2)

    def printany(self,args):
        return args


class VoteData(object):

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
        self.filename = filename
        self.precinct = precinct
        self.jurisdiction=jurisdiction
        self.contest = contest
        self.choice = choice
        self.prop = prop
        self.oval = oval
        self.coords = coords
        self.maxv = maxv # max votes allowed in contest
        self.was_voted = False
        try:
            self.stats = stats[:]
            if stats is None:
                print "No stats while creating vote data"
        except:
            print "No stats while creating vote data"
        try:
             self.red_intensity = stats[0]
             self.red_darkestfourth = stats[1]
             self.red_secondfourth = stats[2]
             self.red_thirdfourth = stats[3]
             self.red_lightestfourth = stats[4]

             self.green_intensity = stats[5]
             self.green_darkestfourth = stats[6]
             self.green_secondfourth = stats[7]
             self.green_thirdfourth = stats[8]
             self.green_lightestfourth = stats[9]

             self.blue_intensity = stats[10]
             self.blue_darkestfourth = stats[11]
             self.blue_secondfourth = stats[12]
             self.blue_thirdfourth = stats[13]
             self.blue_lightestfourth = stats[14]

             self.adjusted_x = stats[15]
             self.adjusted_y = stats[16]
             self.suspicious = stats[17]
        except Exception, e:
             print e
             pdb.set_trace()
        
        # stats 0, 5, 10 represent mean intensity on R,G,B,
        # test average against vote threshold and set was_voted true
        # if value is below

        # stats 1,2 and 6,7 and 10,11 represent darkest/darker pixel counts
        # on R, G, B; test average sum against dark_pixel threshold and
        # set was_voted true if value is below

        voted_intensity = False
        voted_count = False
        if int((stats[0]+stats[5]+stats[10])/3) < const.vote_intensity_threshold:
             voted_intensity = True
             self.was_voted = True
        if int((stats[0]+stats[5]+stats[10])/3) >= const.problem_intensity_threshold:
             const.logger.error("Image %s too light at %s: %s %s %s" 
                                % (filename, oval,stats[0],stats[5],stats[10]))
        if int((stats[1]+stats[2]
                +stats[6]+stats[7]
                +stats[11]+stats[12])/3 > const.dark_pixel_threshold):
             voted_count = True
             self.was_voted = True
        if voted_intensity <> voted_count:
             print "AMBIG VOTE",self
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
    
