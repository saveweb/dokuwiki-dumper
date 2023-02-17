# DokuWiki Scraper

> A tool for archiving DokuWiki.

## Requirements

- Python 3.8+ (tested on 3.10)
- beautifulsoup4
- requests
- lxml

Recommend using `DokuWikiScraper` on _modern_ filesystems, such as `ext4` or `btrfs`. `NTFS` is not recommended because of it denys many special characters in filename.

## Install `dokuWikiScraper` with `Poetry`

- Install `Poetry`

    ```bash
    pip3 install poetry
    ```

- Install `dokuWikiScraper`

    ```bash
    git clone https://github.com/saveweb/dokuwiki-scraper
    cd dokuwiki-scraper
    poetry install
    poetry build
    pip install --force-reinstall dist/dokuWikiScraper*.whl
    ```


## Usage

`dokuWikiScraper [-h] [--content] [--media] [--skip-to SKIP_TO] url`

```text
--content          Dump content
--media            Dump media
--skip-to SKIP_TO  Skip to title number(default: 0)
```

## Dump structure

| Directory | Description |
|-----------|-------------|
| `attic` | old revisions of page. |
| `dumpMeta` | (dokuWikiScraper only) metadata of the dump. |
| `media` | media files. |
| `meta` |  metadata of the page. |
| `pages` | latest page content. |

`dumpMeta/titles.txt`

> List of page titles, last line is `--END--` if the list is complete.

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

`dumpMeta` dir is only used by `dokuWikiScraper`, you can ignore it.

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