#!/usr/bin/env python3

import sys, getopt
import zipfile
import shutil
import glob
import xml.etree.ElementTree as ET
from pathlib import Path, PurePath
from io import BytesIO

working_folder_name = "_s1rename_temp"
xmlns_attribute = 'xmlns:x="http://www.presonus.com/"'

def usage():
    print('rename-audio-files.py -s <song-file> -f <media-folder> -i <input-prefix> -o <output-prefix>')
    sys.exit(2)

def prepare_xml_file(file, root_tag):
    lines = []
    with open(file, encoding='UTF-8') as f:
        lines = f.readlines()
    
    root_str = '<' + root_tag
    processed = []
    for idx, line in enumerate(lines):
        if line.startswith(root_str):
            line = line.replace(root_tag, root_tag + ' ' + xmlns_attribute, 1)
        processed.append(line)

    xml = ''.join(processed)
    return xml

def restore_xml(xml, root_tag):
    lines = xml.splitlines()
    
    root_str = '<' + root_tag
    processed = []
    for idx, line in enumerate(lines):
        if line.startswith(root_str):
            line = line.replace(root_tag + ' ' + xmlns_attribute, root_tag, 1)
        processed.append(line)

    restored = '\n'.join(processed)
    return restored

def get_song_file(songfile):
    full = PurePath(songfile)
    path = full.parent
    stem = full.stem
    suffix = full.suffix
    return {'full': full, 'path': path, 'stem': stem, 'suffix': suffix}

def get_working_folder(songfile):
    path = Path(songfile['path']) / working_folder_name
    return path

def prepare_song(songfile):
    shutil.copyfile(songfile['full'], str(songfile['full']) + ".rename-bak")

    working_folder = get_working_folder(songfile)
    if working_folder.exists() and working_folder.is_dir():
        shutil.rmtree(working_folder)

    with zipfile.ZipFile(songfile['full'], 'r') as zip_ref:
        zip_ref.extractall(working_folder)

def finalize_song(songfile):
    working_folder = get_working_folder(songfile)
    path_and_stem = songfile['path'] / songfile['stem']
    shutil.make_archive(path_and_stem, 'zip', working_folder)
    shutil.move(str(path_and_stem) + '.zip', str(path_and_stem) + songfile['suffix'])

def get_files_to_rename(songfile, mediafolder, inputprefix, outputprefix):
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
        originalFile = PurePath(original)
        originalPath = originalFile.parent
        originalStem = originalFile.stem
        originalSuffix = originalFile.suffix
        renamedStem = outputprefix + '-' + str(idx+1).zfill(zfill_count)
        renamedFile = originalPath / (renamedStem + originalSuffix)
        rename_list.append({'originalFile': originalFile, 'originalStem': originalStem, 'renamedFile': renamedFile, 'renamedStem': renamedStem})

    return rename_list

def get_events_to_rename(files_to_rename):
    event_list = []
    return event_list

def rename_files(files_to_rename):
    for idx, rename in enumerate(files_to_rename):
        shutil.copy(rename['originalFile'], rename['renamedFile'])
    return files_to_rename

def rename_file_references(songfile, files_to_rename):
    # files are referenced using URL notation
    replacements = {'file://' + str(e['originalFile']): 'file://' + str(e['renamedFile']) for e in files_to_rename}

    # file references are all contained in the file Song/mediapool.xml
    working_folder = get_working_folder(songfile)
    mediapool = PurePath(working_folder) / 'Song' / 'mediapool.xml'

    shutil.copyfile(mediapool, str(mediapool) + ".rename-bak")

    # Studio One does not include xml namespace declarations in its files
    # and ElementTree can't handle elements with undeclared xml namespaces,
    # so we need to preprocess the file and add a bogus declaration
    xml = prepare_xml_file(mediapool, "MediaPool")
    root = ET.fromstring(xml)
    for audioClip in root.iter('AudioClip'):
        urlElements = audioClip.findall("Url[@{http://www.presonus.com/}id='path']")
        for urlElement in urlElements:
            url = urlElement.attrib['url']
            if url in replacements:
                urlElement.attrib['url'] = replacements[url]

    et = ET.ElementTree(root)
    # need to register the namespace with prefix 'x' so that the
    # output matches what Studio One produces
    ET.register_namespace("x", "http://www.presonus.com/")

    # fake file to obtain a string representation of the whole
    # file so that we can post-process it to remove the bogus
    # xml namespace declaration from the root element
    fake_file = BytesIO()
    et.write(fake_file, encoding='utf-8', xml_declaration=True) 
    xml_with_changes = fake_file.getvalue().decode('utf-8')
    processed = restore_xml(xml_with_changes, "MediaPool")

    with open(str(mediapool) + ".new.xml", "w") as mediapool_file:
        mediapool_file.write(processed)

    return files_to_rename

def rename_event_references(events_to_rename):
    return events_to_rename

def main(argv):
    inputprefix = ''
    outputprefix = ''
    songfileOpt = ''
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
            songfileOpt = arg
        elif opt in ("-f", "--mediafolder"):
            mediafolder = arg

    if inputprefix == '' or outputprefix == '' or songfileOpt == '' or mediafolder == '':
        usage()

    songfile = get_song_file(songfileOpt)

    #prepare_song(songfile)
    files_to_rename = get_files_to_rename(songfile, mediafolder, inputprefix, outputprefix)
    rename_files(files_to_rename)
    rename_file_references(songfile, files_to_rename)
    events_to_rename = get_events_to_rename(files_to_rename)
    rename_event_references(events_to_rename)
    songfile['stem'] = 'zipped'
    finalize_song(songfile)

if __name__ == "__main__":
   main(sys.argv[1:])