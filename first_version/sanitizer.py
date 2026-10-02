class JsonSanitizer:
    """Se lit comme un fichier, mais remplace 'NaN' par 'null' au fil de l'eau."""

    def __init__(self, source):
        self._src = source
        self._buf = b""
        self._eof = False

    def read(self, size=65536):
        while len(self._buf) < size and not self._eof:
            chunk = self._src.read(size)
            if not chunk:
                self._eof = True
                break
            self._buf += chunk
        cleaned = self._buf.replace(b"NaN", b"null")
        if self._eof:
            self._buf = b""
            return cleaned
        hold = 2 if cleaned.endswith(b"Na") else (1 if cleaned.endswith(b"N") else 0)
        if hold:
            self._buf = cleaned[-hold:]
            return cleaned[:-hold]
        self._buf = b""
        return cleaned