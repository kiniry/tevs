#!/usr/bin/env python
import sys
import os
import shutil
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


def mark_error(*files):
    for file in files:
        const.logger.error("Could not process ballot " + os.path.basename(file))
        try:
            shutil.copy2(file, util.root("errors", os.path.basename(file)))
        except IOError:
            util.fatal("Could not copy unprocessable file to errors dir")
    return len(files)

def main():
    # get command line arguments
    config.get_args()

    # read configuration from tevs.cfg and set constants for this run
    logger = config.get_config()

    #create initial top level dirs, if they do not exist
    for p in ("templates", "results", "proc", "unproc", "errors"):
        util.mkdirp(util.root(p))

    #XXX nexttoprocess.txt belongs under data root?
    next_ballot = next.File("nexttoprocess.txt", const.num_pages)

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

    total_proc, total_unproc = 0, 0
    base = os.path.basename
    # While ballot images exist in the directory specified in tevs.cfg,
    # create ballot from images, get landmarks, get layout code, get votes.
    # Write votes to database and results directory.  Repeat.
    try:
        for n in next_ballot:
            unprocs = [filen(dirn("unproc", n + m), n + m) + ".jpg" 
                        for m in range(const.num_pages)]
            if not os.path.exists(unprocs[0]):
                logger.info(base(unprocs[0]) + " does not exist. No more records to process")
                break
            for i, f in enumerate(unprocs[1:]):
                if not os.path.exists(f):
                    logger.info(base(f) + " does not exist. Cannot proceed.")
                    for j in range(i):
                        logger.info(base(unprocs[j]) + " will NOT be processed")
                    total_unproc += mark_error(*unprocs[:i-1])
                    return

            #Processing

            logger.info("Processing: %s:\n %s" % 
                (n, "".join("\t%s\n" % base(u) for u in unprocs))
            )

            try:
                ballot = ballotfrom(unprocs, extensions)
                results = ballot.ProcessPages()
            except BallotException as e:
                total_unproc += mark_error(*unprocs)
                logger.exception("Could not process %s and %s" % names)
                continue

            csv = Ballot.results_to_CSV(results)
            moz = Ballot.results_to_mosaic(results)

            #Write all data

            #make dirs:
            proc1d = dirn("proc", n)
            resultsd = dirn("results", n)
            for p in (proc1d, resultsd):
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
                #dbc does not commit if there is an error, just need to remove 
                #partial files
                remove_partial(results_filename + ".txt")
                remove_partial(results_filename + ".jpg")
                util.fatal("Could not commit vote information to database")

            #Post-processing

            # move the images from unproc to proc
            procs = [filen(proc1d, n + m) + ".jpg"
                        for m in range(const.num_pages)]
            for a, b in zip(unprocs, procs):
                try:
                    os.rename(a, b)
                except OSError as e:
                    util.fatal("Could not rename %s", a)
            total_proc += const.num_pages
    finally:
        cache.save()
        dbc.close()
        next_ballot.save()
        print total_proc, "ballot(s) processed."
        if total_unproc > 0:
            print total_unproc, "ballot(s) could NOT be processed."

if __name__ == "__main__":
    main()
    #import cProfile as profile
    #profile.Profile.bias = 3.15e-6
    #profile.run('main()', 'prof.%s' % sys.argv[1])
