#!/usr/bin/python3

# requires packages psutil, gitpython

import logging
import sys
import os
from os import path
from git.repo.base import Repo
import shutil
import stat
import hashlib
import psutil
import getopt

# global variables
SERVICEBASE = "/home/pi/pimon"
REPOS = ["datacollector", "monitorwebapp"]
LOGTOCONSOLE = False

# set up logging
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

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
        logging.info("Log to console")
        LOGTOCONSOLE = True
        logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
    else:
        logging.info("Log to /etc/servicecontroller.log")
        LOGTOCONSOLE = False
        filehandler = logging.FileHandler('/tmp/servicecontroller.log', 'a')
        log = logging.getLogger()  # root logger - Good to get it only once.
        for hdlr in log.handlers[:]:  # remove the existing file handlers
            if isinstance(hdlr,logging.FileHandler):
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
    logging.info("Clone repository %s", repopath)

    try:
        Repo.clone_from(repopath, reponame)
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
    logging.info("Remove files for %s in %s", reponame, repopath)

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

# check whether two files are identical or not
def compFiles(filepath1, filepath2):

    def md5(fname):
        md5hash = hashlib.md5()
        with open(fname) as handle: #opening the file one line at a time for memory considerations
            for line in handle:
                md5hash.update(line.encode('utf-8'))
        return(md5hash.hexdigest())

    return md5(filepath1) == md5(filepath2)

# check whether files have changed
def updateFromReposIfChanged(reponame):
    # traverse root directory, and list directories as dirs and files as files
    filesupdated = 0
    fileschecked = 0
    repopath = reponame
    for root, dirs, files in os.walk(repopath):
        path = root.split(os.sep)
        #print((len(path) - 1) * '---', os.path.basename(root))
        # we don't want any of the git meta files
        if (len(path) < 2) or (path[1] != '.git'):
            for file in files:
                fileschecked = fileschecked + 1
                filepathsource = root + '/' + file
                filepathtarget = SERVICEBASE + '/' + root + '/' + file
                logging.info("Check files %s and %s", filepathsource, filepathtarget)

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
            if "python3" in p.exe():
                print(p.name(), p.cmdline)
        except Exception as e:
            a = 0


def main():
    logging.info("##############################")
    logging.info("Service Controller has started")
    logging.info("##############################")

    # get and interpret command line options
    getCmdOptions()

    if IsWindows == True:
        logging.info("Running on Windows")
    else:
        logging.info("Running on Linux")

    # log start up message
    logging.info("***************************************************************")
    logging.info("Web Monitor Application has started")
    logging.info("Running %s", __file__)
    logging.info("Working directory is %s", os.getcwd())

    for reponame in REPOS:
        logging.info("Process repository %s", reponame)

        # clone the repos
        cloneRepo(reponame)

        # check whether any files have changed (or are new)
        if (updateFromReposIfChanged(reponame) > 0):
            logging.info("Files have changed for %s.  Restart the process.", reponame)
        restartProcess(reponame)

        # clean up the repo
        cleanRepo(reponame)

# run the main loop
main()
