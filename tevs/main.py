#!/usr/bin/env python
import sys
import os
import os.path
import errno
import string

import psycopg2

import site; site.addsitedir("/home/jimmy/tevs") #XXX
from PILB import Image, ImageStat, ImageDraw

import const #To be deprecated
import config

import util
import Ballot
BallotException = Ballot.BallotException

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
        util.fatal("Corrupt ballot_id")

    return ballot_id

def save_voteinfo(cur, ballot_id, voteinfo): #XXX needs to be updated
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
                vd.stats.adjusted.x,
                vd.stats.adjusted.y, 

                vd.stats.red.intensity,
                vd.stats.red.darkest_fourth,
                vd.stats.red.second_fourth,
                vd.stats.red.third_fourth,
                vd.stats.red.lightest_fourth,

                vd.stats.green.intensity,
                vd.stats.green.darkest_fourth,
                vd.stats.green.second_fourth,
                vd.stats.green.third_fourth,
                vd.stats.green.lightest_fourth,

                vd.stats.blue.intensity,
                vd.stats.blue.darkest_fourth,
                vd.stats.blue.second_fourth,
                vd.stats.blue.third_fourth,
                vd.stats.blue.lightest_fourth,

                vd.was_voted
            )
        )

def main():
     # get command line arguments
     config.get_args()

     # read configuration from tevs.cfg and set constants for this run
     logger = config.get_config()

     # connect to db and open cursor
     try:
         conn = psycopg2.connect(database=const.dbname, user=const.dbpwd)
     except DatabaseError as e:
         util.fatal("Could not connect to database")
     cur = conn.cursor()

     try:
         ballotfrom = Ballot.LoadBallotType(const.layout_brand)
     except KeyError as e:
         util.fatal("No such ballot type: " + const.layout_brand + ": check tevs.cfg")

     cache = Ballot.TemplateCache(util.root("templates"))
     extensions = Ballot.Extensions(template_cache=cache)
     
     numlist = []
     try:
          with open("numlist.txt", "r") as f:
              numlist = [int(line) for line in f]
     except IOError:
          pass #no numlist.txt
     except ValueError as e:
          util.fatal("Malformed numlist.txt")

     base = os.path.basename
     # While ballot images exist in the directory specified in tevs.cfg,
     # create ballot from images, get landmarks, get layout code, get votes.
     # Write votes to database and results directory.  Repeat.
     while True:
          #Preprocessing
          n = get_nextnum(numlist)
          name1, name2, procname1, procname2, resultsfilename = build_dirs(n)

          if not os.path.exists(name1):#TODO this should all be in a finally
              logger.info(base(name1) + " does not exist. No more records to process")
              conn.close()
              cache.save()
              sys.exit(0)

          #Processing

          logger.info("Processing: %s: %s & %s" % (n, base(name1), base(name2)))

          names = [name1, name2]
          name2save = name2
          if not os.path.exists(name2):
              names = name1
              name2save = "<No such file>"
          try:
              ballot = ballotfrom(names, extensions)
              results = ballot.ProcessPages()
          except BallotException as e:
              util.fatal("Could not analyze ballot")

          csv = Ballot.results_to_CSV(results)
          moz = Ballot.results_to_mosaic(results)

          #Write all data
          try:
              moz.save(resultsfilename.replace("txt", "jpg")) #XXX should add to config file
          except Exception as e: #TODO what exceptions does boximage.save throw?
              util.fatal("Could not write vote boxes to disk")

          util.genwriteto(resultsfilename, csv)

          searchkey = "$".join(p.template.precinct for p in ballot.pages)
          logger.info("processed " + searchkey)

          ballot_id = insert_ballot(cur, searchkey[:14], name1, name2save)

          save_voteinfo(cur, ballot_id, ballot.results) #XXX needs to be updated

          try:
              conn.commit()
          except psycopg2.DatabaseError as e:
             util.fatal("Could not commit vote information to database")

          #Post-processing

          # move the images from unproc to proc
          try:
               os.rename(name1, procname1)
          except OSError as e:
               util.fatal("Could not rename %s", name1)

          try:
               if os.path.exists(name2): #in case ballot isn't 2 sided
                   os.rename(name2, procname2)
          except OSError as e:
               util.fatal("Could not rename %s", name2)

          #All processing and post processsing succesful, record
          n = save_nextnum(n) #XXX should really only write to disk once at end

if __name__ == "__main__":
    main()
