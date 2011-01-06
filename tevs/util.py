import sys
import os
import getopt
import ConfigParser
import logging
import const
from Ballot import Ballot

def get_args():
     """Get command line arguments"""
     try:
          opts, args = getopt.getopt(sys.argv[1:],
                                     "tdrq",
                                     [ "templates",
                                       "debug",
                                       "retry-on-missing",
                                       "question-user"
                                       ]
                                     ) 
     except getopt.GetoptError:
          print "usage:"
          sys.exit(2)
     templates_only = False
     debug = False
     retry = False
     question = False
     for opt, arg in opts:
          if opt in ("-t", "--templates"):
               templates_only = True
          if opt in ("-d", "--debug"):
               debug = True
          if opt in ("-r", "--retry-on-missing"):
               retry = True
          if opt in ("-q", "--question-user"):
               question = True
               
     const.templates_only = templates_only
     const.debug = debug
     const.retry = retry
     const.question = question
     print "OPTS", opts
     print "ARGS", args

def get_config():
     config = ConfigParser.ConfigParser()
     config.read("tevs.cfg")

     # first, get log file name so log can be opened
     const.logfilename = config.get("Paths","logfilename")
     if const.debug:
          logging.basicConfig(filename=const.logfilename,level=logging.DEBUG)
     else:
          logging.basicConfig(filename=const.logfilename,level=logging.INFO)

     logger = logging.getLogger("extraction")
     logger.addHandler(logging.StreamHandler(sys.stderr))
     const.logger = logger

     # then both log and print other config info for this run
     bwi = config.get("Sizes","ballot_width_inches")
     bhi = config.get("Sizes","ballot_height_inches")
     owi = config.get("Sizes","oval_width_inches")
     ohi = config.get("Sizes","oval_height_inches")
     cthoi = config.get("Sizes","candidate_text_horiz_offset_inches")
     vthoi = config.get("Sizes","vote_target_horiz_offset_inches")
     cwi = config.get("Sizes","candidate_text_width_inches")
     chi = config.get("Sizes","candidate_text_height_inches")
     mchi = config.get("Sizes","minimum_contest_height_inches")
     acbi = config.get("Sizes","allowed_corner_black_inches")
     allowed_tangent = config.get("Sizes","allowed_tangent")
     vit = config.get("Votes","vote_intensity_threshold")
     dpt = config.get("Votes","dark_pixel_threshold")
     pit = config.get("Votes","problem_intensity_threshold")
     tdpi = config.get("Scanner","template_dpi")
     bdpi = config.get("Scanner","ballot_dpi")
     const.ballot_width_inches = float(bwi)
     const.ballot_height_inches = float(bhi)
     const.oval_width_inches = float(owi)
     const.oval_height_inches = float(ohi)
     const.candidate_text_horiz_offset_inches = float(cthoi)
     const.vote_target_horiz_offset_inches = float(vthoi)
     const.candidate_text_width_inches = float(cwi)
     const.candidate_text_height_inches = float(chi)
     const.minimum_contest_height_inches = float(mchi)
     const.allowed_corner_black_inches = float(acbi)
     const.allowed_tangent = float(allowed_tangent)
     const.vote_intensity_threshold = float(vit)
     const.problem_intensity_threshold = float(pit)
     const.dark_pixel_threshold = int(dpt)
     const.ballot_dpi = int(bdpi)
     const.template_dpi = int(tdpi)
     const.layout_brand = config.get("Layout","brand")
     const.on_new_layout = config.get("Mode","on_new_layout")
     const.proc = config.get("Paths","proc")
     const.unproc = config.get("Paths","unproc")
     const.results = config.get("Paths","results")
     const.writeins = config.get("Paths","writeins")
     const.boxes_root = config.get("Paths","boxes_root")
     save_vops = config.get("Mode","save_vops")
     const.save_vops = save_vops.strip() == "True"
     pfs = config.get("Paths","procformatstring")
     ufs = config.get("Paths","unprocformatstring")
     rfs = config.get("Paths","resultsformatstring")
     mfs = config.get("Paths","masksformatstring")
     templates_path = config.get("Paths","templates")
     backtemplates_path = config.get("Paths","backtemplates")
     const.procformatstring = pfs.replace(
         "thousands","%03d").replace("units","%06d")
     const.unprocformatstring = ufs.replace(
         "thousands","%03d").replace("units","%06d") 
     const.resultsformatstring = rfs.replace(
         "thousands","%03d").replace("units","%06d")
     const.masksformatstring = mfs.replace(
         "thousands","%03d").replace("units","%06d")
     const.templates_path = templates_path
     const.backtemplates_path = backtemplates_path

     print "Log file", const.logfilename
     print "Ballot width in inches", const.ballot_width_inches
     print "Ballot height in inches", const.ballot_height_inches
     print "Voteop width in inches", const.oval_width_inches
     print "Voteop height in inches", const.oval_height_inches
     print "Format string for processed files:", const.procformatstring
     print "substituted with 123456", const.procformatstring % (
          123456/1000,123456)
     print "Format string for unprocessed, results, and masks files:"
     print const.unprocformatstring
     print const.unprocformatstring % (123456/1000,123456)
     print const.resultsformatstring
     print const.resultsformatstring % (123456/1000,123456)
     print const.masksformatstring
     print const.masksformatstring % (123456/1000,123456)
     logger.info( "Ballot width in inches %f"%const.ballot_width_inches)
     logger.info( "Ballot height in inches %f"%const.ballot_height_inches)
     logger.info( "Voteop width in inches %f"%const.oval_width_inches)
     logger.info( "Voteop height in inches %f"%const.oval_height_inches)
     logger.info( "Format string for processed files: %s" 
                  % const.procformatstring)
     logger.info( "substituted with 123456: %s" 
                  % (const.procformatstring % (123456/1000,123456)))
     logger.info( "Format strings for unprocessed, results, masks files:")
     logger.info( const.unprocformatstring)
     logger.info( const.unprocformatstring % (123456/1000,123456))
     logger.info( const.resultsformatstring)
     logger.info( const.resultsformatstring % (123456/1000,123456))
     logger.info( const.masksformatstring)
     logger.info( const.masksformatstring % (123456/1000,123456))
     return logger

def initialize_from_templates():
     """Read layout info from templates directory."""
     try:
          # for each file in templates directory, 
          # add contents to fronts dictionary in Ballot module,
          # keyed by name; create None entry in backs dictionary
          print "Reading templates from %s" % const.templates_path
          for f in os.listdir(const.templates_path):

               print f,

               ff = open("%s/%s" % (const.templates_path,f),"r")
               template_text = ff.read()
               Ballot.front_dict[f] = template_text
               Ballot.precinct_dict[f] = "1"
               ff.close()
               try:
                    ff = open("%s/%s" % (const.backtemplates_path,f),"r")
                    template_text = ff.read()
                    Ballot.back_dict[f] = template_text
                    ff.close()
               except: 
                    pass
          print
     except Exception, e:
          const.logger.warning("Could not load existing template entries.")
          const.logger.warning(e)


def get_maxv_from_text(text):
     """Look for hint about maximum votes allowed in contest"""
     maxv = 1
     if (text.find("to 2") > 1):
          maxv = 2
     elif (text.find("to 3") > 1):
          maxv = 3
     elif (text.find("to 4") > 1):
          maxv = 4
     elif (text.find("to 5") > 1):
          maxv = 5
     if (text.find("Two") > 1):
          maxv = 2
     elif (text.find("Thre") > 1):
          maxv = 3
     elif (text.find("Four") > 1):
          maxv = 4
     elif (text.find("Five") > 1):
          maxv = 5
     return maxv

def image_diff(im1,im2,x,y,deltatang,lx,ly):
    """NOT IN USE"""
    # scale down the images and offsets by scalefactor
    # rotate im2 by deltatang and offset it by scaled x and y,
    # to bring im2 into approx alignment with im1,
    # thicken the dark spots on im1, and use
    # ImageChops.strays to spot areas on im2 that are dark 
    # where the corresponding area on im1 is not;
    # we might also want to report/return
    # the total number of nonblack pixels in the screened image
    # (x',y') =  (ax + by + c, dx + ey + f)

    #xresult = (xforcalc * cosra) - (yforcalc * (sinra))
    #yresult = (xforcalc * sinra) + (yforcalc * cosra)
    scaledown = 2.
    newsize1 = (int(round(im1.size[0]/scaledown)),
                int(round(im1.size[1]/scaledown)))
    newsize2 = (int(round(im2.size[0]/scaledown)),
                int(round(im2.size[1]/scaledown)))
    im1 = im1.resize(newsize1,Image.BILINEAR)
    im2 = im2.resize(newsize2,Image.BILINEAR)
    im1 = im1.thicken()
    # in addition to thickening image1, all vote areas should be darkened !!!
    affine = [math.cos(deltatang),
              -math.sin(deltatang),
              int(round(x/scaledown)),
              math.sin(deltatang),
              math.cos(deltatang),
              int(round(y/scaledown))
              ]
    # first offset the image by landmarks so the landmarks are at 0,0
    im2 = im2.transform(im2.size,Image.AFFINE, affine, Image.BILINEAR)
    im2 = ImageChops.strays(im1,im2)
    return im2



# rotation about a landmark point lx,ly by an amount equivalent to 
# that which caused dx x offset specified when dy is as specified
def rotate_pt_by(x,y,deltatang,lx,ly):
    """rotate x,y about lx,ly adjusting for tilt given by dx and dy""" 

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
    const.logger.debug("orig x,y (%d,%d) adjusted x,y (%d, %d)"
                       % (origx,origy,x,y)
                       )
    return (x,y)


def rotate_pt(x,y,hdist,dx,dy,lx,ly):
    """NOT IN USE"""
    # rotate x,y about lx,ly adjusting for tilt given by dx and dy""" 
    # We are adding one to dy here; check to see if there's any opportunity
    # to round dy earlier in the calling sequence...!!!
    if (hdist == 0):
        ra = 0
    else:
        ra = math.atan(float(-(dy+1))/hdist) 
                      
    # adjust from degrees to radians
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
    logger.debug("orig x,y (%d,%d) adjusted x,y (%d, %d)"%(origx,origy,x,y))
    return (x,y)

# Remove punctuation and special chars from text, except for space
def alnumify(instring):
     filtered = filter(lambda x: (x.isalnum() or x.isspace()) and x, instring)
     return filtered

# Reasonable text assumptions
def clean_text(instring):
    """Make reasonable guesses about known common OCR failures"""
    # letter I surrounded by lower case letters is really letter ell
    # united States is United States, etc...
    # vvnte VVnte is Write
    # MO_ is NO_
    # l\/l is M
    instring = instring.replace("united States","United States")
    instring = instring.replace("MO ", "NO ")
    instring = instring.replace("l\/l", "M")
    instring = instring.replace("VVnte","Write")
    instring = instring.replace("Wnte","Write")
    instring = instring.replace("vv","W")
    return instring

def get_region_text(im, x1, y1, x2, y2):
     """ read text from image (may no longer be in use"""
     # return text within provided bounds
     if x1<1:x1=1
     if y1<1:y1=1
     if x2>=im.size[0]:x2=im.size[0]-1
     if y2>=im.size[1]:y2=im.size[1]-1
     if y1>=y2:
          return("")
     logger.debug("Cropping %d %d %d %d" % (x1,y1,x2,y2))
     crop = im.crop((x1,y1,x2,y2))
     contrast = crop.point(threshold48table)
     crop.save("regionorig.tif")
     contrast.save("region.tif")
     p = subprocess.Popen(["/usr/local/bin/tesseract", "region.tif", "region"])
     sts = os.waitpid(p.pid,0)[1]
     #os.system("/usr/local/bin/tesseract region.tif region 2>/dev/null")
     tempf = open("region.txt")
     text = tempf.read()
     tempf.close()
     return clean_text(text.replace("\n","/").replace(",",";"))


