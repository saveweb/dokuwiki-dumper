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
import time

import requests
# import gzip, 7z

from dokuWikiDumper.__version__ import DUMPER_VERSION
from dokuWikiDumper.dump.content import dumpContent
from dokuWikiDumper.dump.info import update_info
from dokuWikiDumper.dump.media import dumpMedia
from dokuWikiDumper.utils.config import update_config
from dokuWikiDumper.utils.session import createSession
from dokuWikiDumper.utils.util import avoidSites, buildBaseUrl, getDokuUrl, smkdirs, standardizeUrl, url2prefix


def getArgumentParser():
    parser = argparse.ArgumentParser(description='dokuWikiDumper')
    parser.add_argument('url', help='URL of the dokuWiki', type=str)
    parser.add_argument('--content', action='store_true', help='Dump content')
    parser.add_argument('--media', action='store_true', help='Dump media')
    parser.add_argument(
        '--skip-to', help='Skip to title number (default: 0)', type=int, default=0)
    parser.add_argument(
        '--path', help='Specify dump directory (default: <site>-<date>)', type=str, default='')
    parser.add_argument(
        '--no-resume', help='Do not resume a previous dump (default: resume)', action='store_true')
    parser.add_argument(
        '--threads', help='Number of threads to use (default: 1, not recommended to set > 5)', type=int, default=1)
    parser.add_argument('--insecure', action='store_true',
                        help='Disable SSL certificate verification')
    # parser.add_argument('-u', '--user', help='Username')
    # parser.add_argument('-p', '--password', help='Password')
    # parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    return parser


def checkArgs(args):
    if not args.content and not args.media:
        print('Nothing to do. Use --content and/or --media to specify what to dump.')
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
    if args.threads > 10:
        print('Warning: Number of threads > 10 may cause problems.')
        time.sleep(3)
        input('Press Enter to continue...')
        return True

    return True


def getParameters():
    parser = getArgumentParser()
    args = parser.parse_args()
    if not checkArgs(args):
        parser.print_help()
        exit(1)
    return args


def dump():
    args = getParameters()
    urlInput = args.url
    skipTo = args.skip_to

    session = createSession()
    if args.insecure:
        session.verify = False
        requests.packages.urllib3.disable_warnings()
        print("Warning: SSL certificate verification disabled.")

    stdUrl = standardizeUrl(urlInput)
    dokuUrl = getDokuUrl(stdUrl, session=session)
    avoidSites(dokuUrl)
    baseUrl = buildBaseUrl(dokuUrl)
    dumpDir = url2prefix(dokuUrl) + '-' + \
        time.strftime("%Y%m%d") if not args.path else args.path
    if args.no_resume:
        if os.path.exists(dumpDir):
            print(
                'Dump directory already exists. (You can use --path to specify a different directory.)')
            return 1

    # smkdirs(dumpDir)
    smkdirs(dumpDir, '/dumpMeta')
    print('Dumping to ', dumpDir, '\nBase URL: ',
          baseUrl, '\nDokuPHP URL: ', dokuUrl)

    _config = {'url_input': urlInput,  # type: str
               'std_url': stdUrl,  # type: str
               'doku_url': dokuUrl,  # type: str
               'base_url': baseUrl,  # type: str
               'dokuWikiDumper_version': DUMPER_VERSION,
               }
    update_config(dumpDir=dumpDir, config=_config)
    update_info(dumpDir, doku_url=dokuUrl, session=session)

    if args.content:
        print('\nDumping content...\n')
        dumpContent(doku_url=dokuUrl, dumpDir=dumpDir,
                    session=session, skipTo=skipTo, threads=args.threads)
    if args.media:
        print('\nDumping media...\n')
        dumpMedia(url=baseUrl, dumpDir=dumpDir,
                  session=session, threads=args.threads)
    print('\n\n--Done--')
