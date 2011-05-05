#!/usr/bin/env python

import pygtk
pygtk.require('2.0')
import gtk
import gobject
import select
import subprocess
import os
import webbrowser

msg0 = """This DVD contains free software enabling you to demonstrate TEVS, the Trachtenberg Election Verification System.  In addition to TEVS, it includes sample ballot images of two different designs: Hart Intercivic and ESS. Each set of sample ballot images is included at two different scanning resolutions.

TEVS is copyright 2009, 2010, 2011 Mitch Trachtenberg and is licensed under the GNU General Public License version 3.

In addition to TEVS and the sample images, this DVD includes the Ubuntu variant of the Linux operating system, the Postgres SQL database program, the Python programming language, and other useful software, including.... 

Each "count" button invokes TEVS using a different configuration file, which
points TEVS to different image locations.  Once ballots have been counted and
processed, you may display the ballots with TEVS' vote interpretation overlaid
upon them by clicking the "Display" button.  You can show the source and
processed files yourself by going to the out directory in your Home Folder.
You can go into the database tables yourself by running the psql program and
using the following commands: psql hart150 or psql hart300 or psql seq150 or
psql seq300 or psql scanned, depending on which results database you wish to
view.  """

tevsp = os.path.expanduser("~/tevs/tevs")

def browse(file):
    file = os.path.expanduser(file)
    webbrowser.open("file://" + file)

def command(*args):
    return (os.path.join(tevsp, args[0]),) + args[1:]

def term(*args):
    return ("/usr/bin/gnome-terminal", "-x") + command(*args)

def run(*args):
    print 'run', args
    return subprocess.Popen(args, cwd=tevsp)

class App(object):
    def __init__(self, topwindow):
        """Create app"""

        App.root = topwindow
        vbox = gtk.VBox()
        App.root.add(vbox)

        hart300 = BallotKind("Hart Images, 300 dpi", "hart300.cfg")
        hart150 = BallotKind("Hart Images, 150 dpi", "hart150.cfg")
        seq300 = BallotKind("Sequoia Images, 300 dpi", "seq300.cfg")
        seq150 = BallotKind("Sequoia Images, 150 dpi", "seq150.cfg")

        vbox.pack_start(hart300.frame, expand=False)
        vbox.pack_start(hart150.frame, expand=False)
        vbox.pack_start(seq300.frame, expand=False)
        vbox.pack_start(seq150.frame, expand=False)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        buffer = gtk.TextBuffer()
        buffer.set_text(msg0)
        self.text_view = gtk.TextView(buffer)
        self.text_view.set_wrap_mode(gtk.WRAP_WORD)

        self.text_view.set_border_width(10)
        sw.add(self.text_view)

        vbox.pack_start(sw)

class BallotKind(object):
    def __init__(self, label, cfg_file):
        self.cfg_file = cfg_file

        #create all the buttons
        count = gtk.Button("Count votes")
        count.connect("clicked", self.count, None)

        display = gtk.Button("Display with vote overlay")
        display.connect("clicked", self.display, None)

        #group buttons together horizontally
        group = gtk.HBox()
        for b in (count, display):
            group.pack_start(b)

        #create a frame with the given label
        frame = gtk.Frame()
        frame.set_label(label)
        frame.set_shadow_type(1)
        frame.set_border_width(10)
        frame.add(group)
        self.frame = frame

    def count(self, button, data):
        cp = run(*term("main.py", "--config", self.cfg_file))
        #need a thread to wait for cp.pid to terminate 

    def display(self, button, data):
        dp = run(*command("show_ballots.py", "--config", self.cfg_file))

def main():
    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.set_title("TEVS Demo")
    app = App(window)
    window.show_all()
    gtk.main()
    browse("~/tevs/tevs/docs/sphinx/index.html")

if __name__ == '__main__':
    main()
