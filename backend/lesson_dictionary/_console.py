"""Force UTF-8 console output so Hindi/Santali text prints on Windows."""

import sys


def enable_utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass