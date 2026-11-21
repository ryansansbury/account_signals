"""DNS messages as bytes: a query for one name and type, and the MX and TXT answers read back out of a reply.

owner/dns.py sends the queries through the machine's own resolver. This module is the wire format alone (RFC 1035), so
the tests can check it on replies built by hand with no network. A name in a reply can point back to an earlier name
(compression), and a pointer that loops or runs off the end is refused instead of followed. Standard library only.
"""
import random
import struct

TYPES = {"MX": 15, "TXT": 16}
CLASS_IN = 1


def query(name, qtype, ident=None):
    """(ident, the query's bytes) for one name and type, with recursion asked for."""
    ident = random.randrange(65536) if ident is None else ident
    head = struct.pack(">HHHHHH", ident, 0x0100, 1, 0, 0, 0)
    labels = b"".join(bytes([len(p)]) + p.encode("ascii") for p in name.strip(".").split(".") if p)
    return ident, head + labels + b"\x00" + struct.pack(">HH", TYPES[qtype], CLASS_IN)


def read_name(msg, at, hops=0):
    """(the name at this offset, the offset just past it in the message)."""
    labels, end = [], None
    while True:
        if at >= len(msg) or hops > 20:
            raise ValueError("a name runs off the end of the reply or loops")
        n = msg[at]
        if n & 0xC0 == 0xC0:
            if at + 1 >= len(msg):
                raise ValueError("a pointer runs off the end of the reply")
            pointer = ((n & 0x3F) << 8) | msg[at + 1]
            if pointer >= at:
                raise ValueError("a pointer points forward")
            end = at + 2 if end is None else end
            at, hops = pointer, hops + 1
            continue
        if n == 0:
            return ".".join(labels), (at + 1 if end is None else end)
        labels.append(msg[at + 1:at + 1 + n].decode("ascii", "replace"))
        at += 1 + n


def answers(msg, ident=None):
    """(rcode, truncated, [(type name, value)]) from a reply. MX values are the mail host, TXT values the text joined."""
    if len(msg) < 12:
        raise ValueError("the reply is shorter than its header")
    rid, flags, qd, an, _, _ = struct.unpack(">HHHHHH", msg[:12])
    if ident is not None and rid != ident:
        raise ValueError("the reply answers another query")
    at = 12
    for _ in range(qd):
        _, at = read_name(msg, at)
        at += 4
    out = []
    for _ in range(an):
        _, at = read_name(msg, at)
        if at + 10 > len(msg):
            raise ValueError("an answer runs off the end of the reply")
        rtype, _, _, rdlen = struct.unpack(">HHIH", msg[at:at + 10])
        at += 10
        rdata = msg[at:at + rdlen]
        if rtype == TYPES["MX"] and rdlen >= 3:
            host, _ = read_name(msg, at + 2)
            out.append(("MX", host.lower()))
        elif rtype == TYPES["TXT"]:
            parts, i = [], 0
            while i < len(rdata):
                n = rdata[i]
                parts.append(rdata[i + 1:i + 1 + n].decode("utf-8", "replace"))
                i += 1 + n
            out.append(("TXT", "".join(parts)))
        at += rdlen
    return flags & 0x000F, bool(flags & 0x0200), out
