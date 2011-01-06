from PILB import Image, ImageStat
import os
import sys
import subprocess
import re
import const
from Ballot import BtRegion

# splits argument is conf_hll[x] from HartBallot, 
# a confirmed horizontal line list containing entries 
# with [integer, 'h'|'v'] where each integer 
# paired with 'h' is the y offset of a horizontal line, 
# presumably a contest start or end,
# and integers paired with 'v' are offsets of vote boxes
def ocr(im,br,dpi,x1,x2,splits):
    """ ocr runs ocr and assembles appends to the list of BtRegions"""
    const.logger.debug("ocr handed x1 = %d, dpi = %d" % (x1,dpi))
    box_type = ""
    text = ""
    nexty = None
    for n in range(len(splits)-1):
        print "*",
        text = ""
        # for votes, we need to step past the vote area
        if splits[n][1]=="v":
            startx = x1 + int(
                round(const.candidate_text_horiz_offset_inches*dpi))
            box_type = "v"
        # while for other text, we just step past the border line
        else:
            startx = x1 + (dpi/40)
            box_type = "h"
            for m in range(n+1,len(splits)):
                if splits[m][1]=='h':
                    nexty = splits[m][0]
                    break
        croplist = (startx+1,splits[n][0]+1,x2-2,splits[n+1][0]-2)
        text = ""

        if croplist[3]<=croplist[1]:
            const.logger.debug( "Negative height to croplist")
            continue
        crop = im.crop(croplist)
        gaps = crop.gethgaps((128,1))
        # we now need to split line by line at the gaps:
        # first, discard the first gap if it starts from 0
        if len(gaps)==0:
            pass
        elif gaps[0][1] == 0:
            gaps = gaps[1:]
        # then, take from the start to the first gap start
        if len(gaps)==0:
            # just use crop
            zone = crop
        else:
            zone_croplist = (0,0,crop.size[0]-1, gaps[0][1])
            #print "Zone croplist",zone_croplist
            if zone_croplist[3]<=zone_croplist[1]:
                #print "Negative height to zone_croplist"
                continue
            zone = crop.crop(zone_croplist)
        zone.save("/tmp/region.tif")
        p = subprocess.Popen(["/usr/local/bin/tesseract", 
                              "/tmp/region.tif", 
                              "/tmp/region"],
                             stdout = subprocess.PIPE,
                             stderr = subprocess.PIPE
                             )
        errstuff = p.stderr.read()
        outstuff = p.stdout.read()
        sts = os.waitpid(p.pid,0)[1]
        if len(errstuff)>100:
            print errstuff
            pdb.set_trace()
        tempf = open("/tmp/region.txt")
        text += tempf.read()
        tempf.close()
        # then, take from the first gap end to the next gap start
        for m in range(len(gaps)):
            print "*",
            end_of_this_gap = gaps[m][3]-2
            try:
                start_of_next_gap = gaps[m+1][1]
            except:
                start_of_next_gap = crop.size[1]-2
            zone_croplist = (0,
                             end_of_this_gap,
                             crop.size[0]-1,
                             start_of_next_gap)
            if (start_of_next_gap - end_of_this_gap) < (dpi/16):
                continue
            zone = crop.crop(zone_croplist)
            #enhancer = ImageEnhance.Sharpness(zone)
            #enhancer.enhance(2.0).save("region.tif")
            zone.save("/tmp/region.tif")
            p = subprocess.Popen(["/usr/local/bin/tesseract", 
                                  "/tmp/region.tif", 
                                  "/tmp/region"],
                                 stdout = subprocess.PIPE,
                                 stderr = subprocess.PIPE
                                 )
            errstuff = p.stderr.read()
            outstuff = p.stdout.read()
            sts = os.waitpid(p.pid,0)[1]
            if len(errstuff)>100:
                print errstuff
                pdb.set_trace()
            tempf = open("/tmp/region.txt")
            text += tempf.read()
            tempf.close()
        text = text.replace("\n","/").replace(",","comma")
        text = text.replace("'",'squot')
        text = text.replace('"','dquot')
        text = text.replace('\/','(M)').replace("IVI","(M)IVI")
        text = text.replace("|(M)","(M)").replace("I(M)","(M)")
        text = text.replace("(M)|","M").replace("(M)I","M")
        text = text.replace("|","I")
        text = re.sub(r'[^a-zA-Z0-9_ /]+', '', text)
        # now create a BTRegion from the item
        if box_type == "v":
            purpose = BtRegion.OVAL
            #coord = (croplist[0] - ((3*dpi)/8),croplist[1]-(dpi/50))
            # vote boxes begin 1/10" in from edge of contest box
            coord = (x1+(int(dpi*const.vote_target_horiz_offset_inches)),croplist[1]-(dpi*0.02))
            bbox = croplist
        else:
            purpose = BtRegion.CONTEST
            coord = (croplist[0],croplist[1])
            bbox = (croplist[0],croplist[1],croplist[2],nexty)
        br.append(BtRegion(bbox=bbox,
                           purpose=purpose,
                           coord = coord,
                           text = text))
    print
    return(text)

