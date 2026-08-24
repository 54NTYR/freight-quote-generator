"""Syncs issued quotes into Twenty (CRM). Fail-soft by design: a CRM outage
must never block quoting. Reads config.json 'crm' block."""
import logging
from datetime import datetime, timedelta, timezone

import requests

from config import load_config
from twenty_client import TwentyClient

log = logging.getLogger("crm_bridge")


def _cfg():
    return load_config().get("crm", {}) or {}


def _client():
    c = _cfg()
    return TwentyClient(c["base_url"], c["api_key"]) if c.get("api_key") else None


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def on_quote_issued(customer_name, contact_email, quote_number, mode,
                    total, origin_zip, dest_zip, transit_days):
    try:
        cfg = _cfg()
        client = _client()
        if client is None:
            return None  # CRM not configured — silent no-op
        domain = contact_email.rsplit("@", 1)[-1].lower() if "@" in contact_email else None
        company = (client.find_company_by_domain(domain) if domain else None) \
            or client.create_company(customer_name or domain or "Unnamed", domain)
        person = None
        if contact_email:
            person = client.find_person_by_email(contact_email)
            if person is None:
                person = client.create_person(
                    contact_email,
                    (customer_name or "Contact").split()[0],
                    company_id=company["id"])
            else:
                try:
                    client.attach_person_to_company(person["id"], company["id"])
                except Exception:
                    log.exception("Person→Company link failed (quote unaffected)")
        client.create_note(
            f"Quote {quote_number} issued",
            f"{mode} · {origin_zip} → {dest_zip} · ${float(total or 0):,.2f} · "
            f"~{transit_days} d transit",
            person_id=person["id"] if person else None, company_id=company["id"])
        client.create_task(
            f"Follow up: quote {quote_number} ({mode})",
            f"{customer_name} · ${float(total or 0):,.2f} · {origin_zip}→{dest_zip}",
            due_at=(datetime.now(timezone.utc) + timedelta(days=3)).isoformat())
        quote_id = None
        try:
            existing = client.find_quote_by_number(quote_number)
            if existing:
                quote_id = existing["id"]
            else:
                quote_id = client.create_quote(
                    quote_number, mode, origin_zip, dest_zip,
                    total, transit_days, company["id"])["id"]
            client.update_company(company["id"], {"lastQuoteAt": _now_iso()})
        except Exception:
            log.exception("Quote object / lastQuoteAt sync failed (quote unaffected)")
        if cfg.get("webhook_quote_issued"):
            requests.post(cfg["webhook_quote_issued"], json={
                "quoteNumber": quote_number, "mode": mode, "total": total,
                "originZip": origin_zip, "destZip": dest_zip,
                "transitDays": transit_days, "companyId": company["id"],
                "quoteId": quote_id},
                timeout=15)
        return {"companyId": company["id"],
                "personId": person["id"] if person else None,
                "quoteId": quote_id}
    except Exception:
        log.exception("CRM sync failed (quote unaffected)")
        return None
