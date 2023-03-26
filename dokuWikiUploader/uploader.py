import argparse
import hashlib
import time
import os
import subprocess
import json

from internetarchive import get_item

from dokuWikiDumper.utils.util import url2prefix
from dokuWikiDumper.dump.info import get_info
from dokuWikiDumper.dump.info import INFO_WIKI_NAME, INFO_RAW_TITLE, INFO_DOKU_URL, INFO_LANG, INFO_ICON_URL
from dokuWikiDumper.utils.config import get_config

from .__version__ import UPLOADER_VERSION

collection = 'opensource'
USER_AGENT = 'dokuWikiUploader/' + UPLOADER_VERSION


def file_sha1(path):
    buffer = bytearray(65536)
    view = memoryview(buffer)
    digest = hashlib.sha1()

    with open(path, mode="rb") as f:
        while True:
            n = f.readinto(buffer)

            if not n:
                break

            digest.update(view[:n])

    return digest.hexdigest()


def read_ia_keys(keysfile):
    ''' Return: tuple(`access_key`, `secret_key`) '''
    with open(keysfile, 'r', encoding='utf-8') as f:
        key_lines = f.readlines()

    access_key = key_lines[0].strip()
    secret_key = key_lines[1].strip()

    return access_key, secret_key


def upload(args={}):
    dump_dir = args.dump_dir
    path7z = args.path7z # '/usr/bin/7z'
    access_key, secret_key = read_ia_keys(os.path.expanduser(args.keysfile))
    info = get_info(dump_dir)
    config = get_config(dump_dir)
    headers = {"User-Agent": USER_AGENT}


    title = (info.get(INFO_WIKI_NAME) if info.get(INFO_WIKI_NAME) else info.get(INFO_RAW_TITLE))
    title = title if info.get(INFO_RAW_TITLE) else url2prefix(info.get(INFO_DOKU_URL))
    title = title if title else 'Unknown'
    try:
        _dump_dir_ab = os.path.abspath(dump_dir)
        _dump_dir_name = os.path.basename(_dump_dir_ab)
        _dump_dir_name = _dump_dir_name.split('-')
        identifier = _dump_dir_name[0] + '-' + _dump_dir_name[1]
    except:
        identifier = url2prefix(info.get(INFO_DOKU_URL)) + '-' +  time.strftime("%Y%m%d")

    description = \
f'''DokuWiki: [{title}].

Dumped with <a href="https://github.com/saveweb/dokuwiki-dumper" rel="nofollow">dokuWiki-Dumper</a> v{config.get('dokuWikiDumper_version')}, and uploaded with dokuWikiUploader v{UPLOADER_VERSION}.
'''
    keywords = [
                    "wiki",
                    "wikiteam",
                    "DokuWiki",
                    "dokuWikiDumper",
                    "wikidump",
                    title,
                    url2prefix(info.get(INFO_DOKU_URL)),
                ]
    # Item metadata
    md = {
        "mediatype": "web",
        "collection": collection,
        "title": "Wiki - " + title,
        "description": description,
        "language": info.get(INFO_LANG) if info.get(INFO_LANG) else config.get('lang'), # 'lang' as the key name <= dokuWikiDumper v0.1.0
        "last-updated-date": time.strftime("%Y-%m-%d"),
        "subject": "; ".join(
            keywords
        ),  # Keywords should be separated by ; but it doesn't matter much; the alternative is to set one per field with subject[0], subject[1], ...
        "originalurl": info.get(INFO_DOKU_URL),
    }
    dirs_to_7z = ["attic","html","media","pages"]
    filedict = {} # remote filename: local filename
    # list all files in dump_dir/dumpMeta
    for dir in os.listdir(os.path.join(dump_dir, "dumpMeta/")):
        filedict.update({identifier+"-"+"dumpMeta/"+os.path.basename(dir): os.path.join(dump_dir, "dumpMeta/", dir)})
    for dir in dirs_to_7z:
        _dir = os.path.join(dump_dir, dir)
        if os.path.isdir(_dir):
            print(f"Compressing {_dir}...\n")
            level = 1 if dir == "media" else 5 # 
            filedict.update({identifier+"-"+dir+".7z": compress(_dir, path7z, level=level)})

    # Upload files and update metadata
    print("Preparing to upload...")
    try:
        item = get_item(identifier)
        for file_in_item in item.files:
            if file_in_item["name"] in filedict:
                filedict.pop(file_in_item["name"])
                print(f"File {file_in_item['name']} already exists in {identifier}.")
        print(f"Uploading {len(filedict)} files...")
        r = item.upload(
            files=filedict,
            metadata=md,
            access_key=access_key,
            secret_key=secret_key,
            verbose=True,
            queue_derive=False,
        )

        item.modify_metadata(md)  # update
        print(
            "You can find it in https://archive.org/details/%s"
            % (identifier)
        )
    except Exception as e:
        print(e)

def compress(dir, bin7z: str, level: int = 5):
    ''' Compress dir into dump_dir.7z and return the absolute path to the compressed file. '''
    dir = os.path.abspath(dir) # remove trailing slash
    dir_7z = dir + ".7z"
    if os.path.exists(dir_7z):
        print(f"File {dir_7z} already exists. Skip compressing.")
        return dir_7z
    
    subprocess.run(
        [bin7z, "a", "-t7z", "-m0=lzma2", f"-mx={level}", "-scsUTF-8",
            "-md=64m", "-ms=off", dir_7z+".tmp", dir],
        check=True,
    )
    # move tmp file to final file
    os.rename(dir_7z+".tmp", dir_7z)
    return dir_7z


def main(params=[]):

    parser = argparse.ArgumentParser(
        """dokuWikiUploader"""
    )
    parser.description = "Upload a DokuWiki dump to Internet Archive." + f" (Version: {UPLOADER_VERSION})."
    parser.add_argument("-kf", "--keysfile", default="~/.doku_uploader_ia_keys",
                        help="Path to the IA S3 keys file. (first line: access key, second line: secret key) [default: ~/.doku_uploader_ia_keys]")
    parser.add_argument("-p7z", "--path7z", default="7z",
                        help="Path to 7z binary. [default: 7z]")
    parser.add_argument("dump_dir", help="Path to the wiki dump directory.")
    args = parser.parse_args()

    upload(args)


if __name__ == "__main__":
    main()
