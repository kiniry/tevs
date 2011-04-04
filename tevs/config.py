import getopt
import ConfigParser
import logging
import const
import sys
import os

def yesno(cfg, grp, itm):
    so = cfg.get(grp, itm)
    s = so.strip().lower()
    if s in "yes y true t".split():
        return True
    if s in "no n false f".split():
        return False
    raise ValueError("% is not a valid choice for %s in %s" % (so, grp, itm))

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

def get_config():
     config = ConfigParser.ConfigParser()
     config.read("tevs.cfg")

     path = lambda v: os.path.expanduser(config.get("Paths", v))
     # first, get log file name so log can be opened
     const.logfilename = path("logfilename")
     if const.debug:
          logging.basicConfig(filename=const.logfilename, level=logging.DEBUG)
     else:
          logging.basicConfig(filename=const.logfilename, level=logging.INFO)

     logger = logging.getLogger("extraction")
     logger.addHandler(logging.StreamHandler(sys.stderr))
     const.logger = logger

     # then both log and print other config info for this run
     bwi = config.get("Sizes", "ballot_width_inches")
     bhi = config.get("Sizes", "ballot_height_inches")
     owi = config.get("Sizes", "oval_width_inches")
     ohi = config.get("Sizes", "oval_height_inches")
     cthoi = config.get("Sizes", "candidate_text_horiz_offset_inches")
     vthoi = config.get("Sizes", "vote_target_horiz_offset_inches")
     cwi = config.get("Sizes", "candidate_text_width_inches")
     chi = config.get("Sizes", "candidate_text_height_inches")
     mchi = config.get("Sizes", "minimum_contest_height_inches")
     acbi = config.get("Sizes", "allowed_corner_black_inches")
     allowed_tangent = config.get("Sizes", "allowed_tangent")

     vit = config.get("Votes", "vote_intensity_threshold")
     dpt = config.get("Votes", "dark_pixel_threshold")
     pit = config.get("Votes", "problem_intensity_threshold")

     tdpi = config.get("Scanner", "template_dpi")
     bdpi = config.get("Scanner", "ballot_dpi")

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
     const.dpi = const.ballot_dpi #oops
     const.template_dpi = int(tdpi)

     const.num_pages = int(config.get("Mode", "images_per_ballot"))
     const.layout_brand = config.get("Layout", "brand")
     const.on_new_layout = config.get("Mode", "on_new_layout")

     const.save_vops = yesno(config, "Mode", "save_vops")

     const.root = path("root")

     const.use_db = yesno(config, "Database", "use_db")
     const.dbname = config.get("Database", "name")
     const.dbpwd  = config.get("Database", "password")

     return logger

