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

class ActionExportHtmlDisabled(Exception):
    def __init__(self, title):
        self.title = title

    def __str__(self):
        return "Action: export_html is disabled for [[%s]]" % self.title