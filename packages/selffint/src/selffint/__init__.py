"""SelfFint — the finance surface for Beyond.

SelfFint is the thing a finance team opens to answer four questions without
opening an ERP: who owes us, what GST did we collect, what input credit are we
about to lose, and what did payroll cost.

It is a **connector**, not an ERP. The books live in ERPNext/Frappe; this
package keeps a local mirror of the documents it needs, computes the four
reports against that mirror, and writes exactly one kind of document back
(a *draft* sales invoice) when the user asks it to.

Why a connector and not a vendored copy: ERPNext is GPL-3.0-only and cannot be
installed as a library (it needs MariaDB, Redis and a `bench` layout). Vendoring
it would re-licence Beyond and would still not run. See `docs/SELFFINT-PLAN.md`
for the full reasoning.

    from selffint import SelfFintApi, asgi_app

    api = SelfFintApi()
    app.mount("/api/plugins/self-fint", asgi_app(api))

Everything here is standard library only.
"""

from __future__ import annotations

from .api import SelfFintApi, Response
from .asgi import asgi_app
from .client import (
    FrappeAuthError,
    FrappeClient,
    FrappeError,
    FrappeNotFound,
    FrappePermissionError,
    FrappeValidationError,
    Site,
)
from .reports import ar_aging, gst_summary, payroll_summary
from .recon import ReconResult, reconcile_2b
from .store import MirrorStore
from .sync import SYNCED_DOCTYPES, sync_site

__version__ = "1.0.0"

__all__ = [
    "MirrorStore",
    "ReconResult",
    "Response",
    "SYNCED_DOCTYPES",
    "SelfFintApi",
    "Site",
    "FrappeAuthError",
    "FrappeClient",
    "FrappeError",
    "FrappeNotFound",
    "FrappePermissionError",
    "FrappeValidationError",
    "ar_aging",
    "asgi_app",
    "gst_summary",
    "payroll_summary",
    "reconcile_2b",
    "sync_site",
]
