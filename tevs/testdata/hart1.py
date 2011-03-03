import util_test
import Ballot
from hart_ballot import *
import hart_ballot_test

ball = HartBallot('testdata/hart1.jpg', Ballot.Extensions())
ball.ProcessPages()
contests = ball.pages[0].template.contests

print "    mg = CONCHO("
for contest in contests:
    print '        (%d, %d, %d, %d, "%s", "%s",' % (
        contest.x, contest.y,
        contest.w, contest.h,
        contest.prop, contest.description
    )
    for choice in contest.choices:
        print '            (%d, %d, "%s", x, False, x),' % (
            contest.x, contest.y,
            contest.description
        )
    print '        ),'
print '    )'
