"""Retailer discovery is metadata only; extraction requires representative fixtures."""
from email.utils import parseaddr

from ..imports.models import MARKETPLACES

_RETAILERS = (
    ("amazon", "Amazon", tuple(sorted(MARKETPLACES)), True),
    ("flipkart", "Flipkart", ("flipkart.com", "flipkart.net"), False),
    ("myntra", "Myntra", ("myntra.com",), False),
    ("meesho", "Meesho", ("meesho.com",), False),
    ("ajio", "Ajio", ("ajio.com",), False),
    ("other", "Other", (), False),
)


def catalogue():
    return [{"id": key, "name": name, "extraction_supported": supported,
             "support_note": "Conservative labeled Amazon fixtures only; review every extraction." if supported else "Metadata discovery only; extraction awaits representative fixtures."}
            for key, name, _, supported in _RETAILERS]


def sender_retailer(sender):
    if not isinstance(sender, str) or len(sender) > 4096:
        return None
    address = parseaddr(sender)[1].lower()
    domain = address.rsplit("@", 1)[-1] if "@" in address else ""
    for key, _, domains, _ in _RETAILERS:
        if any(domain == d or domain == "shipment-tracking." + d for d in domains):
            return key
    return None


def search_domains():
    return [domain for _, _, domains, _ in _RETAILERS for domain in domains]
