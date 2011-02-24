import const
from PILB import Image, ImageDraw
import util_test
import Ballot

class ShillBallot(Ballot.Ballot):
    #XXX extract_VOP really really should just be in Ballot
    def extract_VOP(self, page, rotate, scale, choice):
        pass #only part needed by CapturePageInfo
# page needs a nonnil template, a rotator, dpi's set.
# 

def CapturePageInfo_test():
    assert False#needs extensions.transformer
    #can create a mock up page, just need to make sure boxes are extracted

def IsVoted_test(): #add loop that makes a speck in the center instead of
#filling the whole thing in
    carve = (25, 25, 75, 75) #filled entirely
    speck = (47, 47, 53, 53) #filled barely
    def do(color, box, v, a):
        i = Image.new("RGB", (100, 100), "#fff")
        d = ImageDraw.Draw(i)
        d.rectangle((20, 20, 80, 80), fill="#000")
        d.rectangle(carve, fill="#fff")
        d.rectangle(box, fill=("#" + color*3))
        s = Ballot.IStats(i.cropstats(100, 5, 20, 20, 60, 60, 1))
        vp, ap = Ballot.IsVoted(i, s, None)
        assert vp == v and ap == a

    const.vote_intensity_threshold = 200
    const.dark_pixel_threshold = 741

    for v, a, colors in (
            #voted  ambig  colors
            (True,  False, "05"),
            (True,  True,  "abcde"),
            (False, False, "f"),
        ):
        for color in colors:
            do(color, carve, v, a)

    for v, a, colors in (
            #voted  ambig  colors
            (True,  False, "0"),
            (True,  True,  "5"),
            (False, False, "abcdef"),
        ):
        for color in colors:
            do(color, speck, v, a)

