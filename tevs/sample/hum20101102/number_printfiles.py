import os
dirname = "fromprintfiles"
flist = os.listdir(dirname)
flist.sort()
counter = 1
for f in flist:
    os.rename("%s/%s" % (dirname,f),"%s/tmp_%03d.jpg" % (dirname,counter))
    counter += 1
    print counter
print "Done"
