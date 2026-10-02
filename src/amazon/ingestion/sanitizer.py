from __future__ import annotations

from typing import BinaryIO


class JsonSanitizer:
    """File-like wrapper that rewrites the invalid JSON token ``NaN`` into ``null`` on the fly."""

    _TOKEN = b"NaN"
    _REPLACEMENT = b"null"
    _DEFAULT_CHUNK = 65536

    def __init__(self, source: BinaryIO) -> None:
        self._source = source
        self._buffer = b""
        self._eof = False

    def read(self, size: int = _DEFAULT_CHUNK) -> bytes:
        if size == 0:
            # ijson calls read(0) to probe whether the stream yields bytes or str:
            # it must return b"" WITHOUT consuming anything.
            return b""
        if size is None or size < 0:
            size = self._DEFAULT_CHUNK
        # Read enough bytes that, after holding back a partial token, output is non-empty.
        target = size + len(self._TOKEN)
        while len(self._buffer) < target and not self._eof:
            chunk = self._source.read(size)
            if not chunk:
                self._eof = True
                break
            self._buffer += chunk

        cleaned = self._buffer.replace(self._TOKEN, self._REPLACEMENT)
        if self._eof:
            self._buffer = b""
            return cleaned

        hold = self._partial_token_length(cleaned)
        if hold:
            self._buffer = cleaned[-hold:]
            return cleaned[:-hold]
        self._buffer = b""
        return cleaned

    @classmethod
    def _partial_token_length(cls, data: bytes) -> int:
        """Length of the longest proper prefix of ``NaN`` that ends ``data`` (0, 1 or 2)."""
        for length in range(len(cls._TOKEN) - 1, 0, -1):
            if data.endswith(cls._TOKEN[:length]):
                return length
        return 0
