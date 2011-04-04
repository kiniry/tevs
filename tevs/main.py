#!/usr/bin/env python
import sys
import os
import errno
import string

import site; site.addsitedir(os.path.expanduser("~/tevs")) #XXX
from PILB import Image, ImageStat, ImageDraw #XXX only here so we break

import const #To be deprecated
import config
import util
import db
import next
import Ballot


BallotException = Ballot.BallotException

def remove_partial(fname):
    try:
        os.unlink(fname)
    except KeyboardInterrupt:
        raise
    except Exception: #bad form but we really don't care
        pass

def dirn(dir, n): # where dir is the "unrooted" name
    return util.root(dir, "%03d" % (n/1000,))

def filen(dir, n): #where dir is from dirn
    return os.path.join(dir, "%06d" % n)

def main():
    # get command line arguments
    config.get_args()

    # read configuration from tevs.cfg and set constants for this run
    logger = config.get_config()

    #create initial top level dirs, if they do not exist
    for p in ("templates", "results", "proc", "unproc"):
        util.mkdirp(util.root(p))

    #XXX nexttoprocess.txt belongs under data root?
    next_ballot = next.File("nexttoprocess.txt", 2)

    try:
        ballotfrom = Ballot.LoadBallotType(const.layout_brand)
    except KeyError as e:
        util.fatal("No such ballot type: " + const.layout_brand + ": check tevs.cfg")

    cache = Ballot.TemplateCache(util.root("templates"))
    extensions = Ballot.Extensions(template_cache=cache)
   
    # connect to db and open cursor
    if const.use_db:
        try:
            dbc = db.PostgresDB(const.dbname, const.dbpwd)
        except db.DatabaseError:
            util.fatal("Could not connect to database")
    else:
        dbc = db.NullDB()


    base = os.path.basename
    # While ballot images exist in the directory specified in tevs.cfg,
    # create ballot from images, get landmarks, get layout code, get votes.
    # Write votes to database and results directory.  Repeat.
    try:
        for n in next_ballot:
            unproc1 = filen(dirn("unproc", n), n) + ".jpg"
            unproc2 = filen(dirn("unproc", n + 1), n + 1) + ".jpg"
            if not os.path.exists(unproc1):
                logger.info(base(unproc1) + " does not exist. No more records to process")
                break
            if not os.path.exists(unproc2):
                logger.info(base(unproc2) + " does not exist.")
                logger.info("Warning: " + base(unproc2) + 
                    " will not be processed. Single sided.")

            #Processing

            logger.info("Processing: %s: %s & %s" % 
                (n, base(unproc1), base(unproc2))
            )

            names = [unproc1, unproc2]
            unproc2save = unproc2
            if not os.path.exists(unproc2):
                names = unproc1
                unproc2save = "<No such file>"
            try:
                ballot = ballotfrom(names, extensions)
                results = ballot.ProcessPages()
            except BallotException as e:
                util.fatal("Could not analyze ballot")

            csv = Ballot.results_to_CSV(results)
            moz = Ballot.results_to_mosaic(results)

            #Write all data

            #make dirs:
            proc1d = dirn("proc", n)
            proc2d = dirn("proc", n + 1)
            resultsd = dirn("results", n)
            for p in (proc1d, proc2d, resultsd):
                util.mkdirp(p)

            #write csv and mosaic
            resultsfilename = filen(resultsd, n)
            util.genwriteto(resultsfilename + ".txt", csv)
            try:
                moz.save(resultsfilename + ".jpg")
            except Exception as e: #TODO what exceptions does boximage.save throw?
                #do not let partial results give us a false sense of security
                remove_partial(resultsfilename + ".txt")
                util.fatal("Could not write vote boxes to disk")

            #write to the database
            try:
                dbc.insert(ballot)
            except db.DatabaseError:
                remove_partial(results_filename + ".txt")
                remove_partial(results_filename + ".jpg")
                util.fatal("Could not commit vote information to database")

            #Post-processing

            # move the images from unproc to proc
            proc1 = filen(proc1d, n) + ".jpg"
            proc2 = filen(proc2d, n + 1) + ".jpg"
            try:
                os.rename(unproc1, proc1)
            except OSError as e:
                util.fatal("Could not rename %s", unproc1)

            try:
                if unproc2save != "<No such file>":
                    os.rename(unproc2, proc2)
            except OSError as e:
                util.fatal("Could not rename %s", unproc2)
    finally:
        cache.save()
        dbc.close()
        next_ballot.save()

if __name__ == "__main__":
    main()
    #import cProfile as profile
    #profile.Profile.bias = 3.15e-6
    #profile.run('main()', 'prof.%s' % sys.argv[1])
