"""Published SOP PDFs bundled with the app and the git repo."""
from __future__ import annotations

import os

from paths import resource_dir

SOP_FILES = (
    {
        "slug": "ltl-single",
        "title": "LTL Single Shipment Quote SOP",
        "filename": "SOP-LTL-Single-Shipment.pdf",
        "blurb": "One LTL shipment on one lane. How to fill the form, what the math does, and what the customer sees.",
    },
    {
        "slug": "ltl-tiered",
        "title": "LTL Tiered Quote SOP",
        "filename": "SOP-LTL-Tiered.pdf",
        "blurb": "Volume price ladders, consolidation savings, and how to talk a customer through buying more pallets at once.",
    },
    {
        "slug": "ftl",
        "title": "FTL Quote SOP",
        "filename": "SOP-FTL.pdf",
        "blurb": "A whole truck for one customer. Equipment, miles, fuel, extras, and the printed ledger.",
    },
    {
        "slug": "drayage",
        "title": "Drayage Quote SOP",
        "filename": "SOP-Drayage.pdf",
        "blurb": "Short container moves from a port or rail yard. Chassis, accessorials, and the DRAY-Q print name.",
    },
    {
        "slug": "international",
        "title": "International Quote SOP",
        "filename": "SOP-International.pdf",
        "blurb": "Ocean lanes, Incoterms, landed cost, and the INTL-Q print name.",
    },
    {
        "slug": "settings",
        "title": "Settings SOP",
        "filename": "SOP-Settings.pdf",
        "blurb": "The settings cog: your name on quotes, the shared Google quote counter, customers, terminals, and this SOP library.",
    },
)


def sops_dir() -> str:
    return os.path.join(resource_dir(), "sops")


def sop_path(filename: str) -> str:
    return os.path.join(sops_dir(), filename)


def allowed_sop_filenames() -> set[str]:
    return {row["filename"] for row in SOP_FILES}
