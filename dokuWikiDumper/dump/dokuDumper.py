# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import os
import sys
import time

import requests
# import gzip, 7z
from dokuWikiDumper.utils.util import print_with_lock as print

from dokuWikiDumper.__version__ import DUMPER_VERSION, dokuWikiDumper_outdated_check
from dokuWikiDumper.dump.content import dumpContent
from dokuWikiDumper.dump.html import dump_HTML
from dokuWikiDumper.dump.info import update_info
from dokuWikiDumper.dump.media import dumpMedia
from dokuWikiDumper.dump.pdf import dump_PDF
from dokuWikiDumper.utils.config import update_config
from dokuWikiDumper.utils.patch import SessionMonkeyPatch
from dokuWikiDumper.utils.session import createSession, load_cookies, login_dokuwiki
from dokuWikiDumper.utils.util import avoidSites, buildBaseUrl, getDokuUrl, smkdirs, standardizeUrl, uopen, url2prefix

DEFAULT_THREADS = -1 # magic number, -1 means use 1 thread.

def getArgumentParser():
    parser = argparse.ArgumentParser(description='dokuWikiDumper Version: '+ DUMPER_VERSION)
    parser.add_argument('url', help='URL of the dokuWiki (provide the doku.php URL)', type=str)

    group_download = parser.add_argument_group("Data to download", "What info download from the wiki")

    group_download.add_argument('--content', action='store_true', help='Dump content')
    group_download.add_argument('--media', action='store_true', help='Dump media')
    group_download.add_argument('--html', action='store_true', help='Dump HTML')
    group_download.add_argument('--pdf', action='store_true',
                        help='Dump PDF [default: false] (Only available on some wikis with the PDF export plugin)'+
                        ' (Only dumps the latest PDF revision)')

    parser.add_argument('--current-only', dest='current_only', action='store_true',
                        help='Dump latest revision, no history [default: false]')
    parser.add_argument(
        '--skip-to', help='!DEV! Skip to title number [default: 0]', type=int, default=0)
    parser.add_argument(
        '--path', help='Specify dump directory [default: <site>-<date>]', type=str, default='')
    parser.add_argument(
        '--no-resume', help='Do not resume a previous dump [default: resume]', action='store_true')
    parser.add_argument(
        '--threads', help='Number of sub threads to use [default: 1], not recommended to set > 5', type=int, default=DEFAULT_THREADS)
    parser.add_argument(
        '--i-love-retro',  action='store_true', dest='user_love_retro',
        help='Do not check the latest version of dokuWikiDumper (from pypi.org) before running [default: False]')

    parser.add_argument('--insecure', action='store_true',
                        help='Disable SSL certificate verification')
    parser.add_argument('--ignore-errors', action='store_true',
                        help='!DANGEROUS! ignore errors in the sub threads. This may cause incomplete dumps.')
    parser.add_argument('--ignore-action-disabled-edit', action='store_true',
                        help='Some sites disable edit action for anonymous users and some core pages. '+
                        'This option will ignore this error and textarea not found error.'+
                        'But you may only get a partial dump. '+
                        '(only works with --content)', dest='ignore_action_disabled_edit')
    parser.add_argument('--ignore-disposition-header-missing', action='store_true',
                        help='Do not check Disposition header, useful for outdated (<2014) DokuWiki versions '
                        '[default: False]', dest='ignore_disposition_header_missing')
    parser.add_argument('--trim-php-warnings', action='store_true', dest='trim_php_warnings',
                        help='Trim PHP warnings from requests.Response.text')

    parser.add_argument('--delay', help='Delay between requests [default: 0.0]', type=float, default=0.0)
    parser.add_argument('--retry', help='Maximum number of retries [default: 5]', type=int, default=5)
    parser.add_argument('--hard-retry', type=int, default=3, dest='hard_retry',
                        help='Maximum number of retries for hard errors [default: 3]')

    parser.add_argument('--parser', help='HTML parser [default: lxml]', type=str, default='lxml')

    parser.add_argument('--username', help='login: username')
    parser.add_argument('--password', help='login: password')
    # parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--cookies', help='cookies file')
    parser.add_argument('--auto', action='store_true', 
                        help='dump: content+media+html, threads=5, ignore-action-disable-edit. (threads is overridable)')

    return parser


def checkArgs(args):
    if not args.content and not args.media and not args.html and not args.pdf:
        print('Nothing to do. Use --content and/or --media and/or --html and/or --pdf to specify what to dump.')
        return False
    if not args.url:
        print('No URL specified.')
        return False
    if args.skip_to < 0:
        print('Skip to number must be >= 0.')
        return False
    if args.threads < 1:
        print('Number of threads must be >= 1.')
        return False
    if args.threads > 5:
        print('Warning: threads > 5 , will bring a lot of pressure to the server.')
        print('Original site may deny your request, even ban our UA.')
        time.sleep(3)
        input('Press Enter to continue...')
    if args.ignore_errors:
        print('Warning: You have chosen to ignore errors in the sub threads. This may cause incomplete dumps.')
        time.sleep(3)
        input('Press Enter to continue...')
    if args.username and not args.password:
        print('Warning: You have specified a username but no password.')
        return False
    if args.ignore_action_disabled_edit and not args.content:
        print('Warning: You have specified --ignore-action-disabled-edit, but you have not specified --content.')
        return False
    if args.delay < 0:
        print('Delay must be >= 0.')
        return False
    if args.delay > 0.0 and args.threads > 1:
        print(f"Warning: You have specified a delay and more than one thread ({args.threads}).")
        print("!!! Delay will be applied to each thread separately !!!")
        time.sleep(3)
        input('Press Enter to continue...')
    if args.retry < 0:
        print('Retry must be >= 0.')
        return False
    if args.parser:
        try:
            from bs4 import BeautifulSoup, FeatureNotFound
            BeautifulSoup("", args.parser)
            os.environ['htmlparser']=args.parser
        except FeatureNotFound:
            print("Parser %s not found. Please install first following "
                  "https://www.crummy.com/software/BeautifulSoup/bs4/doc/#installing-a-parser"%(args.parser))
            return False
    return True


def getParameters():
    parser = getArgumentParser()
    args = parser.parse_args()

    if args.auto:
        args.content = True
        args.media = True
        args.html = True
        args.threads = args.threads if args.threads >= 1 else 5
        args.ignore_action_disabled_edit = True
    else:
        # reset magic number
        args.threads = args.threads if args.threads >= 1 else 1
    print('Threads:', args.threads)
    if not checkArgs(args):
        parser.print_help()
        sys.exit(1)

    return args


def dump():
    args = getParameters()
    if not args.user_love_retro:
        dokuWikiDumper_outdated_check()
    url_input = args.url
    skip_to = args.skip_to

    session = createSession(retries=args.retry)
    if args.insecure:
        session.verify = False
        requests.packages.urllib3.disable_warnings()
        print("Warning: SSL certificate verification disabled.")
    session_monkey = SessionMonkeyPatch(session=session, delay=args.delay, msg='',
                                        hard_retries=args.hard_retry,
                                        trim_PHP_warnings=args.trim_php_warnings)
    session_monkey.hijack()

    std_url = standardizeUrl(url_input)
    doku_url = getDokuUrl(std_url, session=session)

    avoidSites(doku_url, session=session)

    print('Init cookies:', session.cookies.get_dict())
    if args.username:
        login_dokuwiki(doku_url=doku_url, session=session,
                       username=args.username, password=args.password)
    if args.cookies:
        load_cookies(session, args.cookies)


    base_url = buildBaseUrl(doku_url)
    dumpDir = url2prefix(doku_url) + '-' + \
        time.strftime("%Y%m%d") if not args.path else args.path.rstrip('/')
    if args.no_resume:
        if os.path.exists(dumpDir):
            print(
                'Dump directory already exists. (You can use --path to specify a different directory.)')
            return 1

    smkdirs(dumpDir, '/dumpMeta')
    print('Dumping to ', dumpDir,
          '\nBase URL: ', base_url,
          '\nDokuPHP URL: ', doku_url)

    _config = {'url_input': url_input,  # type: str
               'std_url': std_url,  # type: str
               'doku_url': doku_url,  # type: str
               'base_url': base_url,  # type: str
               'dokuWikiDumper_version': DUMPER_VERSION,
               }
    update_config(dumpDir=dumpDir, config=_config)
    update_info(dumpDir, doku_url=doku_url, session=session)
    if args.content:
        if os.path.exists(os.path.join(dumpDir, 'content_dumped.mark')):
            print('Content already dumped.')
        else:
            print('\nDumping content...\n')
            dumpContent(doku_url=doku_url, dumpDir=dumpDir,
                        session=session, skipTo=skip_to, threads=args.threads,
                        ignore_errors=args.ignore_errors,
                        ignore_action_disabled_edit=args.ignore_action_disabled_edit,
                        ignore_disposition_header_missing=args.ignore_disposition_header_missing,
                        current_only=args.current_only)
            with open(os.path.join(dumpDir, 'content_dumped.mark'), 'w') as f:
                f.write('done')
    if args.html:
        if os.path.exists(os.path.join(dumpDir, 'html_dumped.mark')):
            print('HTML already dumped.')
        else:
            print('\nDumping HTML...\n')
            dump_HTML(doku_url=doku_url, dumpDir=dumpDir,
                    session=session, skipTo=skip_to, threads=args.threads,
                    ignore_errors=args.ignore_errors, current_only=args.current_only)
            with open(os.path.join(dumpDir, 'html_dumped.mark'), 'w') as f:
                f.write('done')
    if args.media: # last, so that we can know the dump is complete.
        if os.path.exists(os.path.join(dumpDir, 'media_dumped.mark')):
            print('Media already dumped.')
        else:
            print('\nDumping media...\n')
            dumpMedia(base_url=base_url, dumpDir=dumpDir,
                    session=session, threads=args.threads,
                    ignore_errors=args.ignore_errors)
            with open(os.path.join(dumpDir, 'media_dumped.mark'), 'w') as f:
                f.write('done')
    if args.pdf:
        if os.path.exists(os.path.join(dumpDir, 'pdf_dumped.mark')):
            print('PDF already dumped.')
        else:
            print('\nDumping PDF...\n')
            dump_PDF(doku_url=base_url, dumpDir=dumpDir,
                    session=session, threads=args.threads,
                    ignore_errors=args.ignore_errors, current_only=True)
                    # to avoid overload the server, we only dump the current revision of the PDF.
            with open(os.path.join(dumpDir, 'pdf_dumped.mark'), 'w') as f:
                f.write('done')


    session_monkey.release()
    print('\n\n--Done--')
