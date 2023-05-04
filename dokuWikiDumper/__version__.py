DUMPER_VERSION = '0.1.22'

from dokuWikiDumper.exceptions import VersionOutdatedError


def get_latest_version():
    '''Returns the latest version of dokuwikidumper.'''
    project_url_pypi = 'https://pypi.org/pypi/dokuwikidumper/json'
    project_url_github = 'https://api.github.com/repos/saveweb/dokuwiki-dumper/releases/latest'
    
    import requests
    try:
        response = requests.get(project_url_pypi, timeout=5, headers={'Accept': 'application/json', 'Accept-Encoding': 'gzip'})
    except requests.exceptions.Timeout or requests.exceptions.ConnectionError:
        print('Warning: Could not get latest version of dokuwikidumper from pypi.org. (Timeout)')
        return None
    if response.status_code == 200:
        data = response.json()
        latest_version = data['info']['version']
        return latest_version
    else:
        print('Warning: Could not get latest version of dokuwikidumper.')
        return None

def dokuWikiDumper_outdated_check():
    latest_version = get_latest_version()
    if latest_version is None:
        return
    if latest_version != DUMPER_VERSION:
        print('=' * 47)
        print(f'Warning: You are using an outdated version of dokuwikidumper ({DUMPER_VERSION}).')
        print(f'         The latest version is {latest_version}.')
        print(f'         You can update dokuwikidumper with "pip3 install --upgrade dokuwikidumper".')
        print('=' * 47, end='\n\n')
        raise VersionOutdatedError(version=DUMPER_VERSION)

    print(f'You are using the latest version of dokuwikidumper.')