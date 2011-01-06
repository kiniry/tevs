import sys
import os
import os.path
import errno
import gc
import string

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
          try:
              os.makedirs(os.path.dirname(item))
          except Exception as e:
              if e.errno == errno.EEXIST:
                  continue #fake mkdir -p
              print "Could not create directory %s; %s" % (
                    item,e)
              logger.error("Could not create directory %s; %s" % 
                     (item,e))
              sys.exit(1)
     return name1, name2, procname1, procname2, resultsfilename

def save_nextnum(n):
     """Save number in nexttoprocess.txt"""
     try:
          n = n+2
          hw = open("nexttoprocess.txt","w")#XXX needs to not be in cwd
          hw.write("%d"%n)
          hw.close()
     except Exception as e:
          logger.debug("Could not write %d to nexttoprocess.txt %s\n" % 
                       (n,e))
     return n

def get_nextnum(numlist):
     """get next number for processing from list or persistent file"""
     if len(numlist)>0:
          n = numlist[0]
          numlist = numlist[1:]
     else:
          try:
               hw = open("nexttoprocess.txt","r")
               hwline = hw.readline()
               hw.close()
               n = string.atoi(hwline)
               logger.info("Processing %d"%n)
          except:
               logger.error( 
                    "Could not read nexttoprocess.txt, setting n to 1")
               n = 1
     return n


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
          numlistfile = open("numlist.txt","r")
          for numline in numlistfile.readlines():
               num = int(numline)
               numlist.append(num)
     except IOError:
          pass #no numlist.txt

     # While ballot images exist in the directory specified in tevs.cfg,
     # create ballot from images, get landmarks, get layout code, get votes.
     # Write votes to database and results directory.  Repeat.
     while True:
          n = get_nextnum(numlist)
          name1, name2, procname1, procname2, resultsfilename = build_dirs(n)
          print "Processing:\n", n, "\n", name1, name2

          try:
               newballot = bh.ballotfrom(name1,name2)
          except Exception as e:
               print e
               logger.error("Exception %s at ballot creation, [A|B]%s\n" 
                            % (e,name1)) 
               sys.exit(1) #continue

          try:
               tiltinfo = newballot.GetLandmarks()
          except Exception as e:
               print e
               logger.error("Exception %s at GetLandmarks, [A|B]%s\n" % (e,name1)) 
               sys.exit(1) #continue

          try:
               layout_codes = newballot.GetLayoutCode()
          except Exception as e:
               print e
               logger.error("Exception %s at GetLayoutCode, [A|B]%s\n" % (e,name1)) 
               sys.exit(1) #continue

          search_key = "%07d%07d" % (layout_codes[0][0],layout_codes[0][1])

          if search_key not in Ballot.front_dict:
               print search_key, "not in front_dict"

          try:
               front_layout = newballot.GetFrontLayout()
          except Exception as e:
               print e
               logger.error("Exception %s at GetFrontLayout, [A|B]%s\n" % (e,name1)) 
               sys.exit(1) #continue

          try:
               back_layout = newballot.GetBackLayout()
          except Exception as e:
               print e
               logger.error("Exception %s at GetBackLayout, [A|B]%s\n" % (e,name1)) 
               sys.exit(1) #continue

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
          except:
               ballot_id = "ERROR"
          conn.commit()

          # we now need to retrieve the newly created serial ballot id 
          try:
               print "Storing results"
               newballot.CaptureVoteInfo()
               boximage = Image.new("RGB",(1650,1200),color="white")
               counter = 0
               draw = ImageDraw.Draw(boximage)
               keys = newballot.vote_box_images.keys()
               keys.sort()
               for key in keys:
                    boximage.paste(
                         newballot.vote_box_images[key],
                         ( ((counter % 10) * 150)+50, (counter/10) * 70 )
                         )
                    draw.text(
                         ( ((counter % 10) * 150)+50,((counter/10) * 70)+40 ),
                         "%s_%04d_%04d" % (key[0],key[1],key[2]),
                         fill="black")
                    counter += 1

               boximage.save(resultsfilename.replace("txt","jpg"))
               vi = newballot.WriteVoteInfo()
               resultsfile = open(resultsfilename,"w+")
               resultsfile.write(vi)
               resultsfile.close()
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
                    # open the results file and write the results

          except Exception as e:
               print e
               logger.error("Exception %s at Capture or WriteVoteInfo, %s, %s\n" % (e,name1,name2)) 
               sys.exit(1) #continue

          # move the images from unproc to proc
          try:
               os.rename(name1,procname1)
          except IOError:
               logger.error("Could not rename %s" % name1)
               sys.exit(1)
          try:
               os.rename(name2,procname2)
          except IOError:
               logger.error("Could not rename %s" % name2)
               sys.exit(1)
          n = save_nextnum(n)
