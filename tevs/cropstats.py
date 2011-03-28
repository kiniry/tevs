from PIL import Image

#thresholds for colors
low_bin = 64
med_bin = 128
hi_bin  = 192

def cropstats(im, x, y):
    data = im.getdata()
    columns = im.size[0]
    rows = im.size[1]
    tot = [0, 0, 0]
    avg = [0., 0., 0.]
    lowest = [0, 0, 0]
    low = [0, 0, 0]
    high = [0, 0, 0]
    highest = [0, 0, 0]
    interior_dark = 0

    n = 0
    for r in range(rows):
        for c in range(columns):
            datum = data[n]
            for color in range(3):
                tot[color] += datum[color]
                if datum[color] < low_bin:
                    lowest[color] += 1
                elif datum[color] < med_bin:
                    low[color] += 1
                elif datum[color] < hi_bin:
                    high[color] += 1
                else: # highest ( <255 )
                    highest[color] += 1
                if ((r > rows/3) and (r < (2*rows)/3) 
                     and (c > columns/3) and (c < (2*columns)/3)
                     ):
                    if datum[color] < hi_bin:
                        interior_dark += 1
            n += 1

    #n = rows*columns
    for color in range(3):
        avg[color] = float(tot[color])/n

    # return the information, for now, as cropstats in PILB;
    # later, put in Istats form
    retlist = []
    colorname = ("red", "green", "blue")
    for color in range(3):
        retlist.append(avg[color])
        retlist.append(lowest[color])
        retlist.append(low[color])
        retlist.append(high[color])
        retlist.append(highest[color])
    retlist.append(x)
    retlist.append(y)
    retlist.append(interior_dark)

    return retlist

