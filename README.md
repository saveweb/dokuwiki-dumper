# DokuWiki Dumper

> A tool for archiving DokuWiki.

Recommend using `dokuWikiDumper` on _modern_ filesystems, such as `ext4` or `btrfs`. `NTFS` is not recommended because of it denys many special characters in filename.

## Requirements

### dokuWikiDumper

- Python 3.8+ (developed on py3.10)
- beautifulsoup4
- requests
- lxml

### dokuWikiUploader

> **NOTE: `dokuWikiUploader` is not ready yet.**  
> Upload dump to [Internet Archive](https://archive.org/)

- internetarchive
- 7z

## Install `dokuWikiDumper` with `Poetry`

- Install `Poetry`

    ```bash
    pip3 install poetry
    ```

- Install `dokuWikiDumper`

    ```bash
    git clone https://github.com/saveweb/dokuwiki-dumper
    cd dokuwiki-dumper
    poetry install
    poetry build
    pip install --force-reinstall dist/dokuWikiDumper*.whl
    ```

## Usage

```bash
usage: dokuWikiDumper [-h] [--content] [--media] [--html] [--skip-to SKIP_TO] [--path PATH] [--no-resume] [--threads THREADS]
                      [--insecure] [--ignore-errors] [--ignore-action-disabled-edit] [--username USERNAME] [--password PASSWORD]
                      [--cookies COOKIES] [--auto]
                      url

dokuWikiDumper

positional arguments:
  url                   URL of the dokuWiki

options:
  -h, --help            show this help message and exit
  --content             Dump content
  --media               Dump media
  --html                Dump HTML
  --skip-to SKIP_TO     !DEV! Skip to title number [default: 0]
  --path PATH           Specify dump directory [default: <site>-<date>]
  --no-resume           Do not resume a previous dump [default: resume]
  --threads THREADS     Number of sub threads to use [default: 1], not recommended to set > 5
  --insecure            Disable SSL certificate verification
  --ignore-errors       !DANGEROUS! ignore errors in the sub threads. This may cause incomplete dumps.
  --ignore-action-disabled-edit
                        Some sites disable edit action for anonymous users and some core pages.This option will ignore this error.
                        But you may only get a partial dump. (only works with --content)
  --username USERNAME   login: username
  --password PASSWORD   login: password
  --cookies COOKIES     cookies file
  --auto                dump: content+media+html, threads=5, ignore-action-disable-edit
```

For most cases, you can use `--auto` to dump the site.

```bash
dokuWikiDumper https://example.com/wiki/ --auto
```

which is equivalent to

```bash
dokuWikiDumper https://example.com/wiki/ --content --media --html --threads 5 --ignore-action-disabled-edit
```

> Highly recommend using `--username` and `--password` to login (or using `--cookies`), because some sites may disable anonymous users to access some pages or check the raw wikitext.

`--cookies` accepts a Netscape cookies file, you can use [cookies.txt Extension](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/) to export cookies from Firefox. It also accepts a json cookies file created by [Cookie Quick Manager](https://addons.mozilla.org/en-US/firefox/addon/cookie-quick-manager/).

## Dump structure

<!-- Dump structure -->
| Directory or File       | Description                                 |
|-----------              |-------------                                |
| `attic/`                | old revisions of page.                      |
| `dumpMeta/`             | (dokuWikiDumper only) metadata of the dump. |
| `dumpMeta/config.json`  | dump's configuration.                       |
| `dumpMeta/favicon.ico`  | favicon of the site.                        |
| `dumpMeta/files.txt`    | list of filename.                           |
| `dumpMeta/index.html`   | homepage of the wiki.                       |
| `dumpMeta/info.json`    | infomations of the wiki.                    |
| `dumpMeta/titles.txt`   | list of page title.                         |
| `media/`                | media files.                                |
| `meta/`                 | metadata of the pages.                      |
| `pages/`                | latest page content.                        |
<!-- /Dump structure -->

## Available Backups/Dumps

> `dokuWikiDumper` and `dokuWikiUploader` is still in development, so there is no available backup on the Internet Archive yet.  

I made some backups for testing, you can check out the list: <https://github.com/orgs/saveweb/projects/4>.  
I will upload them to the Internet Archive when `dokuWikiDumper` is stable enough and `dokuWikiUploader` is ready.

> If you dumped a dokuwiki and want to share it, please feel free to open an issue, I will add it to the list.

## How to import dump to DokuWiki

If you need to import dokuwiki, please add the following configuration to `local.php`

```php
$conf['fnencode'] = 'utf-8'; // dokuwiki default: 'safe' (url encode)
# 'safe' => Non-ASCII characters will be escaped as %xx form.
# 'utf-8' => Non-ASCII characters will be preserved as UTF-8 characters.

$conf['compression'] = '0'; // dokuwiki default: 'gz'.
# 'gz' => attic/<id>.<rev_id>.txt.gz
# 'bz2' => attic/<id>.<rev_id>.txt.bz2
# '0' => attic/<id>.<rev_id>.txt
```

Import `pages` dir if you only need the latest version of the page.  
Import `meta` dir if you need the **changelog** of the page.  
Import `attic` and `meta` dirs if you need the old revisions **content** of the page.  
Import `media` dir if you need the media files.

`dumpMeta` dir is only used by `dokuWikiDumper`, you can ignore it.

## Information

### DokuWiki links

- [DokuWiki](https://www.dokuwiki.org/)
- [DokuWiki changelog](https://www.dokuwiki.org/changelog)
- [DokuWiki source code](https://github.com/splitbrain/dokuwiki)

### Other tools

- [MediaWiki Scraper](https://github.com/mediawiki-client-tools/mediawiki-scraper) (aka `wikiteam3`), a tool for archiving MediaWiki, forked from [WikiTeam](https://github.com/wikiteam/wikiteam/) and has been rewritten in Python 3.
- [WikiTeam](https://github.com/wikiteam/wikiteam/), a tool for archiving MediaWiki, written in Python 2.

## License

GPLv3

## Contributors

This tool is based on an unmerged PR (_8 years ago!_) of [WikiTeam](https://github.com/WikiTeam/wikiteam/): [DokuWiki dump alpha](https://github.com/WikiTeam/wikiteam/pull/243) by [@PiRSquared17](https://github.com/PiRSquared17).

I ([@yzqzss](https://github.com/yzqzss)) have rewritten the code in Python 3 and added some features, also fixed some bugs.
