import os
import sys
import subprocess
import uuid
import re
import const
import util
import Ballot

# splits argument is conf_hll[x] from HartBallot, 
# a confirmed horizontal line list containing entries 
# with [integer, 'h'|'v'] where each integer 
# paired with 'h' is the y offset of a horizontal line, 
# presumably a contest start or end,
# and integers paired with 'v' are offsets of vote boxes
def ocr(im, contests, dpi, x1, x2, splits, xtnz): #XXX can replace all of this with a single Page at some point?
    """ ocr runs ocr and assembles appends to the list of BtRegions"""
    const.logger.debug("ocr handed x1 = %d, dpi = %d" % (x1, dpi))
    box_type = ""
    nexty = None
    cand_horiz_off = int(round(
        const.candidate_text_horiz_offset_inches*dpi
    ))
    vote_target_off = int(round(
        const.vote_target_horiz_offset_inches*dpi
    ))
    dpi16 = dpi/16
    dpi40 = dpi/40
    dpi_02 = int(round(dpi*0.02))
    invalid = lambda region: region[3] <= region[1]

    for n, split in enumerate(splits[:-1]):
        # for votes, we need to step past the vote area
        oval = False
        if split[1] == "v":
            startx = x1 + cand_horiz_off
            oval = True
        else:
            # while for other text, we just step past the border line
            startx = x1 + dpi40
            for y, dir in splits[n+1:]:
                if dir == 'h':
                    nexty = y
                    break

        croplist = (startx+1, split[0]+1, x2-2, splits[n+1][0]-2)
        if invalid(croplist):
            continue #XXX is this an error from somewhere?
        crop = im.crop(croplist)
        gaps = crop.gethgaps((128, 1))

        # we now need to split line by line at the gaps:
        # first, discard the first gap if it starts from 0
        if len(gaps) > 0 and gaps[0][1] == 0:
            gaps = gaps[1:]

        zone = crop

        # then, take from the start to the first gap start
        if len(gaps) != 0:
            zcroplist = (0, 0, crop.size[0]-1, gaps[0][1])
            if invalid(zcroplist):
                continue
            zone = crop.crop(zcroplist)

        text = xtnz.ocr_engine(zone)

        # then, take from the first gap end to the next gap start
        for m, gap in enumerate(gaps):
            end_of_this_gap = gap[3] - 2
            try:
                start_of_next_gap = gaps[m+1][1]
            except:
                start_of_next_gap = crop.size[1] - 2
            zone_croplist = (0,
                             end_of_this_gap,
                             crop.size[0]-1,
                             start_of_next_gap)
            if start_of_next_gap - end_of_this_gap < dpi16:
                continue #XXX is this not an error?
            zone = crop.crop(zone_croplist)
            text += xtnz.ocr_engine(zone)

        text = xtnz.ocr_cleaner(text)

        x, y, w = croplist[:3]
        if oval:
            # vote boxes begin 1/10" in from edge of contest box
            C = Ballot.Choice(
                x1 + vote_target_off,
                croplist[1] - dpi_02,
                text
            )
            contests[-1].append(C)
        else:
            contests.append(Ballot.Contest(x, y, w, nexty, None, text))

#XXX choice of OCR routine should be in config
_devnull = open("/dev/null", "w")
def tesseract(zone):
    "run the tesseract ocr engine on Image zone"
    #So we can run this function simultaneously from
    #multiple processes without fear of collissions
    badge = uuid.uuid4().hex
    ft = "/tmp/region-" + badge
    try:
        zone.save(ft + ".tif")
        p = subprocess.Popen(
            [
                "/usr/local/bin/tesseract", #XXX location should be in cfg 
                ft + ".tif", 
                ft
            ],
            stdin  = _devnull,
            stdout = _devnull,
            stderr = subprocess.PIPE
        )
        err = p.stderr.read()
        sts = os.waitpid(p.pid, 0)[1]
        if sts != 0 or len(err) > 100:
            const.logger.error(err)
            raise BallotException("OCR failed")
        text = util.readfrom(ft + ".txt")
    finally:
        for p in (".tif", ".txt"):
            util.rmf(ft + p)
    return text

#XXX choice of OCR text cleaner should be config
_scrub = re.compile(r'[^a-zA-Z0-9_ /]+')
def clean_ocr_text(text):
    "remove common ocr artifacts"
    text = text.strip(
              ).replace("\n",   "/"
              ).replace(",",    "comma"
              ).replace("'",    'squot' #XXX remove these two: make serializers do their own escaping
              ).replace('"',    'dquot'
              ).replace('\/',   '(M)'
              ).replace("IVI",  "(M)IVI"
              ).replace("|(M)", "(M)"
              ).replace("I(M)", "(M)"
              ).replace("(M)|", "M"
              ).replace("(M)I", "M"
              ).replace("|",    "I"
           )
    return _scrub.sub('', text)

