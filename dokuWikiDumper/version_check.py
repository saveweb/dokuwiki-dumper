from dokuWikiDumper.exceptions import VersionOutdatedError
from dokuWikiDumper.version import get_latest_version, get_version


def dokuWikiDumper_outdated_check():
    latest_version = get_latest_version()
    if latest_version is None:
        return
    if latest_version != get_version():
        print('=' * 47)
        print(f'Warning: You are using an outdated version of dokuWikiDumper ({get_version()}).')
        print(f'         The latest version is {latest_version}.')
        print('         You can update dokuWikiDumper with "pip3 install --upgrade dokuWikiDumper".')
        print('=' * 47, end='\n\n')
        raise VersionOutdatedError(version=get_version())
    print('You are using the latest version of dokuwikidumper.')
