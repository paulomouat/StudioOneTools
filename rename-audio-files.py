#!/usr/bin/env python3

import sys, getopt
import zipfile
import shutil
import glob
from pathlib import Path

working_folder = "_s1rename_temp"

def usage():
    print('rename-audio-files.py -s <song-file> -f <media-folder> -i <input-prefix> -o <output-prefix>')
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

def get_renamed(mediafolder, inputprefix, outputprefix):
    inputpath = mediafolder + "/" + inputprefix
    outputpath = mediafolder + "/" + outputprefix
    
    print('reading files with path and prefix', inputpath)
    print('writing files with path and prefix', outputpath)

    single = glob.glob(inputpath + '.wav')
    rest = glob.glob(inputpath + '(*).wav')
    rest.sort()
    
    existing = []
    existing.extend(single)
    existing.extend(rest)

    rename_list = []
    len_existing = len(existing)
    zfill_count = 2 if len_existing < 100 else len(str(len_existing))
    for idx, original in enumerate(existing):
        renamed = outputpath + '-' + str(idx+1).zfill(zfill_count) + '.wav'
        rename_list.append({'original': original, 'renamed': renamed})

    return rename_list

def rename_files(mediafolder, inputprefix, outputprefix):
    renamed = get_renamed(mediafolder, inputprefix, outputprefix)
    print('renamed:', renamed)
    return renamed

def main(argv):
    inputprefix = ''
    outputprefix = ''
    songfile = ''
    mediafolder = ''

    try:
        opts, args = getopt.getopt(argv, "s:f:i:o:", ["songfile=", "mediafolder=", "inputprefix=", "outputprefix="])
    except getopt.GetoptError:
        usage()
    
    for opt, arg in opts:
        if opt in ("-i", "--inputprefix"):
            inputprefix = arg
        elif opt in ("-o", "--outputprefix"):
            outputprefix = arg
        elif opt in ("-s", "--songfile"):
            songfile = arg
        elif opt in ("-f", "--mediafolder"):
            mediafolder = arg

    if inputprefix == '' or outputprefix == '' or songfile == '' or mediafolder == '':
        usage()

    prepare_song(songfile)
    rename_files(mediafolder, inputprefix, outputprefix)    
    finalize_song('zipped.song')

if __name__ == "__main__":
   main(sys.argv[1:])