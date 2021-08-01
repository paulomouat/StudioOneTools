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
    print('replace-audio-format.py -s <song-file> -f <media-folder> -i <input-format> -o <output-format>')
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

def get_files_to_rename(songfile, mediafolder, inputformat, outputformat):
    print('mediafolder:', mediafolder)    
    print('inputprefix:', inputformat)
    print('outputprefix:', outputformat)

    existing = glob.glob(mediafolder + '/*.' + outputformat)

    rename_list = []
    for idx, renamed in enumerate(existing):
        renamedFile = Path(renamed).resolve()
        renamedPath = renamedFile.parent
        renamedStem = renamedFile.stem
        originalStem = renamedStem
        originalSuffix = "." + inputformat
        originalFile = renamedPath / (originalStem + originalSuffix)
        rename_list.append({'originalFile': originalFile, 'originalStem': originalStem, 'renamedFile': renamedFile, 'renamedStem': renamedStem})

    return rename_list

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

                attributes = audioClip.find("Attributes[@{urn:presonus}id='format']")
                if attributes is not None:
                    attributes.attrib['bitDepth'] = "24"
                    attributes.attrib['formatType'] = "1"
                    if 'sampleType' in attributes.attrib:
                        attributes.attrib.pop('sampleType')

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

def main(argv):
    inputformat = ''
    outputformat = ''
    songfileOpt = ''
    mediafolder = ''

    try:
        opts, args = getopt.getopt(argv, "s:f:i:o:", ["songfile=", "mediafolder=", "inputformat=", "outputformat="])
    except getopt.GetoptError:
        usage()
    
    for opt, arg in opts:
        if opt in ("-i", "--inputformat"):
            inputformat = arg
        elif opt in ("-o", "--outputformat"):
            outputformat = arg
        elif opt in ("-s", "--songfile"):
            songfileOpt = arg
        elif opt in ("-f", "--mediafolder"):
            mediafolder = arg

    if inputformat == '' or outputformat == '' or songfileOpt == '' or mediafolder == '':
        usage()

    resolved_media_folder = Path(mediafolder).resolve()
    if not resolved_media_folder.is_dir():
        print('media folder', mediafolder, 'not found in current directory')
        sys.exit(2)

    print('media folder', mediafolder, 'resolved to', resolved_media_folder)

    songfile = get_song_file(songfileOpt)

    prepare_song(songfile)
    files_to_rename = get_files_to_rename(songfile, mediafolder, inputformat, outputformat)
    renamed_file_references = rename_file_references(songfile, files_to_rename)
    finalize_song(songfile)

if __name__ == "__main__":
   main(sys.argv[1:])