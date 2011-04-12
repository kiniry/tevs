#!/usr/bin/env python
import sys
import os
import shutil
import errno
import getopt
import logging

import site; site.addsitedir(os.path.expanduser("~/tevs")) #XXX
from PILB import Image, ImageStat, ImageDraw #XXX only here so we break

import const #To be deprecated
import config
import util
import db
import next
import Ballot
BallotException = Ballot.BallotException

def get_args():
    """Get command line arguments"""
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                    "tdc:",
                                    ["templates",
                                     "debug",
                                     "config="
                                    ]
                                   ) 
    except getopt.GetoptError:
        #note that logging doesn't exist yet
        sys.stderr.write(
            "usage: %s -tdc --templates --debug --config=file" % sys.argv[0]
        )
        sys.exit(2)
    templates_only = False
    debug = False
    config = "tevs.cfg"
    for opt, arg in opts:
        if opt in ("-t", "--templates"):
            templates_only = True
        if opt in ("-d", "--debug"):
            debug = True
        if opt in ("-c", "--config"):
            config = arg

    const.templates_only = templates_only
    const.debug = debug
    return config

def remove_partial(fname):
    try:
        os.unlink(fname)
    except KeyboardInterrupt:
        raise
    except Exception: #bad form but we really don't care
        pass

def _fn(n):
    return "%03d" % (n/1000,)

def incomingn(n):
    return filen(os.path.join(const.incoming, _fn(n)), n) + ".jpg"

def dirn(dir, n): # where dir is the "unrooted" name
    return util.root(dir, _fn(n))

def filen(dir, n): #where dir is from dirn
    return os.path.join(dir, "%06d" % n)

def mark_error(e, *files):
    log = logging.getLogger('')
    if e is not None:
        log.error(e)
    for file in files:
        log.error("Could not process ballot " + os.path.basename(file))
        try:
            shutil.copy2(file, util.root("errors", os.path.basename(file)))
        except IOError:
            util.fatal("Could not copy unprocessable file to errors dir")
    return len(files)

def main():
    # get command line arguments
    cfg_file = get_args()

    # read configuration from tevs.cfg and set constants for this run
    config.get(cfg_file)
    util.mkdirp(const.root)
    log = config.logger(util.root("log.txt"))

    #create initial top level dirs, if they do not exist
    for p in ("templates", "results", "proc", "errors"):
        util.mkdirp(util.root(p))

    next_ballot = next.File(util.root("nexttoprocess.txt"), const.num_pages)

    try:
        ballotfrom = Ballot.LoadBallotType(const.layout_brand)
    except KeyError as e:
        util.fatal("No such ballot type: " + const.layout_brand + ": check " + cfg_file)

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
            unprocs = [incomingn(n + m) for m in range(const.num_pages)]
            if not os.path.exists(unprocs[0]):
                log.info(base(unprocs[0]) + " does not exist. No more records to process")
                break
            for i, f in enumerate(unprocs[1:]):
                if not os.path.exists(f):
                    log.info(base(f) + " does not exist. Cannot proceed.")
                    for j in range(i):
                        log.info(base(unprocs[j]) + " will NOT be processed")
                    total_unproc += mark_error(None, *unprocs[:i-1])
                    return

            #Processing

            log.info("Processing %s:\n %s" % 
                (n, "\n".join("\t%s" % base(u) for u in unprocs))
            )

            try:
                ballot = ballotfrom(unprocs, extensions)
                results = ballot.ProcessPages()
            except BallotException as e:
                total_unproc += mark_error(e, *unprocs)
                log.exception("Could not process ballot")
                continue

            csv = Ballot.results_to_CSV(results)
            moz = Ballot.results_to_mosaic(results)
            wrins = []
            for i, r in enumerate(results):
                if r.is_writein and r.was_voted:
                    wrins.append((i, r.image))

            #Write all data

            #make dirs:
            proc1d = dirn("proc", n)
            resultsd = dirn("results", n)
            resultsfilename = filen(resultsd, n)
            for p in (proc1d, resultsd):
                util.mkdirp(p)
            wrind = os.path.join(dirn("writeins", n), resultsfilename)
            if len(wrins) != 0:
                util.mkdirp(wrind)

            #write csv and mosaic
            util.genwriteto(resultsfilename + ".txt", csv)
            try:
                moz.save(resultsfilename + ".jpg")
            except Exception as e: #TODO what exceptions does image.save throw?
                #do not let partial results give us a false sense of security
                remove_partial(resultsfilename + ".txt")
                util.fatal("Could not write vote boxes to disk")

            for i, wrin in wrins:
                try:
                    wrin.save(os.path.join(wrind, "%d.jpg" % i))
                except Exception as e: #TODO what exceptions does image.save throw?
                    shutil.rmdir(wrind)
                    remove_partial(resultsfilename + ".txt")
                    remove_partial(resuktsfilename + ".jpg")
                    util.fatal("Could not write write ins to disk")

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
            log.info("%d ballot pages processed succesfully", const.num_pages)
    finally:
        cache.save()
        dbc.close()
        next_ballot.save()
        log.info("%d ballot(s) processed", total_proc)
        if total_unproc > 0:
            log.warning("%d ballot(s) coult NOT be processed.", total_unproc)

if __name__ == "__main__":
    main()
    #import cProfile as profile
    #profile.Profile.bias = 3.15e-6
    #profile.run('main()', 'prof.%s' % sys.argv[1])
