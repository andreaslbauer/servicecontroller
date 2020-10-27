#!/usr/bin/python3

# requires packages psutil, gitpython

import logging
import sys
import os
from os import path
from git.repo.base import Repo
import git
import shutil
import stat
import hashlib
import psutil
import getopt
import time

# global variables
SERVICEBASE = "/home/pi/pimon"
REPOS = ["datacollector", "monitorwebapp"]
LOGTOCONSOLE = False
UPDATEWAITTIME = 60 * 15

# set up logging
logging.basicConfig(filename="/tmp/servicecontroller.log", format='%(asctime)s %(levelname)s %(message)s',
                    level=logging.INFO)

# check whether Windows or Linux
IsWindows = False
if sys.platform.startswith('win'):
    IsWindows = True


# get the command line options
def getCmdOptions():
    # get the command line options
    full_cmd_arguments = sys.argv

    # Keep all but the first
    argument_list = full_cmd_arguments[1:]

    if ('-c' in argument_list):
        logging.debug("Log to console")
        LOGTOCONSOLE = True
        logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
    else:
        logging.debug("Log to /etc/servicecontroller.log")
        LOGTOCONSOLE = False
        filehandler = logging.FileHandler('/tmp/servicecontroller.log', 'a')
        log = logging.getLogger()  # root logger - Good to get it only once.
        for hdlr in log.handlers[:]:  # remove the existing file handlers
            if isinstance(hdlr, logging.FileHandler):
                log.removeHandler(hdlr)
        log.addHandler(filehandler)

    logging.info("Command line arguments passed: %s", argument_list)


# if on Windows we're running on the dev laptop.  Log to console
if IsWindows == True:
    SERVICEBASE = "C:/opt/pimon"
else:
    SERVICEBASE = "/home/pi/pimon"


# get a specific file from github
def cloneRepoFromGithub(reponame):
    repopath = "https://github.com/andreaslbauer/" + reponame
    localrepopath = SERVICEBASE + '/' + reponame
    logging.debug("Clone repository %s to local path %s", repopath, localrepopath)

    try:

        Repo.clone_from(repopath, localrepopath)
        logging.info("Successfully cloned repository %s", repopath)

    except Exception as e:
        logging.exception("Exception occurred while trying to clone repo %s", reponame)
        logging.error("Unable to clone repository %s", reponame)


# clone all repos in our repo list from github
def cloneRepo(reponame):
    cloneRepoFromGithub(reponame)


# delete all repo directories
def cleanRepo(reponame):
    # delete all the repo directories
    repopath = './' + reponame
    logging.debug("Remove files for %s in %s", reponame, repopath)

    try:
        for root, dirs, files in os.walk(repopath):
            for dir in dirs:
                os.chmod(path.join(root, dir), stat.S_IRWXU)
            for file in files:
                os.chmod(path.join(root, file), stat.S_IRWXU)
        shutil.rmtree(repopath)

    except Exception as e:
        logging.exception("Exception occurred while trying to delete repo %s", reponame)
        logging.error("Unable to remove repository %s", reponame)


# check and update repo
def checkUpdateRepo(reponame):
    repopath = SERVICEBASE + '/' + reponame
    # check whether directory exists
    if not (os.path.exists(repopath)):
        logging.debug("Path %s for repo %s does not exist, clone repo", repopath, reponame)
        cloneRepo(reponame)
        return True
    else:
        try:
            repo = git.Repo(repopath)
            reporemotename = repo.remotes.origin.name
            logging.debug("Path %s for repo %s does exist, update repo from %s", repopath, reponame, reporemotename)
            repo = git.Repo(repopath)
            changes = repo.remotes.origin.pull()
            # print(changes[0])
            # print(changes[0].flags)

            if changes[0].flags != 4:
                logging.info("Changes have been found for %s", repopath)
                return True
            else:
                return False

        except Exception as e:
            logging.exception("Exception occurred while trying to update repo %s", reponame)
            logging.error("Unable to update repository %s", reponame)
            return False


# check whether two files are identical or not
def compFiles(filepath1, filepath2):
    def md5(fname):
        md5hash = hashlib.md5()
        with open(fname) as handle:  # opening the file one line at a time for memory considerations
            for line in handle:
                md5hash.update(line.encode('utf-8'))
        return (md5hash.hexdigest())

    return md5(filepath1) == md5(filepath2)


# check whether files have changed
def updateFromReposIfChanged(reponame):
    # traverse root directory, and list directories as dirs and files as files
    filesupdated = 0
    fileschecked = 0
    repopath = reponame
    for root, dirs, files in os.walk(repopath):
        path = root.split(os.sep)
        # print((len(path) - 1) * '---', os.path.basename(root))
        # we don't want any of the git meta files
        if (len(path) < 2) or (path[1] != '.git'):
            for file in files:
                fileschecked = fileschecked + 1
                filepathsource = root + '/' + file
                filepathtarget = SERVICEBASE + '/' + root + '/' + file
                logging.debug("Check files %s and %s", filepathsource, filepathtarget)

                # first check whether the file exists in the target directory
                if not (not (os.path.exists(filepathtarget) == False) and not (
                        compFiles(filepathsource, filepathtarget) == False)):
                    # copy over the file
                    logging.info("Update file %s to %s", filepathsource, filepathtarget)
                    shutil.copyfile(filepathsource, filepathtarget)
                    filesupdated = filesupdated + 1

    logging.info("For repo %s checked %i files and updated %i files", reponame, fileschecked, filesupdated)
    return filesupdated


# restart process
def restartProcess(reponame):
    for p in psutil.process_iter():
        try:
            pexe = ""
            try:
                pexe = p.exe()
            except Exception as e:
                pexe = ""

            if "python3" in pexe:

                # see whether this is the process in question
                cmdline = p.cmdline()[1]
                if (reponame in cmdline):
                    logging.info("Found process %s (%s) with PID %s, kill it", cmdline, pexe, p.pid)

                    # stop the process
                    p.kill()
                    p.wait(timeout=10)

        except Exception as e:
            logging.exception("Exception occurred while trying to stop process %s", reponame)
            logging.error("Unable to stop process %s", reponame)

    # restart the process
    cmdline = "python3 " + SERVICEBASE + "/" + reponame + "/" + reponame + ".py &"
    logging.info("Start: %s", cmdline)
    os.system(cmdline)


def main():
    logging.info("##############################")
    logging.info("Service Controller has started")
    logging.info("##############################")

    # get and interpret command line options
    # getCmdOptions()

    if IsWindows == True:
        logging.info("Running on Windows")
    else:
        logging.info("Running on Linux")

    # log start up message
    logging.info("***************************************************************")
    logging.info("Service Controller Application has started")
    logging.info("Running %s", __file__)
    logging.info("Working directory at start is %s", os.getcwd())
    os.chdir(SERVICEBASE)
    logging.info("Working directory now is %s", os.getcwd())

    # start the services
    for reponame in REPOS:
        restartProcess(reponame)

    # now loop forever and check whether the code has changed
    # fetch it and restart the process if yes
    while True:
        for reponame in REPOS:
            logging.debug("Process repository %s", reponame)

            # check and update repos as needed
            if checkUpdateRepo(reponame):
                logging.info("Files have changed for %s.  Restart the process.", reponame)
                restartProcess(reponame)

        # sleep for 1 minute
        time.sleep(UPDATEWAITTIME)

# run the main loop
main()
