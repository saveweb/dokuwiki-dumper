import argparse
import hashlib
import shutil
import time
import os
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

from internetarchive import get_item, Item
import requests

from dokuWikiDumper.utils.util import url2prefix
from dokuWikiDumper.dump.info.info import get_info
from dokuWikiDumper.dump.info.info import INFO_WIKI_NAME, INFO_RAW_TITLE, INFO_DOKU_URL, INFO_LANG
from dokuWikiDumper.utils.config import get_config

from .__version__ import UPLOADER_VERSION


# Constants
DEFAULT_COLLECTION = 'opensource'
USER_AGENT = f'dokuWikiUploader/{UPLOADER_VERSION}'
UPLOADED_MARK = 'uploaded_to_IA.mark'
BUFFER_SIZE = 65536

# Directory configurations
DIRS_TO_7Z = ["attic", "html", "media", "pages", "pdf", "meta"]
MARK_FILES = {
    "attic": "content_dumped.mark",
    "pages": "content_dumped.mark", 
    "html": "html_dumped.mark",
    "media": "media_dumped.mark",
    "pdf": "pdf_dumped.mark",
    "dumpMeta": "dumpMeta/",
    "meta": "meta/"
}

# Compression levels
MEDIA_COMPRESSION_LEVEL = 1
DEFAULT_COMPRESSION_LEVEL = 5
NO_COMPRESSION_LEVEL = 0


@dataclass
class UploadConfig:
    """Configuration for upload process."""
    dump_dir: str
    path7z: str
    access_key: str
    secret_key: str
    collection: str
    pack_dumpMeta_dir: bool
    level0_no_compress: List[str]
    delete_after_upload: bool = False


@dataclass
class WikiMetadata:
    """Wiki metadata container."""
    name: str
    url: Optional[str]
    language: Optional[str]
    raw_title: Optional[str]


class IAUploader:
    """Internet Archive uploader for DokuWiki dumps."""
    
    def __init__(self, config: UploadConfig):
        self.config = config
        self.headers = {"User-Agent": USER_AGENT}
        
    def upload_dump(self) -> None:
        """Main upload process."""
        if self._is_already_uploaded():
            print("This dump has already been uploaded.")
            print(f"If you want to upload it again, please remove the file '{UPLOADED_MARK}'.")
            return
            
        try:
            # Prepare metadata and files
            wiki_meta = self._extract_wiki_metadata()
            identifier = self._generate_identifier()
            files_to_upload = self._prepare_files(identifier)
            
            # Upload to Internet Archive
            item_metadata = self._create_item_metadata(wiki_meta)
            self._upload_to_ia(identifier, files_to_upload, item_metadata)
            
            # Update metadata with URLs
            self._update_item_metadata(identifier, wiki_meta)
            
            # Mark as uploaded
            self._mark_as_uploaded()
            
            # Cleanup if requested
            if self.config.delete_after_upload:
                self._cleanup_dump_dir()
                
            print(f"\n\n--Done--\nYou can find it in https://archive.org/details/wiki-{identifier}")
            
        except Exception as e:
            print(f"Upload failed: {e}")
            raise
    
    def _is_already_uploaded(self) -> bool:
        """Check if dump is already uploaded."""
        return os.path.exists(os.path.join(self.config.dump_dir, UPLOADED_MARK))
    
    def _extract_wiki_metadata(self) -> WikiMetadata:
        """Extract wiki metadata from dump directory."""
        info = get_info(self.config.dump_dir)
        config = get_config(self.config.dump_dir)
        
        # Determine wiki name
        wiki_name = (info.get(INFO_WIKI_NAME) or 
                     info.get(INFO_RAW_TITLE))
        
        # Fallback to URL-based name if no name found
        if not wiki_name:
            if doku_url := info.get(INFO_DOKU_URL):
                wiki_name = url2prefix(doku_url, ascii_slugify=False)
        
        # Final fallback
        wiki_name = wiki_name or 'Unknown'
        
        # Handle special case for 'start' pages:
        # some sites use 'wikiname [pagetitle]' as the title instead of 'pagetitle [wikiname]'.
        # so, fallback to INFO_RAW_TITLE
        if wiki_name == 'start' and info.get(INFO_RAW_TITLE):
            raw_title = info.get(INFO_RAW_TITLE)
            if raw_title:
                wiki_name = raw_title.replace('[start]', '')
        
        # Clean up wiki name
        wiki_name = wiki_name.replace('\r', '').replace('\n', '').strip()
        
        return WikiMetadata(
            name=wiki_name,
            url=info.get(INFO_DOKU_URL),
            language=info.get(INFO_LANG) or config.get('lang'),
            raw_title=info.get(INFO_RAW_TITLE)
        )
    
    def _generate_identifier(self) -> str:
        """Generate identifier from dump directory name."""
        dump_dir_ab = os.path.abspath(self.config.dump_dir)
        dump_dir_basename = os.path.basename(dump_dir_ab)
        
        # Validate dump directory name format
        parts = dump_dir_basename.split('-') # Punycoded domain may contain multiple `-`
        if len(parts) < 2:
            raise ValueError(f'Invalid dump directory name: {dump_dir_basename}')
        
        try:
            timestamp = int(parts[-1])
            if timestamp < 20230200:
                raise ValueError(
                    f'Invalid dump directory name: {dump_dir_basename}, '
                    'created before dokuWikiDumper was born!?'
                )
        except ValueError as e:
            if "created before" not in str(e):
                raise ValueError(f'Invalid dump directory name: {dump_dir_basename}')
            raise
        
        return dump_dir_basename
    
    def _prepare_files(self, identifier: str) -> Dict[str, str]:
        """Prepare files for upload."""
        filedict = {}
        
        # Handle dumpMeta directory
        dirs_to_pack = DIRS_TO_7Z.copy()
        if self.config.pack_dumpMeta_dir:
            if "dumpMeta" not in dirs_to_pack:
                dirs_to_pack.append("dumpMeta")
        else:
            self._add_dumpmeta_files(identifier, filedict)
        
        # Compress and add directories
        for dir_name in dirs_to_pack:
            dir_path = os.path.join(self.config.dump_dir, dir_name)
            if os.path.isdir(dir_path):
                self._validate_directory_completion(dir_name)
                compressed_file = self._compress_directory(dir_path, dir_name)
                filedict[f"{identifier}-{dir_name}.7z"] = compressed_file
        
        return filedict
    
    def _add_dumpmeta_files(self, identifier: str, filedict: Dict[str, str]) -> None:
        """Add individual dumpMeta files to upload list."""
        dumpmeta_dir = os.path.join(self.config.dump_dir, "dumpMeta")
        if os.path.exists(dumpmeta_dir):
            for item in os.listdir(dumpmeta_dir):
                item_path = os.path.join(dumpmeta_dir, item)
                remote_name = f"{identifier}-dumpMeta/{item}"
                filedict[remote_name] = item_path
    
    def _validate_directory_completion(self, dir_name: str) -> None:
        """Validate that directory dumping is complete."""
        mark_file = MARK_FILES.get(dir_name)
        if mark_file and not mark_file.endswith('/'):
            mark_path = os.path.join(self.config.dump_dir, mark_file)
            if not os.path.exists(mark_path):
                raise Exception(
                    f"Directory {dir_name} is not finished. "
                    f"Please run dokuWikiDumper again. ({mark_file} not found)"
                )
    
    def _compress_directory(self, dir_path: str, dir_name: str) -> str:
        """Compress directory to 7z format."""
        print(f"Compressing {dir_path}...")
        
        # Determine compression level
        if dir_name in self.config.level0_no_compress:
            level = NO_COMPRESSION_LEVEL
            print(f"Packing {dir_name} with level 0 compression...")
        elif dir_name in ["media", "pdf"]:
            level = MEDIA_COMPRESSION_LEVEL
        else:
            level = DEFAULT_COMPRESSION_LEVEL
        
        return self._compress_with_7z(dir_path, level)
    
    def _compress_with_7z(self, dir_path: str, level: int) -> str:
        """Compress directory using 7z."""
        dir_path = os.path.abspath(dir_path)
        output_file = f"{dir_path}.7z"
        temp_file = f"{output_file}.tmp"
        
        if os.path.exists(output_file):
            print(f"File {output_file} already exists. Skip compressing.")
            return output_file
        
        # Build command
        if level == NO_COMPRESSION_LEVEL:
            cmd = [
                self.config.path7z, "a", "-t7z", f"-mx={level}",
                "-scsUTF-8", "-ms=off", temp_file, dir_path
            ]
        else:
            cmd = [
                self.config.path7z, "a", "-t7z", "-m0=lzma2", f"-mx={level}",
                "-scsUTF-8", "-md=64m", "-ms=off", temp_file, dir_path
            ]
        
        subprocess.run(cmd, check=True)
        os.rename(temp_file, output_file)
        return output_file
    
    def _create_item_metadata(self, wiki_meta: WikiMetadata) -> Dict[str, str]:
        """Create initial item metadata."""
        config = get_config(self.config.dump_dir)
        
        keywords = ["wiki", "wikiteam", "DokuWiki", "dokuWikiDumper", "wikidump"]
        if wiki_meta.name and wiki_meta.name not in keywords:
            keywords.append(wiki_meta.name)
        if wiki_meta.url:
            keywords.append(url2prefix(wiki_meta.url, ascii_slugify=False))
        
        description = (
            f"DokuWiki: {wiki_meta.name}\n<br>\n<br>\n"
            f"Dumped with DokuWiki-Dumper v{config.get('dokuWikiDumper_version')}, "
            f"and uploaded with dokuWikiUploader v{UPLOADER_VERSION}."
        )
        
        metadata = {
            "mediatype": "web",
            "collection": self.config.collection,
            "title": f"Wiki - {wiki_meta.name}",
            "description": description,
            "last-updated-date": time.strftime("%Y-%m-%d", time.gmtime()),
            "subject": "; ".join(keywords[:5]),  # Initial keywords only
            "upload-state": "uploading",
        }
        
        if wiki_meta.language:
            metadata["language"] = wiki_meta.language
            
        return metadata
    
    def _upload_to_ia(self, identifier: str, files: Dict[str, str], metadata: Dict[str, str]) -> None:
        """Upload files to Internet Archive."""
        remote_identifier = f"wiki-{identifier}"
        
        print(f"Identifier (Local): {identifier}")
        print(f"Identifier (Remote): {remote_identifier}")
        
        # Check for existing files
        item = get_item(remote_identifier)
        files_to_upload = self._filter_existing_files(item, files)
        
        print(f"Uploading {len(files_to_upload)} files...")
        print(metadata)
        
        if files_to_upload:
            item.upload(
                files=files_to_upload,
                metadata=metadata,
                access_key=self.config.access_key,
                secret_key=self.config.secret_key,
                verbose=True,
                queue_derive=False,
            )
        
        print(f"Uploading {len(files_to_upload)} files: Done.\n")
        
        # Wait for item to be created
        self._wait_for_item_creation(remote_identifier)
    
    def _filter_existing_files(self, item: Item, files: Dict[str, str]) -> Dict[str, str]:
        """Filter out files that already exist in the item."""
        existing_files = {f["name"] for f in item.files}
        filtered_files = {}
        
        for remote_name, local_path in files.items():
            if remote_name in existing_files:
                print(f"File {remote_name} already exists in item.")
            else:
                filtered_files[remote_name] = local_path
                
        return filtered_files
    
    def _wait_for_item_creation(self, identifier: str, max_tries: int = 30) -> None:
        """Wait for item to be created on Internet Archive."""
        tries = max_tries
        item = get_item(identifier)
        
        while not item.exists and tries > 0:
            print(f"Waiting for item to be created ({tries})...", end='\r')
            time.sleep(30)
            item = get_item(identifier)
            tries -= 1
    
    def _update_item_metadata(self, identifier: str, wiki_meta: WikiMetadata) -> None:
        """Update item metadata with URLs and final information."""
        remote_identifier = f"wiki-{identifier}"
        item = get_item(remote_identifier)
        
        print("Updating description...")
        
        updates = {}
        
        # Update description with URL
        if (wiki_meta.url and 
            (wiki_meta.url not in item.metadata.get("description", "") or
             'https://github.com/saveweb/dokuwiki-dumper' not in item.metadata.get("description", ""))):
            
            description_with_url = (
                f'DokuWiki: <a href="{wiki_meta.url}" rel="nofollow">{wiki_meta.name}</a>\n'
                '<br>\n<br>\n'
                f'Dumped with <a href="https://github.com/saveweb/dokuwiki-dumper" rel="nofollow">'
                f'DokuWiki-Dumper</a> v{get_config(self.config.dump_dir).get("dokuWikiDumper_version")}, '
                f'and uploaded with dokuWikiUploader v{UPLOADER_VERSION}.'
            )
            updates["description"] = description_with_url
        
        # Update other metadata fields
        current_date = time.strftime("%Y-%m-%d", time.gmtime())
        if item.metadata.get("last-updated-date") != current_date:
            updates["last-updated-date"] = current_date
        
        # Update subject with length limits
        subject = self._create_subject_string(wiki_meta)
        if item.metadata.get("subject") != subject:
            updates["subject"] = subject
        
        if wiki_meta.url and item.metadata.get("originalurl") != wiki_meta.url:
            updates["originalurl"] = wiki_meta.url
        
        if item.metadata.get("upload-state") != "uploaded":
            updates["upload-state"] = "uploaded"
        
        # Apply updates
        if updates:
            response = item.modify_metadata(
                metadata=updates,
                access_key=self.config.access_key,
                secret_key=self.config.secret_key
            )
            
            if isinstance(response, requests.Response):
                print(response.text)
                response.raise_for_status()
                print("Updating description: Done.")
            else:
                print("Unexpected response type during metadata update")
        else:
            print("Updating description: No need to update.")
    
    def _create_subject_string(self, wiki_meta: WikiMetadata) -> str:
        """Create subject string respecting IA's 255 byte limit."""
        base_keywords = ["wiki", "wikiteam", "DokuWiki", "dokuWikiDumper", "wikidump"]
        all_keywords = base_keywords.copy()
        
        if wiki_meta.name and wiki_meta.name not in all_keywords:
            all_keywords.append(wiki_meta.name)
        if wiki_meta.url:
            all_keywords.append(url2prefix(wiki_meta.url, ascii_slugify=False))
        
        # Try full keywords first
        full_subject = "; ".join(all_keywords)
        if len(full_subject.encode("utf-8")) <= 255:
            return full_subject
        
        # Try without wiki name
        without_name = base_keywords + ([url2prefix(wiki_meta.url, ascii_slugify=False)] if wiki_meta.url else [])
        subject_without_name = "; ".join(without_name)
        if len(subject_without_name.encode("utf-8")) <= 255:
            return subject_without_name
        
        # Fallback to base keywords only
        return "; ".join(base_keywords)
    
    def _mark_as_uploaded(self) -> None:
        """Mark dump as uploaded."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        mark_content = f"Uploaded to Internet Archive with dokuWikiUploader v{UPLOADER_VERSION} on {timestamp}"
        
        mark_path = os.path.join(self.config.dump_dir, UPLOADED_MARK)
        with open(mark_path, "w", encoding='UTF-8') as f:
            f.write(mark_content)
    
    def _cleanup_dump_dir(self) -> None:
        """Delete dump directory after upload."""
        print("Deleting the dump dir in 5 seconds...(Ctrl+C to cancel)", end="")
        for _ in range(5):
            print(".", end="", flush=True)
            time.sleep(1)
        shutil.rmtree(self.config.dump_dir)
        print("Deleted!")


# Utility functions
def file_sha1(path: str) -> str:
    """Calculate SHA1 hash of a file."""
    buffer = bytearray(BUFFER_SIZE)
    view = memoryview(buffer)
    digest = hashlib.sha1()

    with open(path, mode="rb") as f:
        while True:
            n = f.readinto(buffer)
            if not n:
                break
            digest.update(view[:n])

    return digest.hexdigest()


def read_ia_keys(keysfile: str) -> Tuple[str, str]:
    """Read Internet Archive keys from file.
    
    Returns:
        Tuple of (access_key, secret_key)
    """
    keysfile = os.path.expanduser(keysfile)
    
    
    with open(keysfile, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    if len(lines) < 2:
        raise ValueError("Keys file must contain at least 2 lines")
    
    access_key = lines[0].strip()
    secret_key = lines[1].strip()
        
    return access_key, secret_key


def create_upload_config(args: argparse.Namespace) -> UploadConfig:
    """Create upload configuration from command line arguments."""
    access_key, secret_key = read_ia_keys(args.keysfile)
    
    return UploadConfig(
        dump_dir=args.dump_dir,
        path7z=args.path7z,
        access_key=access_key,
        secret_key=secret_key,
        collection=args.collection,
        pack_dumpMeta_dir=args.pack_dumpMeta,
        level0_no_compress=args.level0_no_compress or [],
        delete_after_upload=args.delete
    )


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        prog="dokuWikiUploader",
        description=f"Upload a DokuWiki dump to Internet Archive. (Version: {UPLOADER_VERSION})."
    )
    
    parser.add_argument(
        "-kf", "--keysfile", 
        default="~/.doku_uploader_ia_keys",
        help="Path to the IA S3 keys file. (first line: access key, second line: secret key) "
             "[default: ~/.doku_uploader_ia_keys]"
    )
    
    parser.add_argument(
        "-p7z", "--path7z", 
        default="7z",
        help="Path to 7z binary. [default: 7z]"
    )
    
    parser.add_argument(
        "-c", "--collection", 
        default=DEFAULT_COLLECTION,
        help="Collection to upload to. ('test_collection' for testing (auto-delete after 30 days) "
             "[default: opensource]"
    )
    
    parser.add_argument(
        "-p", "--pack-dumpMeta", 
        action="store_true",
        help="Pack the dumpMeta/ directory into a 7z file, then upload it. "
             "instead of uploading all files in dumpMeta/ directory individually. "
             "[default: False]"
    )
    
    parser.add_argument(
        '-n', '--level0-no-compress', 
        default=[], 
        dest='level0_no_compress',
        choices=['media', 'pdf'], 
        nargs='?', 
        action='append',
        help='Pack specified dir(s) into 7z file(s) without any compression. (level 0, copy mode)'
    )
    
    parser.add_argument(
        '-d', '--delete', 
        action='store_true', 
        dest='delete',
        help='Delete the dump dir after uploading. [default: False]'
    )
    
    parser.add_argument(
        "dump_dir", 
        help="Path to the wiki dump directory."
    )
    
    return parser


def main(params: Optional[List[str]] = None) -> int:
    """Main entry point."""
    parser = create_argument_parser()
    args = parser.parse_args(params)
    
    try:
        config = create_upload_config(args)
        uploader = IAUploader(config)
        uploader.upload_dump()
        return 0
        
    except KeyboardInterrupt:
        print("\nUpload cancelled by user.")
        return 1
    except Exception as e:
        print(f"Upload failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
