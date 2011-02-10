import sys
import os
import time
from xml.dom import minidom
from xml.parsers.expat import ExpatError

from PILB import Image, ImageStat
import const
import util
import ocr

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
    # dictionaries of front and back templates encountered 
    # are attributes of Ballot class
    front_dict = {} #XXX need to rip out and replace with template_cache
    back_dict = {}
    def __init__(self, images, extensions):
        def iopen(fname):
            try:
                return self.flip(Image.open(fname).convert.("RGB"))
            except:
                fatal(0, "Could not open %s", fname)

        if not isinstance(fnames, basestring):
            self.pages = []
            for fname in fnames:
                image = iopen(fname)
                self.pages.append(Page(const.dpi, 0, 0, 0.0, fname, image))
        else:
            image = iopen(fnames)
            self.pages = [Page(const.dpi, 0, 0, 0.0, fnames, image)]

        self.extensions = extensions

        self.results = []

    def GetLayoutCode(self, page):
        """Find a code that we can use to identify
        all ballots with this layout"""
        if page.layout_code is not None:
            return page.layout_code
        return self.get_layout_code(page) #XXX need to set page.template.precinct = result, but may not have template yet so that needs to be wrangled somewhere at some point

    def FindLandmarks(self, page):
        """Find and record the landmarks for this page so that
        we can compute the locations of VOPs from the layout"""
        return self.find_landmarks(page)

    def BuildLayout(self, page):
        """When no layout is found for a page, we analyze the image,
        and construct a layout that we can use on all similiar page"""
        code = self.GetLayoutCode(page.image)
        layout = self.extensions.template[code]
        if layout is not None:
            return layout

        im = page.image.copy()
        rot = page.rot * 57.2957795 #180/pi
        #XXX unrotate image and cancel out xr, yr
        ideal = Page(const.dpi, xoff, yoff, rot, image=im)
        self.find_landmarks(ideal) 
        layout = self.build_layout(ideal)
        #XXX actually build template from page with contest data returned
             #from build_layout
        self.extensions.template[code] = layout
        return layout

    def CaptureVoteInfo(self):
        """tabulate results for every page"""
        for page in self.pages:
            self.CapturePageInfo(page)
        return self.results

    def CapturePageInfo(self, page):
        "tabulate the votes on a single page"
        T = self.transformer(self.rot, page.template.xoff, page.template.yoff)
        scale = page.dpi / page.template.dpi #should be in rotator--which should just be in Page?

        results = []
        def append(contest, choice, **kw):
            kw.update({
                "filename": page.filename,
                "precint":  page.template.precinct,
            }) 
            results.append(Ballot.VoteData(**kw))

        for contest in page.template.contests:
            if int(contest.h) - int(contest.y) < self.min_contest_height:
                for choice in contest.choices:
                     append(contest, choice) #mark all bad
                continue

            for choice in contest.choices:
                x, y, stats, crop, writein, voted, ambiguous = self.extract_VOP(
                    page, T, scale, choice
                )
                append(contest, choice, x, y, stats, crop, writein, voted, ambiguous)

        self.results.extend(results)
        return results

    def extract_VOP(self, page, choice): #possible to use the one in hart_ballot with some modification?
        raise NotImplementedError("subclasses must define an ExtractVOP method")

    def flip(self, im):
        """this method applies any 90 or 180 degree
        transformation required to make im read top to
        bottom, left to right"""
        raise NotImplementedError("subclasses must define a Flip method")

    def get_layout_code(self, page):
        raise NotImplementedError("subclasses must define a get_layout_code method")

    def find_landmarks(self, page):
        raise NotImplementedError("subclasses must define a find_landmarks method")

    def build_layout(self, page)
        raise NotImplementedError("subclasses must define a build_layout method")

class DuplexBallot(Ballot):
    """A Ballot that handles the troubles that arise from ballots whose
    backside do not have a unique layoutcode on the back page.
    As such get_layout_code will only be called on front pages."""
    def __init__(self, images, extensions):
       if isinstance(images, basestring) or len(image) < 2:
          raise BallotException("Duplex Ballots require at least 2 images")
       super(DuplexBallot, self).__init__(images, extensions)
       #need to duplicate some code here to handle some other stuff?
       #maybe just create a second index of self.pages?

    # does flip need to be duplex'd? Might be rarely used yet useful to some?

    def find_landmarks(self, page):
        self.find_front_landmarks(page)
        self.find_back_landmarks(page)

    def build_layout(self, page):
        self.build_front_layout(page)
        self.build_back_layout(page)

    def find_front_landmarks(self, page):
        raise NotImplementedError("subclasses must define a find_front_landmarks method")

    def build_front_layout(self, page)
        raise NotImplementedError("subclasses must define a build_front_layout method")

    def find_back_landmarks(self, page):
        return self.find_front_landmarks(page)

    def build_back_layout(self, page)
        self.build_front_layout(page)

class _bag(object):
    def __repr__(self):
        return repr(self.__dict__)

class IStats(object):
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

_bad_stats = IStats([-1]*18)

class VoteData(object):
    "All of the data associated with a single vote"
    def __init__(self,
                 filename=None,
                 precinct=None,
                 contest=None,
                 choice=None,
                 prop=None,
                 coords=(-1, -1),
                 maxv=1,
                 stats=_bad_stats,
                 image=None,
                 is_writein=None,
                 was_voted=None,
                 ambiguous=None):
        self.filename = filename
        self.precinct = precinct
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
    #TODO just copied from main.py: rework
    boximage = Image.new("RGB", (1650, 1200), color="white")
    draw = ImageDraw.Draw(boximage)
    keys = ballot.vote_box_images.keys()
    for i, key in enumerate(sorted(keys)):
        left = 50 + 150*(i % 10)
        right = 7*i
        boximage.paste(ballot.vote_box_images[key], (left, right))
        draw.text((left, right + 40), "%s_%04d_%04d" % tuple(key[:3]), fill="black")

class Region(object):
    def __init__(self, x, y, description):
        self.x, self.y = x, y
        self.description = description

    def coords(self):
        return self.x, self.y

class Choice(Region):
     def __init__(self, x, y, description):
         super(Choice, self).__init__(x, y, description)

class Contest(Region):
     def __init__(self, x, y, w, h, prop, description):
         super(Contest, self).__init__(x, y, description)
         self.prop = prop
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

    def as_template(self, precinct, contests):
	"""Given the precinct and contests, convert this page into a Template
        and store that objects as its own template"""
        self.template = Template(self.dpi, self.xoff, self.yoff, self.rot, precinct, contests)
        #TODO could very well put itself into the cache here
        return self.template

class Template(BallotPage):
    """A ballot page that has been fully mapped and is used as a
    template for similiar pages"""
    def __init__(self, dpi, xoff, yoff, rot, precinct, contests=None):
        super(Page, self).__init__(dpi, xoff, yoff, rot)
        self.precinct = precinct
        if contests is None:
            contests = []
        self.contests = contests

    def append(self, contest):
        self.contests.append(contest)

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
    doc = minidom.parseString(xml)

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
            )))

        contests.append(cur)

    return Template(dpi, xoff, yoff, rot, precinct, contests)

class TemplateCache(object):
    def __init__(self, location):
        self.cache = {}
        #attempt to prepopulate cache
        try:
            for file in os.listdir(location):
                data = util.readfrom(file, "<") #default to text that will not parse
                try:
                    tmpl = Template_from_XML(data)
                except ExpatError as e:
                    const.logger.exception("Could not parse " + file)
                    continue
                fname = os.path.basename(file)
                cache[fname] = tmpl
        except OSError:
            pass #no such location yet

    def __call__(self, id):
        return self.__getitem__(id)

    def __getitem__(self, id):
        try:
            return self.cache[id]
        except AttributeError:
            return None

    def __setitem__(self, id, template):
        cache[id] = template

    def save(self):
        util.mkdirp(location)
        for id, template in cache:
            fname = os.path.join(location, id)
            xml = Template_to_xml(template)
            util.writeto(fname, xml)

class NullTemplateCache(object):
    def __init__(self, loc):
        pass
    def __getitem__(self, id):
        pass
    def __setitem__(self, id, t):
        pass
    def save(self):
        pass

NullCache = NullTemplateCache("") #used as the default

def IsVoted(im, stats, choice): #should this be somewhere separate that's "plugged into" the #Ballot object?
    """determine if a box is checked
    and if so whether it is ambiguous"""
    intensity_test = stats.mean_intensity() < const.vote_intensity_threshold
    darkness_test  = stats.mean_darkness()  > const.dark_pixel_threshold
    voted = intensity_test or darkness_test  
    ambiguous = intensity_test != darkness_test
    return voted, ambiguous

def IsWriteIn(im, stats, choice):
    """determine if box is actually a write in"""
    d = choice.description.tolower().find
    if d("write") != -1 or d("vrit") != -1:
        return d("riter") == -1
    return False 

class Extensions(object):
    """A bag for all the various extension objects and functions
    to be passed around to anyone who needs one of these tools
    All extensions must be in the _xpts dict below and must be
    callable"""
    _xpts = {
        "ocr_engine":     ocr.tesseract, 
        "ocr_cleaner":    ocr.clean_ocr_text,
        "template_cache": NullCache,
        "IsWriteIn":      IsWriteIn,
        "IsVoted":        IsVoted,
    }
    def __init__(self, *kw):
        xkeys = self._xpts.keys()
        for x, o in kw.iteritems():
            if x not in xkeys:
                raise ValueError(x + " is not a recognized extension")
            xkeys.remove(x)
            if not callable(x):
                raise ValueError(x + " must be callable")
            self.__dict__[x] = o
        for k in xkeys: #set anything not set to the default
            self.__dict__[k] = self._xpts[k]

