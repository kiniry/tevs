from Ballot import Ballot

class ExtendedBallot(Ballot):
    def __init__(self,im1,im2=None):
        super(ExtendedBallot,self).__init__(im1,im2)

    def printme(self):
        return "EXTENDED"+super(ExtendedBallot,self).printme()

    def __str__(self):
        return "EXTENDED"+super(ExtendedBallot,self).__str__()

    def determine_layout(self):
        print "In %s determine_layout from instance of %s" % ("ExtendedBallot",self.__class__)
        print "Calling superclass' determine_layout"
        super(ExtendedBallot,self).determine_layout()
        print "but then overriding"
        self.layout = "extended default layout"
        return self.layout

    def load_layout(self):
        print "In %s load_layout with layout %s" % (self.__class__,self.layout)
        return self.layout



if __name__ == "__main__":
    ballot = Ballot("one","two")
    extendedballot = ExtendedBallot("one","two")
    print ballot.printme()
    print extendedballot.printme()
    print ballot.printany()
    # class ExtendedBallot has no printany, but inherits from Ballot
    print extendedballot.printany()
