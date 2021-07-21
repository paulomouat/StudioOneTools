#!/usr/bin/env python3

import sys, getopt
import zipfile
import shutil
from pathlib import Path

working_folder = "_s1rename_temp"

def usage():
    print('rename-audio-files.py -s <song-file> -i <input-prefix> -o <output-prefix>')
    sys.exit(2)

def prepare_song(songfile):
    shutil.copyfile(songfile, songfile + ".rename-bak")

    dirpath = Path(working_folder)
    if dirpath.exists() and dirpath.is_dir():
        shutil.rmtree(dirpath)

    with zipfile.ZipFile(songfile, 'r') as zip_ref:
        zip_ref.extractall(working_folder)

def finalize_song(songfile):
    shutil.make_archive(songfile, 'zip', working_folder)
    shutil.move(songfile + '.zip', songfile)

def main(argv):
    inputprefix = ''
    outputprefix = ''
    songfile = ''

    try:
        opts, args = getopt.getopt(argv, "s:i:o:", ["songfile=", "inputprefix=", "outputprefix="])
    except getopt.GetoptError:
        usage()
    
    for opt, arg in opts:
        if opt in ("-i", "--inputprefix"):
            inputprefix = arg
        elif opt in ("-o", "--outputprefix"):
            outputprefix = arg
        elif opt in ("-s", "--songfile"):
            songfile = arg

    if inputprefix == '' or outputprefix == '' or songfile == '':
        usage()

    prepare_song(songfile)
    finalize_song('zipped.song')

if __name__ == "__main__":
   main(sys.argv[1:])