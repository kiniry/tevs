#this is utils for the tests and not a test of utils.py

import site; site.addsitedir("/home/jimmy/tevs") #XXX
from Ballot import *

def CONCHO(*a):
    """each arg is a contest, a list of x,y,w,h, a description; and a
    list of contests, given by a list of x,y, a description, bools of:
    was voted, iswritein, isambiguous, and an optional stats obj. The
    extra information is so we can compare with the [VoteInfo] results.
    CONCHO(
        (x,y,w,h, "prop", "description",
            (x, y, "desc", True, False, True),
            etc...
        ),
        etc...
    )
    returns the data required by the last arg of Page.as_template and
    a list of just the choices for easy comparison against votedata
    """
    ret, all = [], []
    for n in a:
        con = Contest(*n[:-1])
        for c in n[-1]:
            cho = Choice(*c[:3])
            #patch in extra info for concho_vs_vd to read
            cho.cd, cho.v, cho.wi, cho.a = c[2:6]
            #set stats if available
            cho.ss = None if len(c) < 7 else c[6]
            con.append(cho)
            all.append(cho)
        ret.append(con)
    return ret, all

def concho_vs_vd(chos, vds):
    """Takes the second return of CONCHO and the ballot results and
    makes sure everything is the same"""
    for ch, vd in zip(chos, vds):
        if not all(
                ch.cd          == vd.contest,
                ch.v           == vd.was_voted,
                ch.wi          == vd.is_writein,
                ch.a           == vd.ambiguous,
                ch.description == vd.choice,
                ch.x           == vd.coords[0],
                ch.y           == vd.coords[1],
                stats_cmp(ch.ss,  vd.stats)
            ):
            return False
    return True

def stats_cmp(a, b):
    if a is None: #ie, we don't care about this
        return True
    for x, xp in zip(a, b):
        if x != xp:
            return False
    return True

