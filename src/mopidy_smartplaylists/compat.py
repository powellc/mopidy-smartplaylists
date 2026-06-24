"""
Compatibility layer for Mopidy 3 vs 4 differences.

Provides import aliases for APIs that differ between Mopidy 3 and 4:

- ``CoreProxy`` / ``Config`` are available in both but under different modules.
- ``mopidy.types`` (``Uri``, ``SearchField``, ``Query``) only exists in Mopidy 4.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mopidy.config import Config
    from mopidy.core import CoreProxy
    from mopidy.types import Query, SearchField, Uri
else:
    CoreProxy = Any
    Config = dict[str, dict[str, Any]]
    Uri = str
    SearchField = str
    Query = dict
