#!/usr/bin/env python3

import sys, getopt
import calendar, time
import zipfile
import shutil, glob
import xml.etree.ElementTree as ET
from pathlib import Path, PurePath
from io import BytesIO

working_folder_name = "_s1rename_temp"
xmlns = "urn:presonus"
xmlns_attribute = 'xmlns:x="' + xmlns + '"'

def usage():
    print('rename-audio-files.py -s <song-file> -f <media-folder> -i <input-prefix> -o <output-prefix>')
    sys.exit(2)

def get_clipdata_path(stem):
    path = PurePath("ClipData") / "Audio" / stem
    return path

def get_clipdata_url(stem, suffix):
    path = get_clipdata_path(stem)
    url = "media://" + str(path) + "/" + stem + suffix
    return url

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

def finalize_xml_file(et, root_tag, fullpath):
    # fake file to obtain a string representation of the whole
    # file so that we can post-process it to remove the bogus
    # xml namespace declaration from the root element
    fake_file = BytesIO()
    et.write(fake_file, encoding='utf-8', xml_declaration=True) 
    xml_with_changes = fake_file.getvalue().decode('utf-8')
    processed = restore_xml(xml_with_changes, root_tag)

    with open(str(fullpath), "w") as target_file:
        target_file.write(processed)

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
    epoch_seconds = calendar.timegm(time.gmtime())
    shutil.copyfile(songfile['full'], str(songfile['full']) + "." + str(epoch_seconds) + "-bak")

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

    print('mediafolder:', mediafolder)    
    print('inputprefix:', inputprefix)
    print('outputprefix:', outputprefix)

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

def rename_files(files_to_rename):
    for idx, rename in enumerate(files_to_rename):
        shutil.copy(rename['originalFile'], rename['renamedFile'])
    return files_to_rename

def rename_file_references(songfile, files_to_rename):
    # files are referenced using URL notation
    replacements = {
        'file://' + str(e['originalFile']): {
            'renamedFile': 'file://' + str(e['renamedFile']),
            'originalStem': e['originalStem'],
            'renamedStem': e['renamedStem']
        } for e in files_to_rename
    }

    # file references are all contained in the file Song/mediapool.xml
    working_folder = get_working_folder(songfile)
    mediapool = PurePath(working_folder) / 'Song' / 'mediapool.xml'
    shutil.copyfile(mediapool, str(mediapool) + ".rename-bak")

    renamed_file_references = []

    # Studio One does not include xml namespace declarations in its files
    # and ElementTree can't handle elements with undeclared xml namespaces,
    # so we need to preprocess the file and add a bogus declaration
    xml = prepare_xml_file(mediapool, "MediaPool")
    root = ET.fromstring(xml)
    for audioClip in root.iter('AudioClip'):
        urlPaths = audioClip.findall("Url[@{urn:presonus}id='path']")
        for urlPath in urlPaths:
            url = urlPath.attrib['url']
            if url in replacements:
                replacement = replacements[url]
                urlPath.attrib['url'] = replacement['renamedFile']
                originalStem = replacement['originalStem']
                renamedStem = replacement['renamedStem']
                urlBendMarkers = audioClip.find("*//Url[@{urn:presonus}id='bendMarkers']")
                if urlBendMarkers is not None:
                    urlBendMarkers.attrib['url'] = get_clipdata_url(renamedStem, ".audiobendx")
                urlChords = audioClip.find("*//Url[@{urn:presonus}id='chords']")
                if urlChords is not None:
                    urlChords.attrib['url'] = get_clipdata_url(renamedStem, ".chordx")

                # rename clip data files
                # these files are located in child folders of ClipData/Audio, named 
                #   ClipData/Audio/<original stem>
                #       <original stem>.audiobendx
                #       <original stem>.chordx
                clipdata = working_folder / get_clipdata_path(originalStem)
                renamed_clipdata = working_folder / get_clipdata_path(renamedStem)
                shutil.move(str(clipdata / originalStem) + ".audiobendx", str(clipdata / renamedStem) + ".audiobendx")
                shutil.move(str(clipdata / originalStem) + ".chordx", str(clipdata / renamedStem) + ".chordx")
                shutil.move(str(clipdata), str(renamed_clipdata))

                # collect the clip ids of each of the renamed audio files, as we
                # need to know these to rename the events that reference them
                id = audioClip.attrib['mediaID']
                renamed_file_references.append({'id': id, 'originalStem': originalStem, 'renamedStem': renamedStem})

    et = ET.ElementTree(root)
    # need to register the namespace with prefix 'x' so that the
    # output matches what Studio One produces
    ET.register_namespace("x", xmlns)

    finalize_xml_file(et, "MediaPool", mediapool)

    return renamed_file_references

def rename_event_references(songfile, renamed_file_references):
    replacements = {
        e['id']: {
            'originalStem': e['originalStem'],
            'renamedStem': e['renamedStem']
        } for e in renamed_file_references
    }

    # event references are all contained in the file Song/song.xml
    working_folder = get_working_folder(songfile)
    song = PurePath(working_folder) / 'Song' / 'song.xml'
    shutil.copyfile(song, str(song) + ".rename-bak")

    renamed_event_references = []

    # Studio One does not include xml namespace declarations in its files
    # and ElementTree can't handle elements with undeclared xml namespaces,
    # so we need to preprocess the file and add a bogus declaration
    xml = prepare_xml_file(song, "Song")
    root = ET.fromstring(xml)

    for audioEvent in root.iter('AudioEvent'):
        id = audioEvent.attrib['clipID']
        if id in replacements:
            replacement = replacements[id]
            originalStem = replacement['originalStem']
            renamedStem = replacement['renamedStem']
            name = audioEvent.attrib['name']
            if name == originalStem:
                audioEvent.attrib['name'] = renamedStem

    et = ET.ElementTree(root)
    # need to register the namespace with prefix 'x' so that the
    # output matches what Studio One produces
    ET.register_namespace("x", xmlns)

    finalize_xml_file(et, "Song", song)

    return renamed_event_references

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

    prepare_song(songfile)
    files_to_rename = get_files_to_rename(songfile, mediafolder, inputprefix, outputprefix)
    rename_files(files_to_rename)
    renamed_file_references = rename_file_references(songfile, files_to_rename)
    rename_event_references(songfile, renamed_file_references)
    finalize_song(songfile)

if __name__ == "__main__":
   main(sys.argv[1:])