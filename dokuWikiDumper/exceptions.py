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
    
class ContentTypeHeaderNotTextPlain(Exception):
    def __init__(self, r):
        self.url = r.url

    def __str__(self):
        return "Content-Type is not text/plain, URL: %s" % self.url


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
        return "Action: export_html is disabled for [[%s]]" % self.title