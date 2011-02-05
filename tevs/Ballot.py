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

class Ballot(object): #XXX a better name may be something like BallotAnalyzer
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

class _bag(object):
    def __repr__(self):
        return repr(self.__dict__)

class Stats(object):
    def __init__(self, stats):
       self.red, self.green, self.blue = _bag(), _bag(), _bag()
       self.adjusted = _bag()
       (self.red.intensity,
        self.red.darkest_fourth,
        self.red.second_fourth,
        self.red.third_fourth,
        self.red.lightest_fourth,

        self.green.intensity,
        self.green.darkest_fourth,
        self.green.second_fourth,
        self.green.third_fourth,
        self.green.lightest_fourth,

        self.blue.intensity,
        self.blue.darkest_fourth,
        self.blue.second_fourth,
        self.blue.third_fourth,
        self.blue.lightest_fourth,

        self.adjusted.x,
        self.adjusted.y,

        self.suspicious) = stats

    def mean_intensity(self):
        try:
            return self._mean_intensity
        except AttributeError:
            self._mean_intensity = int(round(
                (self.red.intensity +
                 self.green.intensity +
                 self.blue.intensity)/3.0
            ))
            return self._mean_intensity

    def mean_darkness(self):
       """compute mean darkness over each channel using first
       two quartiles."""
       try:
           return self._mean_darkness
       except AttributeError:
           self._mean_darkness = int(round(
               (self.red.darkest_fourth   + self.red.second_fourth   +
                self.blue.darkest_fourth  + self.blue.second_fourth  +
                self.green.darkest_fourth + self.green.second_fourth
               )/3.0
           ))

    def mean_lightness(self):
       """compute mean lightness over each channel using last
       two quartiles."""
       try:
           return self._mean_lightness
       except AttributeError:
           self._mean_lightness = int(round(
               (self.red.lightest_fourth   + self.red.third_fourth   +
                self.blue.lightest_fourth  + self.blue.third_fourth  +
                self.green.lightest_fourth + self.green.third_fourth
               )/3.0
           ))

    def __iter__(self):
       return (x for x in (
           self.red.intensity,
           self.red.darkest_fourth,
           self.red.second_fourth,
           self.red.third_fourth,
           self.red.lightest_fourth,

           self.green.intensity,
           self.green.darkest_fourth,
           self.green.second_fourth,
           self.green.third_fourth,
           self.green.lightest_fourth,

           self.blue.intensity,
           self.blue.darkest_fourth,
           self.blue.second_fourth,
           self.blue.third_fourth,
           self.blue.lightest_fourth,

           self.adjusted.x,
           self.adjusted.y,

           self.suspicious,
      ))

    def CSV_header_line(self):
        return (
            "red_intensity,red_darkest_fourth,red_second_fourth,red_third_fourth,red_lightest_fourth," +
            "green_intensity,green_darkest_fourth,green_second_fourth,green_third_fourth,green_lightest_fourth," +
            "blue_intensity,blue_darkest_fourth,blue_second_fourth,blue_third_fourth,blue_lightest_fourth," +
            "adjusted_x,adjusted_y,was_suspicious"
        )

    def CSV(self):
        return ",".join(self)

    def __repr__(self):
        return repr(self.__dict)

_bad_stats = Stats([-1]*18)

class VoteData(object):
    "All of the data associated with a single vote"
    def __init__(self,
                 filename=None,
                 precinct=None,
                 jurisdiction=None,
                 contest=None,
                 choice=None,
                 prop=None,
                 coords=(-1, -1),
                 maxv=1,
                 stats=None,
                 image=None,
                 is_writein=None,
                 was_voted=None,
                 ambiguous=None):
        self.filename = filename
        self.precinct = precinct
        self.jurisdiction = None
        if contest is not None:
            self.jurisdiction = jurisdiction
        self.contest = None
        if contest is not None:
            self.contest = contest.description
        self.choice = None
        self.prop = None
        if choice is not None:
            self.choice = choice.description
            self.prop = choice.prop
        self.coords = coords
        self.maxv = maxv
        self.image = image
        self.was_voted = was_voted
        self.is_writein = is_writein
        self.ambiguous = ambiguous
        self.stats = stats
        if stats is None:
            self.stats = _bad_stats

    def __repr__(self):
        return repr(self.__dict__)

    def CSV(self):
        "return this vote as a line in CSV format"
        return ",".join((
            self.filename,
            self.precinct,
            self.contest,
            self.prop,
            self.oval,
            self.coords[0], self.coords[1],
            self.stats.CSV(),
            self.maxv,
            self.was_voted,
            self.ambiguous,
            self.is_writein, #BUG runtime insists this is an int, refuses to coerce to string :(
        ))

def results_to_CSV(results, heading=False):
    """Take a list of VoteData and return a generator of CSV 
    encoded information. If heading, insert a descriptive
    header line."""
    if heading:
        yield ( #note that this MUST be kept in sync with the CSV method on VoteData
            "filename,precinct,contest,prop,oval,x,y," +
            self.stats.CSV_header_line() + "," +
            "max_votes,was_voted,is_ambiguous,is_writein\n")
    for out in results:
        yield out.CSV() + "\n"

def results_to_mosaic(results):
    """return an image that is a mosaic of all ovals
    from a list of Votedata"""
    pass #TODO copy from main.py and rework

class Region(object):
    def __init__(self, x, y, description):
        self.x, self.y = x, y
        self.description = description

    def coords(self):
        return self.x, self.y

class Choice(Region):
     def __init__(self, x, y, description):
         super(Region, self).__init__(x, y, description)
         self.prop = prop

class Contest(Region):
     def __init__(self, x, y, w, h, prop, description):
         super(Region, self).__init__(x, y, w, h, description)
         self.jurisdiction = jurisdiction
         self.choices = []

     def bbox(self):
        return self.x, self.y, self.w, self.h

     def append(self, choice):
         self.choices.append(choice)


class BallotPage(object):
    def __init__(self, dpi, xoff, yoff, rot):
        self.dpi = int(dpi)
        self.xoff, self.yoff = int(xoff), int(yoff)
        self.rot = float(rot)

class Page(BallotPage):
    """A ballot page represented by an image and a Template"""
    def __init__(self, dpi, xoff, yoff, rot, filename=None, image=None, template=None):
        super(Page, self).__init__(dpi, xoff, yoff, rot)
        self.image = image
        self.filename = filename
        self.template = template
        #adjust.rotator generalized belongs here?

class Template(BallotPage):
    """A ballot page that has been fully mapped and is used as a
    template for similiar pages"""
    def __init__(self, dpi, xoff, yoff, rot, precinct, contests):
        super(Page, self).__init__(dpi, xoff, yoff, rot)
        self.precinct = precinct
        if contests is None:
            contests = []
        self.contests = contests

def Template_to_XML(ballot):
    acc = ['<?xml version="1.0"?>\n<BallotSide']
    def attrs(**kw):
        for name, value in kw.iteritems():
            acc.extend((" ", name, "='", value, "'"))
    ins = acc.append

    attrs(
        dpi=ballot.dpi,
        precinct=ballot.precinct,
        lx=ballot.xoff,
        ly=ballot.yoff,
        rot=ballot.rot
    )
    ins(">\n")

    for contest in ballot.contests:

        ins("\t<Contest")
        attrs(
            prop=contest.prop,
            text=contest.description,
            x=contest.x,
            y=contest.y,
            x2=contest.w,
            y2=contest.h
        )
        ins(">\n")

        for choice in contest.choices:
            ins("\t\t<oval")
            attrs(
                x=choice.x,
                y=choice.y,
                text=choice.description
            )
            ins(" />\n")

        ins("\t</Contest>\n")
    ins("</BallotSide>\n")
    return "".join(acc)

def Template_from_XML(xml):
    doc = xml.dom.minidom.parseString(xml)

    tag = lambda root, name: root.getElementByTagName(name)
    def attrs(root, *attrs):
        for attr in attrs:
            yield root.getAttribute(attr)

    side = tag(doc, "BallotSide")[0]
    dpi, precinct, xoff, yoff, rot = attrs(
        side,
        "dpi", "precinct", "lx", "ly", "rot"
    )
    contests = []

    for contest in tag(side, "Contest"):
        cur = Contest(*attrs(
            contest,
            "x", "y", "x2", "y2",
            "prop", "text"
        ))

        for choice in tag(contest, "oval"):
            cur.append(Choice(*attrs(
                 choice,
                 "x", "y", "text"
            )

        contests.append(cur)

    return Template(dpi, xoff, yoff, rot, precinct, contests)

