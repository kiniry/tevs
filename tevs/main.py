#!/usr/bin/env python
import sys
import os
import os.path
import errno
import gc
import string

#XXX
import site
site.addsitedir("/home/jimmy/tevs")
import pdb

# modified Python Image Library, with B for Ballot
from PILB import Image, ImageStat
from PILB import ImageDraw
import const
# ballot processing python
#XXX * imports are bad news
from util import *
from Ballot import *
from HartBallot import *
from DieboldBallot import *

# for database
# we initially assume dbname and dbuser mitch in postgresql
import psycopg2

voteop_insertion_string = """INSERT INTO voteops (
 ballot_id,
 contest_text ,
 choice_text ,
 original_x ,
 original_y ,
 adjusted_x ,
 adjusted_y ,
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
%s,  
%s, %s,  
%s, %s,  
%s, %s,
%s, %s, %s, %s, %s, 
%s, %s, %s, %s, %s, 
%s, %s, %s, %s, %s, 
%s
 )"""

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
          mkdirp(os.path.dirname(item))
     return name1, name2, procname1, procname2, resultsfilename

def save_nextnum(n):
     """Save number in nexttoprocess.txt"""
     n += 2
     writeto("nexttoprocess.txt", str(n))
     return n

def get_nextnum(numlist):
     """get next number for processing from list or persistent file"""
     if len(numlist)>0:
          n = numlist[0]
          numlist = numlist[1:]
     else:
         return int(readfrom("nexttoprocess.txt", 1))

def process_ballot(name1, name2, resultsfilename): #TODO: pull all sql out into their own funcs
    #note currently relying on conn, cur being defined globally
    logger = const.logger
    try:
        newballot = bh.ballotfrom(name1, name2)
    except Exception as e:
        logger.error("Exception %s at ballot creation, [A|B]%s\n" 
 		    % (e, name1)) 
        raise

    try:
        tiltinfo = newballot.GetLandmarks()
    except Exception as e:
        logger.error("Exception %s at GetLandmarks, [A|B]%s\n" % (e, name1)) 
        raise

    try:
        layout_codes = newballot.GetLayoutCode()
    except Exception as e:
        logger.error("Exception %s at GetLayoutCode, [A|B]%s\n" % (e, name1)) 
        raise

    search_key = "%07d%07d" % (layout_codes[0][0], layout_codes[0][1])

    if search_key not in Ballot.front_dict: #XXX is there any recovery to do here? is this a fatal error?
        print search_key, "not in front_dict"

    try:
        front_layout = newballot.GetFrontLayout()
    except Exception as e:
        logger.error("Exception %s at GetFrontLayout, [A|B]%s\n" % (e,name1)) 
        raise

    try:
        back_layout = newballot.GetBackLayout()
    except Exception as e:
        logger.error("Exception %s at GetBackLayout, [A|B]%s\n" % (e,name1)) 
        raise

    #if we get this far, create a db record for the ballot

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
    except ValueError:
        ballot_id = "ERROR" #XXX if this happens shouldn't we do something?
    conn.commit()

    # we now need to retrieve the newly created serial ballot id 
    try:
        print "Storing results"
        newballot.CaptureVoteInfo()
        boximage = Image.new("RGB", (1650, 1200), color="white")
        draw = ImageDraw.Draw(boximage)
        keys = newballot.vote_box_images.keys()
        for i, key in enumerate(sorted(keys)):
	    left = 50 + 150*(i % 10)
	    right = 7*i
	    boximage.paste(newballot.vote_box_images[key], (left, right))
	    draw.text((left, right + 40), "%s_%04d_%04d" % tuple(key[:3]), fill="black")

        boximage.save(resultsfilename.replace("txt","jpg"))
        writeto(resultsfilename, newballot.WriteVoteInfo())
        for vd in newballot.results:
	    cur.execute(voteop_insertion_string,
		 (ballot_id,
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
		  vd.was_voted)
	     )
	    conn.commit()
	    # open the results file and write the results

    except Exception as e:
        logger.error("Exception %s at Capture or WriteVoteInfo, %s, %s\n" % (e,name1,name2)) 
        raise
 
if __name__ == "__main__":
     # get command line arguments
     get_args()

     # read configuration from tevs.cfg and set constants for this run
     logger = get_config()

     # connect to db and open cursor
     conn = psycopg2.connect("dbname=jimmy user=jimmy")
     cur = conn.cursor()

     # read templates
     initialize_from_templates()
     
     # a BallotHatchery's "ballotfrom" inspects images 
     # and creates ballots of the correct type
     bh = BallotHatchery()

     numlist = []
     try:
          with open("numlist.txt", "r") as f:
              numlist = [int(line) for line in f]
     except IOError:
          pass #no numlist.txt
     except ValueError:
          logger.error("Malformed numlist.txt")
          sys.exit(1)

     # While ballot images exist in the directory specified in tevs.cfg,
     # create ballot from images, get landmarks, get layout code, get votes.
     # Write votes to database and results directory.  Repeat.
     while True:
          n = get_nextnum(numlist)
          name1, name2, procname1, procname2, resultsfilename = build_dirs(n)

          if not os.path.exists(name1):
              logger.info(name1 + " does not exist. No more records to process")
              sys.exit(0)

          logger.info("Processing: %s: %s & %s" % (n, name1, name2))

          try:
               process_ballot(name1, name2, resultsfilename) ##would rather it returned results data so we can save it all here
          except KeyboardInterrupt:
               sys.exit(0)
          except:
               sys.exit(1)
          # move the images from unproc to proc
          try:
               os.rename(name1, procname1)
          except OSError:
               logger.error("Could not rename %s" % name1)
               sys.exit(1)
          try:
               if os.path.exists(name2): #in case ballot isn't 2 sided
                   os.rename(name2, procname2)
          except OSError:
               logger.error("Could not rename %s" % name2)
               sys.exit(1)
          n = save_nextnum(n)
