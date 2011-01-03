import pygtk
pygtk.require('2.0')
import gtk
import gobject
import select
import subprocess
import os

"""
for x in range(2):
    p = subprocess.Popen(["/usr/bin/python",
                          "scanloop5900.py","-l","18","-d","True"])
    print p.pid
    sleep(10)
    os.kill(p.pid,9)
    print p.pid
"""
last_text = ""
def timeout_func(app):
    global last_text
    try:
        if app.pid:
            (readable,writeable,exceptional) = select.select(
                [app.process_output_pipe.fileno()],[],[],1)
            if len(readable)>0:
                x = app.process_output_pipe.readline()
                #print ("TIMEOUT %s" % x)
                if len(x)>3:
                    last_text = x.replace("\n","")
                    app.label.set_text(last_text)
        else:
            app.label.set_text(last_text)
    except Exception, e:
        print e
    return True

class App():

    timeout = None
    process_object = None
    process_output_pipe = None
    pid = 0
    extractionpid = 0
    label = None
    def button1_cb(self,button,data):
        if App.pid and (App.process_object.returncode is not None):
            os.kill(App.pid,9)
            App.pid = 0
            App.process_object = None
        p = subprocess.Popen(["/usr/bin/python","-u",
                              "scanloop5900.py",
                              "-l","18",
                              "-d","True"],
                             stdout = subprocess.PIPE)
        App.process_object = p
        App.process_output_pipe = p.stdout
        #print p.stdout
        #print p.stdout.fileno()
        App.pid = p.pid
        print "Started scanner at high res",App.pid
        App.label.set_text("HiRes")
    def button2_cb(self,button,data):
        if App.pid and (App.process_object.returncode is not None):
            os.kill(App.pid,9)
            App.pid = 0
            App.process_object = None
        entrytext = App.entry1.get_text()
        entrytext = entrytext.replace('"','').replace("'","")
        if len(entrytext)>0:
            entrytext = '"'+entrytext+'"'
        p = subprocess.Popen(["/usr/bin/python","-u",
                              "scanloop5900.py",
                              "-r","150",
                              "-l","18",
                              "-d","True",
                              "-c",App.entry1.get_text()],
                             stdout = subprocess.PIPE)
        App.process_object = p
        App.pid = p.pid
        App.process_output_pipe = p.stdout
        print "Started scanner at low res",App.pid
        App.label.set_text("LoRes")

    def button3_cb(self,button,data):
        if App.pid and (App.process_object.returncode is not None):
            print "Ending",App.pid
            os.kill(App.pid,9)
            App.pid = 0
            App.process_object = None
        else:
            print "No process to end."

    def __init__(self,topwindow):
        """Create app"""

        App.root = topwindow
        vbox = gtk.VBox()
        App.root.add(vbox)
        button1 = gtk.Button("Scan templates")
        button2 = gtk.Button("Scan ballots")
        button3 = gtk.Button("Stop scanner")
        entrylabel = gtk.Label("Comment below")
        App.entry1 = gtk.Entry(80)
        App.entry1.set_text("")
        App.label = gtk.Label("Status")
        vbox.pack_start(button1)
        vbox.pack_start(button2)
        vbox.pack_start(button3)
        vbox.pack_start(App.label)
        vbox.pack_start(entrylabel)
        vbox.pack_start(App.entry1)
        #extraction = subprocess.Popen(["/usr/bin/python",
        #                      "extraction.py"])
        #App.extractionpid = extraction.pid
        #print "Started image processing subsystem, pid",App.extractionpid


        button1.connect("clicked",self.button1_cb,None)
        button2.connect("clicked",self.button2_cb,None)
        button3.connect("clicked",self.button3_cb,None)
        App.timeout = gobject.timeout_add(1500,timeout_func,self)


def on_delete_event(widget, event):
   return True

if __name__ == '__main__':
    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.connect("delete-event",on_delete_event)
    window.set_title("Scanner")
    app = App(window)
    window.show_all()
    gtk.main()

