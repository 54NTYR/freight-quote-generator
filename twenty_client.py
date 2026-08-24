"""Thin GraphQL client for Twenty. Field/input-type names verified against
the /graphql playground of the deployed version — schema is regenerated from
metadata, so names are stable within a version."""
import requests


def amount_micros(dollars):
    if dollars in (None, ""):
        return None
    return int(round(float(dollars) * 1_000_000))


class TwentyClient:
    def __init__(self, base_url, api_key, timeout=30):
        self.base_url = base_url.rstrip("/")
        self.url = self.base_url + "/graphql"
        self.headers = {"Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"}
        self.timeout = timeout

    def gql(self, query, variables=None):
        r = requests.post(self.url, json={"query": query,
                                          "variables": variables or {}},
                          headers=self.headers, timeout=self.timeout)
        r.raise_for_status()
        body = r.json()
        if body.get("errors"):
            raise RuntimeError(body["errors"])
        return body["data"]

    def health(self):
        return self.gql("query { currentUser { id } }")

    def find_person_by_email(self, email_addr):
        data = self.gql(
            """query($e: String!) {
                 people(filter: {emails: {primaryEmail: {eq: $e}}}, limit: 1) {
                   edges { node { id } } } }""", {"e": email_addr})
        edges = data["people"]["edges"]
        return edges[0]["node"] if edges else None

    def create_person(self, email_addr, first_name, company_id=None):
        d = {"emails": {"primaryEmail": email_addr},
             "name": {"firstName": first_name or "Unknown"}}
        if company_id:
            d["companyId"] = company_id
        data = self.gql(
            """mutation($d: PersonCreateInput!) {
                 createPerson(data: $d) { id } }""", {"d": d})
        return data["createPerson"]

    def attach_person_to_company(self, person_id, company_id):
        return self.gql(
            """mutation($id: UUID!, $d: PersonUpdateInput!) {
                 updatePerson(id: $id, data: $d) { id } }""",
            {"id": person_id, "d": {"companyId": company_id}})["updatePerson"]

    def find_company_by_domain(self, domain):
        data = self.gql(
            """query($d: String!) {
                 companies(filter: {domainName: {url: {eq: $d}}}, limit: 1) {
                   edges { node { id } } } }""", {"d": domain})
        edges = data["companies"]["edges"]
        return edges[0]["node"] if edges else None

    def create_company(self, name, domain=None):
        d = {"name": name}
        if domain:
            d["domainName"] = {"url": domain}
        data = self.gql(
            """mutation($d: CompanyCreateInput!) {
                 createCompany(data: $d) { id } }""", {"d": d})
        return data["createCompany"]

    def update_company(self, company_id, data):
        return self.gql(
            """mutation($id: UUID!, $d: CompanyUpdateInput!) {
                 updateCompany(id: $id, data: $d) { id } }""",
            {"id": company_id, "d": data})["updateCompany"]

    def create_note(self, title, body, person_id=None, company_id=None):
        d = {"title": title, "body": body}
        if person_id:
            d["personIds"] = [person_id]
        if company_id:
            d["companyIds"] = [company_id]
        return self.gql("""mutation($d: NoteCreateInput!) {
                            createNote(data: $d) { id } }""",
                        {"d": d})["createNote"]

    def create_task(self, title, body, due_at):
        return self.gql(
            """mutation($d: TaskCreateInput!) { createTask(data: $d) { id } }""",
            {"d": {"title": title, "body": body, "dueAt": due_at}})["createTask"]

    def find_quote_by_number(self, quote_number):
        data = self.gql(
            """query($n: String!) {
                 quotes(filter: {quoteNumber: {eq: $n}}, limit: 1) {
                   edges { node { id } } } }""", {"n": quote_number})
        edges = data["quotes"]["edges"]
        return edges[0]["node"] if edges else None

    def create_quote(self, quote_number, mode, origin_zip, dest_zip,
                     total, transit_days, company_id):
        d = {
            "name": quote_number,
            "quoteNumber": quote_number,
            "mode": mode,
            "originZip": origin_zip or "",
            "destZip": dest_zip or "",
            "companyId": company_id,
        }
        micros = amount_micros(total)
        if micros is not None:
            d["quotedTotal"] = {"amountMicros": micros, "currencyCode": "USD"}
        if transit_days is not None and transit_days != "":
            d["quotedTransitDays"] = float(transit_days)
        data = self.gql(
            """mutation($d: QuoteCreateInput!) {
                 createQuote(data: $d) { id } }""", {"d": d})
        return data["createQuote"]
