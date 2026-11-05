"""Imported automatically when this directory is on PYTHONPATH: any network use then fails fast.

Used to prove that a command needs no network, in a real subprocess rather than a patched one.
"""

import socket


def _blocked(*_args: object, **_kwargs: object) -> None:
    raise OSError("network access is blocked for this process")


socket.socket.connect = _blocked  # type: ignore[method-assign]
socket.getaddrinfo = _blocked  # type: ignore[assignment]
