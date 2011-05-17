"""config.py offers two services: configuring the default logger and reading
the config file for the TEVS utilities."""
import ConfigParser
import logging
import const
import sys
import os
import errno

__all__ = ['logger', 'get']

def yesno(cfg, grp, itm):
    so = cfg.get(grp, itm)
    s = so.strip().lower()
    if s in "yes y true t".split():
        return True
    if s in "no n false f".split():
        return False
    raise ValueError("% is not a valid choice for %s in %s" % (so, grp, itm))

def logger(file):
    "configure the default logger to use file"
    level = logging.INFO
    if hasattr(const, 'debug') and const.debug:
        level = logging.DEBUG

    logging.basicConfig(
        filename=file,
        format="%(asctime)s: %(levelname)s: %(message)s",
        level=level
    )

    logger = logging.getLogger('')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(
        logging.Formatter("%(message)s\n")
    )
    logger.addHandler(console)
    return logger

def get(cfg_file="tevs.cfg"):
    "get the tevs configuration file in ."
    config = ConfigParser.ConfigParser()
    config.read(cfg_file)

    path = lambda v: os.path.expanduser(config.get("Paths", v))
    const.root = path("root")
    try:
        const.incoming = path("incoming")
    except ConfigParser.NoOptionError:
        const.incoming = os.path.join(const.root, "unproc")

    # first, get log file name so log can be opened
    const.logfilename = os.path.join(const.root, "log.txt") #XXX only needed for scancontrol, view

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
    try:
        hsxoi = config.get("Sizes", "hotspot_x_offset_inches")
        const.hotspot_x_offset_inches = float(hsxoi)
    except ConfigParser.NoOptionError:
        const.hotspot_x_offset_inches = 0.0
    try:
        hsyoi = config.get("Sizes", "hotspot_y_offset_inches")
        const.hotspot_y_offset_inches = float(hsyoi)
    except ConfigParser.NoOptionError:
        const.hotspot_y_offset_inches = 0.0
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

    const.use_db = yesno(config, "Database", "use_db")
    const.dbname = config.get("Database", "name")
    const.dbuser  = config.get("Database", "user")

