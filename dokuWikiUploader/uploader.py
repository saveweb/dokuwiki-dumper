import argparse
import hashlib
import shutil
import time
import os
import subprocess

from internetarchive import get_item
import requests

from dokuWikiDumper.utils.util import url2prefix
from dokuWikiDumper.dump.info.info import get_info
from dokuWikiDumper.dump.info.info import INFO_WIKI_NAME, INFO_RAW_TITLE, INFO_DOKU_URL, INFO_LANG
from dokuWikiDumper.utils.config import get_config

from .__version__ import UPLOADER_VERSION

DEFAULT_COLLECTION = 'opensource'
USER_AGENT = 'dokuWikiUploader/' + UPLOADER_VERSION
UPLOADED_MARK = 'uploaded_to_IA.mark'


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


def upload(args: argparse.Namespace):
    dump_dir = args.dump_dir
    path7z = args.path7z # '/usr/bin/7z'
    access_key, secret_key = read_ia_keys(os.path.expanduser(args.keysfile))
    collection = args.collection
    pack_dumpMeta_dir = args.pack_dumpMeta
    level0_no_compress = args.level0_no_compress


    info = get_info(dump_dir)
    config = get_config(dump_dir)
    headers = {"User-Agent": USER_AGENT}


    wikiname = (info.get(INFO_WIKI_NAME) if info.get(INFO_WIKI_NAME) else info.get(INFO_RAW_TITLE))
    wikiname = wikiname if info.get(INFO_RAW_TITLE) else url2prefix(info.get(INFO_DOKU_URL), ascii_slugify=False)
    wikiname = wikiname if wikiname else 'Unknown'
    if wikiname == 'start':
        # some sites use 'wikiname [pagetitle]' as the title instead of 'pagetitle [wikiname]'.
        # so, fallback to INFO_RAW_TITLE
        wikiname = info.get(INFO_RAW_TITLE)
        assert isinstance(wikiname, str)
        wikiname = wikiname.replace('[start]', '')

    wikiname = wikiname.replace('\r', '').replace('\n', '').strip()
    try:
        _dump_dir_ab = os.path.abspath(dump_dir)
        _dump_dir_basename = os.path.basename(_dump_dir_ab)
        __dump_dir_basename = _dump_dir_basename.split('-')
        if len(__dump_dir_basename) >= 2: # Punycoded domain may contain multiple `-`
            if int(__dump_dir_basename[-1]) < 20230200:
                raise ValueError('Invalid dump directory name: %s, OMG, I cannot believe it was created before dokuWikiDumper was born!? (0w0)' % _dump_dir_basename)
        else:
            raise ValueError('Invalid dump directory name: %s' % _dump_dir_basename)
        identifier_local = _dump_dir_basename
    except Exception as e:
        print(e)
        print("\nSomething went wrong during generating the identifier. \n")
        raise e
    
    identifier_remote = 'wiki-' + identifier_local # 'wiki-' is the prefix of all wikis in archive.org
    # with the prefix, wikidump can go into wikiteam collection.

    # identifier_remote = 'test-wiki-' + identifier_local # 

    description_with_URL = \
f'''DokuWiki: <a href="{info.get(INFO_DOKU_URL)}" rel="nofollow">{wikiname}</a>
<br>
<br>
Dumped with <a href="https://github.com/saveweb/dokuwiki-dumper" rel="nofollow">DokuWiki-Dumper</a> v{config.get('dokuWikiDumper_version')}, and uploaded with dokuWikiUploader v{UPLOADER_VERSION}.'''
    description_without_URL = \
f'''DokuWiki: {wikiname}
<br>
<br>
Dumped with DokuWiki-Dumper v{config.get('dokuWikiDumper_version')}, and uploaded with dokuWikiUploader v{UPLOADER_VERSION}.'''
    keywords_init = [
        "wiki",
        "wikiteam",
        "DokuWiki",
        "dokuWikiDumper",
        "wikidump",
    ]
    keywords_full = keywords_init.copy()
    if wikiname and wikiname not in keywords_full:
        keywords_full.append(wikiname)
    if info.get(INFO_DOKU_URL):
        keywords_full.append(url2prefix(info.get(INFO_DOKU_URL), ascii_slugify=False))


    # Item metadata
    md_init = {
        "mediatype": "web",
        "collection": collection,
        "title": "Wiki - " + wikiname,
        "description": description_without_URL, # without URL, to bypass IA's anti-spam.
        "last-updated-date": time.strftime("%Y-%m-%d", time.gmtime()),
        "subject": "; ".join(
            keywords_init
        ),  # Keywords should be separated by ; but it doesn't matter much; the alternative is to set one per field with subject[0], subject[1], ...
        "upload-state": "uploading",
    }
    language = info.get(INFO_LANG) if info.get(INFO_LANG) else config.get('lang')
    if language:
        md_init.update({
            "language": language,
        })


    dirs_to_7z = ["attic","html","media","pages", "pdf", "meta"]
    mark_files = {"attic":  "content_dumped.mark", 
                "pages":    "content_dumped.mark",
                "html":     "html_dumped.mark",
                "media":    "media_dumped.mark",
                "pdf":      "pdf_dumped.mark",
                "dumpMeta": "dumpMeta/", # no .mark file for dumpMeta, check itself instead.
                "meta":     "meta/" # no .mark file...
                }
    filedict = {} # "remote filename": "local filename"

    if pack_dumpMeta_dir:
        dirs_to_7z.append("dumpMeta")
    else:
        # list all files in dump_dir/dumpMeta
        for dir in os.listdir(os.path.join(dump_dir, "dumpMeta/")):
            filedict.update({identifier_local+"-"+"dumpMeta/"+os.path.basename(dir): os.path.join(dump_dir, "dumpMeta/", dir)})

    for dir in dirs_to_7z:
        _dir = os.path.join(dump_dir, dir)
        if os.path.isdir(_dir):

            if not os.path.exists(os.path.join(dump_dir, mark_files[dir])):
                raise Exception(f"Directory {dir} is not finished. Please run dokuWikiDumper again. ({mark_files[dir]} not found)")

            print(f"Compressing {_dir}...")
            level = 1 if (dir == "media" or dir == "pdf") else 5
            if dir in level0_no_compress:
                print(f"Packing {dir} with level 0 compression...")
                level = 0
            filedict.update({identifier_local+"-"+dir+".7z": compress(_dir, path7z, level=level)})

    # Upload files and update metadata
    print("Preparing to upload...")
    try:
        print(f"Identifier (Local): {identifier_local}")
        print(f"Identifier (Remote): {identifier_remote}")
        item = get_item(identifier_remote)
        for file_in_item in item.files:
            if file_in_item["name"] in filedict:
                filedict.pop(file_in_item["name"])
                print(f"File {file_in_item['name']} already exists in {identifier_remote}.")
        print(f"Uploading {len(filedict)} files...")
        print(md_init)
        if filedict:
            item.upload(
                files=filedict,
                metadata=md_init,
                access_key=access_key,
                secret_key=secret_key,
                verbose=True,
                queue_derive=False,
            )
        print(f"Uploading {len(filedict)} files: Done.\n")


        tries = 30
        item = get_item(identifier_remote) # refresh item
        while not item.exists and tries > 0:
            print(f"Waiting for item to be created ({tries})  ...", end='\r')
            time.sleep(30)
            item = get_item(identifier_remote)
            tries -= 1


        print("Updating description...")
        new_md  = {}
        if (info.get(INFO_DOKU_URL,"") not in item.metadata.get("description", "") or
            'https://github.com/saveweb/dokuwiki-dumper' not in item.metadata.get("description", "")):
            # IA will format the description's HTML, so we can't just use `==` to compare.
            print("    (add URL back: %s )..." % info.get(INFO_DOKU_URL))
            new_md.update({"description": description_with_URL})

        if item.metadata.get("last-updated-date") != time.strftime("%Y-%m-%d", time.gmtime()):
            print("    (update last-updated-date to %s )..." % time.strftime("%Y-%m-%d", time.gmtime()))
            new_md.update({"last-updated-date": time.strftime("%Y-%m-%d", time.gmtime())})
        
        _subject_full = "; ".join(keywords_full)
        _subject_without_wikiname = "; ".join(keywords_init + [url2prefix(info.get(INFO_DOKU_URL), ascii_slugify=False)])
        # IA's subject field has a 255 bytes length limit, so we need to truncate it.
        # wikiname may be too long, remove it first.
        subject_final = _subject_full if len(_subject_full.encode("utf-8")) <= 255 else _subject_without_wikiname
        # if it's still too long, use the init keywords.
        subject_final = subject_final if len(subject_final.encode("utf-8")) <= 255 else "; ".join(keywords_init)
        if item.metadata.get("subject") != subject_final:
            print("    (update subject: %s )..." % subject_final)
            new_md.update({"subject": subject_final})

        if item.metadata.get("originalurl") != info.get(INFO_DOKU_URL):
            print("    (update originalurl: %s )..." % info.get(INFO_DOKU_URL))
            new_md.update({"originalurl": info.get(INFO_DOKU_URL)})

        if item.metadata.get("upload-state") != "uploaded":
            print("    (update upload-state: uploaded)...")
            new_md.update({"upload-state": "uploaded"})

        if new_md:
            r = item.modify_metadata(metadata=new_md, # update
                                    access_key=access_key, secret_key=secret_key)
            if isinstance(r, requests.Request):
                breakpoint() # debug mode
            assert isinstance(r, requests.Response)
            print(r.text)
            r.raise_for_status()
            print("Updating description: Done.")
        else:
            print("Updating description: No need to update.")


        print(
            "\n\n--Done--\nYou can find it in https://archive.org/details/%s"
            % (identifier_remote)
        )
    except Exception as e:
        raise e

def compress(dir, bin7z: str, level: int = 5):
    ''' Compress dir into dump_dir.7z and return the absolute path to the compressed file. '''
    dir = os.path.abspath(dir) # remove trailing slash
    dir_7z = dir + ".7z"
    if os.path.exists(dir_7z):
        print(f"File {dir_7z} already exists. Skip compressing.")
        return dir_7z

    cmds = [bin7z, "a", "-t7z", "-m0=lzma2", f"-mx={level}", "-scsUTF-8",
            "-md=64m", "-ms=off", dir_7z+".tmp", dir]
    if level == 0:
        cmds = [bin7z, "a", "-t7z", f"-mx={level}", "-scsUTF-8",
                "-ms=off", dir_7z+".tmp", dir]


    subprocess.run(
        cmds,
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
                        help="Path to the IA S3 keys file. (first line: access key, second line: secret key)"
                             " [default: ~/.doku_uploader_ia_keys]")
    parser.add_argument("-p7z", "--path7z", default="7z",
                        help="Path to 7z binary. [default: 7z]")
    parser.add_argument("-c", "--collection", default=DEFAULT_COLLECTION,
                        help="Collection to upload to. ('test_collection' for testing (auto-delete after 30 days) "
                             "[default: opensource]")
    parser.add_argument("-p", "--pack-dumpMeta", action="store_true",
                        help="Pack the dumpMeta/ directory into a 7z file, then upload it. "
                             "instead of uploading all files in dumpMeta/ directory individually. "
                             "[default: False]")
    parser.add_argument('-n', '--level0-no-compress',default=[],dest='level0_no_compress',
                        choices=['media', 'pdf'], nargs='?',action='append',
                        help='Pack XXYY dir(s) into 7z file(s) without any compression. (level 0, copy mode)')
    parser.add_argument('-d', '--delete', action='store_true', dest='delete',
                        help='Delete the dump dir after uploading. [default: False]')
    parser.add_argument("dump_dir", help="Path to the wiki dump directory.")
    args = parser.parse_args()

    if os.path.exists(os.path.join(args.dump_dir, UPLOADED_MARK)):
        print("This dump has already been uploaded.")
        print("If you want to upload it again, please remove the file '%s'." % UPLOADED_MARK)
        return 0

    upload(args)

    with open(os.path.join(args.dump_dir, UPLOADED_MARK), "w", encoding='UTF-8') as f:
        f.write("Uploaded to Internet Archive with dokuWikiUploader v%s on %s" % (UPLOADER_VERSION, time.strftime("%Y-%m-%d %H:%M:%S")))
    
    if args.delete:
        print("Deleting the dump dir in 5 seconds...(Ctrl+C to cancel)", end="")
        for _ in range(5):
            print(".", end="", flush=True)
            time.sleep(1)
        shutil.rmtree(args.dump_dir)
        print("Deleted!")

if __name__ == "__main__":
    main()
