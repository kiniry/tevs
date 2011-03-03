import os
from xml.dom import minidom
from xml.parsers.expat import ExpatError

from PILB import Image, ImageDraw, ImageFont
import const
import util
import ocr
import adjust

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
    name = name[0].upper() + name[1:] + "Ballot"
    return getattr(module, name)

class Ballot(object): #XXX a better name may be something like BallotAnalyzer
    def __init__(self, images, extensions):
        #TODO should also take list of (fname, image) pairs 
        def iopen(fname):
            try:
                return self.flip(Image.open(fname).convert("RGB"))
            except:
                util.fatal("Could not open %s", fname)

        self.pages = []
        def add_page(number, fname):
            self.pages.append(Page(
                dpi=const.dpi,
                filename=fname,
                image=iopen(fname),
                number=number,
            ))

        if not isinstance(images, basestring):
            for i, fname in enumerate(images):
                add_page(i, fname)
        else: #just a filename
            add_page(0, images)

        self.extensions = extensions
        self.results = []
        self.laycode_cache = {}

    def ProcessPages(self):
        for page in self.pages:
            self.FindLandmarks(page)
            self.GetLayout(page)
            self.CapturePageInfo(page)
        return self.results #each page has its results?

    def GetLayoutCode(self, page):
        """Find a code that we can use to identify
        all ballots with this layout"""
        try:
            return self.laycode_cache[page.number]
        except KeyError:
            lc = self.get_layout_code(page)
            if len(lc) == 0:
                raise BallotException('Nonsense layout code')
            self.laycode_cache[page.number] = lc
            return lc

    def FindLandmarks(self, page):
        """Find and record the landmarks for this page so that
        we can compute the locations of VOPs from the layout"""
        r, x, y = self.find_landmarks(page)
        page.rot, page.xoff, page.yoff = r, x, y
        return r, x, y

    def GetLayout(self, page):
        """When no layout is found for a page, we analyze the image,
        and construct a layout that we can use on all similiar page"""
        code = self.GetLayoutCode(page)
        tmpl = self.extensions.template_cache[code]
        if tmpl is not None:
            page.template = tmpl
            return tmpl

        contests = self.build_layout(page)
        if len(contests) == 0:
            raise BallotException('No layout was built')
        tmpl = page.as_template(code, contests)
        self.extensions.template_cache[code] = tmpl
        return tmpl

    def CapturePageInfo(self, page):
        "tabulate the votes on a single page"
        if page.template is None:
            raise BallotException("Cannot capture page info without template")
        R = self.extensions.transformer
        T = R(page.rot, page.template.xoff, page.template.yoff)
        scale = page.dpi / page.template.dpi #should be in rotator--which should just be in Page?

        results = []
        def append(contest, choice, **kw):
            kw.update({
                "contest":  contest,
                "choice":   choice,
                "filename": page.filename,
                "precinct": page.template.precinct,
                "number":   page.number
            }) 
            results.append(VoteData(**kw))

        for contest in page.template.contests:
            if int(contest.h) - int(contest.y) < self.min_contest_height: #XXX only defined insubclass!!!!!!
                for choice in contest.choices:
                     append(contest, choice) #mark all bad
                continue

            for choice in contest.choices:
                x, y, stats, crop, voted, writein, ambiguous = self.extract_VOP(
                    page, T, scale, choice
                )
                append(contest, choice, 
                    coords=(x, y), stats=stats, image=crop,
                    is_writein=writein, was_voted=voted, 
                    ambiguous=ambiguous
                )

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

    def build_layout(self, page):
        raise NotImplementedError("subclasses must define a build_layout method")

class DuplexBallot(Ballot):
    """A Ballot that handles the troubles that arise from ballots whose
    backside do not have a unique layoutcode on the back page.
    As such get_layout_code will only be called on front pages."""
    def __init__(self, images, extensions):
       if isinstance(images, basestring) or len(images) < 2:
          raise BallotException("Duplex Ballots require at least 2 images")
       super(DuplexBallot, self).__init__(images, extensions)
       #need to duplicate some code here to handle some other stuff?
       #maybe just create a second index of self.pages?

    # does flip need to be duplex'd? Might be rarely used yet useful to some?

    def ProcessPages(self):
        raise NotImplementedError("TODO")
        pass #needs to process image set pairwise

    def flip(self, im):
        self.flip_front(im)
        self.flip_back(im)

    def find_landmarks(self, page):
        self.find_front_landmarks(page)
        self.find_back_landmarks(page)

    def build_layout(self, page):
        self.build_front_layout(page)
        self.build_back_layout(page)

    def flip_front(self, im):
        raise NotImplementedError("subclasses must define a flip_front method")

    def find_front_landmarks(self, page):
        raise NotImplementedError("subclasses must define a find_front_landmarks method")

    def build_front_layout(self, page):
        raise NotImplementedError("subclasses must define a build_front_layout method")

    def flip_back(self, im):
        return self.flip_front(im)

    def find_back_landmarks(self, page):
        return self.find_front_landmarks(page)

    def build_back_layout(self, page):
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
       self._mean_intensity = None
       self._mean_darkness = None
       self._mean_lightness = None

    def mean_intensity(self):
        if self._mean_intensity is None:
            self._mean_intensity = int(round(
                (self.red.intensity +
                 self.green.intensity +
                 self.blue.intensity)/3.0
            ))
        return self._mean_intensity

    def mean_darkness(self):
       """compute mean darkness over each channel using first
       two quartiles."""
       if self._mean_darkness is None:
           self._mean_darkness = int(round(
               (self.red.darkest_fourth   + self.red.second_fourth   +
                self.blue.darkest_fourth  + self.blue.second_fourth  +
                self.green.darkest_fourth + self.green.second_fourth
               )/3.0
           ))
       return self._mean_darkness

    def mean_lightness(self):
        """compute mean lightness over each channel using last
        two quartiles."""
        if self._mean_lightness is None:
            self._mean_lightness = int(round(
                (self.red.lightest_fourth   + self.red.third_fourth   +
                 self.blue.lightest_fourth  + self.blue.third_fourth  +
                 self.green.lightest_fourth + self.green.third_fourth
                )/3.0
            ))
        return self._mean_lightness

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

    def CSV(self):
        return ",".join(str(x) for x in self)

    def __repr__(self):
        return str(self.__dict__)

def _stats_CSV_header_line():
    return (
        "red_intensity,red_darkest_fourth,red_second_fourth,red_third_fourth,red_lightest_fourth," +
        "green_intensity,green_darkest_fourth,green_second_fourth,green_third_fourth,green_lightest_fourth," +
        "blue_intensity,blue_darkest_fourth,blue_second_fourth,blue_third_fourth,blue_lightest_fourth," +
        "adjusted_x,adjusted_y,was_suspicious"
    )

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
                 ambiguous=None,
                 number=-1):
        self.filename = filename
        self.precinct = precinct
        self.contest = None
        if contest is not None:
            self.contest = contest.description
        self.choice = None
        self.prop = prop
        if choice is not None:
            self.choice = choice.description
            try:
                self.prop = choice.prop
            except AttributeError:
                pass
        self.coords = coords
        self.maxv = maxv
        self.image = image
        self.was_voted = was_voted
        self.is_writein = is_writein
        self.ambiguous = ambiguous
        self.stats = stats
        self.number = number

    def __repr__(self):
        return str(self.__dict__)

    def CSV(self):
        "return this vote as a line in CSV format"
        return ",".join(str(s) for s in (
            self.filename,
            self.precinct,
            self.contest,
            self.choice,
            self.prop,
            self.coords[0], self.coords[1],
            self.stats.CSV(),
            self.maxv,
            self.was_voted,
            self.ambiguous,
            self.is_writein,
        ))

def results_to_CSV(results, heading=False):
    """Take a list of VoteData and return a generator of CSV 
    encoded information. If heading, insert a descriptive
    header line."""
    if heading:
        yield ( #note that this MUST be kept in sync with the CSV method on VoteData
            "filename,precinct,contest,choice,prop,x,y," +
            _stats_CSV_header_line() + "," +
            "max_votes,was_voted,is_ambiguous,is_writein\n")
    for out in results:
        yield out.CSV() + "\n"

#get font size
_sszx, _sszy = ImageFont.load_default().getsize(14*'M')
#inset size, px
_xins, _yins = 10, 5
def results_to_mosaic(results):
    """return an image that is a mosaic of all ovals
    from a list of Votedata"""
    # Each tile in the mosaic:
    #  _______________________
    # |           ^           |
    # |         _yins         |
    # |           v           |
    # |        _______        |
    # | _xins | image | _xins |
    # |<----->|_______|<----->| vop or wrin
    # |           ^           |
    # |         _yins         |
    # |           v           |
    # |        _______        |
    # | _xins | _ssz  | _xins |
    # |<----->|_______|<----->| label
    # |           ^           |
    # |         _yins         |
    # |           v           |
    # |_______________________|
    #
    # We don't know for sure whether the label or the image is longer so we
    # take the max of the two.
    vops, wrins = [], []
    vopx, vopy = 0, 0
    for r in results:
        if r.is_writein:
            wrins.append(r)
        else:
            #grab first nonnil image to get vop size
            if vopx == 0 and r.image is not None:
                vopx, vopy = r.image.size
            vops.append(r)

    wrinx, wriny = 0, 0
    if wrins:
        wrinx, wriny = wrins[0].image.size

    # compute area of a vop + decorations
    xs = max(vopx, _sszx) + 2*_xins
    ys = vopy + _sszy + 3*_yins
    # compute area of a wrin + decorations
    wxs = max(wrinx, _sszx) + 2*_xins
    wys = wriny + _sszy + 3*_yins
    if wrinx == 0:
        wxs, wxs = 0, 0 #no wrins

    #compute dimensions of mosaic
    xl = max(10*xs, 4*wxs)
    yle = ys*(1 + len(vops)/10) #end of vop tiling
    yl =  yle + wys*(1 + len(wrins)/4)
    yle += _yins - 1 #so we don't have to add this each time

    moz = Image.new("RGB", (xl, yl), color="white")
    draw = ImageDraw.Draw(moz)
    text = lambda x, y, s: draw.text((x, y), s, fill="black")
    #tile vops
    for i, vop in enumerate(vops):
        d, m = divmod(i, 10)
        x = m*xs + _xins
        y = d*ys + _yins
        if vop.image is not None:
            moz.paste(vop.image, (x, y))
        else:
            X = x + _xins
            Y = y + _yins
            draw.line((X, Y, X + vopx, Y + vopy), fill="red")
            draw.line((X, Y + vopy, X + vopx, Y), fill="red")
        y += _yins + vopy
        label = "%d:%04dx%04d%s%s%s" % (
            vop.number,
            vop.coords[0],
            vop.coords[1],
            "-" if vop.was_voted or vop.ambiguous else "",
            "!" if vop.was_voted else "",
            "?" if vop.ambiguous else ""
        )
        text(x, y, label)

    #tile write ins
    for i, wrin in enumerate(wrins):
        d, m = divmod(i, 4)
        x = m*wxs + _xins
        y = d*wys + yle
        moz.paste(wrin.image, (x, y))
        y += _yins + wriny
        label = "%d_%04d_%04d" % (wrin.number, wrin.coords[0], wrin.coords[1])
        text(x, y, label)

    return moz

class Region(object):
    def __init__(self, x, y, description):
        self.x, self.y = x, y
        self.description = description

    def coords(self):
        return self.x, self.y

class Choice(Region):
     def __init__(self, x, y, description):
         super(Choice, self).__init__(x, y, description)

     def __repr__(self):
         return "\n\t".join(str(p) for p in self.__dict__.iteritems())

class Contest(Region): #XXX prop is weird, what do we do with it?
     def __init__(self, x, y, w, h, prop, description):
         super(Contest, self).__init__(x, y, description)
         self.w = w
         self.h = h
         self.prop = prop
         self.choices = []

     def bbox(self):
        return self.x, self.y, self.w, self.h

     def append(self, choice):
         self.choices.append(choice)

     def __repr__(self):
         s = "Contest:%s, prop:%s\n" % (self.description, self.prop)
         s += "\n\t".join(str(s) for s in self.choices)
         return s


class _scannedPage(object):
    def __init__(self, dpi, xoff, yoff, rot):
        self.dpi = int(dpi)
        self.xoff, self.yoff = int(xoff), int(yoff)
        self.rot = float(rot)

class Page(_scannedPage):
    """A ballot page represented by an image and a Template"""
    def __init__(self, dpi=0, xoff=0, yoff=0, rot=0.0, filename=None, image=None, template=None, number=0):
        super(Page, self).__init__(dpi, xoff, yoff, rot)
        self.image = image
        self.filename = filename
        self.template = template
        self.number = number

    def as_template(self, precinct, contests):
        """Given the precinct and contests, convert this page into a Template
        and store that objects as its own template"""
        t = Template(self.dpi, self.xoff, self.yoff, self.rot, precinct, contests)
        self.template = t
        return t

    def __repr__(self):
        return str(self.__dict__)

class Template(_scannedPage):
    """A ballot page that has been fully mapped and is used as a
    template for similiar pages"""
    def __init__(self, dpi, xoff, yoff, rot, precinct, contests):
        super(Template, self).__init__(dpi, xoff, yoff, rot)
        self.precinct = precinct
        self.contests = contests

    def append(self, contest):
        self.contests.append(contest)

    def __repr__(self):
        return str(self.__dict__)

def Template_to_XML(ballot):
    acc = ['<?xml version="1.0"?>\n<BallotSide']
    def attrs(**kw):
        for name, value in kw.iteritems():
            acc.extend((" ", str(name), "='", str(value), "'"))
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

    tag = lambda root, name: root.getElementsByTagName(name)
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

    dpi, xoff, yoff, rot = int(dpi), int(dpi), int(yoff), float(rot)
    return Template(dpi, xoff, yoff, rot, precinct, contests)

class TemplateCache(object):
    def __init__(self, location):
        self.cache = {}
        self.location = location
        #attempt to prepopulate cache
        try:
            for file in os.listdir(location):
                data = util.readfrom(file, "<") #default to text that will not parse
                try:
                    tmpl = Template_from_XML(data)
                except ExpatError:
                    if data != "<":
                        const.logger.exception("Could not parse " + file)
                    continue
                fname = os.path.basename(file)
                self.cache[fname] = tmpl
        except OSError:
            const.logger.info("No templates found")

    def __call__(self, id):
        return self.__getitem__(id)

    def __getitem__(self, id):
        try:
            return self.cache[id]
        except KeyError:
            return None

    def __setitem__(self, id, template):
        self.cache[id] = template

    def save(self):
        util.mkdirp(self.location)
        for id, template in self.cache.iteritems():
            fname = os.path.join(self.location, id)
            xml = Template_to_XML(template)
            util.writeto(fname, xml)

class NullTemplateCache(object):
    def __init__(self, loc):
        pass
    def __call__(self, id):
        pass
    def __getitem__(self, id):
        pass
    def __setitem__(self, id, t):
        pass
    def save(self):
        pass

NullCache = NullTemplateCache("") #used as the default

def IsVoted(im, stats, choice):
    """determine if a box is checked
    and if so whether it is ambiguous"""
    intensity_test = stats.mean_intensity() < const.vote_intensity_threshold
    darkness_test  = stats.mean_darkness()  > const.dark_pixel_threshold
    voted = intensity_test or darkness_test  
    ambiguous = intensity_test != darkness_test
    return voted, ambiguous

def IsWriteIn(im, stats, choice):
    """determine if box is actually a write in
    >>> test = lambda t: "ok" if IsWriteIn(None, None, Choice(0,0,t)) else None
    >>> test("Garth Marenghi")
    >>> test("is a write in")
    'ok'
    >>> test("John Riter for emperor")
    >>> test("vvritten")
    'ok'
    """
    d = lambda x: choice.description.lower().find(x) != -1
    if d("write") or d("vrit"):
        return not d("riter")
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
        "transformer":    adjust.rotator,
    }
    def __init__(self, **kw):
        xkeys = self._xpts.keys()
        for x, o in kw.iteritems():
            if x not in xkeys:
                raise ValueError(x + " is not a recognized extension")
            xkeys.remove(x)
            if not callable(o):
                raise ValueError(x + " must be callable")
            self.__dict__[x] = o
        for k in xkeys: #set anything not set to the default
            self.__dict__[k] = self._xpts[k]

