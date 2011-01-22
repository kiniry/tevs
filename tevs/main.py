#!/usr/bin/env python
import sys
import os
import os.path
import errno
import string

import psycopg2


#XXX
import site
site.addsitedir("/home/jimmy/tevs")

from PILB import Image, ImageStat
from PILB import ImageDraw
import const

import util
from Ballot import Ballot, BallotException, LoadBallotType

def build_dirs(n):
     """create any necessary new directories using paths from tevs.cfg"""
     # generate filenames using the new image number(s)
     # create additional subdirectories as needed 
     # in proc, results, masks directories
     name1 = const.unprocformatstring % (n/1000, n)
     name2 = const.unprocformatstring % ((n+1)/1000, n+1)
     procname1 = const.procformatstring % (n/1000, n)
     procname2 = const.procformatstring % ((n+1)/1000, n+1)
     resultsfilename = const.resultsformatstring % (n/1000, n)
     masksfilename1 = const.masksformatstring % (n/1000, n)
     masksfilename2 = const.masksformatstring % ((n+1)/1000, n+1)
     for item in (name1,
                  name2,
                  procname1,
                  procname2,
                  resultsfilename, 
                  masksfilename1,
                  masksfilename2):
          util.mkdirp(os.path.dirname(item))
     return name1, name2, procname1, procname2, resultsfilename

def save_nextnum(n):
     """Save number in nexttoprocess.txt"""
     n += 2
     util.writeto("nexttoprocess.txt", str(n))
     return n

def get_nextnum(numlist):
     """get next number for processing from list or persistent file"""
     if len(numlist) > 0:
          n, numlist = numlist[0], numlist[1:]
     else:
         return int(util.readfrom("nexttoprocess.txt", 1))

def insert_ballot(cur, search_key, name1, name2):
    "insert a ballot into db, returns id"
    cur.execute("""INSERT INTO ballots (
		 processed_at, 
		 code_string, 
		 file1, file2) 
		 VALUES (now(), %s, %s, %s) RETURNING ballot_id ;""",
	      (search_key, name1, name2)
	      )
    sql_ret = cur.fetchall()

    try:
        ballot_id = int(sql_ret[0][0])
    except ValueError as e:
        util.fatal(e, "Corrupt ballot_id")

    return ballot_id

def save_voteinfo(cur, ballot_id, voteinfo):
    "write voteinfo to db"
    for vd in voteinfo:
        cur.execute(
            """INSERT INTO voteops (
                ballot_id,
                contest_text,
                choice_text,

                original_x,
                original_y,
                adjusted_x,
                adjusted_y,

                red_mean_intensity,
                red_darkest_pixels,
                red_darkish_pixels,
                red_lightish_pixels,
                red_lightest_pixels,

                green_mean_intensity,
                green_darkest_pixels,
                green_darkish_pixels,
                green_lightish_pixels,
                green_lightest_pixels,

                blue_mean_intensity,
                blue_darkest_pixels,
                blue_darkish_pixels,
                blue_lightish_pixels,
                blue_lightest_pixels,

                was_voted
            ) VALUES (
                %s, %s, %s,  
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, 
                %s, %s, %s, %s, %s, 
                %s, %s, %s, %s, %s, 
                %s
            )""",
            (
                ballot_id,
                vd.contest,
                vd.choice,

                vd.coords[0],
                vd.coords[1],
                vd.adjusted_x,
                vd.adjusted_y, 

                vd.red_intensity,
                vd.red_darkestfourth,
                vd.red_secondfourth,
                vd.red_thirdfourth,
                vd.red_lightestfourth,

                vd.green_intensity,
                vd.green_darkestfourth,
                vd.green_secondfourth,
                vd.green_thirdfourth,
                vd.green_lightestfourth,

                vd.blue_intensity,
                vd.blue_darkestfourth,
                vd.blue_secondfourth,
                vd.blue_thirdfourth,
                vd.blue_lightestfourth,

                vd.was_voted
            )
        )

def process_ballot(ballot):
    logger = const.logger

    try:
        tiltinfo = ballot.GetLandmarks()
    except Exception as e: #XXX
        util.fatal(e, "failure at GetLandmarks for %s", name1) 

    try:
        layout_codes = ballot.GetLayoutCode()
    except Exception as e: #XXX
        util.fatal(e, "failure at GetLayoutCode for %s", name1) 

    search_key = "%07d%07d" % tuple(layout_codes[0][:2])

    if search_key not in Ballot.front_dict: #XXX is there any recovery to do here? is this a util.fatal error?
        print search_key, "not in front_dict"

    try:
        front_layout = ballot.GetFrontLayout()
    except Exception as e: #XXX
        util.fatal(e, "failure at GetFrontLayout for %s", name1) 

    try:
        back_layout = ballot.GetBackLayout()
    except Exception as e: #XXX
        util.fatal(e, "failure at GetBackLayout for %s", name1) 

    try:
        ballot.CaptureVoteInfo()
    except Exception as e: #XXX
        util.fatal(e, "Failed to CaptureVoteInfo")

    #create mosaic of all vote ovals
    boximage = Image.new("RGB", (1650, 1200), color="white")
    draw = ImageDraw.Draw(boximage)
    keys = ballot.vote_box_images.keys()
    for i, key in enumerate(sorted(keys)):
        left = 50 + 150*(i % 10)
        right = 7*i
        boximage.paste(ballot.vote_box_images[key], (left, right))
        draw.text((left, right + 40), "%s_%04d_%04d" % tuple(key[:3]), fill="black")

    return search_key, boximage, ballot.WriteVoteInfo(), ballot.results

 
if __name__ == "__main__":
     # get command line arguments
     util.get_args()

     # read configuration from tevs.cfg and set constants for this run
     logger = util.get_config()

     # connect to db and open cursor
     try:
         conn = psycopg2.connect(database=const.dbname, user=const.dbpwd)
     except DatabaseError as e:
         util.fatal(e, "Could not connect to database")
     cur = conn.cursor()

     try:
         ballotfrom = LoadBallotType(const.layout_brand)
     except KeyError as e:
         util.fatal(e, "No such ballot type: " + const.layout_brand + " check tevs.cfg")

     # read templates
     util.initialize_from_templates()
     
     numlist = []
     try:
          with open("numlist.txt", "r") as f:
              numlist = [int(line) for line in f]
     except IOError:
          pass #no numlist.txt
     except ValueError as e:
          util.fatal(e, "Malformed numlist.txt")

     # While ballot images exist in the directory specified in tevs.cfg,
     # create ballot from images, get landmarks, get layout code, get votes.
     # Write votes to database and results directory.  Repeat.
     while True:
          #Preprocessing
          n = get_nextnum(numlist)
          name1, name2, procname1, procname2, resultsfilename = build_dirs(n)

          if not os.path.exists(name1):
              logger.info(name1 + " does not exist. No more records to process")
              conn.close()
              sys.exit(0)

          #Processing

          logger.info("Processing: %s: %s & %s" % (n, name1, name2))

          try:
              image1 = Image.open(name1).convert("RGB")
              image1.filename = name1
          except IOException as e:
              util.fatal(e, "Could not open " + name1)
          try:
              image2 = Image.open(name2).convert("RGB")
              image2.filename = name2
          except IOError: #XXX could produce other errors
              image2 = None

          try:
              ballot = ballotfrom(image1, image2)
          except BallotException as e:
              util.fatal(e, "Could not create ballot")

          searchkey, boximage, voteinfo, voteresults = process_ballot(ballot)

          #Write all data

          try:
              boximage.save(resultsfilename.replace("txt", "jpg")) #XXX should add to config file
          except Exception as e: #TODO what exceptions does boximage.save throw?
              util.fatal(e, "Could not write vote boxes to disk")

          util.writeto(resultsfilename, voteinfo)

          ballot_id = insert_ballot(cur, searchkey, name1, name2)

          save_voteinfo(cur, ballot_id, voteresults)

          try:
              conn.commit()
          except psycopg2.DatabaseError as e:
              util.fatal(e, "Could not commit vote information to database")

          #Post-processing

          # move the images from unproc to proc
          try:
               os.rename(name1, procname1)
          except OSError as e:
               util.fatal(e, "Could not rename %s", name1)

          try:
               if os.path.exists(name2): #in case ballot isn't 2 sided
                   os.rename(name2, procname2)
          except OSError as e:
               util.fatal(e, "Could not rename %s", name2)

          #All processing and post processsing succesful, record
          n = save_nextnum(n)

