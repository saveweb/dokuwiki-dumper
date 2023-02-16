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

import gzip

from dokuWikiScraper.dump.content import dumpContent
from dokuWikiScraper.dump.media import dumpMedia

from dokuWikiScraper.utils.session import createSession
from dokuWikiScraper.utils.util import avoidSites, buildBaseUrl, getDokuUrl, smkdir, standardizeUrl, url2prefix


def dump(urlInput: str = ''):
    skipTo = 0 # TODO: add skipTo argument
    session = createSession()
    stdUrl = standardizeUrl(urlInput)
    dokuUrl = getDokuUrl(stdUrl, session=session)
    avoidSites(dokuUrl)
    baseUrl = buildBaseUrl(dokuUrl)
    dumpDir = url2prefix(dokuUrl)
    print('Dumping to ', dumpDir, '\nBase URL: ', baseUrl, '\nDokuPHP URL: ', dokuUrl)
    smkdir(dumpDir)
    dumpContent(url=dokuUrl, dumpDir=dumpDir, session=session, skipTo=skipTo)
    dumpMedia(url=baseUrl, dumpDir=dumpDir, session=session)
    print('--Done--')
