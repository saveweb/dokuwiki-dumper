# DokuWiki Dumper

> A tool for archiving DokuWiki.

Recommend using `dokuWikiDumper` on _modern_ filesystems, such as `ext4` or `btrfs`. `NTFS` is not recommended because of it denys many special characters in filename.

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
pip3 install dokuWikiDumper
```

### Install `dokuWikiDumper` with `Poetry` (for developers)

- Install `Poetry`

    ```bash
    pip3 install poetry
    ```

- Install `dokuWikiDumper`

    ```bash
    git clone https://github.com/saveweb/dokuwiki-dumper
    cd dokuwiki-dumper
    poetry install
    rm dist/ -rf
    poetry build
    pip install --force-reinstall dist/dokuWikiDumper*.whl
    ```

## Usage

```bash
usage: dokuWikiDumper [-h] [--content] [--media] [--html] [--pdf] [--current-only] [--skip-to SKIP_TO] [--path PATH] [--no-resume] [--threads THREADS]
                      [--insecure] [--ignore-errors] [--ignore-action-disabled-edit] [--ignore-disposition-header-missing] [--trim-php-warnings]
                      [--delay DELAY] [--retry RETRY] [--hard-retry HARD_RETRY] [--parser PARSER] [--username USERNAME] [--password PASSWORD]
                      [--cookies COOKIES] [--auto]
                      url

dokuWikiDumper Version: 0.1.20

positional arguments:
  url                   URL of the dokuWiki (provide the doku.php URL)

options:
  -h, --help            show this help message and exit
  --current-only        Dump latest revision, no history [default: false]
  --skip-to SKIP_TO     !DEV! Skip to title number [default: 0]
  --path PATH           Specify dump directory [default: <site>-<date>]
  --no-resume           Do not resume a previous dump [default: resume]
  --threads THREADS     Number of sub threads to use [default: 1], not recommended to set > 5
  --insecure            Disable SSL certificate verification
  --ignore-errors       !DANGEROUS! ignore errors in the sub threads. This may cause incomplete dumps.
  --ignore-action-disabled-edit
                        Some sites disable edit action for anonymous users and some core pages. This option will ignore this error and textarea not
                        found error.But you may only get a partial dump. (only works with --content)
  --ignore-disposition-header-missing
                        Do not check Disposition header, useful for outdated (<2014) DokuWiki versions [default: False]
  --trim-php-warnings   Trim PHP warnings from HTML [default: False]
  --delay DELAY         Delay between requests [default: 0.0]
  --retry RETRY         Maximum number of retries [default: 5]
  --hard-retry HARD_RETRY
                        Maximum number of retries for hard errors [default: 3]
  --parser PARSER       HTML parser [default: lxml]
  --username USERNAME   login: username
  --password PASSWORD   login: password
  --cookies COOKIES     cookies file
  --auto                dump: content+media+html, threads=5, ignore-action-disable-edit. (threads is overridable)

Data to download:
  What info download from the wiki

  --content             Dump content
  --media               Dump media
  --html                Dump HTML
  --pdf                 Dump PDF [default: false] (Only available on some wikis with the PDF export plugin) (Only dumps the latest PDF revision)
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

I made some backups for testing, you can check out the list: <https://github.com/orgs/saveweb/projects/4>.

> Some wikidump has been uploaded to IA, you can check out: <https://archive.org/search?query=subject%3A"dokuWikiDumper">
>
> If you dumped a DokuWiki and want to share it, please feel free to open an issue, I will add it to the list.

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

### Other tools

- [MediaWiki Scraper](https://github.com/mediawiki-client-tools/mediawiki-scraper) (aka `wikiteam3`), a tool for archiving MediaWiki, forked from [WikiTeam](https://github.com/wikiteam/wikiteam/) and has been rewritten in Python 3.
- [WikiTeam](https://github.com/wikiteam/wikiteam/), a tool for archiving MediaWiki, written in Python 2.

## License

GPLv3

## Contributors

This tool is based on an unmerged PR (_8 years ago!_) of [WikiTeam](https://github.com/WikiTeam/wikiteam/): [DokuWiki dump alpha](https://github.com/WikiTeam/wikiteam/pull/243) by [@PiRSquared17](https://github.com/PiRSquared17).

I ([@yzqzss](https://github.com/yzqzss)) have rewritten the code in Python 3 and added some features, also fixed some bugs.
