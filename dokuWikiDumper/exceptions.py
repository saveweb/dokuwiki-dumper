import os
import traceback

from dokuWikiDumper.version import get_version


class VersionOutdatedError(Exception):
    def __init__(self, version):
        self.version = version

    def __str__(self):
        return "Version outdated: %s" % self.version

class HTTPStatusError(Exception):
    def __init__(self, r):
        self.status_code = r.status_code
        self.url = r.url

    def __str__(self):
        return "HTTP Status Code: %s, URL: %s" % (self.status_code, self.url)


class DispositionHeaderMissingError(Exception):
    def __init__(self, r):
        self.url = r.url

    def __str__(self):
        return "Disposition header missing, URL: %s" % self.url

class ActionExportRawDisabled(Exception):
    def __init__(self, title):
        self.title = title

    def __str__(self):
        return "Action: export_raw is disabled for [[%s]]" % self.title

class ActionEditDisabled(Exception):
    def __init__(self, title):
        self.title = title

    def __str__(self):
        return "Action: edit is disabled for [[%s]]" % self.title


class ActionIndexDisabled(Exception):
    def __init__(self):
        pass

    def __str__(self):
        return "Action: index is disabled"
    

class ActionEditTextareaNotFound(Exception):
    def __init__(self, title):
        self.title = title

    def __str__(self):
        return "Action: edit: textarea not found for [[%s]]" % self.title


class ActionExportHtmlDisabled(Exception):
    def __init__(self, title):
        self.title = title

    def __str__(self):
        return "Action: export_xhtml is disabled for [[%s]]" % self.title


class ActionRevisionsDisabled(Exception):
    def __init__(self, title):
        self.title = title

    def __str__(self):
        return "Action: revisions is disabled for [[%s]]" % self.title


class RevisionListNotFound(Exception):
    def __init__(self, title):
        self.title = title

    def __str__(self):
        return "Revision list not found for [[%s]]" % self.title


def show_edge_case_warning(**context):
    if os.environ.get('EDGECASE_OK'):
        return

    print(
    "[WARNING]\n"
    "--------------------------------------------\n"
    "The program is about to enter an edge case code, "
    "which lacks real world testing, I'm not sure if the code that runs next can handle it properly. "
    "So I hope you could paste the following details to <https://github.com/saveweb/dokuwiki-dumper/discussions> "
    "to help me improve the code, Thanks!")
    print("------------------------------------------")
    calledfrom = traceback.extract_stack(limit=2)[0]
    print("VERSION:", get_version())
    print("FUNC:", f'{calledfrom.filename}:{calledfrom.lineno} ', "FUNC:", calledfrom.name)
    print("CONTEXT:", context)
    print("------------------------------------------")
    print("To continue executing the edge case code, re-run with environment variable EDGECASE_OK=1 set.")
    os._exit(13)
