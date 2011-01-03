# rotation about a landmark point lx,ly by an amount equivalent to 
# that which caused dx x offset specified when dy is as specified
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
    yforcalc = -(y-ly)
    xforcalc = x-lx
    ysinra = yforcalc * sinra
    ycosra = yforcalc * cosra
    xresult = (xforcalc * cosra) - (yforcalc * (sinra))
    yresult = (xforcalc * sinra) + (yforcalc * cosra)
    #switch result back to positive down
    y = -yresult + ly
    x = xresult+lx
    const.logger.debug("orig x,y (%d,%d) adjusted x,y (%d, %d)"%(origx,origy,x,y))
    return (x,y)

