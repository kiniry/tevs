# rotation about a landmark point lx,ly by an amount equivalent to 
# that which caused dx x offset specified when dy is as specified
from __future__ import division
import math
import const

def rotate_pt_by(x,y,deltatang,lx,ly):
    """rotate x,y about lx,ly adjusting for tilt given by deltatang""" 

    ra = math.atan(deltatang) 
    cosra = math.cos(ra)
    sinra = math.sin(ra)
    
    origx = x
    origy = y

    # our y's are positive down, not positive up
    yforcalc = ly - y
    xforcalc = x - lx
    x = lx + (xforcalc * cosra - yforcalc * sinra)
    y = ly - (xforcalc * sinra + yforcalc * cosra)

    const.logger.debug("orig x,y (%d,%d) adjusted x,y (%d, %d)" % (origx, origy, x, y))
    return x, y

def translator(ideal, local, tilt):
    """
    takes:
      ideal=[(x0,y0), (x1,y1), (x2,y2)] - landmarks in layout
      local=[(x0,y0), (x1,y1), (x2,y2)] - landmarks in ballot
        where pair 0 is the upper left hand pair
          pair 1 is the upper right hand pair
          and pair 2 is lower left hand pair,
          for both layout and ballot, and all
          values are >= 0.
      tilt = tilt in radians
    returns:
      a function that given ideal coordinates returns the
      actual position

    we use this as our layout's landmarks throughout
    >>> orig = ((0,0), (10,0), (0,10))

    >>> t = translator(orig, #identity test
    ...     orig,
    ...     0) 
    >>> t(5, 7)
    (5, 7)
    >>> t(0, 0)
    (0, 0)
    >>> t(325839258, 32943924)
    (325839258, 32943924)

    >>> t = translator(orig, #only scaling required
    ...     ((0,0), (5,0),  (0,5)), 0)
    >>> t(10, 10)
    (5, 5)
    >>> t(10, 5)
    (5, 3)
 
    >>> t = translator(orig, #only scaling, other way
    ...     ((0,0), (20,0), (0,20)), 0)
    >>> t(10, 10)
    (20, 20)
    >>> t(5, 5)
    (10, 10)

    >>> t = translator(orig, #only translation required
    ...     ((5,1), (15,1), (5,11)), 0)
    >>> t(2, 2)
    (7, 3)
    >>> t(60, -9)
    (65, -8)

    >>> r = int(round(5*math.sqrt(2)))
    >>> #10/7 needed to counteract false scaling from rounding
    >>> #resulting from using irrationals in the example
    >>> t = translator(orig, #only rotation required
    ...     ((0,0), (r,r), (-r,r)), 1) #45 deg, cw (because of y inversion)
    >>> t(0, 0)
    (0, 0)
    >>> t(1, 1)
    (0, 1)
    >>> t(10, 10) #fails because of false scaling
    (0, 14)
    >>> t(50, 100) #fails because of false scaling
    (-35, 106)
    """

    #we don't need all the coords we ask for
    #but it's easier to ask for logically related
    #pairs than make the user remember which to
    #ignore.
    (xi0, yi0), (xi1, _),  (_,  yi2) = ideal
    (x0,  y0),  (x1,  x2), (y1, y2)  = local

    #get rotation factors
    at = math.atan(tilt)
    sin, cos = math.sin(at), math.cos(at)

    #rotate x0,y0,x1,y2 wrt ideal to compute scale and offset
    #so the slant doesn't skew the numbers
    
    xr0 = x0*cos - y0*sin
    yr0 = x0*sin + y0*cos
    xr1 = x1*cos - y1*sin
    yr2 = x2*sin + y2*cos

    #compute x and y scale factors
    Xs = (xr1 - xr0) / (xi1 - xi0)
    Ys = (yr2 - yr0) / (yi2 - yi0)
 
    #compute x and y offset
    X = xr0 - xi0
    Y = yr0 - yi0
  
    def trans(x, y):
        #shift by determined offset (X, Y)
        dx, dy = x + X, y + Y
        #rotate and scale
        x = Xs*cos*dx - Ys*sin*dy
        y = Xs*sin*dx + Ys*cos*dy
        #round and return
        x = int(round(x))
        y = int(round(y))
        return x, y
    return trans

if __name__ == '__main__':
    import doctest
    doctest.testmod()
