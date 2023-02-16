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
import gzip

from dokuWikiScraper.dump.content import dumpContent
from dokuWikiScraper.dump.media import dumpMedia

from dokuWikiScraper.utils.session import createSession
from dokuWikiScraper.utils.util import avoidSites, buildBaseUrl, getDokuUrl, smkdir, standardizeUrl, url2prefix

def getArgumentParser():
    parser = argparse.ArgumentParser(description='dokuWikiScraper')
    parser.add_argument('url', help='URL of the dokuWiki', type=str)
    parser.add_argument('--content', action='store_true', help='Dump content')
    parser.add_argument('--media', action='store_true', help='Dump media')
    # parser.add_argument('output', help='Output directory')
    parser.add_argument( '--skip-to', help='Skip to title number(default: 0)', type=int, default=0)
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
    stdUrl = standardizeUrl(urlInput)
    dokuUrl = getDokuUrl(stdUrl, session=session)
    avoidSites(dokuUrl)
    baseUrl = buildBaseUrl(dokuUrl)
    dumpDir = url2prefix(dokuUrl)
    print('Dumping to ', dumpDir, '\nBase URL: ', baseUrl, '\nDokuPHP URL: ', dokuUrl)
    smkdir(dumpDir)
    if args.content:
        dumpContent(url=dokuUrl, dumpDir=dumpDir, session=session, skipTo=skipTo)
    if args.media:
        dumpMedia(url=baseUrl, dumpDir=dumpDir, session=session)
    print('--Done--')
