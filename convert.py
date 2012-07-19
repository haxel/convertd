#!/usr/bin/env python

import os,signal,time,shutil

from twisted.application import service,internet
from twisted.internet import reactor,defer
from twisted.internet.task import LoopingCall
from twisted.internet.protocol import Factory ,ProcessProtocol
from twisted.protocols.basic import LineOnlyReceiver

ROOT = "/path/to/root/"
TMP = "/tmp/"
FFMPEG = "/usr/bin/ffmpeg"
ARGS_3GP = ["-s","sqcif","-r","12","-ac","1","-ar","8000","-ab","12","-y"]
ARGS_FLV = ["-s","320x240","-y"]
MAXTIME = 60

class ffmpegProtocol(ProcessProtocol):

    def __init__(self,service,file):
        self.file = file
        self.service = service
    
    def connectionMade(self):
        print "start task %d" % self.transport.pid
        self.file.startConversion(self.transport.pid)

    def processEnded(self, status):
        rc = status.value.exitCode
        if rc == 0:
            self.service.renderVideoDone(self.file)
        else:
            self.service.renderVideoError(self.file)

class File:
    
    def __init__(self,name,format):
        self.process = None
        self.name = name
        self.format = format
        self.start = 0
        
    def startConversion(self,pid):
        self.process = pid
        self.start = time.time()

    def checkConversion(self):
        if self.start == 0: return 0
        if (time.time() - self.start) > MAXTIME:
            if self.process: 
                os.kill(self.process,signal.SIGKILL) 
                print str(self) + " was taking too long probably went bonkers - i killed it"
    
    def basename(self,ext):
        return ".".join(self.name.split(".")[:-1] + [ext])
        
    def __cmp__(self,other):
        if self.name == other.name and self.format == other.format: 
            return 0
        return 1
    
    def __repr__(self):
        return self.name + " -> "  + self.format
        
        
class ConvertProtocol(LineOnlyReceiver):
    delimiter = '\n'
    
    def lineReceived(self, line):
        (name,format) = line.strip().split(" | ")
        self.service.addJob(name,format)
        self.transport.loseConnection()

class ConvertService(service.Service):
    
    def __init__(self):
        self.files = []
        self.working = 0
        self.watchdog = LoopingCall(self.checkJobs)
        self.watchdog.start(20)
        
    def getFactory(self):
        f = Factory()
        f.protocol = ConvertProtocol
        f.protocol.service = self
        return f        

    def renderVideoDone(self,file):
        print "%s is converted!" % file
        if file.format == "3gp":
            source = TMP + file.basename("3gp")
            destination = ROOT + "orbit_mobile/" + file.basename("3gp")
        elif file.format == "flv":
            source = TMP + file.basename("flv")
            destination = ROOT + "orbit/" + file.basename("flv")
        shutil.copyfile(source, destination)
        self.finishJob(file)

    def renderVideoError(self,file):
        print "error rendering %s!" % file
        self.finishJob(file)

    def finishJob(self,file):
        self.working = 0
        self.files.remove(file)
        self.renderVideo()

    def nextJob(self):
        if len(self.files): 
            file = self.files[0]
            return file

    def checkJobs(self):
        for f in self.files:
            f.checkConversion()

    def addJob(self,filename,fileformat):            
        if len(self.files) > 100:
            print "TOO MANY JOBS!!"
            return
        file = File(filename,fileformat)
        if file in self.files:
            print str(file) + " is already in queue!"
        else: 
            self.files.append(file)
            self.renderVideo()
            self.working = 1
            print str(file) + " added to queue!"

    def renderVideo(self):
        if self.working or len(self.files) == 0: 
            return
        file = self.nextJob()
        if not file: return
        ffmpeg = ffmpegProtocol(self,file)

        from twisted.internet import reactor
        oldfile = ROOT + file.name
        if file.format == "3gp":
            newfile = TMP + file.basename("3gp")
            args = [FFMPEG,"-i",oldfile]+ARGS_3GP+[newfile]
        elif file.format == "flv":
            newfile = TMP + file.basename("flv")
            args = [FFMPEG,"-i",oldfile]+ARGS_FLV+[newfile]
        reactor.spawnProcess(ffmpeg,FFMPEG,args) # childFDs={ 0: 0, 1: 1, 2: 2} for debugging
    
try:
    os.unlink('/tmp/converterd.sock')
except OSError:
    pass


application = service.Application("convertd")
serviceCollection = service.IService(application)
s = ConvertService()
internet.UNIXServer("/tmp/converterd.sock",s.getFactory()).setServiceParent(serviceCollection)
