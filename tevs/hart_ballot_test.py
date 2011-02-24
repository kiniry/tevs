import util_test
import Ballot
import hart_ballot


def flip_test():
    assert False
    #Needs to pass a good ballot, flipped and unflipped
    #doesn't matter if it flips things that aren't

def find_landmarks_test():
    assert False
    #give it a good ballot with a series of offsets and rotations and
    #compare against handcalced rotations. This is really testing 
    #gethartlandmarks

def get_layout_code_test():
    assert False
    #give it a few with and without barcodes or bad barcodes

def extract_VOP_test():#XXX move if/when pushed to superclass
    assert False
    # This we can give fake data, make a mosaic to cut off with a 
    # like set of fake Contest/Choice trees

def build_layout_test():
    assert False
    #generate images with "just" layout, like an empty grid of sorts
    #and give it a fake ocr and fake con/cho's and check them against
    #each other

