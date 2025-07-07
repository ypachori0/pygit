# needs to be in the same directory as wyag

# since Git is a CLI application, we need something to parse command line arguments
# we will use the argparse module in order to do that
import argparse

# going to use configparser module to write a configuration file in the same format as Microsoft INI
import configparser

# for date/time manipulation
from datetime import datetime

# git saves the numerical owner/group ID of files so we will need to use the grp and pwd modules to read them from the Unix database
import grp, pwd

# we will need to do filematching for .gitignore
from fnmatch import fnmatch

# since git uses SHA-1 for encryption, we will have to do so as well, it is found in the hashlib module
import hashlib

from math import ceil

# for filesystem abstraction
import os

import re

# using sys to access the command line arguments
import sys

# using zlib to compress everything
import zlib

# program will define what arguments it needs and then argparse will figure out how to parse them out of sys.argv
# need to create an argparse.ArgumentParser instance, which is a container for argument specifications
argparser = argparse.ArgumentParser(description="The stupidest content tracker") # description parameter is the text to display before the argument help

# the main command will be "git" and then comes subcommands ("add", "commit", etc). in argparse these are called "subparsers"
# for now we just need to declare that the CLI will use subparsers and that all invocations will require a subparse
# title parameter is used to label the group of subcommands in the generated help output
# dest parameter specifies the attribute name where the chosen subcommand's name will be stored after parsing the arguments
# so basically what's happening: creating a group for subcommands under the "Commands" heading in help text, and then ensuring that the selected subcommand name will be stored in args.command
argsubparsers = argparser.add_subparsers(title="Commands", dest="command")

# defining the subcommands
def main(argv=sys.argv[1:]):
    args = argparser.parse_args(argv)
    match args.command:
        case "add"          : cmd_add(args)
        case "cat-file"     : cmd_cat_file(args)
        case "check-ignore" : cmd_check_ignore(args)
        case "checkout"     : cmd_checkout(args)
        case "commit"       : cmd_commit(args)
        case "hash-object"  : cmd_hash_object(args)
        case "init"         : cmd_init(args)
        case "log"          : cmd_log(args)
        case "ls-files"     : cmd_ls_files(args)
        case "ls-tree"      : cmd_ls_tree(args)
        case "rev-parse"    : cmd_rev_parse(args)
        case "rm"           : cmd_rm(args)
        case "show-ref"     : cmd_show_ref(args)
        case "status"       : cmd_status(args)
        case "tag"          : cmd_tag(args)
        case _              : print("Bad command.")

# git repository is made up of a "work tree" and a "git directory". the work tree has all the project files, git directory is like the brain of git: it contains everything git knows about the repo
# the contents of the file are passed through a hashing function and stored as blobs in .git/objects. the working tree contains any subdirectories and the names of all the files (no content)

# to make a new Repository object, we first need to make sure that the directory exists and cotnains a subdirectory called .git
# then we read its configuration in .git/config and make sure core.repositoryformatversion is 0

class GitRepository (object):
    """A git repository"""

    # initializing the worktree, git directory, and configuration files
    worktree = None
    gitdir = None
    conf = None

    # initializing the Repository class constructor
    # self = instance of class that is currently used, path = path to the working directory, force = boolean used to bypass validation checks (default to False)
    def __init__(self, path, force=False):
        self.worktree = path # store the path to the work tree
        self.gitdir = os.path.join(path, ".git") # construct path to git directory inside the work tree

        # checking to see if the directory exists
        if not (force or os.path.isdir(self.gitdir)):
            raise Exception(f"Not a Git repository {path}")
        
        # read configuration file in .git/config
        self.conf = configparser.ConfigParser()
        cf = repo_file(self, "config")

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Configuration file missing")
        
        # reading the configuration file to make sure core.repositoryformatversion is 0
        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception("Unsupported repositoryformatversion: {vers}")
            
### Helper Functions

# path building function
def repo_path(repo, *path):
    """Compute path under repo's gitdir."""
    return os.path.join(repo.gitdir, *path)

# function to return and/or create a path to a file. only creates directories up to last component
def repo_file(repo, *path, mkdir=False):
    """Same as repo_path, but create dirname(*path) if absent"""

    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)
    
# function to return and/or create a path to a directory
def repo_dir(repo, *path, mkdir=False):
    """Same as repo_path, but mkdir *path if absent if mkdir"""

    path = repo_path(repo, *path)
    
    if os.path.exists(path):
        if (os.path.isdir(path)):
            return path
        else:
            raise Exception(f"Not a directory {path}")
        
    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None
    
    # .git/objects/: the object store
    # .git/refs/: the reference store, contains "heads" and "tags" subdirectories
    # .git/HEAD: reference to the current HEAD
    # .git/config: the repo's config file
    # .git/description: description of repo's contents
    
# to create a new repo, we start with a directory (create one if doesn't exist) and then create the git directory inside it
def repo_create(path):
    """Create a new repository at path"""
    
    repo = GitRepository(path,True) # force is set to True because this is a new repository so we don't want to check whether it exists or not

    # first, make sure path either doesn't exist or is an empty dir
    if os.path.exists(repo.worktree): # checking if worktree directory already exists
        if not os.path.isdir(repo.worktree): # if it exists but is not a directory, raise an error
            raise Exception(f"{path} is not a directory!")
        if os.path.exists(repo.gitdir) and os.listdir(repo.gitdir): # if .git exists but is not empty, raise an error
            raise Exception (f"{path} is not empty!")
    else: # if worktree doesn't exist, create it
        os.makedirs(repo.worktree)

    assert repo_dir(repo, "branches", mkdir=True)
    assert repo_dir(repo, "objects", mkdir=True)
    assert repo_dir(repo, "refs", "tags", mkdir=True)
    assert repo_dir(repo, "refs", "heads", mkdir=True)

    # .git/description
    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unnamed repository; edit this file 'description' to name the repository.\n")

    # .git/head
    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/master\n")

    with open(repo_file(repo, "HEAD"), "w") as f:
        config = repo_default_config()
        config.write(f)

    return repo

# config file is an INI-like file with a single section ([core]) and 3 fields:
# repositoryformatversion = 0: version of the gitdir format. 0 means initial format, 1 is same with extensions. If >1, git panics
# filemode = false: disable tracking of file modes (permissions) changes in work tree (just control whether git trakcs changes to file permissions, like if a file has been made executable or not)
# bare = false: indicates that the repo has a worktree (just controls whether the repo has a working directory)
def repo_default_config():
    ret = configparser.ConfigParser()

    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")

    return ret

# init command
# first, need to create an argparse subparser to handle our command's argument
argsp = argsubparsers.add_parser("init", help="Initialize a new, empty repository.")
argsp.add_argument("path",
                   metavar="direcory",
                   nargs="?",
                   default=".",
                   help="Where to create the repository.")

# second, we need a "bridge" function that will read argument values from the object returned by argparse and call the actual function with correct values
def cmd_init(args):
    repo_create(args.path)