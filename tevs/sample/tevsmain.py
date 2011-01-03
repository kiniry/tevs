import sys
import os
import site
site.addsitedir("/usr/local/lib/python2.6/site-packages")
from PILB import Image, ImageStat

import gc
import const
import pdb

from tevs.utils.util import *
from tevs.ballottypes.Ballot import *
from tevs.ballottypes.HartBallot import *
from tevs.ballottypes.DieboldBallot import *

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



if __name__ == "__main__":

     # get command line arguments
     get_args()

     # read configuration from tevs.cfg and set constants for this run
     logger = get_config()

     # connect to db and open cursor
     conn = psycopg2.connect("dbname=mitch user=mitch")
     cur = conn.cursor()
     cur.execute("select current_date;")
     cur.execute("select * from test;")
     print cur.fetchall()
     conn.commit()
     # read templates
     
     initialize_from_templates()
     
     pdb.set_trace()
     bh = BallotHatchery()

     #for dirnum in range(1,2):
     for dirnum in range(610,650):
          fullpath = "/media/VANCOUVER1/Batches/Batch%03d/" % (dirnum,)
          #fullpath = "/home/mitch/" 
          try:
               batches = os.listdir(fullpath)
          except OSError:
               print "No batch at",fullpath
               continue
          batches.sort()
          for myfile in batches:
               if not myfile.startswith("A00"):
                    continue
               try:
                    newballot = bh.ballotfrom(
                         "%sA%s" % (fullpath,myfile[1:]),
                         "%sB%s" % (fullpath,myfile[1:]))
               except Exception, e:
                    print e
                    logger.error("Exception %s at ballot creation, [A|B]%s\n" % (e,myfile[1:])) 
                    continue
               try:
                    tiltinfo = newballot.GetLandmarks()
               except Exception, e:
                    print e
                    logger.error("Exception %s at GetLandmarks, [A|B]%s\n" % (e,myfile[1:])) 
                    continue
               try:
                    layout_codes = newballot.GetLayoutCode()
               except Exception, e:
                    print e
                    logger.error("Exception %s at GetLayoutCode, [A|B]%s\n" % (e,myfile[1:])) 
                    continue

               search_key = "%07d%07d" % (layout_codes[0][0],layout_codes[0][1])
               #search_key = layout_codes[0]
               if search_key not in Ballot.front_dict:
                    print search_key, "not in front_dict"
               try:
                    front_layout = newballot.GetFrontLayout()
               except Exception, e:
                    print e
                    logger.error("Exception %s at GetFrontLayout, [A|B]%s\n" % (e,myfile[1:])) 
                    continue
               try:
                    back_layout = newballot.GetBackLayout()
               except Exception, e:
                    print e
                    logger.error("Exception %s at GetBackLayout, [A|B]%s\n" % (e,myfile[1:])) 
                    continue

               # the ballots table was created with this SQL
               """
               create table ballots (
                ballot_id serial PRIMARY KEY,
                processed_at timestamp,
                code_string char(14),
                layout_code bigint,
                file1 varchar(80),
                file2 varchar(80)
               );
               """
               #if we get this far, create a db record for the ballot

               cur.execute("""INSERT INTO ballots (
                              processed_at, 
                              code_string, 
                              file1, file2) 
                              VALUES (now(), %s, %s, %s) RETURNING ballot_id ;""",
                           (search_key,
                            "%sA%s" % (fullpath,myfile[1:]),
                            "%sB%s" % (fullpath,myfile[1:])
                            )
                           )
               sql_ret = cur.fetchall()
               try:
                    ballot_id = int(sql_ret[0][0])
               except:
                    ballot_id = "ERROR"
               conn.commit()
               # we now need to retrieve the newly created serial ballot id 
               try:
                    newballot.CaptureVoteInfo()
                    vi = newballot.WriteVoteInfo()
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

vd.blue_intensity ,
vd.blue_darkestfourth ,
vd.blue_secondfourth ,
vd.blue_thirdfourth ,
vd.blue_lightestfourth ,
vd.was_voted)
)
                    conn.commit()
                    f = open("Vancouvervoteinfo.csv","a")
                    f.write(vi)
                    f.close()
               except Exception, e:
                    print e
                    logger.error("Exception %s at Capture or WriteVoteInfo, [A|B]%s\n" % (e,myfile[1:])) 
                    continue
               gc.collect()


# the ballots table was created with this SQL
"""
               create table ballots (
                ballot_id serial PRIMARY KEY,
                processed_at timestamp,
                code_string char(14),
                layout_code bigint,
                file1 varchar(80),
                file2 varchar(80)
               );
"""

# the voteops table was created with this SQL
"""
create table voteops (
       voteop_id serial PRIMARY KEY,
       ballot_id int REFERENCES ballots (ballot_id),
       contest_text varchar(80),
       choice_text varchar(80),
       original_x smallint,
       original_y smallint,
       adjusted_x smallint,
       adjusted_y smallint,
       red_mean_intensity smallint,
       red_darkest_pixels smallint,
       red_darkish_pixels smallint,
       red_lightish_pixels smallint,
       red_lightest_pixels smallint,
       green_mean_intensity smallint,
       green_darkest_pixels smallint,
       green_darkish_pixels smallint,
       green_lightish_pixels smallint,
       green_lightest_pixels smallint,
       blue_mean_intensity smallint,
       blue_darkest_pixels smallint,
       blue_darkish_pixels smallint,
       blue_lightish_pixels smallint,
       blue_lightest_pixels smallint,
       was_voted boolean
);
"""
