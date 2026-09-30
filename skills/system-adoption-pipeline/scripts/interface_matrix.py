#!/usr/bin/env python3
"""Build an N-squared interface matrix (DSM) report from a Markdown inventory.

Input: one Markdown file holding a Components table and an Interfaces table.
Output: a deterministic Markdown report on stdout. Exit 1 on a bad input row.
Stdlib only.

With --certify LEDGER the same input is certified instead of reported. The
ledger is a Markdown file kept beside the input and written during review: one
disposition table, columns `Kind | Finding | Disposition | Reason | Reviewer |
Date | Fingerprint`, keying every finding by stable identity rather than input
line — interface-row findings (candidates, gaps) as `producer -> consumer:
flows`, unstated pairs as `A -> B`, boundary findings by component name,
uncited source spans as `L7-9@<source sha256>` — with a content fingerprint
(the record's blocker lines carry current fingerprints to paste) pinning what
was dispositioned. Certification exits 0 when every finding is dispositioned;
3 naming every blocker, entries whose finding drifted from the input as
`drifted:` and findings no entry covers as `unreviewed:`; and 1 on a bad
ledger row, a duplicate identity in the ledger or the input, or an invocation
whose flags do not replay the ones the ledger's `## Certification record`
section declares. Every run writes a standalone certification record beside
the ledger (<ledger>.cert.md) binding the input, report and (when --source
ran) source sha256, the gate result and the effective flags; a pass also
stamps the same record into the ledger as its `## Certification record`
section.
"""

import argparse
import difflib
import graphlib
import hashlib
import json
import re
import sys

COMPONENT_COLUMNS = ("component", "kind", "notes")
INTERFACE_COLUMNS = ("producer", "consumer", "flows", "format", "trigger", "owner")
RULE_COLUMNS = ("producer class", "consumer class", "disposition", "reason")
ATTRS = ("Flows", "Format", "Trigger", "Owner")
DISPOSITIONS = ("none", "review")
LEDGER_COLUMNS = ("kind", "finding", "disposition", "reason", "reviewer",
                  "date", "fingerprint")
LEDGER_KINDS = ("candidate", "gap", "boundary", "pair", "span")
KIND_NOUNS = {
    "candidate": "missing-component candidate",
    "gap": "interface gap",
    "boundary": "boundary finding",
    "pair": "unstated pair",
    "span": "uncited span",
}
KIND_VERBS = {
    "candidate": "is unresolved",
    "gap": "has no disposition",
    "boundary": "is unexplained",
    "pair": "has no disposition",
    "span": "is unread",
}
CITE = re.compile(r"(?<![A-Za-z0-9])L(\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*)")


def is_external(cell):
    """True if a `Kind` puts the component outside the system boundary.

    The same token test check_plan.py uses: the Kind's first word is `external`, or the
    Kind carries the token `(external)`. So `External system` and `actor (external)` are
    outside; `externalize`, `non-external store` and `(externalish)` are ours to build.
    """
    words = cell.strip().lower().split()
    return bool(words) and (words[0] == "external" or "(external)" in words)


def near(head, names):
    """Header cells that are one of `names` or a near-miss spelling of one."""
    return sum(1 for c in head if difflib.get_close_matches(c, names, n=1, cutoff=0.8))


def citations(text, lineno=0):
    """Every source line cited in a cell: `L7`, `L7-9`, `L7,11-12`."""
    nums = []
    for m in CITE.finditer(text):
        for part in m.group(1).split(","):
            if "-" in part:
                a, b = part.split("-")
                if int(b) < int(a):
                    die("reversed citation range L%s-%s at line %d" % (a, b, lineno))
                nums.extend(range(int(a), int(b) + 1))
            else:
                nums.append(int(part))
    return nums


def nonneg(value):
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError("must be 0 or more, not %d" % n)
    return n


def die(msg):
    sys.stderr.write("error: %s\n" % msg)
    raise SystemExit(1)


def cells(line):
    """Split a table row on unescaped pipes.

    A backslash escapes the next character and is dropped: `\\|` is a literal
    pipe inside a cell, `\\\\` is a literal backslash and leaves the following
    `|` as a delimiter. A trailing lone backslash is dropped.
    """
    parts, buf, esc = [], [], False
    for ch in line.strip():
        if esc:
            buf.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == "|":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return [p.strip() for p in parts]


def md(value):
    """Escape a cell value for emission inside a Markdown table."""
    return value.replace("|", "\\|")


def is_sep(line):
    return "-" in line and set(line.strip()) <= set("|-: ")


def columns(head, required, lineno):
    """Map required column names to their position, by header name."""
    at = {}
    for n, name in enumerate(head):
        at.setdefault(name, n)
    missing = [c for c in required if c not in at]
    if missing:
        die("table at line %d is missing column(s): %s" % (lineno, ", ".join(missing)))
    return at


def is_header(lines, i):
    """A header row is a `|` line whose next line is a separator row."""
    return (
        lines[i].strip().startswith("|")
        and i + 1 < len(lines)
        and is_sep(lines[i + 1])
    )


def parse(text):
    """Return (components, interfaces, rules, cites, has_rules); tables by header row."""
    components = []  # (name, kind, class, status, line_no)
    interfaces = []  # dict
    rules = []  # dict
    cites = []  # (input line, cited source line, covers) of every active row
    found = {}  # kind -> header line of the first such table
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip().startswith("|"):
            i += 1
            continue
        if not is_header(lines, i):
            sys.stderr.write("warning: line %d: table row outside any table ignored\n" % (i + 1))
            i += 1
            continue
        head = [c.lower() for c in cells(line)]
        shared_c = len(set(head) & set(COMPONENT_COLUMNS))
        shared_i = len(set(head) & set(INTERFACE_COLUMNS))
        # only a header naming both class columns can be the Rules table, so a foreign
        # `| Disposition | Reason |` or `| Producer class | Reason |` table is not ours
        shared_r = (len(set(head) & set(RULE_COLUMNS))
                    if {"producer class", "consumer class"} <= set(head) else 0)
        if max(shared_c, shared_i, shared_r) < 2:
            # someone else's table: skip its header, separator and rows. But a header that
            # near-misses two or more required names is a typo'd table of ours, not a
            # foreign one — say so rather than dropping its rows in silence
            near_r = (near(head, RULE_COLUMNS)
                      if near(head, ("producer class", "consumer class")) >= 2 else 0)
            if max(near(head, COMPONENT_COLUMNS), near(head, INTERFACE_COLUMNS), near_r) >= 2:
                sys.stderr.write(
                    "warning: line %d: table header misspells a Components, Interfaces or "
                    "Rules column set; the whole table was ignored\n" % (i + 1))
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|") and not is_header(lines, i):
                i += 1
            continue
        # a `component` column settles it, so a Components table missing a required
        # column is diagnosed as that, not as a malformed Interfaces table
        if shared_r > max(shared_c, shared_i):
            kind, at = "rules", columns(head, RULE_COLUMNS, i + 1)
        elif "component" in head or (shared_c >= shared_i and "producer" not in head):
            kind, at = "components", columns(head, COMPONENT_COLUMNS, i + 1)
        else:
            kind, at = "interfaces", columns(head, INTERFACE_COLUMNS, i + 1)
        if kind in found:
            die("second %s table at line %d (first at line %d); put addenda in the "
                "first table, below its existing rows" % (kind.capitalize(), i + 1, found[kind]))
        found[kind] = i + 1
        i += 2
        while i < len(lines) and lines[i].strip().startswith("|"):
            # a separator on the next line means this line is a new table's header
            if is_header(lines, i):
                break
            row = cells(lines[i])
            row += [""] * (len(head) - len(row))
            lineno = i + 1
            # only active modelled rows count for coverage: a rule's Reason is a
            # justification, not a component or an interface, and a superseded row models
            # nothing any more, so their citations cover nothing — they are still
            # range-checked, a citation the source does not have is wrong either way
            covers = kind != "rules" and not superseded(status(row, at))
            cites.extend((lineno, n, covers)
                         for n in citations(" | ".join(row), lineno))
            if kind == "components":
                components.append(
                    (row[at["component"]], row[at["kind"]].lower(),
                     row[at["class"]] if "class" in at else "", status(row, at), lineno)
                )
            elif kind == "rules":
                rules.append(
                    {
                        "producer": row[at["producer class"]],
                        "consumer": row[at["consumer class"]],
                        "disposition": row[at["disposition"]].strip().lower(),
                        "reason": row[at["reason"]],
                        "status": status(row, at),
                        "line": lineno,
                    }
                )
            else:
                interfaces.append(
                    {
                        "producer": row[at["producer"]],
                        "consumer": row[at["consumer"]],
                        "attrs": {a: row[at[a.lower()]] for a in ATTRS},
                        "source": row[at["source"]] if "source" in at else "",
                        "status": status(row, at),
                        "line": lineno,
                    }
                )
            i += 1
    for kind, required in (("components", COMPONENT_COLUMNS), ("interfaces", INTERFACE_COLUMNS)):
        if kind not in found:
            die("no %s table found (expected columns: %s)" % (kind.capitalize(), ", ".join(required)))
    return components, interfaces, rules, cites, "rules" in found


def status(row, at):
    """The optional Status cell, or empty when the table has no Status column."""
    return row[at["status"]] if "status" in at else ""


def superseded(value):
    """A Status of `superseded <date>: <reason>` retires the row."""
    return value.strip().lower().startswith("superseded")


def blank(value):
    return value == "" or value == "?"


def build(components, interfaces, rules=()):
    names = []
    class_of = {}
    external = set()
    seen = {}
    active = {}  # active component -> line it was declared on
    retired = {}  # superseded component -> line it was declared on
    retired_components = 0
    for name, kind, cls, state, lineno in components:
        if not name:
            die("empty component name at line %d" % lineno)
        seen[name] = lineno
        if superseded(state):
            # a name may be retired any number of times and re-declared later
            retired[name] = lineno
            retired_components += 1
            continue
        if name in active:
            die("duplicate component %r at line %d (first at line %d)"
                % (name, lineno, active[name]))
        active[name] = lineno
        class_of[name] = cls
        names.append(name)
        if is_external(kind):
            external.add(name)

    def check(who, val, lineno):
        if val not in active and val in retired:
            die("superseded component %r named as %s at line %d (retired at line %d)"
                % (val, who, lineno, retired[val]))
        if val not in seen:
            die("unknown %s %r at line %d" % (who, val, lineno))

    known = {c for c in class_of.values() if c}
    for rule in rules:
        if superseded(rule["status"]):
            continue
        if rule["disposition"] not in DISPOSITIONS:
            die("rule at line %d: unknown disposition %r (expected %s)"
                % (rule["line"], rule["disposition"], " or ".join(DISPOSITIONS)))
        for who in ("producer", "consumer"):
            if rule[who] != "*" and rule[who] not in known:
                die("rule at line %d names %s class %r that no component has"
                    % (rule["line"], who, rule[who]))

    specified, gaps, nones, candidates = [], [], [], []
    retired_interfaces = 0
    for iface in interfaces:
        if superseded(iface["status"]):
            retired_interfaces += 1
            continue
        p, c = iface["producer"], iface["consumer"]
        if p == "?" or c == "?":
            for who, val in (("producer", p), ("consumer", c)):
                if val != "?":
                    check(who, val, iface["line"])
            candidates.append(iface)
            continue
        for who, val in (("producer", p), ("consumer", c)):
            check(who, val, iface["line"])
        if iface["attrs"]["Flows"].lower() == "none":
            nones.append(iface)
            continue
        missing = [a for a in ATTRS if blank(iface["attrs"][a])]
        if missing:
            iface["missing"] = missing
            gaps.append(iface)
        else:
            specified.append(iface)
    return (names, external, specified, gaps, nones, candidates,
            (retired_interfaces, retired_components), class_of)


def tarjan(names, edges):
    """Iterative Tarjan SCC. Returns SCCs as lists of names, reverse topological."""
    index = {}
    low = {}
    on_stack = set()
    stack = []
    result = []
    counter = [0]
    succ = {n: [] for n in names}
    for a, b in edges:
        if a != b:
            succ[a].append(b)

    for root in names:
        if root in index:
            continue
        work = [(root, 0)]
        while work:
            node, pi = work.pop()
            if pi == 0:
                index[node] = low[node] = counter[0]
                counter[0] += 1
                stack.append(node)
                on_stack.add(node)
            recurse = False
            for n in range(pi, len(succ[node])):
                nxt = succ[node][n]
                if nxt not in index:
                    work.append((node, n + 1))
                    work.append((nxt, 0))
                    recurse = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if recurse:
                continue
            if low[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    comp.append(w)
                    if w == node:
                        break
                result.append(comp)
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
    return result


def partition(names, edges):
    order_of = {n: i for i, n in enumerate(names)}
    sccs = tarjan(names, edges)
    for comp in sccs:
        comp.sort(key=order_of.get)
    sccs.sort(key=lambda c: order_of[c[0]])
    scc_of = {}
    for sid, comp in enumerate(sccs):
        for n in comp:
            scc_of[n] = sid
    graph = {sid: set() for sid in range(len(sccs))}
    for a, b in edges:
        if scc_of[a] != scc_of[b]:
            graph[scc_of[b]].add(scc_of[a])  # predecessors
    ts = graphlib.TopologicalSorter(graph)
    ts.prepare()
    ordered = []
    while ts.is_active():
        ready = sorted(ts.get_ready(), key=lambda s: order_of[sccs[s][0]])
        for sid in ready:
            ordered.append(sid)
            ts.done(sid)
    return [sccs[s] for s in ordered]


def spread(pairs, sample_n, order):
    """Stratified sample of unstated pairs: round-robin over producer rows.

    Quota by rounds: every row with unpicked pairs gets +1 per round; a round with
    more open rows than slots left spends them on evenly spaced rows. Within a row
    the picks are spread along it, phase-shifted by row index so that single picks
    sweep across columns. Deterministic, no randomness.
    """
    if sample_n == 0 or sample_n >= len(pairs):
        return pairs
    pos = {n: i for i, n in enumerate(order)}
    rows = {}
    for a, b in pairs:
        rows.setdefault(a, []).append(b)
    keys = sorted(rows, key=lambda a: pos[a])
    for a in keys:
        rows[a].sort(key=lambda b: pos[b])
    total = len(keys)
    quota = dict.fromkeys(keys, 0)
    left = sample_n
    while left:
        open_rows = [a for a in keys if quota[a] < len(rows[a])]
        if len(open_rows) <= left:
            for a in open_rows:
                quota[a] += 1
            left -= len(open_rows)
        else:
            for t in range(left):
                quota[open_rows[t * len(open_rows) // left]] += 1
            left = 0
    picks = []
    for i, a in enumerate(keys):
        q, m = quota[a], len(rows[a])
        for t in range(q):
            picks.append((a, rows[a][(t * total + i) * m // (q * total)]))
    return picks


def coverage(cites, path):
    """Report lines and uncited spans for `--source`: which source lines nothing
    cites. Returns (lines, spans as (first, last)); exit 1 on L>EOF."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    bad = sorted({(n, ln) for ln, n, _ in cites if n > len(lines) or n < 1})
    if bad:
        for n, ln in bad:
            if n < 1:
                sys.stderr.write("error: citation L%d at input line %d: source line "
                                 "numbers start at 1\n" % (n, ln))
            else:
                sys.stderr.write("error: citation L%d at input line %d is beyond %s (%d lines)\n"
                                 % (n, ln, path, len(lines)))
        raise SystemExit(1)
    cited = {n for _, n, covers in cites if covers}
    empty = sum(1 for t in lines if not t.strip())
    spans = []
    for i, text in enumerate(lines, 1):
        if not text.strip() or i in cited:
            continue
        if spans and all(not lines[k - 1].strip() for k in range(spans[-1][1] + 1, i)):
            spans[-1][1] = i
        else:
            spans.append([i, i])
    out = ["## 10. Source coverage\n"]
    out.append("`%s`: %d lines (%d blank), %d cited, %d uncited (non-blank).\n"
               % (path, len(lines), empty, len(cited), sum(b - a + 1 for a, b in spans)
                  - sum(1 for a, b in spans for k in range(a, b + 1) if not lines[k - 1].strip())))
    if spans:
        out.append("Nothing cites these spans — unmodelled components and interfaces hide here.\n")
        out.append("| lines | first line |")
        out.append("|---|---|")
        for a, b in spans:
            label = "L%d" % a if a == b else "L%d-%d" % (a, b)
            out.append("| %s | %s |" % (label, md(lines[a - 1].strip()[:80])))
    else:
        out.append("Every non-blank source line is cited.")
    out.append("")
    return out, spans


def span_label(span):
    """`L7` or `L7-9`, the label the coverage section and a ledger row share."""
    a, b = span
    return "L%d" % a if a == b else "L%d-%d" % (a, b)


def edges_of(specified, gaps, nones):
    """Stated pairs and their matrix marks: `X` specified, `g` gap; a `none` stated."""
    edge_of = {}
    for iface in specified:
        edge_of[(iface["producer"], iface["consumer"])] = "X"
    for iface in gaps:
        edge_of.setdefault((iface["producer"], iface["consumer"]), "g")
    stated = set(edge_of) | {(i["producer"], i["consumer"]) for i in nones}
    return edge_of, stated


def unstated_pairs(names, external, stated):
    """Pairs no row states: neither an interface, a gap nor an explicit `none`."""
    return [
        (a, b)
        for a in names
        for b in names
        if a != b
        and (a, b) not in stated
        and not (a in external and b in external)
    ]


def boundary(names, external, edges):
    """Internal components by boundary state: (internal, unfed, unconsumed, isolated).

    Nobody feeds an unfed component, nothing consumes an unconsumed one's output,
    an isolated one has no interface at all. A self-dependency is not an edge
    here: it neither feeds nor consumes anyone else.
    """
    ins = {n: 0 for n in names}
    outs = {n: 0 for n in names}
    for a, b in edges:
        outs[a] += 1
        ins[b] += 1
    internal = [n for n in names if n not in external]
    return (internal,
            [n for n in internal if not ins[n] and outs[n]],
            [n for n in internal if not outs[n] and ins[n]],
            [n for n in internal if not ins[n] and not outs[n]])


def settle(pairs, edge_of, rules, class_of):
    """Match unstated pairs against the active class rules, as report() renders them.

    Returns (active_rules, residue, matched, settled, by_rule, overrides);
    `residue` is the pairs no `none` rule settled — the pairs a review must
    disposition one by one.
    """
    def side(want, name):
        """`*` matches any classed component; a blank Class matches nothing."""
        cls = class_of.get(name, "")
        return bool(cls) and (want == "*" or want == cls)

    def hit(rule, a, b):
        return side(rule["producer"], a) and side(rule["consumer"], b)

    active_rules = [r for r in rules if not superseded(r["status"])]
    matched = {r["line"]: 0 for r in active_rules}
    settled = {r["line"]: 0 for r in active_rules}
    residue, by_rule = [], 0
    for a, b in pairs:
        hits = [r for r in active_rules if hit(r, a, b)]
        for r in hits:
            matched[r["line"]] += 1
        if hits and all(r["disposition"] == "none" for r in hits):
            by_rule += 1
            # a settled pair is attributed to every rule that settled it, so the
            # settled column sums to at least `by_rule`, not exactly to it
            for r in hits:
                settled[r["line"]] += 1
        else:
            residue.append((a, b))
    overrides = [
        (r["line"], a, b)
        for a, b in sorted(edge_of)
        for r in active_rules
        if r["disposition"] == "none" and hit(r, a, b)
    ]
    return active_rules, residue, matched, settled, by_rule, overrides


def report(names, external, specified, gaps, nones, candidates, retired, class_of,
           rules=(), sample_n=20, cov=None, has_rules=False):
    edge_of, stated = edges_of(specified, gaps, nones)

    edges = sorted(k for k in edge_of if k[0] != k[1])
    selfdeps = sorted({a for a, b in edge_of if a == b})
    blocks = partition(names, edges)
    order = [n for block in blocks for n in block]
    loops = [b for b in blocks if len(b) > 1]

    internal, unfed, unconsumed, isolated = boundary(names, external, edges)

    unstated = unstated_pairs(names, external, stated)

    active_rules, residue, matched, settled, by_rule, overrides = settle(
        unstated, edge_of, rules, class_of)

    unclassed = [n for n in names if not class_of.get(n, "")]

    out = []
    w = out.append
    w("# Interface matrix report\n")
    w("## 1. Summary\n")
    w("- components: %d (%d internal, %d external)" % (len(names), len(internal), len(external)))
    w("- specified interfaces: %d" % len(specified))
    w("- interfaces with gaps: %d" % len(gaps))
    w("- explicit none: %d" % len(nones))
    w("- missing-component candidates: %d" % len(candidates))
    w("- unstated pairs: %d" % len(unstated))
    w("- feedback loops: %d" % len(loops))
    w("- self-dependencies: %d" % len(selfdeps))
    w("- superseded rows: %d (interfaces %d, components %d)\n" % (sum(retired), retired[0], retired[1]))

    w("## 2. Missing-component candidates\n")
    if candidates:
        w("| line | producer | consumer | flows |")
        w("|---|---|---|---|")
        for c in sorted(candidates, key=lambda c: c["line"]):
            w("| line %d | %s | %s | %s |" % (c["line"], md(c["producer"]), md(c["consumer"]), md(c["attrs"]["Flows"])))
    else:
        w("None.")
    w("")

    w("## 3. Interface gaps\n")
    if gaps:
        w("| line | producer | consumer | missing |")
        w("|---|---|---|---|")
        for g in sorted(gaps, key=lambda g: g["line"]):
            w("| line %d | %s | %s | %s |" % (g["line"], md(g["producer"]), md(g["consumer"]), ", ".join(g["missing"])))
    else:
        w("None.")
    w("")

    w("## 4. Boundary check\n")
    w("External components are exempt.\n")
    w("- nothing feeds (internal): %s" % (", ".join(unfed) or "none"))
    w("- output nothing consumes (internal): %s" % (", ".join(unconsumed) or "none"))
    w("- isolated (internal): %s\n" % (", ".join(isolated) or "none"))

    w("## 5. Feedback loops\n")
    if loops:
        for n, block in enumerate(loops, 1):
            w("- loop %d (%d members): %s" % (n, len(block), ", ".join(block)))
    else:
        w("No feedback loops.")
    w("")
    w("Self-dependencies: %s\n" % (", ".join(selfdeps) or "none"))

    w("## 6. Partitioned order\n")
    for n, name in enumerate(order, 1):
        tag = " (loop)" if len(blocks[[i for i, b in enumerate(blocks) if name in b][0]]) > 1 else ""
        w("%d. %s%s" % (n, name, tag))
    w("")

    w("## 7. Unstated pairs\n")
    shown = spread(residue, sample_n, order)
    w("showing %d of %d (neither an interface nor `none`; external-to-external excluded)\n" % (len(shown), len(residue)))
    for a, b in shown:
        w("- %s -> %s" % (a, b))
    w("")

    w("## 8. Matrix\n")
    w("Row feeds column. Legend: `X` specified, `g` gap, `-` none, blank unstated, `S` self.\n")
    pos = {n: i for i, n in enumerate(order)}
    none_pairs = {(i["producer"], i["consumer"]) for i in nones}
    width = max([len(n) for n in order] + [1])
    cw = max(3, len(str(len(order))) + 1)
    header = " " * (width + 4) + "".join("%-*d" % (cw, i + 1) for i in range(len(order)))
    w("```")
    w(header)
    below_ok = True
    loop_id = {n: i for i, b in enumerate(blocks) for n in b}
    for i, row in enumerate(order):
        marks = []
        for j, col in enumerate(order):
            if row == col:
                mark = "S" if row in selfdeps else "."
            elif (row, col) in edge_of:
                mark = edge_of[(row, col)]
            elif (row, col) in none_pairs:
                mark = "-"
            else:
                mark = " "
            if mark not in (" ", ".", "-") and i > j and loop_id[row] != loop_id[col]:
                below_ok = False
            marks.append(mark)
        w("%3d %-*s%s" % (i + 1, width, row, "".join("%-*s" % (cw, " " + m) for m in marks)))
    w("```\n")
    if not below_ok:
        sys.stderr.write("error: below-diagonal mark outside a loop block: partition is wrong\n")
        raise SystemExit(2)
    w("below-diagonal check: every below-diagonal mark lies inside a loop block.")

    if has_rules:
        w("")
        w("## 9. Class rules\n")
        w("- unclassed components (no rule matches them; their pairs stay in section 7): %s\n"
          % (", ".join(unclassed) or "none"))
        if active_rules:
            w("`pairs settled` = unstated pairs this rule left settled `none` (0 for a "
              "`review` rule, and 0 where a `review` rule overrode it); "
              "`pairs matched` = pairs the rule matched at all. A pair settled by several "
              "`none` rules is counted under each, so the settled column sums to at least "
              "the total below it.\n")
            w("| line | producer class | consumer class | disposition | pairs settled | pairs matched | reason |")
            w("|---|---|---|---|---|---|---|")
            for r in active_rules:
                w("| line %d | %s | %s | %s | %d | %d | %s |"
                  % (r["line"], md(r["producer"]), md(r["consumer"]), r["disposition"],
                     settled[r["line"]], matched[r["line"]], md(r["reason"])))
            dead = ["line %d" % r["line"] for r in active_rules if not matched[r["line"]]]
            w("")
            w("- dead rules (no unstated pair matched): %s" % (", ".join(dead) or "none"))
            w("- unstated pairs settled none by rule: %d (left out of section 7)" % by_rule)
            w("- residue for pair-by-pair review: %d" % len(residue))
            w("")
            w("`none` rules that match an explicit interface (review the rule):\n")
            if overrides:
                w("| rule line | producer | consumer |")
                w("|---|---|---|")
                for line, a, b in overrides:
                    w("| line %d | %s | %s |" % (line, md(a), md(b)))
            else:
                w("None.")
        else:
            w("No active rules.")
        w("")
    if cov:
        w("")
        out.extend(cov)
    return "\n".join(out).rstrip("\n") + "\n"


def record_heading(line):
    """True for a heading of any level naming the certification record."""
    text = line.strip()
    return text.startswith("#") and text.lstrip("#").strip().lower() == "certification record"


def parse_declared_flags(value, ln):
    """The certification record's flags line, back into (--sample, --source)."""
    m = re.match(r"^--sample (\d+)(?: --source (.+))?$", value)
    if not m:
        die("certification record at line %d: flags %r must read "
            "'--sample N [--source PATH]'" % (ln, value))
    return (int(m.group(1)), m.group(2))


def read_ledger(path):
    """Ledger disposition rows and the flags its certification record pins.

    Returns (rows, declared): rows are (kind, finding, disposition, reason,
    reviewer, date, fingerprint, line) from the ledger's one disposition table
    — the one table naming Kind and Finding; declared is the (--sample N,
    --source PATH) the ledger's `## Certification record` section declares, or
    None when the ledger pins none. A row of the wrong width, an unknown kind,
    or a row without a finding, disposition, reviewer, date and fingerprint is
    bad input, exactly like a bad row of the input file.
    """
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    rows = []
    seen = 0
    rec_seen = 0
    declared = None  # (flags, line) once a `- flags:` line is read
    i = 0
    while i < len(lines):
        if record_heading(lines[i]):
            if rec_seen:
                die("second certification record at line %d (first at line %d)"
                    % (i + 1, rec_seen))
            rec_seen = i + 1
            i += 1
            while i < len(lines) and not lines[i].lstrip().startswith("#"):
                m = re.match(r"^- flags: (.+)$", lines[i])
                if m:
                    if declared is not None:
                        die("certification record declares flags twice, at lines "
                            "%d and %d" % (declared[1], i + 1))
                    declared = (parse_declared_flags(m.group(1).strip(), i + 1),
                                i + 1)
                i += 1
            continue
        if not is_header(lines, i):
            i += 1
            continue
        head = [c.lower() for c in cells(lines[i])]
        if not {"kind", "finding"} <= set(head):
            i += 1
            continue
        if seen:
            die("second disposition table at line %d (first at line %d)" % (i + 1, seen))
        seen = i + 1
        at = columns(head, LEDGER_COLUMNS, i + 1)
        i += 2
        while i < len(lines) and lines[i].strip().startswith("|") and not is_header(lines, i):
            row = cells(lines[i])
            if len(row) != len(head):
                die("ledger row at line %d has %d cells, expected %d"
                    % (i + 1, len(row), len(head)))
            kind = row[at["kind"]].strip().lower()
            if kind not in LEDGER_KINDS:
                die("ledger row at line %d: unknown kind %r (expected one of: %s)"
                    % (i + 1, kind, ", ".join(LEDGER_KINDS)))
            if not all(row[at[c]].strip() for c in
                       ("finding", "disposition", "reviewer", "date", "fingerprint")):
                die("ledger row at line %d needs a finding, a disposition, a "
                    "reviewer, a date and a fingerprint" % (i + 1))
            rows.append(tuple(row[at[c]].strip() for c in
                              ("kind", "finding", "disposition", "reason",
                               "reviewer", "date", "fingerprint")) + (i + 1,))
            i += 1
    if not seen:
        die("no disposition table in %s (expected columns: %s)"
            % (path, ", ".join(LEDGER_COLUMNS)))
    return rows, declared[0] if declared else None


def check_flags(args, declared):
    """--certify replays the recorded review exactly: the invocation's flags
    must match the ones the ledger's certification record declares, so a run
    without --source cannot silently skip the span checks."""
    sample, source = declared
    if args.sample != sample:
        die("the ledger's certification record declares --sample %d but "
            "certification was invoked with --sample %d; replay the recorded "
            "review exactly (amend the record section to re-review under other "
            "flags)" % (sample, args.sample))
    if not args.source and source:
        die("the ledger's certification record declares --source %s but "
            "certification was invoked without it; the span checks cannot be "
            "skipped" % source)
    if args.source and not source:
        die("the ledger's certification record declares no --source but "
            "certification was invoked with --source %s; replay the recorded "
            "review exactly" % args.source)
    if args.source and source and args.source != source:
        die("the ledger's certification record declares --source %s but "
            "certification was invoked with --source %s; replay the recorded "
            "review exactly" % (source, args.source))


def parse_finding(kind, finding, ln, has_source):
    """A ledger Finding cell back into its identity key, by kind.

    Interface-row findings read `producer -> consumer: flows`, pairs `A -> B`,
    boundary findings name the component, spans `L7-9@<source sha256>`. The
    identity is what drift matching keys on; a cell that cannot be an identity
    at all is a bad ledger row, not drift.
    """
    if kind in ("candidate", "gap"):
        if " -> " not in finding or ": " not in finding.split(" -> ", 1)[1]:
            die("ledger row at line %d: %s finding %r must read "
                "'producer -> consumer: flows'" % (ln, kind, finding))
        producer, rest = finding.split(" -> ", 1)
        consumer, flows = rest.split(": ", 1)
        return (producer.strip(), consumer.strip(), flows.strip())
    if kind == "pair":
        if " -> " not in finding:
            die("ledger row at line %d: pair finding %r must read 'A -> B'"
                % (ln, finding))
        a, b = finding.split(" -> ", 1)
        return (a.strip(), b.strip())
    if kind == "boundary":
        return (finding,)
    if not has_source:
        die("ledger row at line %d dispositions source span %r but certification "
            "was invoked without --source" % (ln, finding))
    label, _, sha = finding.rpartition("@")
    if not sha or not re.match(r"^L\d+(-\d+)?$", label):
        die("ledger row at line %d: span finding %r must read "
            "'L7-9@<source sha256>'" % (ln, finding))
    first, _, last = label[1:].partition("-")
    return (sha, int(first), int(last or first))


def fingerprint(*parts):
    """A stable content fingerprint: the sha256 of the parts as canonical JSON."""
    return hashlib.sha256(json.dumps(list(parts)).encode("utf-8")).hexdigest()


def row_fingerprint(iface):
    """An interface row's full content: its identity cells plus format,
    trigger, owner and source, so any edit to a dispositioned row is drift."""
    return fingerprint(iface["producer"], iface["consumer"],
                       *[iface["attrs"][a] for a in ATTRS], iface["source"])


def sha256_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_path(ledger_path):
    """The standalone record file lives beside the ledger."""
    return (ledger_path[:-3] if ledger_path.endswith(".md") else ledger_path) + ".cert.md"


def stamp_ledger_record(ledger_path, record):
    """Write the record into the ledger's certification-record section,
    replacing the section a previous pass stamped."""
    section = "## Certification record" + record[record.index("\n"):]
    with open(ledger_path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    out, i, stamped = [], 0, False
    while i < len(lines):
        if record_heading(lines[i]):
            i += 1
            while i < len(lines) and not lines[i].lstrip().startswith("#"):
                i += 1
            out.extend(section.rstrip("\n").split("\n"))
            stamped = True
            if i < len(lines):
                out.append("")
            continue
        out.append(lines[i])
        i += 1
    if not stamped:
        if out and out[-1].strip():
            out.append("")
        out.extend(section.rstrip("\n").split("\n"))
    with open(ledger_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")


def certify(args, built, rules, spans, rendered):
    """Judge the ledger against the findings the report derives from the input.

    Returns (record, refused): the record names every blocker — an entry whose
    finding drifted (gone from the input, or changed since disposition) and
    every finding no entry covers — plus every advisory, a gap dispositioned
    open, which may legitimately stay open; refused means exit 3.
    """
    names, external, specified, gaps, nones, candidates, retired, class_of = built

    # the ledger keys interface-row findings by producer, consumer and flows,
    # so two active input rows sharing that identity would be one ambiguous
    # finding: an input error under --certify (generation is unchanged)
    first_line = {}
    for iface in sorted((i for group in (specified, gaps, nones, candidates)
                         for i in group), key=lambda i: i["line"]):
        key = (iface["producer"], iface["consumer"], iface["attrs"]["Flows"])
        if key in first_line:
            die("input rows at lines %d and %d share one interface identity "
                "(%s -> %s: %s); the review ledger cannot tell them apart"
                % (first_line[key], iface["line"], key[0], key[1], key[2]))
        first_line[key] = iface["line"]

    rows, declared = read_ledger(args.certify)
    if declared is not None:
        check_flags(args, declared)

    entries, seen_keys = [], {}
    for kind, finding, disposition, reason, reviewer, date, fp, ln in rows:
        key = parse_finding(kind, finding, ln, bool(args.source))
        if (kind, key) in seen_keys:
            die("ledger rows at lines %d and %d both disposition %s %r"
                % (seen_keys[(kind, key)], ln, kind, finding))
        seen_keys[(kind, key)] = ln
        entries.append((kind, key, finding, fp, disposition, reason, ln))

    edge_of, stated = edges_of(specified, gaps, nones)
    internal, unfed, unconsumed, isolated = boundary(
        names, external, sorted(k for k in edge_of if k[0] != k[1]))
    residue = settle(unstated_pairs(names, external, stated), edge_of, rules,
                     class_of)[1]
    why = {}
    for group, label in ((unfed, "nothing feeds it"),
                         (unconsumed, "nothing consumes its output"),
                         (isolated, "isolated")):
        for n in group:
            why[n] = label
    src_sha = sha256_file(args.source) if args.source else None

    # every finding the gate can refuse on, keyed by stable identity with the
    # content fingerprint the ledger pins — input line numbers appear only in
    # the notes, never in the identity, so unrelated edits do not re-open rows
    found = {}  # (kind, identity) -> (label, fingerprint, note)
    for c in sorted(candidates, key=lambda c: c["line"]):
        key = (c["producer"], c["consumer"], c["attrs"]["Flows"])
        found[("candidate", key)] = ("%s -> %s: %s" % key, row_fingerprint(c),
                                     "input line %d" % c["line"])
    for g in sorted(gaps, key=lambda g: g["line"]):
        key = (g["producer"], g["consumer"], g["attrs"]["Flows"])
        found[("gap", key)] = ("%s -> %s: %s" % key, row_fingerprint(g),
                               "input line %d, missing %s"
                               % (g["line"], ", ".join(g["missing"])))
    for n in names:
        if n in why:
            found[("boundary", (n,))] = (n, fingerprint(n, why[n]), why[n])
    for a, b in residue:
        found[("pair", (a, b))] = ("%s -> %s" % (a, b), fingerprint(a, b),
                                   "no row states it")
    for s in spans:
        found[("span", (src_sha, s[0], s[1]))] = (
            "%s@%s" % (span_label(s), src_sha), fingerprint(src_sha, s[0], s[1]),
            "of %s" % args.source)

    drifted, unreviewed, advisories, covered = [], [], [], set()
    for kind, key, label, fp, disposition, reason, ln in entries:
        f = found.get((kind, key))
        if f is None:
            drifted.append("drifted: %s %s (ledger line %d) no longer matches any "
                           "%s finding in the input" % (KIND_NOUNS[kind], label, ln, kind))
            continue
        # the identity still exists: the finding is covered by this entry even
        # when its content moved, so it is drift, never also unreviewed
        covered.add((kind, key))
        if fp != f[1]:
            drifted.append("drifted: %s %s (ledger line %d) changed since "
                           "disposition; current fingerprint %s"
                           % (KIND_NOUNS[kind], label, ln, f[1]))
        elif kind == "gap" and disposition.lower().startswith("open"):
            advisories.append("gap %s (%s): %s"
                              % (label, f[2], " — ".join(
                                  x for x in (disposition, reason) if x)))
    for (kind, key), (label, fp, note) in found.items():
        if (kind, key) not in covered:
            unreviewed.append("unreviewed: %s %s (%s) %s (fingerprint %s)"
                              % (KIND_NOUNS[kind], label, note, KIND_VERBS[kind], fp))

    blockers = drifted + unreviewed
    if blockers:
        sys.stderr.write("error: certification refused: %d blocker(s) (%d drifted, "
                         "%d unreviewed), named in the record\n"
                         % (len(blockers), len(drifted), len(unreviewed)))
    return (certification_record(args, blockers, advisories,
                                 sha256_file(args.input), sha256_text(rendered),
                                 src_sha),
            bool(blockers))


def certification_record(args, blockers, advisories, input_sha, report_sha, src_sha):
    """The certification record: written beside the ledger as a standalone
    file, printed, and — after a pass — stamped into the ledger itself. It
    binds the exact input, report and (when --source ran) source file by
    sha256, the gate result and the flags the review ran under; a later
    --certify must replay those flags exactly."""
    out = ["# Interface matrix certification", ""]
    out.append("- input: %s (sha256 %s)" % (args.input, input_sha))
    out.append("- ledger: %s" % args.certify)
    out.append("- gate: %s" % ("refused" if blockers else "certified"))
    out.append("- report: sha256 %s" % report_sha)
    out.append("- flags: --sample %d%s" % (args.sample,
                                           " --source %s" % args.source if args.source else ""))
    if src_sha:
        out.append("- source: %s (sha256 %s)" % (args.source, src_sha))
    out.append("- blockers: %s" % (len(blockers) if blockers else "none"))
    out.extend("  - %s" % b for b in blockers)
    out.append("- advisories: %s" % (len(advisories) if advisories else "none"))
    out.extend("  - %s" % a for a in advisories)
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", help="Markdown file with Components and Interfaces tables")
    ap.add_argument("--certify", metavar="LEDGER",
                    help="review ledger to certify the input against instead of "
                         "printing the report: exit 0 with a certification record, "
                         "exit 3 naming every blocker (drifted or unreviewed), "
                         "exit 1 on a bad ledger row, a duplicate identity, or "
                         "flags that do not replay the recorded review (ledger "
                         "format in the module docstring)")
    ap.add_argument("--sample", type=nonneg, default=20, help="unstated pairs to print (0 = all)")
    ap.add_argument("--source", help="source file whose L<n> citations to check for coverage")
    args = ap.parse_args(argv)
    # Windows consoles default to legacy codepages (cp437/cp850/cp1252) and CI pipes
    # may be plain ASCII; writing the report raw then dies mid-report with
    # UnicodeEncodeError. Reconfigure stdout to UTF-8 so the report is byte-identical
    # whatever the console or pipe claims (Python 3.7+; 3.9 is the floor).
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        pass
    with open(args.input, encoding="utf-8") as fh:
        text = fh.read()
    components, interfaces, rules, cites, has_rules = parse(text)
    if args.source:
        cov, spans = coverage(cites, args.source)
    else:
        cov, spans = None, []
    built = build(components, interfaces, rules)
    if args.certify:
        # the gate certifies what the report shows: render it once — coverage
        # section included when --source ran — so certification dies on the same
        # invariant (exit 2) and the record can bind the report's sha256; then
        # judge the ledger against the same derivation. The record replaces the
        # rendered report on stdout, lands beside the ledger as a standalone
        # file, and a pass also stamps it into the ledger itself.
        rendered = report(*built, rules=rules, sample_n=args.sample, cov=cov,
                          has_rules=has_rules)
        record, refused = certify(args, built, rules, spans, rendered)
        with open(record_path(args.certify), "w", encoding="utf-8") as fh:
            fh.write(record)
        if not refused:
            stamp_ledger_record(args.certify, record)
        sys.stdout.write(record)
        return 3 if refused else 0
    sys.stdout.write(report(*built, rules=rules, sample_n=args.sample, cov=cov,
                            has_rules=has_rules))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
