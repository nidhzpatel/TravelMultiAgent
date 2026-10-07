from __future__ import annotations

import logging
import re


class SecretRedactionFilter(logging.Filter):
    _patterns = (
        re.compile(r"(Bearer\s+)[^\s]+", re.IGNORECASE),
        re.compile(r"((?:api[_-]?key|token|password)=)[^\s&]+", re.IGNORECASE),
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern in self._patterns:
            message = pattern.sub(r"\1[REDACTED]", message)
        record.msg = message
        record.args = ()
        return True
