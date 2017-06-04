import os
import sys
import glob

import subprocess
import shutil
import time
import thread

import __main__ # the module which imported us



scriptdir = os.path.dirname(os.path.abspath(__main__.__file__))
wdirFromScriptDir = "" # everything is relative (by default) the the folder where the importing script is
def wdir(*sub):
    #this function handles correctly the case sub is actually a full path and not a relative path since os.path.join with an absolute path returns just the second element
    return os.path.abspath(os.path.join(scriptdir, wdirFromScriptDir, *sub))

# this file is in root/utils
rootdir = os.path.abspath(os.path.join( os.path.dirname(os.path.abspath(__file__)), ".."))



IGNORE = 1
GET = 2
def run(cmd, stdout=None, allowFail=False, shell=False):
    # stdout can be one of None, GET, IGNORE
    if isinstance(cmd, str) and not shell: # if it's a shell command it should be a long string
        cmd = cmd.split()
    print "**", cmd
    procout = None
    if stdout is not None:
        procout = subprocess.PIPE
    p = subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout=procout, shell=shell)
    pout, perr = p.communicate()
    retcode = p.poll()
    if retcode != 0:
        print "Exit code=", retcode
        if allowFail:
            return False
        print "Command failed:", cmd
        if not stdout:
            print "Output=", pout
        raise Exception("Failed command")
    if stdout == GET:
        return pout
    return True

def run_getstr(cmd):
    s = run(cmd, stdout=GET).strip()
    #print s
    return s



def chdir(rel_path):
    wpath = wdir(rel_path)
    print "** changing dir to", wpath
    os.chdir(wpath)


def mkdir(rel_path, doPrint=True):
    if doPrint:
        print "** mkdir", rel_path
    wpath = wdir(rel_path)
    if not os.path.exists(wpath):
        os.makedirs(wpath)

def symlink(linkName, linkTo):
    linkPath = wdir(linkName)
    print "** symlink name=", linkName, " to=", linkTo
    if os.path.islink(linkPath):
        print "  ** removing existing", linkPath
        os.unlink(linkPath)
    if os.path.exists(linkPath):
        raise Exception("Real file/directory exists but I want to create a link there " + linkPath)
    os.symlink(linkTo, linkPath) # will throw if it exists
    return linkName

def copy3(src, dst, need_name_concat=True):
    if os.path.islink(src):
        if need_name_concat:
            dst = dst + "/" + os.path.basename(src)
        linkto = os.readlink(src)
        if os.path.exists(dst):
            os.unlink(dst)
        print "    LINK", src, dst, linkto
        os.symlink(linkto, dst)
    else:
        shutil.copy2(src, dst)

def mcopytree(src, dst, ignore, fileFilter):
    # copytree that doesn't fail if directories already exist
    if fileFilter:
        names = [os.path.basename(s) for s in glob.glob( os.path.join(src, fileFilter))]
        # and take directories as well
        for n in os.listdir(src):
            if os.path.isdir(os.path.join(src, n)):
                names.append(n)
    else:
        names = os.listdir(src)

    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    if not os.path.exists(dst):
        os.makedirs(dst)
    for name in names:
        if name in ignored_names:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        if os.path.isdir(srcname):
            mcopytree(srcname, dstname, ignore, fileFilter)
        else:
            copy3(srcname, dstname, need_name_concat=False) # already did the name concat


def cp(rel_from, rel_to_dir, ignore=None, createSubDir=False, asName=False, overwrite=True, fileFilter=None):
    # asName means dst already contains the name of the file
    print "** Copying", rel_from, "to", rel_to_dir
    wdst_dir = wdir(rel_to_dir)
    real_wdst_dir = wdst_dir if not asName else os.path.dirname(wdst_dir)
    if not os.path.exists(real_wdst_dir):
        print "  creating dir", real_wdst_dir
        os.makedirs(real_wdst_dir)
    wsrc = wdir(rel_from)
    gl = glob.glob(wsrc)
    assert len(gl) > 0, "No files found in glob " + wsrc
    if asName:
        assert len(gl) == 1, "cp asName can only copy one file " + wsrc
    for sp in gl:
        if os.path.isdir(sp):
            print "  DIR ", sp
            assert not asName
            dst = wdst_dir
            if len(gl) > 1 or createSubDir: # if this was the result of a glob of multiple files in a directory, need to create a subdirectory with this specific name
                dst = os.path.join(wdst_dir, os.path.basename(sp))
            mcopytree(sp, dst, ignore, fileFilter)
        else:
            print "  FILE", sp
            dst = os.path.join(wdst_dir, os.path.basename(sp))
            if not overwrite and os.path.exists(dst):
                print "   ** not overwriting", dst
                continue
            if not asName:
                copy3(sp, wdst_dir)
            else:
                shutil.copyfile(sp, wdst_dir)



def extract(rel_path, to_sub):
    if rel_path[0] == '/': # not an absolute file path
        path = rel_path
    else:
        path = wdir(rel_path)

    to = wdir(to_sub)
    if not os.path.exists(to):
        os.makedirs(to)
    if rel_path.endswith(".tar.bz2"):
        run("tar -xjf %s -C %s" % (path, to), stdout=IGNORE )
    elif rel_path.endswith(".tar.gz") or rel_path.endswith(".tgz"):
        run("tar -xzf %s -C %s" % (path, to), stdout=IGNORE )
    elif rel_path.endswith(".7z") or rel_path.endswith(".zip"):
        run("7z x -y %s -o%s" % (path, to), stdout=IGNORE )
    else:
        raise Exception("Do not know how to extract " + rel_path)

def msetenv(k, v):
    print "**ENV", k, "=", str(v)
    if v is not None:
        os.environ[k] = v
    else:
        del os.environ[k]


def extend_env(d):
    # add the dictionary variables to the current environment and save the previous environment
    if d is None:
        return None
    oldenv = {}
    for k,v in d.iteritems():
        if k in os.environ:
            oldenv[k] = os.environ[k]
        else:
            oldenv[k] = None
        msetenv(k, v)
    return oldenv

def rename(rel_from, rel_to):
    fromn = wdir(rel_from)
    ton = wdir(rel_to)
    print "** renaming", fromn, "to", ton
    os.rename(fromn, ton)

def rmtree(rel_path):
    p = wdir(rel_path)
    print "** deltree", p
    shutil.rmtree(p)



def opt_arg(options, arg, mustHave=False, default=None):
    for o in options:
        if o.startswith(arg):
            return o[len(arg):]
    if mustHave:
        raise Exception("Did not find argument `%s`" % arg)
    return default

def opt_arg_exists(options, arg):
    for o in options:
        if o.startswith(arg):
            return True
    return False



def threadPool(argLst, func, threadCount):
    done = []
    def consume():
        try:
            while True:
                x = argLst.pop()
                ln = len(argLst) #count will not be accurate since other threads might have popped in the mean time. it's a close approximation for display
                func(ln, *x)
        except IndexError:
            pass
        done.append(0)

    for i in xrange(0, threadCount):
        thread.start_new_thread(consume, ())

    while len(done) < threadCount:
        time.sleep(0.5)




# ----------------------------------------------------- command line parser ------------------------------------------------------------------

class Step:
    def __init__(self, name, func, isInBuild=True, args="", takesRestOfLine=False):
        self.name = name
        self.func = func
        self.isInBuild = isInBuild
        self.args = args
        self.takesRestOfLine = takesRestOfLine # line in adb shell bla bla bla

class StepsGroup:
    def __init__(self, name, stepsNames):
        self.name = name
        self.steps = stepsNames

# builds is a list of Steps
# groups is a list of StepGroup - named aggregations of steps
def run_steps(argv, builds, options, pre_build=None, do_get_pkgs=False, options_desc=None, check_opts=None, groups=None):
    print "started with arguments:", argv

    def dispHelp():
        defDisp = [b.name + " " + b.args for b in builds if b.isInBuild]
        addDisp = [b.name + " " + b.args for b in builds if not b.isInBuild]

        print "\nAvailable options:\n  --help\n  all  :build all default steps"
        if options_desc is not None:
            print options_desc
        print "\nIndividual build steps:\n  " + ("\n  ".join(defDisp))
        if groups is not None:
            print "\nConvenience Groups:"
            for g in groups:
                print " ", g.name, "->", " ".join(g.steps)

        if len(addDisp) > 0:
            print "\nAdditional commands:\n  " + ("\n  ".join(addDisp))

        print ""

    buildNames = [b.name for b in builds]
    groupNames = [] if groups is None else [g.name for g in groups]
    options.extend(argv[1:])
    # validate
    hasSteps = 0
    foundSteps = [] # used for logging
    wantAllSteps = False
    wantRestOfSteps = False
    for o in options:
        if o == "--help":
            dispHelp()
            return 1
        if o == "all":
            wantAllSteps = True
            continue
        if o == "rest":
            wantRestOfSteps = True
            continue
        if o in buildNames:
            hasSteps += 1
            foundSteps.append(o)
            b = builds[buildNames.index(o)]
            if b.takesRestOfLine:
                break # means we should stop parsing
            continue
        if o in groupNames:
            g = [gi for gi in groups if gi.name == o][0]
            for gstep in g.steps:
                hasSteps += 1
                foundSteps.append(gstep)
                options.append(gstep)
                b = builds[buildNames.index(gstep)] # checks its a step
                assert not b.takesRestOfLine, "can't take rest of line for group item"
            continue
        if o[0] != "-":
            print "Unknown option:", o
            return 1

    if wantAllSteps and wantRestOfSteps:
        raise Exception("Can't have 'all' and 'rest' in the same command")

    if hasSteps == 0:
        if wantRestOfSteps:
            raise Exception("to use 'rest' you must specify a step to start from")
        elif not wantAllSteps:
            dispHelp()
            return 1
    elif hasSteps == 1:
        if wantRestOfSteps:
            started = False
            for bt in builds:
                if not started and bt.name in options:
                    started = True
                if started and bt.isInBuild:
                    options.append(bt.name)
    else:
        if wantRestOfSteps:
            raise Exception("Can't have 'rest' with more than 1 steps to start from")

    if wantAllSteps:
        for bt in builds:
            if bt.isInBuild:
                options.append(bt.name)

    if check_opts is not None:
        check_opts(options)
    print "options=", options

    if pre_build is not None:
        pre_build()

    for b in builds:
        if b.name in options:
            print "\n", "-"*70, b.name, "-"*70, "\n"
            b.func()

