import copy

import util

class Set(object):
    def __init__(self, list_name):
        self.numlist = []
        self.list_name = list_name
        try:
            with open(list_name, "r") as f:
                self.numlist = [int(line) for line in f]
        except IOError:
            pass #no numlist.txt, ignore
        except ValueError:
            util.fatal("Malformed numlist.txt")

    def __iter__(self):
        for i in copy(self.numlist):
            self.numlist = self.numlist[1:]
            yield i

    def save(self):
        util.writeto(self.list_name, "\n".join(str(i) for i in self.numlist))


class File(object):
    def __init__(self, next_file, inc):
        self.inc = inc
        self.next_file = next_file
        self.next = int(util.readfrom(next_file, 1))

    def __iter__(self):
        yield self.next
        while True:
            self.next += self.inc
            yield self.next

    def save(self):
        util.writeto(self.next_file, str(self.next))

class Simple(object):
    def __init__(self, start=0, inc=1):
        self.start, self.inc = start, inc

    def __iter__(self):
        n = self.start
        while True:
            n += self.inc
            yield n

    def save(self):
        pass
