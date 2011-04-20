#!/usr/bin/env python
import db
import config
import const #XXX tbd
import util

console = """
Total voted boxes:\t{num_voted}
Total unvoted boxes:\t{num_non_voted}
Total suspicious votes:\t{num_weird}
Total bad votedatas:\t{num_bad}
"""[1:] #get rid of \n after the quotes on top, bottom \n needed

def main():
    config.get()
    log = config.logger(util.root("log.txt"))
    try:
        dbc = db.PostgresDB(const.dbname, const.dbpwd)
    except db.DatabaseError:
        util.fatal("Could not connect to database")
    q = dbc.query
    q1 = dbc.query1

    num_vops = q1("select count(was_voted) from voteops")[0]
    num_voted = q1("select count(was_voted) from voteops where was_voted")[0]
    num_weird = q1("select count(suspicious) from voteops where suspicious")[0]
    num_bad = q1("select count(original_x) from voteops where original_x = -1")[0]
    num_non_voted = num_vops - num_voted

    meani = zip(*q(
    """select (red_mean_intensity,
            green_mean_intensity,
            blue_mean_intensity)
        from voteops
        where red_mean_intensity != -1"""
    ))
    #meani = [sum(int(i) for i in x)/len(x) for x in meani]
    print meani

    print console.format(**locals())

if __name__ == '__main__':
    main()