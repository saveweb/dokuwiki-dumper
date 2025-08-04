# DokuWiki Dumper

![Dynamic JSON Badge](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Farchive.org%2Fadvancedsearch.php%3Fq%3Dsubject%3AdokuWikiDumper%26rows%3D1%26page%3D1%26output%3Djson&query=%24.response.numFound&label=DokuWiki%20Dumps%40IA)
[![PyPI version](https://badge.fury.io/py/dokuwikidumper.svg)](https://badge.fury.io/py/dokuwikidumper)


> A tool for archiving DokuWiki.

Recommend using `dokuWikiDumper` on _modern_ filesystems, such as `ext4` or `btrfs`. `NTFS` is not recommended because it denies many special characters in the filename.

# For webmaster

We crawl every MediaWiki site (with 1.5s crawl-delay) every year and upload to the Internet Archive. If you don’t want your wiki to be archived, add the following to your `<domain>/robots.txt`:

```robots.txt
User-agent: dokuWikiDumper
Disallow: /
```

Our bots are running on the following IPs: [wikiteam3.txt](https://static.saveweb.org/bots_ips/wikiteam3.txt) (ips, contact) | [wikiteam3.ips.txt](https://static.saveweb.org/bots_ips/wikiteam3.ips.txt) (ips)

## Requirements

### dokuWikiDumper

- Python 3.8+ (developed on py3.10)
- beautifulsoup4
- requests
- lxml
- rich

### dokuWikiUploader

> Upload wiki dump to [Internet Archive](https://archive.org/).
> `dokuWikiUploader -h` for help.

- internetarchive
- p7zip (`7z` command) (`p7zip-full` package)

## Install `dokuWikiDumper`

> `dokuWikiUploader` is included in `dokuWikiDumper`.

### Install `dokuWikiDumper` with `pip` (recommended)

> <https://pypi.org/project/dokuwikidumper/>

```bash
pip3 install dokuWikiDumper --upgrade
```

## Usage

```bash
usage: dokuWikiDumper [-h] [--content] [--media] [--html] [--pdf] [--current-only] [--path PATH] [--no-resume] [--threads THREADS] [--i-love-retro] [--insecure] [--ignore-errors] [--ignore-action-disabled-edit] [--trim-php-warnings]
                      [--export-xhtml-action {export_html,export_xhtml}] [--delay DELAY] [--retry RETRY] [--hard-retry HARD_RETRY] [--parser PARSER] [--username USERNAME] [--password PASSWORD] [--verbose] [--cookies COOKIES] [--auto] [-u]
                      [-g UPLOADER_ARGS] [--force]
                      url

dokuWikiDumper Version: 0.1.48

positional arguments:
  url                   URL of the dokuWiki (provide the doku.php URL)

options:
  -h, --help            show this help message and exit
  --current-only        Dump latest revision, no history [default: false]
  --path PATH           Specify dump directory [default: <site>-<date>]
  --no-resume           Do not resume a previous dump [default: resume]
  --threads THREADS     Number of sub threads to use [default: 1], not recommended to set > 5
  --i-love-retro        Do not check the latest version of dokuWikiDumper (from pypi.org) before running [default: False]
  --insecure            Disable SSL certificate verification
  --ignore-errors       !DANGEROUS! ignore errors in the sub threads. This may cause incomplete dumps.
  --ignore-action-disabled-edit
                        Some sites disable edit action for anonymous users and some core pages. This option will ignore this error and textarea not found error.But you may only get a partial dump. (only works with --content)
  --trim-php-warnings   Trim PHP warnings from requests.Response.text
  --export-xhtml-action {export_html,export_xhtml}
                        HTML export action [default: export_xhtml]
  --delay DELAY         Delay between requests [default: 0.0]
  --retry RETRY         Maximum number of retries [default: 5]
  --hard-retry HARD_RETRY
                        Maximum number of retries for hard errors [default: 3]
  --parser PARSER       HTML parser [default: lxml]
  --username USERNAME   login: username
  --password PASSWORD   login: password
  --verbose             Verbose output
  --cookies COOKIES     cookies file
  --auto                dump: content+media+html, threads=3, ignore-action-disable-edit. (threads is overridable)
  -u, --upload          Upload wikidump to Internet Archive after successfully dumped (only works with --auto)
  -g UPLOADER_ARGS, --uploader-arg UPLOADER_ARGS
                        Arguments for uploader.
  --force               To dump even if a recent dump exists on IA

Data to download:
  What info download from the wiki

  --content             Dump content
  --media               Dump media
  --html                Dump HTML
  --pdf                 Dump PDF [default: false] (Only available on some wikis with the PDF export plugin) (Only dumps the latest PDF revision)```

For most cases, you can use `--auto` to dump the site.

```bash
dokuWikiDumper https://example.com/wiki/ --auto
```

which is equivalent to

```bash
dokuWikiDumper https://example.com/wiki/ --content --media --html --threads 3 --ignore-action-disabled-edit
```

> Highly recommend using `--username` and `--password` to login (or using `--cookies`), because some sites may disable anonymous users to access some pages or check the raw wikitext.

`--cookies` accepts a Netscape cookies file, you can use [cookies.txt Extension](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/) to export cookies from Firefox. It also accepts a json cookies file created by [Cookie Quick Manager](https://addons.mozilla.org/en-US/firefox/addon/cookie-quick-manager/).

## Dump structure

<!-- Dump structure -->
| Directory or File       | Description                                 |
|-----------              |-------------                                |
| `attic/`                | old revisions of page. (wikitext)           |
| `dumpMeta/`             | (dokuWikiDumper only) metadata of the dump. |
| `dumpMeta/check.html`   | ?do=check page of the wiki.                 |
| `dumpMeta/config.json`  | dump's configuration.                       |
| `dumpMeta/favicon.ico`  | favicon of the site.                        |
| `dumpMeta/files.txt`    | list of filename.                           |
| `dumpMeta/index.html`   | homepage of the wiki.                       |
| `dumpMeta/info.json`    | infomations of the wiki.                    |
| `dumpMeta/titles.txt`   | list of page title.                         |
| `html/`                 | (dokuWikiDumper only) HTML of the pages.    |
| `media/`                | media files.                                |
| `meta/`                 | metadata of the pages.                      |
| `pages/`                | latest page content. (wikitext)             |
| `*.mark`                | mark file.                                  |
<!-- /Dump structure -->

## Available Backups/Dumps

Check out: <https://archive.org/search?query=subject%3A"dokuWikiDumper">

## How to import dump to DokuWiki

If you need to import Dokuwiki, please add the following configuration to `local.php`

```php
$conf['fnencode'] = 'utf-8'; // Dokuwiki default: 'safe' (url encode)
# 'safe' => Non-ASCII characters will be escaped as %xx form.
# 'utf-8' => Non-ASCII characters will be preserved as UTF-8 characters.

$conf['compression'] = '0'; // Dokuwiki default: 'gz'.
# 'gz' => attic/<id>.<rev_id>.txt.gz
# 'bz2' => attic/<id>.<rev_id>.txt.bz2
# '0' => attic/<id>.<rev_id>.txt
```

Import `pages` dir if you only need the latest version of the page.  
Import `meta` dir if you need the **changelog** of the page.  
Import `attic` and `meta` dirs if you need the old revisions **content** of the page.  
Import `media` dir if you need the media files.

`dumpMeta` and `html` dirs are only used by `dokuWikiDumper`, you can ignore it.

## Information

### DokuWiki links

- [DokuWiki](https://www.dokuwiki.org/)
- [DokuWiki changelog](https://www.dokuwiki.org/changelog)
- [DokuWiki source code](https://github.com/splitbrain/dokuwiki)

- [DokuWiki - ArchiveTeam Wiki](https://wiki.archiveteam.org/index.php/DokuWiki)

### Other tools

- [wikiteam/WikiTeam](https://github.com/wikiteam/wikiteam/), a tool for archiving MediaWiki, written in Python 2 that you won't want to use nowadays. :(
- [mediawiki-client-tools/MediaWiki Scraper](https://github.com/mediawiki-client-tools/mediawiki-scraper) (aka `wikiteam3`), a tool for archiving MediaWiki, forked from [WikiTeam](https://github.com/wikiteam/wikiteam/) and has been rewritten in Python 3. (Lack of code writers and reviewers, STWP no longer maintains this repo.)
- [saveweb/WikiTeam3](https://github.com/saveweb/wikiteam3) forked from MediaWiki Scraper, maintained by STWP. :)
- [DigitalDwagon/WikiBot](https://github.com/DigitalDwagon/WikiBot) a Discord and IRC bot to run the dokuWikiDumper and wikiteam3 in the background.

## License

GPLv3

## Contributors

This tool is based on an unmerged PR (_8 years ago!_) of [WikiTeam](https://github.com/WikiTeam/wikiteam/): [DokuWiki dump alpha](https://github.com/WikiTeam/wikiteam/pull/243) by [@PiRSquared17](https://github.com/PiRSquared17).

I ([@yzqzss](https://github.com/yzqzss)) have rewritten the code in Python 3 and added ~~some features, also fixed~~ some bugs.
