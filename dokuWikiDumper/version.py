__VERSION__ = 'unknown'

try:
    from importlib.metadata import version
    __VERSION__ = version('dokuwikidumper')
except Exception:
    pass

def get_version():
    return __VERSION__


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
