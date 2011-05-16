"""The Ballot module provides all the necessary tools for analyzing a set of
Ballot images. It is designed to be easy to use and easy to extend.
"""
import os
import math
from xml.dom import minidom
from xml.parsers.expat import ExpatError
import logging

import site; site.addsitedir(os.path.expanduser("~/tevs")) #XXX
from PILB import Image, ImageDraw, ImageFont, ImageChops
import const
import util
import ocr
import adjust

__all__ = [
    'BallotException', 'LoadBallotType', 'Ballot', 'DuplexBallot', 'IStats',
    'VoteData', 'results_to_CSV', 'results_to_mosaic', 'Choice', 'VOP', 
    'WriteIn', 'Jurisdiction', 'Contest', 'Page', 'Template',
    'Template_to_XML', 'Template_from_XML', 'TemplateCache', 'NullCache',
    'IsVoted', 'IsWriteIn', 'Extensions',
]

class BallotException(Exception):
    "Raised if analysis of a ballot image cannot continue"
    pass

def LoadBallotType(name):
    """LoadBallotType  takes a string describing the name of a kind of ballot
    layout and returns the appropriate subclass of Ballot for processing ballot
    images of that kind. The returned value must be called with the same
    arguments as the Ballot class's __init__ as documented below.  
    
    If no such kind is supported, raises ValueError
    """
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

class Ballot(object):
    """A Ballot takes a set of images and an Extension object. The set of
    images can be described as either a string representing the filename of a
    single ballot image or an iterable of filenames representing the filenames
    of an ordered set of ballot images.

    When the ballot is created, it attempts to open all of the files given to
    it via PIL. It also attempts to flip the images (see the flip method below)
    It builds a list of Page encapsulating the images.

    The Ballot class cannot be used directly. It must be used via a subclass
    that implements the required abstract methods (documented below). However,
    Ballot provides the interface for interacting with a subclass. To get the
    appropriate subclass use LoadBallotType and create Ballots from its
    returned factory.

    To use a Ballot, only call the methods that are AllCaps. To create a ballot
    subclass, override only the methods that are no_caps.

    Important data members are:
        * self.pages - a list of Page objects
        * self.extensions - the Extension object this object was
          instantiated with
        * self.results - a list of VoteData (empty until CapturePageInfo is
          called)
        * self.log - a useful reference to the default logger, see the Python
          logging module.
    """
    def __init__(self, images, extensions):
        #TODO should also take list of (fname, image) pairs 
        def iopen(fname):
            try:
                return self.flip(Image.open(fname).convert("RGB"))
            except BallotException:
                raise
            except KeyboardInterrupt:
                raise
            except IOError:
                raise BallotException("Could not open %s", fname)

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
        self.log = logging.getLogger('')

    def _page(self, page):
        if type(page) is not int:
            return page
        try:
            return self.pages[page]
        except IndexError:
            raise BallotException("Invalid page number")

    def MakeTemplates(self):
        """This is a helper method for when you ONLY want to make 
        templates from a set of pages, such as when you have a set of higher
        resolution images."""
        acc = []
        for page in self.pages:
            self.FindLandmarks(page)
            acc.append(self.BuildLayout(page))
        return acc

    def ProcessPages(self):
        """Helper to process and anaylze all the pages of this Ballot. There is
        no need to do anything else when using this method"""
        for page in self.pages:
            self.FindLandmarks(page)
            self.BuildLayout(page)
            self.CapturePageInfo(page)
        return self.results

    def GetLayoutCode(self, page=0):
        """Find a code that we can use to identify all ballots with this
        layout. 
        
        This layout code is used as the key in the template cache
        defined in the Extension object. It is typically the barcode on the
        side of a ballot image but it may be any code that uniquely describes a
        ballot.

        The associated abstract method is get_layout_code.
        
        GetLayoutCode is called with the page number or a particular Page
        object (that MUST be in self.pages). It returns the layout code, which
        is typically a string.
        
        If no layout code can be found, a BallotException is raised."""
        page = self._page(page)
        return self._GetLayoutCode(page)

    def _GetLayoutCode(self, page):
        if page.blank:
            return "blank"
        try:
            return self.laycode_cache[page.number]
        except KeyError:
            lc = self.get_layout_code(page)
            self.laycode_cache[page.number] = lc
            page.barcode = lc
            return lc

    def FindLandmarks(self, page=0):
        """Find and record the landmarks for this page so that we can compute
        the locations of VOPs from the layout. A landmark is any identifying
        characteristic of a ballot image that can be used to account for any
        slight rotation and shifting to the left and right of the image so that
        we may account for these minor distortions.
        
        The associated abstract method is find_landmarks.
        
        FindLandmarks is called with the page number or a particular Page
        object (that MUST be in self.pages). It returns the rotation, the x
        offset, and the y offset of the ballot image. This information is
        unimportant to most users and can in general be safely ignored.

        If no landmarks can be found, raises BallotException.
        """
        page = self._page(page)
        r, x, y = self.find_landmarks(page)
        page.rot, page.xoff, page.yoff = r, x, y
        return r, x, y

    def BuildLayout(self, page=0):
        """Create a Template from a Page. The Template contains all of the
        layout information and textual descriptions of any page with the same
        layout code. If there is already a template associated with the page's
        layout code in the template cache of this instance's Extension object,
        that template will be used, avoiding the expensive operation of
        building a layout.

        The associated abstract method is build_layout.

        BuildLayout is called with the page number or a particular Page
        object (that MUST be in self.pages). It returns the Template created
        from the specified Page. 
        
        If it cannot build a sensible layout, it will raise a BallotException.
        """
        pagenum = page
        page = self._page(page)
        code = self.GetLayoutCode(page)
        tmpl = self.extensions.template_cache[code]
        if tmpl is not None:
            page.template = tmpl
            return tmpl

        self.log.info(
            "Building a template for %s may take up to a minute",
            code,
        )
        # derotate image before trying to build layout.
        # page.rot is tangent, equiv to rot in radians for small values
        # convert to degrees for call to Image.rotate
        r2d = 180/3.14
        page.image = page.image.rotate(-r2d * page.rot, Image.BILINEAR)
        self.FindLandmarks(pagenum)
        tree = self.build_layout(page)
        if len(tree) == 0:
            raise BallotException('No layout was built')
        tree = self.OCRDescriptions(page, tree)
        tmpl = page.as_template(code, tree)
        self.extensions.template_cache[code] = tmpl
        page.template = tmpl
        return tmpl

    def OCRDescriptions(self, page, tree): #XXX should this be private?
        "This is called automatically by BuildLayout"
        return tree #STAGE OCRwalk
        for subtree in tree:
            _ocr1(self.extensions, page, subtree)
        return tree

    def CapturePageInfo(self, page=0):
        """
        CapturePageInfo walks the layout and creates a VoteData object for each
        VOP.

        CapturePageInfo is called with the page number or a particular Page
        object (that MUST be in self.pages). It returns a list of VoteData for
        the specific page and adds that to self.results (note that calling this
        on multiple self.pages out of order will mean that the votes in
        self.results will not be in the same order as that of self.pages)

        CapturePageInfo never raises BallotException on its own, but it does
        call the IsVoted and IsWriteIn methods of the Extensions object it was
        instantiated with, and they are allowed to raise. However, the default
        methods included by this module do not.
        """
        page = self._page(page)
        self._CapturePageInfo(page)
        
    def _CapturePageInfo(self, page):
        if page.blank:
            return []
        if page.template is None:
            self.BuildLayout(page)
        R = self.extensions.transformer
        T = R(page.rot, page.template.xoff, page.template.yoff)
        scale = page.dpi / page.template.dpi #should be in rotator--which should just be in Page?

        results = []
        def append(contest, choice, **kw):
            kw.update({
                "contest":  contest,
                "choice":   choice,
                "filename": page.filename,
                "barcode":  page.template.barcode,
                "number":   page.number
            }) 
            results.append(VoteData(**kw))

        for contest in page.template.contests:
            if int(contest.y2) - int(contest.y) < self.min_contest_height: #XXX only defined insubclass!!!!!!
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
        #should ONLY extract VOPs, have a separate method for seeing if they're voted
        raise NotImplementedError("subclasses must define an ExtractVOP method")

    def flip(self, im):
        """This method applies any 90 or 180 degree transformation required to 
        make im read top to bottom, left to right.
        
        If it is not overriden in a subclass it simply returns the image as is
        and assumes that no scanned images can be flipped. There is no
        associated Flip method as this is called in Ballot.__init__
        """
        return im

    def get_layout_code(self, page):
        """get_layout_code takes a Page and returns a string representing a
        layout code. It MUST locate and interpret some data on a ballot
        image that can uniquely determine all images that have the same layout.

        It should only be called indirectly via GetLayoutCode.

        If no layout code can be found, it must raise a BallotException.
        """
        raise NotImplementedError("subclasses must define a get_layout_code method")

    def find_landmarks(self, page):
        """find_landmarks takes a Page and returns the rotation, x offset, and
        y offset resulting from scanning a ballot image. Rotation is a float.
        The x and y offsets are ints.

        landmarks are one or more known points on a ballot image that can be
        used in isolation or conjunction to infer the displacement naturally
        caused during scanning. 

        It should only be called indirectly via FindLandmarks.

        If no landmarks can be found, it must raise a BallotException. If the
        landmarks are offset too far or rotated too much for any further
        analysis to continue, find_landmarks MUST raise a BallotException.
        """
        raise NotImplementedError("subclasses must define a find_landmarks method")

    def build_layout(self, page):
        """build_layout takes a Page and computes a Template.

        It should only be called indirectly via BuildLayout.

        If a layout cannot be built, for example because a scanned image is
        incomplete, it must raise BallotException.
        """
        raise NotImplementedError("subclasses must define a build_layout method")

class DuplexBallot(Ballot):
    """A Ballot that handles the troubles that arise from ballots whose
    backside do not have a unique layoutcode on the back page. 

    It is in many ways identical to Ballot, however every no_caps method is
    overriden and calls no_caps_front and no_caps_back. All no_caps_back
    methods by default simply call their associated no_caps_front, so
    operations that do not require special consideration for back pages need
    only be overriden once. For example, overriding build_layout_front but
    not build_layout_back will call build_layout_front on both of a pair of
    ballot images. But overriding build_layout_front and build_layout_back will
    cause build_layout_front to be called on the first of each pair of images
    and build_layout_back to be called on the last of each pair of images.

    Note that the above implies that a subclasser should not override the
    no_caps methods but the no_caps_front and, where appropriate, the
    no_caps_back methods instead. The exception is get_layout_code which is
    unchanged and only called on the front page of each ballot pair.

    The AllCaps interface is the same except that each method returns a pair of
    data for each pair of pages-unless otherwise specified. If given an index 
    to the page number, the index refers to the pair-that is the first and 
    second image is index 0, the third and fourth image is index 1, and so on.

    DuplexBallot must be given an iterable of image names that must be of even
    length.

    """
    def __init__(self, images, extensions):
        if isinstance(images, basestring) or len(images) < 2:
            raise TypeError("Duplex Ballots require at least 2 images")

        if len(images)%2:
            raise TypeError("Requires an even number of ballot images")
        self.pages = []
        number = 0
        for fnames in zip(images[::2], images[1::2]):
            try:
                f = self.flip_front(Image.open(fnames[0]).convert("RGB"))
                b = self.flip_back(Image.open(fnames[1]).convert("RGB"))
            except BallotException:
                raise
            except KeyboardInterrupt:
                raise
            except IOError:
                raise BallotException("Could not open one of %s", fnames)
            if not self.is_front(f):
                f, b = b, f
                fnames = fnames[::-1]
            self.pages.append((
                Page(
                    dpi=const.dpi,
                    filename=fnames[0],
                    image=f,
                    number="%df" % number,
                ),
                Page(
                    dpi=const.dpi,
                    filename=fnames[1],
                    image=b,
                    number="%db" % (number + 1,),
                )
            ))
            number += 2

        self.extensions = extensions
        self.results = []
        self.laycode_cache = {}
        self.log = logging.getLogger('')

    def _page(self, page):
        if type(page) is not int:
            try:
                if len(page) != 2:
                    raise TypeError("page must either be length 2 or an int")
            except AttributeError:
                raise TypeError("page must either be length 2 or an int")
            return page
        try:
            if page%2:
                raise BallotException("Invalid page number")
            return (self.pages[page], self.pages[page+1])
        except IndexError:
            raise BallotException("Invalid page number")

    def _swap(self, page):
        front, back = self._page(page)
        if type(page) != int:
            for i, p in enumerate(self.pages):
                if p[0] == front:
                    page = i
                    break
        #permute
        front.number, back.number = back.number, front.number
        self.pages[page] = (back, front)
        return back, front

    def GetLayoutCode(self, page=0):
        """Only returns layout code for first page in pair-next page is that
        layout code + "back" """
        front, back = self._page(page)
        try:
            return self._GetLayoutCode(front)
        except BallotException: #no layout code found, try swapping front&back
            code = self._GetLayoutCode(back)
            #we didn't raise so back and front are most likely swapped
            #in order to permute in place we need page to be an int, if not we 
            #recreate it
            self._swap(page)
            return code

    def FindLandmarks(self, page=0):
        "returns ((rf, rx, ry), (rb, rx, ry))"
        front, back = self._page(page)
        try:
            r, x, y = self.find_front_landmarks(front)
        except BallotException:
            #see if the error was caused by front and back being switched
            front, back = self._swap(page)
            r, x, y = self.find_front_landmarks(front)
        front.rot, front.xoff, front.yoff = r, x, y
        r2, x2, y2 = self.find_back_landmarks(back)
        back.rot, back.xoff, back.yoff = r2, x2, y2
        return (r, x, y), (r2, x2, y2)

    def _BuildLayout1(self, page, lc, tree):
        if len(tree) == 0:
            raise BallotException('No front layout was built')
        tree = self.OCRDescriptions(page, tree)
        tmpl = page.as_template(lc, tree)
        self.extensions.template_cache[lc] = tmpl
        page.template = tmpl
        return tmpl

    def BuildLayout(self, page=0):
        "returns (front_layout, back_layout)"
        front, back = self._page(page)
        lc = self.GetLayoutCode(page)
        ft = self.extensions.template_cache[lc]
        bt = self.extensions.template_cache["%sback" % (lc,)]
        if ft is not None:
            front.template = ft
        else:
            tree = self.build_front_layout(front)
            ft = self._BuildLayout1(front, lc, tree)
        if bt is not None:
            back.template = bt
        else:
            tree = self.build_back_layout(back)
            bt = self._BuildLayout1(back, "%sback" % (lc,), tree)
        return ft, bt

    #CapturePageInfo can just call super, but must make sure template is built first
    def CapturePageInfo(self, page=0):
        "returns list of results of both pages processed"
        front, back = self._page(page)
        return self._CapturePageInfo(front) + self._CapturePageInfo(back)

    def is_front(self, im):
        """If unimplemented, returns True. Note that this is called After
        flip_front/flip_back"""
        return True

    def flip_front(self, im):
        "if unimplemented, returns im unmodified"
        return im

    def find_front_landmarks(self, page):
        "see documentation for find_landmarks in Ballot"
        raise NotImplementedError("subclasses must define a find_front_landmarks method")

    def build_front_layout(self, page):
        "see documentation for build_layout in Ballot"
        raise NotImplementedError("subclasses must define a build_front_layout method")

    def flip_back(self, im):
        "if unimplemented, calls flip_front"
        return self.flip_front(im)

    def find_back_landmarks(self, page):
        "if unimplemented, calls find_front_landmarks"
        return self.find_front_landmarks(page)

    def build_back_layout(self, page):
        "if unimplemented, calls build_front_layout"
        return self.build_front_layout(page)

def _ocr1(extensions, page, node):
    "this is the backing routine for Ballot.OCRDescriptions"
    crop = page.image.crop(node.bbox())
    if type(node) in (Jurisdiction, Contest, Choice):
        temp = extensions.ocr_engine(crop)
        temp = extensions.ocr_cleaner(temp)
        node.description = temp
    else:
        node.image = crop
    for child in node.children():
        _ocr1(extensions, page, child)

class _bag(object):
    def __repr__(self):
        return repr(self.__dict__)

class IStats(object): #TODO move to cropstats or new pilb module
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
    """All of the data associated with a single vote.

    The below information is relative to the Page this VOP came from.
       * self.filename - the filename of the ballot image
       * self.barcode - the layout code of the ballot
       * self.jurisdiction - the text of the jurisdiction header of this VOP
       * self.contest - the text of the contest header of this VOP
       * self.choice - the text of this VOP
       * self.coords - the pair of (x, y) coordinates of the upperleft corner
          of the VOP
       * self.maxv - the max votes allowed in the contest of this VOP
       * self.stats - an IStats object for self.image
       * self.image - a crop from the image in self.filename containig the VOP
          (including write in if applicable)
       * self.is_writein - Boolean 
       * self.was_voted - Boolean
       * self.ambiguous - True if we're not 100% sure a VOP was indeed voted.
       * self.number - the page number this VOP came from

    Called with no keyword arguments it creates the special VoteData object
    represinting an improperly processed vote.
    """
    def __init__(self,
                 filename=None,
                 barcode=None,
                 jurisdiction=None, 
                 contest=None, 
                 choice=None,
                 coords=(-1, -1), #XXX just save bbox?
                 maxv=1,
                 stats=_bad_stats,
                 image=None,
                 is_writein=None,
                 was_voted=None,
                 ambiguous=None,
                 number=-1):
        self.filename = filename
        self.barcode = barcode
        self.contest = contest
        self.jurisdiction = jurisdiction
        if contest is not None:
            self.contest = contest.description
        self.choice = None
        if choice is not None:
            self.choice = choice.description
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
            self.barcode,
            self.jurisdiction,
            self.contest,
            self.choice,
            self.coords[0], self.coords[1],
            self.stats.CSV(),
            self.maxv,
            self.was_voted,
            self.ambiguous,
            self.is_writein,
        ))

def results_to_CSV(results, heading=False): #TODO need a results_from_CSV
    """Take a list of VoteData and return a generator of CSV 
    encoded information. If heading, insert a descriptive
    header line."""
    if heading:
        yield ( #note that this MUST be kept in sync with the CSV method on VoteData
            "filename,barcode,jurisdiction,contest,choice,x,y," +
            _stats_CSV_header_line() + "," +
            "max_votes,was_voted,is_ambiguous,is_writein\n")
    for out in results:
        yield out.CSV() + "\n"

#get font size
_sszx, _sszy = ImageFont.load_default().getsize(14*'M')
#inset size, px
_xins, _yins = 10, 5
def results_to_mosaic(results):
    """Return an image that is a mosaic of all ovals
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
        label = "%s:%04dx%04d%s%s%s" % (
            vop.number,
            vop.coords[0],
            vop.coords[1],
            "-" if vop.was_voted or vop.ambiguous else "",
            "!" if vop.was_voted else "",
            "?" if vop.ambiguous else ""
        )
        text(x, y, label)

    #tile write ins
    for i, wrin in enumerate(wrins): #XXX this part is screwed up and I need to fix it
        d, m = divmod(i, 4)
        x = m*wxs + _xins
        y = d*wys + yle
        moz.paste(wrin.image, (x, y))
        y += _yins + wriny
        label = "%d_%04d_%04d" % (wrin.number, wrin.coords[0], wrin.coords[1])
        text(x, y, label)

    return moz

class Region(object):
    def __init__(self, x, y, x2, y2):
        self.x, self.y, self.x2, self.y2 = x, y, x2, y2
        self.description = None #there will be one of these two but not both
        self.image = None

    def coords(self):
        return self.x, self.y

    def bbox(self):
        return self.x, self.y, self.x2, self.y2

    def children(self):
        return []


#A choice has and must have one and only one VOP--VOP is an essentially useless
#class but it is way easier to think about it this way instead of having one
#object with two bounding boxes
class Choice(Region):
    """An item in a layout hierarchy representing an individual vote
    opportunities text, as a bounding box, and, if it has been OCRed, by a
    string, self.description.
    
    After creation, self.VOP should be set to an instance of VOP. If it is
    WriteIn, self.description should remain None.
    """ 
    def __init__(self, x, y, description): #XXX need to add x2, y2, vop, axe description
        super(Choice, self).__init__(x, y, -1, -1) #XXX
        self.VOP = None
        self.description = description #XXX change to None

    def children(self):
        """returns self.VOP or []"""
        return self.VOP or []

class VOP(Region):
    """The bounding box of a VOP. If this is the VOP of a write in, set
    self.WriteIn to a WriteIn object for the write in's bounding box.
    """
    def __init__(self, x, y, x2, y2):
        super(VOP, self).__init__(x, y, x2, y2)
        self.WriteIn = WriteIn

    def children(self):
        """return self.WriteIn or []"""
        return self.WriteIn or []

class WriteIn(Region):
    """The bounding box for a WriteIn, not including the VOP of the WriteIn. It
    is the child of its VOP, so in:
        
         Contest:
         
            [ ] Choice a

            [ ] Choice b
         
            [ ] Write in

            `____________`
    

    WriteIn will be the child of the VOP to the left of the Choice "Write in" """
    def __init__(self, x, y, x2, y2):
        super(VOP, self).__init__(x, y, x2, y2)

class Jurisdiction(Region):
    """The top level item in a layout hierarchy. Its children are a list of
    Contest's. A ballot may have zero or more Jurisdictions. If there are no
    Jurisdictions, all of the top level elements in the template must be
    Contest's, and the children of a Jurisdiction must be Contest's. An example
    of a Jurisdiction is a ballot containing contests for both a state and
    county election: In this case, the template should have a state
    Jurisdiction, containing all of the Contest's for the state election; and a
    county Jurisdiction, containing all of the Contest's for the county
    election. The bounding box of a Jurisdiction should only enclose the text
    of the description, such as the word 'State'."""
    def __init__(self, x, y, x2, y2):
        super(Jurisdiction, self).__init__(x, y, x2, y2)
        self.contests = []

    def append(self, contest):
        self.contests.append(contest)

    def children(self):
        return self.contests

class Contest(Region):
    """Either the top level item in a layout hierarchy or the child of a
    Jurisdiction. A Contest is the bounding box of the text describing a single
    vote. It's children are the Choice's available in that contest. For
    example:

         Vote for one:

             [ ] Billy

             [ ] Jane

    The contest would be the bounding box around the text "Vote for one:" and
    its children would be the Choice's for Billy and Jane.
    """
    def __init__(self, x, y, x2, y2, prop, description): #XXX axe prop/description
        super(Contest, self).__init__(x, y, x2, y2)
        self.prop = prop #XXX del
        self.w = x2 #XXX del
        self.h = y2 #XXX del
        self.description = description #XXX change to None
        self.choices = []

    def append(self, choice):
        self.choices.append(choice)

    def children(self):
        return self.choices

class _scannedPage(object):
    def __init__(self, dpi, xoff, yoff, rot, image):
        self.dpi = int(dpi)
        self.xoff, self.yoff = int(xoff), int(yoff)
        self.rot = float(rot)
        self.image = image

def _fixup(im, rot, xoff, yoff):
    return im.rotate(180*rot/math.pi)

class Page(_scannedPage):
    """A ballot page represented by an image and a Template. It is created by
    Ballot.__init__ for each ballot image. Important properties:
    
       * self.filename - the name of the file of the ballot image
       * self.image - the PIL image created from self.filename
       * self.dpi - an integer specifying the DPI of the image
       * self.template - The Template created by Ballot.BuildLayout or None
       * self.barcode - The barcode associated with self.template
       * self.blank - a special sentinel indicator for pages intentionally left
          blank
       * self.number - the page number
       * self.xoff - the x offset of the ballot within the ballot image
       * self.yoff - the y offset of the ballot within the ballot image
       * self.rot - the rotation of the ballot within the ballot image

    Note that self.rot is in radians, which is used by python's math library,
    but that the rotate method in PIL uses degrees.
    """
    def __init__(self, dpi=0, xoff=0, yoff=0, rot=0.0, filename=None, image=None, template=None, number=0):
        super(Page, self).__init__(dpi, xoff, yoff, rot, image)
        self.filename = filename
        self.template = template
        self.number = number
        self.blank = False
        self.barcode = ""

    def as_template(self, barcode, contests):
        """Given the barcode and contests, convert this page into a Template
        and store that objects as its own template. This is handled by
        Ballot.BuildLayout"""
        t = Template(self.dpi, self.xoff, self.yoff, self.rot, barcode, contests, self.image) #XXX update
        self.template = t
        return t

    def fixup(self):
        """Undo the xoff, yoff, and rot of self.image. This is not necessary
        but useful for saving "pretty versions" of ballot images, as template
        cache does for the images that templates are created from."""
        self.image = _fixup(self.image)
        self.rot, self.xoff, self.yoff = 0.0, 0, 0
        return self.image

    def __iter__(self):
        if self.template is None:#XXX should be jurisdictions
            raise StopIteration()
        return iter(self.template)

    def __repr__(self):
        return str(self.__dict__)

class Template(_scannedPage):
    """A ballot page that has been fully mapped and is used as a
    template for similiar pages. A template MAY have an associated
    image but it is not guranteed.
    
    A Template is very similiar to a Page but it contains the layout
    information of every Page with the same barcode. As an iterator, it yields
    all the top level elements stored in the template in the order they were
    discovered."""
    def __init__(self, dpi, xoff, yoff, rot, barcode, contests, image=None):
        super(Template, self).__init__(dpi, xoff, yoff, rot, image)
        self.barcode = barcode
        self.contests = contests #TODO should be jurisdictions

    def append(self, contest):
        "add a new contest to the template"
        self.contests.append(contest)

    def __iter__(self):
        if self.contests is None: #XXX both should be jurisdictions
            raise StopIteration()
        return iter(self.contests)

    def __repr__(self):
        return str(self.__dict__)

def Template_to_XML(template): #XXX needs to be updated for jurisdictions
    """Takes a template object and returns a serialization in XML format"""
    acc = ['<?xml version="1.0"?>\n<BallotSide']
    def attrs(**kw):
        for name, value in kw.iteritems(): #TODO change ' < > et al to &ent;
            name, value = str(name), str(value)
            acc.extend((" ", name, "='", value, "'"))
    ins = acc.append

    attrs(
        dpi=template.dpi,
        barcode=template.barcode,
        lx=template.xoff,
        ly=template.yoff,
        rot=template.rot
    )
    ins(">\n")

    #TODO add jurisdictions loop
    for contest in template.contests: #XXX should be jurisdiction
        ins("\t<Contest")
        attrs(
            prop=contest.prop,#XXX del
            text=contest.description,
            x=contest.x,
            y=contest.y,
            x2=contest.x2,
            y2=contest.y2
        )
        ins(">\n")

        for choice in contest.choices:
            ins("\t\t<oval")
            attrs(
                x=choice.x,
                y=choice.y,
                x2=choice.x2,
                y2=choice.y2,
                text=choice.description
            )
            ins(" />\n")
            #TODO add loop for vops that checks for writeins

        ins("\t</Contest>\n")
    ins("</BallotSide>\n")
    return "".join(acc)

def Template_from_XML(xml): #XXX needs to be updated for jurisdictions
    """Takes an XML string generated from Template_to_XML and returns a
    Template"""
    doc = minidom.parseString(xml)

    tag = lambda root, name: root.getElementsByTagName(name)
    def attrs(root, *attrs):
        get = root.getAttribute
        for attr in attrs:
            if type(attr) is tuple:
                t, a = attr
                yield t(get(a))
            else:
                yield get(attr)

    side = tag(doc, "BallotSide")[0]
    dpi, barcode, xoff, yoff, rot = attrs(
        side,
        (int, "dpi"), "barcode", (int, "lx"), (int, "ly"), (float, "rot")
    )
    contests = []

    for contest in tag(side, "Contest"):
        cur = Contest(*attrs(
            contest,
            (int, "x"), (int, "y"), (int, "x2"), (int, "y2"),
            "prop", "text"
        ))

        for choice in tag(contest, "oval"):
            cur.append(Choice(*attrs(
                 choice,
                 (int, "x"), (int, "y"), 
                 #(int, "x2"), (int, "y2"), #STAGE choice
                 "text"
            )))

        contests.append(cur)

    return Template(dpi, xoff, yoff, rot, barcode, contests)

BlankTemplate = Template(0, 0, 0, 0.0, "blank", [])

class TemplateCache(object):
    """A TemplateCache stores Templates by their barcode and loads and saves
    them in a directory location. When instantiated, it loads all templates
    into ram for quick access. It does not automatically save templates, but
    provides methods for saving them. It uses Template_to_XML/Template_from_XML
    for the serialization and deserialization of the template. For storing and
    retrieving templates from the cache it behaves as a standard dictionary.
    """
    def __init__(self, location):
        self.cache = {}
        self.location = location
        util.mkdirp(location)
        self.log = logging.getLogger('')
        #attempt to prepopulate cache
        try:
            for file in os.listdir(location):
                if os.path.splitext(file)[1] == ".jpg":
                    continue
                rfile = os.path.join(location, file)
                data = util.readfrom(rfile, "<") #default to text that will not parse
                try:
                    tmpl = Template_from_XML(data)
                except ExpatError:
                    if data != "<":
                        self.log.exception("Could not parse " + file)
                    continue
                fname = os.path.basename(file)
                self.cache[fname] = tmpl
        except OSError:
            self.log.info("No templates found")

    def __call__(self, id):
        return self.__getitem__(id)

    def __getitem__(self, id):
        id = str(id)
        if id == "blank":
            return BlankTemplate
        try:
            return self.cache[id]
        except KeyError:
            self.log.info("No template found for %s", id)
            return None

    def __setitem__(self, id, template):
        id = str(id)
        if id == "blank":
            return
        self.cache[id] = template
        self.log.info("Template %s created", id)

    def save(self, id):
        id = str(id)
        "write the template id to disk at self.location"
        fname = os.path.join(self.location, id)
        if not os.path.exists(fname):
            template = self.cache[id]
            if template is None:
                return
            xml = Template_to_XML(template)
            util.writeto(fname, xml)
            if template.image is not None:
                try:
                    im = _fixup(
                        template.image, 
                        template.rot, 
                        template.xoff,
                        template.yoff
                    )
                    im.save(fname + ".jpg")
                except IOError:
                    util.fatal("could not save image of template")
            self.log.info("new template %s saved", fname)

    def save_all(self):
        "save all templates that are not already saved"
        for id in self.cache.iterkeys():
            self.save(id)

class NullTemplateCache(object):
    "A Template Cache that is a no-op for all methods"
    def __init__(self, loc):
        pass
    def __call__(self, id):
        pass
    def __getitem__(self, id):
        if id == "blank":
            return BlankTemplate
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

def IsWriteIn(im, stats, choice): #XXX build_layout must set
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

