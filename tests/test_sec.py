"""engine/sec.py and owner/sec.py offline, on made-up companies: the dates and amounts, the Form D tables read and the
ones that name people never opened, the match with its confidence, the SEC record check, the URL guard that refuses
/cgi-bin, the throttle stop, and the contact line written once from git's config."""
import io
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import sec  # noqa: E402
from owner import sec as osec  # noqa: E402


def tsv(rows):
    head = list(rows[0])
    return "\t".join(head) + "\n" + "".join("\t".join(str(r[h]) for h in head) + "\n" for r in rows)


class Tracking(zipfile.ZipFile):
    """A zip that remembers which members were opened."""
    opened = []

    def open(self, name, *args, **kwargs):
        Tracking.opened.append(name if isinstance(name, str) else name.filename)
        return super().open(name, *args, **kwargs)


def data_set():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("2026Q3_d/FORMDSUBMISSION.tsv", tsv([
            {"ACCESSIONNUMBER": "0001-26-1", "FILING_DATE": "15-SEP-2026", "SUBMISSIONTYPE": "D", "TESTORLIVE": "LIVE"},
            {"ACCESSIONNUMBER": "0001-26-2", "FILING_DATE": "2026-09-20", "SUBMISSIONTYPE": "D/A", "TESTORLIVE": "LIVE"}]))
        z.writestr("2026Q3_d/ISSUERS.tsv", tsv([
            {"ACCESSIONNUMBER": "0001-26-1", "IS_PRIMARYISSUER_FLAG": "YES", "CIK": "1234567",
             "ENTITYNAME": "Wobbleton Freight, Inc.", "CITY": "DENVER", "STATEORCOUNTRY": "CO", "ISSUERPHONENUMBER": "x"},
            {"ACCESSIONNUMBER": "0001-26-2", "IS_PRIMARYISSUER_FLAG": "YES", "CIK": "7654321",
             "ENTITYNAME": "Snorvel Energy LLC", "CITY": "AUSTIN", "STATEORCOUNTRY": "TX", "ISSUERPHONENUMBER": "y"}]))
        z.writestr("2026Q3_d/OFFERING.tsv", tsv([
            {"ACCESSIONNUMBER": "0001-26-1", "SALE_DATE": "2026-09-01", "TOTALOFFERINGAMOUNT": "25000000",
             "TOTALAMOUNTSOLD": "18,500,000", "INDUSTRYGROUPTYPE": "Other Technology"},
            {"ACCESSIONNUMBER": "0001-26-2", "SALE_DATE": "", "TOTALOFFERINGAMOUNT": "Indefinite",
             "TOTALAMOUNTSOLD": "0", "INDUSTRYGROUPTYPE": "Other Energy"}]))
        z.writestr("2026Q3_d/RELATEDPERSONS.tsv", "ACCESSIONNUMBER\tFIRSTNAME\tLASTNAME\n0001-26-1\tPat\tExample\n")
        z.writestr("2026Q3_d/SIGNATURES.tsv", "ACCESSIONNUMBER\tSIGNATURENAME\n0001-26-1\tPat Example\n")
    return buf.getvalue()


class Reading(unittest.TestCase):
    def test_dates_and_amounts(self):
        self.assertEqual(sec.iso("15-SEP-2026"), "2026-09-15")
        self.assertEqual(sec.iso("09/15/2026"), "2026-09-15")
        self.assertEqual(sec.iso("soon"), "")
        self.assertEqual(sec.amount("18,500,000"), 18500000)
        self.assertIsNone(sec.amount("Indefinite"))

    def test_the_tables_that_name_people_are_never_opened(self):
        Tracking.opened = []
        rows = sec.form_d_rows(Tracking(io.BytesIO(data_set())))
        self.assertFalse(any("RELATEDPERSONS" in m or "SIGNATURES" in m for m in Tracking.opened))
        self.assertEqual(len(rows), 2)
        first = rows[0]
        self.assertEqual((first["cik"], first["filed"], first["sold"], first["offered"], first["state"]),
                         (1234567, "2026-09-15", 18500000, 25000000, "CO"))
        self.assertNotIn("Pat", json.dumps(rows))
        self.assertNotIn("ISSUERPHONENUMBER", json.dumps(rows))

    def test_tickers(self):
        raw = json.dumps({"0": {"cik_str": 99, "ticker": "GRND", "title": "GRINDLEWICK HEALTH, INC."}}).encode()
        self.assertEqual(sec.tickers(raw), [{"cik": 99, "ticker": "GRND", "name": "GRINDLEWICK HEALTH, INC."}])


class Matching(unittest.TestCase):
    rows = sec.form_d_rows(zipfile.ZipFile(io.BytesIO(data_set())))

    def account(self, name, *states):
        return {"account": name, "hub": {"state": states[0]} if states else None,
                "cities": [{"state": s} for s in states]}

    def test_a_full_name_in_a_state_where_it_hires_is_high(self):
        m = sec.match(self.account("Wobbleton Freight", "CO"), [], self.rows)
        self.assertEqual((m["cik"], m["source"], m["confidence"]), (1234567, "form d", "high"))

    def test_a_filer_by_the_name_in_another_state_is_a_namesake(self):
        m = sec.match(self.account("Wobbleton Freight", "WA"), [], self.rows)
        self.assertEqual((m["cik"], m["confidence"]), (None, "unmatched"))

    def test_postings_with_no_state_leave_a_filer_medium(self):
        self.assertEqual(sec.match(self.account("Wobbleton Freight"), [], self.rows)["confidence"], "medium")

    def test_a_shortened_name_needs_its_state(self):
        tick = [{"cik": 5, "ticker": "SNV", "name": "Snorvel Energy Technologies"}]
        self.assertEqual(sec.match(self.account("Snorvel", "NY"), tick, [])["confidence"], "unmatched")

    def test_two_identities_in_its_states_stay_unmatched(self):
        rows = self.rows + [dict(self.rows[0], cik=2222222, accession="x")]
        m = sec.match(self.account("Wobbleton Freight", "CO"), [], rows)
        self.assertEqual((m["cik"], m["confidence"]), (None, "unmatched"))

    def test_no_name_stays_unmatched(self):
        self.assertEqual(sec.match(self.account("Quorvex", "CA"), [], self.rows)["confidence"], "unmatched")

    def test_the_sec_record_adds_its_evidence(self):
        tick = [{"cik": 99, "ticker": "GRND", "name": "GRINDLEWICK HEALTH, INC."}]
        acct = self.account("Grindlewick Health", "MA")
        m = sec.match(acct, tick, [])
        self.assertEqual(m["confidence"], "high")
        subs = {"website": "https://www.grindlewick.example", "sicDescription": "Services",
                "addresses": {"business": {"stateOrCountry": "MA"}}}
        got = sec.confirm(m, subs, acct, "grindlewick.example")
        self.assertEqual(got["confidence"], "high")
        self.assertEqual(len(got["evidence"]), 3)

    def test_form_d_dates_from_a_submissions_file(self):
        subs = {"filings": {"recent": {"form": ["10-K", "D", "D/A"], "filingDate": ["2026-01-02", "2026-02-03",
                                                                                     "2026-03-04"],
                                       "accessionNumber": ["a", "b", "c"]}}}
        self.assertEqual(sec.form_d_dates(subs), [("2026-02-03", "D", "b"), ("2026-03-04", "D/A", "c")])


class Owner(unittest.TestCase):
    def test_the_guard_refuses_cgi_bin_and_other_hosts(self):
        for url in ("https://www.sec.gov/cgi-bin/browse-edgar?company=x", "https://example.com/files/company_tickers.json",
                    "http://www.sec.gov/files/company_tickers.json", "https://www.sec.gov/Archives/edgar/data/1/x.xml"):
            with self.assertRaises(ValueError):
                osec.check_url(url)
        osec.check_url("https://data.sec.gov/submissions/CIK0000000099.json")
        osec.check_url("https://www.sec.gov/files/structureddata/data/form-d-data-sets/2026q1_d.zip")
        osec.check_url("https://www.sec.gov/files/datastandardsinnovation/data/form-d-data-sets/2026q2_d.zip")
        for url in ("https://www.sec.gov/files/other/data/form-d-data-sets/notes.txt",
                    "https://www.sec.gov/files/x/data/other-sets/2026q2_d.zip"):
            with self.assertRaises(ValueError):
                osec.check_url(url)

    def test_a_throttle_stops_the_run(self):
        saved = (osec.urllib.request.urlopen, osec.DELAY)
        try:
            def refuse(*a, **k):
                raise osec.urllib.error.HTTPError("u", 429, "slow down", {}, None)
            osec.urllib.request.urlopen, osec.DELAY = refuse, 0
            with self.assertRaises(osec.Throttled):
                osec.get("https://www.sec.gov/files/company_tickers.json", "ua")
        finally:
            osec.urllib.request.urlopen, osec.DELAY = saved

    def test_the_quarters_on_the_page(self):
        page = ('<a href="/files/structureddata/data/form-d-data-sets/2023q4_d.zip">x</a>'
                '<a href="/files/structureddata/data/form-d-data-sets/2026q3_d.zip">y</a>')
        self.assertEqual(list(osec.quarters(page)), ["2026q3"])

    def test_the_contact_line_is_written_once_from_git(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(dir=scratch))
        try:
            class R:
                def __init__(self, out):
                    self.stdout = out
            answers = {"user.name": "Pat Example", "user.email": "pat@example.org"}
            runner = lambda cmd, **k: R(answers[cmd[-1]] + "\n")  # noqa: E731
            path = tmp.joinpath("sec_contact.txt")
            self.assertEqual(osec.contact(path, runner), "Pat Example pat@example.org")
            self.assertTrue(path.exists())
            self.assertEqual(osec.contact(path, lambda *a, **k: R("")), "Pat Example pat@example.org")
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
