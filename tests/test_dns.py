"""engine/dnswire.py, engine/stack.py and owner/dns.py offline: queries and replies built by hand, compression, a
truncated answer that moves to TCP, the refusals, the vendor facts with no verification token kept, the postings'
tools, the CRM agreement, and a read written with no TXT text in it."""
import json
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import dnswire, stack  # noqa: E402
from owner import dns as odns  # noqa: E402

TOKEN = "ms81234567"


def labels(name):
    return b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00"


def reply(ident, name, qtype, records, truncated=False):
    """A reply to one question, each answer's name a pointer back to the question at offset 12."""
    flags = 0x8180 | (0x0200 if truncated else 0)
    out = struct.pack(">HHHHHH", ident, flags, 1, len(records), 0, 0) + labels(name)
    out += struct.pack(">HH", dnswire.TYPES[qtype], 1)
    for rtype, value in records:
        if rtype == "MX":
            rdata = struct.pack(">H", 10) + labels(value)
        else:
            parts = [value[i:i + 255] for i in range(0, len(value), 255)] or [""]
            rdata = b"".join(bytes([len(p)]) + p.encode() for p in parts)
        out += struct.pack(">HHHIH", 0xC00C, dnswire.TYPES[rtype], 1, 300, len(rdata)) + rdata
    return out


class Wire(unittest.TestCase):
    def test_a_query(self):
        ident, packet = dnswire.query("wobbleton.example", "TXT", ident=7)
        self.assertEqual(struct.unpack(">HHHHHH", packet[:12]), (7, 0x0100, 1, 0, 0, 0))
        self.assertEqual(packet[12:12 + 19], labels("wobbleton.example"))
        self.assertEqual(packet[-4:], struct.pack(">HH", 16, 1))

    def test_mx_and_txt_answers(self):
        msg = reply(9, "wobbleton.example", "TXT", [("TXT", "v=spf1 include:_spf.salesforce.com ~all"),
                                                     ("TXT", "MS=" + TOKEN), ("TXT", "x" * 300)])
        rcode, truncated, out = dnswire.answers(msg, 9)
        self.assertEqual((rcode, truncated), (0, False))
        self.assertEqual(out[0], ("TXT", "v=spf1 include:_spf.salesforce.com ~all"))
        self.assertEqual(out[2], ("TXT", "x" * 300))
        mx = reply(3, "wobbleton.example", "MX", [("MX", "wobbleton-example.mail.protection.outlook.com")])
        self.assertEqual(dnswire.answers(mx, 3)[2], [("MX", "wobbleton-example.mail.protection.outlook.com")])

    def test_the_refusals(self):
        with self.assertRaises(ValueError):
            dnswire.answers(reply(1, "a.example", "TXT", []), 2)
        loop = struct.pack(">HHHHHH", 1, 0x8180, 1, 0, 0, 0) + b"\xc0\x0c"
        with self.assertRaises(ValueError):
            dnswire.answers(loop, 1)
        with self.assertRaises(ValueError):
            dnswire.answers(b"\x00\x01", 1)


class Lookup(unittest.TestCase):
    def test_a_truncated_answer_moves_to_tcp(self):
        calls = []

        def sender(server, packet, tcp):
            calls.append(tcp)
            ident = struct.unpack(">H", packet[:2])[0]
            return reply(ident, "wobbleton.example", "TXT", [("TXT", "v=spf1 ~all")], truncated=not tcp)
        rcode, out = odns.lookup("192.0.2.1", "wobbleton.example", "TXT", sender)
        self.assertEqual((rcode, calls, out), (0, [False, True], [("TXT", "v=spf1 ~all")]))

    def test_a_dead_resolver_gives_an_error_after_one_retry(self):
        saved = odns.time.sleep
        odns.time.sleep = lambda s: None
        try:
            def sender(server, packet, tcp):
                raise OSError("no route")
            self.assertEqual(odns.lookup("192.0.2.1", "wobbleton.example", "MX", sender), (-1, []))
        finally:
            odns.time.sleep = saved


class Stack(unittest.TestCase):
    def test_vendor_facts_keep_no_token(self):
        read = stack.read_records(["wobbleton-example.mail.protection.outlook.com"],
                                  ["v=spf1 include:123456.spf03.hubspotemail.net include:_spf.salesforce.com ~all",
                                   "MS=" + TOKEN, "some-other-verification=abc"])
        vendors = {(f["vendor"], f["kind"]) for f in read["facts"]}
        self.assertEqual(vendors, {("HubSpot", "spf"), ("Salesforce", "spf"), ("Microsoft 365", "mx"),
                                   ("Microsoft 365", "txt")})
        self.assertNotIn(TOKEN, json.dumps(read))
        self.assertNotIn("abc", json.dumps(read))
        self.assertEqual((read["spf"], read["txt_records"]), (True, 3))

    def test_the_postings_tools(self):
        sigs = [{"family": "stack", "tool": "Salesforce", "strength": "lists", "url": "u1"},
                {"family": "stack", "tool": "Salesforce", "strength": "uses", "url": "u2"},
                {"family": "stack", "tool": "Sales Cloud", "strength": "uses", "url": "u3"},
                {"family": "revops", "tool": "", "strength": "", "url": "u4"}]
        got = stack.from_postings(sigs, {"Salesforce": "CRM"})
        self.assertEqual(got["Salesforce"], {"category": "CRM", "uses": 2, "lists": 1, "url": "u2"})

    def test_the_crm_agreement(self):
        sigs = [{"family": "stack", "tool": "HubSpot", "strength": "uses", "url": "u"}]
        agree = stack.stack(sigs, {"facts": [{"vendor": "HubSpot", "category": "CRM", "kind": "spf"}]})
        differ = stack.stack(sigs, {"facts": [{"vendor": "Salesforce", "category": "CRM", "kind": "spf"}]})
        alone = stack.stack(sigs, {"facts": []})
        self.assertEqual(stack.agreement({"a": agree, "b": differ, "c": alone}), (2, 1))


class Read(unittest.TestCase):
    def test_a_read_is_written_with_no_txt_text(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(dir=scratch))
        saved = (odns.OUT, odns.targets, odns.resolver, odns.today, odns.allowed)
        try:
            odns.OUT, odns.targets = tmp, lambda: [("Wobbleton Freight", "wobbleton.example")]
            odns.resolver, odns.today, odns.allowed = (lambda: "192.0.2.1"), (lambda: "2026-11-15"), (lambda: None)

            def sender(server, packet, tcp):
                ident = struct.unpack(">H", packet[:2])[0]
                qtype = "MX" if packet[-4:-2] == struct.pack(">H", 15) else "TXT"
                recs = ([("MX", "wobbleton-example.mail.protection.outlook.com")] if qtype == "MX" else
                        [("TXT", "MS=" + TOKEN), ("TXT", "v=spf1 include:mailgun.org ~all")])
                return reply(ident, "wobbleton.example", qtype, recs)
            self.assertEqual(odns.main([], sender=sender), 0)
            text = tmp.joinpath("2026-11-15.json").read_text(encoding="utf-8")
            self.assertNotIn(TOKEN, text)
            got = json.loads(text)["Wobbleton Freight"]
            self.assertEqual((got["status"], got["txt_records"], len(got["facts"])), ("ok", 2, 3))
        finally:
            odns.OUT, odns.targets, odns.resolver, odns.today, odns.allowed = saved
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
