# rotation about a landmark point lx,ly by an amount equivalent to 
# that which caused dx x offset specified when dy is as specified
from __future__ import division
import math

def rotator(tang, xl, yl):
    """
    Given the difference in rotation between a ballot template
    and a particular ballot and the position of the landmark
    in the ballot template, return a function that given a
    coordinate pair in a template returns the corresponding
    coordinates in that particular ballot.

    >>> r = rotator(0, 88, 122)
    >>> r(98, 1030)
    (98, 1030)
    >>> r(464, 280)
    (464, 280)
    >>> r(832, 1746)
    (832, 1746)
    >>> r = rotator(.0687, 88, 122)
    >>> r(98, 1030)
    (160, 1027)
    >>> r(464, 280)
    (474, 254)
    >>> r(832, 1746)
    (942, 1691)
    """
    ra = math.atan(tang)
    cos, sin = math.cos(ra), math.sin(ra)
    def r(x, y):
        """
        Transform (x, y) from the layout into
        (x, y) in the particular ballot
        """
        # shift ballot relative to layout
        xs = x - xl
        ys = yl - y

        # rotate about layout's orgin
        xr = xs*cos - ys*sin
        yr = xs*sin + ys*cos

        # shift back to ballot coords
        xd = xl + xr
        yd = yl - yr

        return int(round(xd)), int(round(yd))
    return r

def rotate_pt_by(x,y,deltatang,lx,ly):
    """rotate x,y about lx,ly adjusting for tilt given by deltatang""" 

    ra = math.atan(deltatang) 
    cosra = math.cos(ra)
    sinra = math.sin(ra)
    origx = x
    origy = y

    # our y's are positive down, not positive up
    xforcalc = x - lx
    yforcalc = ly - y
    x = lx + (xforcalc * cosra - yforcalc * sinra)
    y = ly - (xforcalc * sinra + yforcalc * cosra)

    return x, y


if __name__ == '__main__':
    import doctest
    doctest.testmod()
