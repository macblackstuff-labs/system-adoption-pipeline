#!/usr/bin/env python3
"""Pass 7 of the adoption pipeline: the deterministic checklist over passes 1-6.

Reads the five Markdown artifacts written from the templates in ../templates and
reports five checks. Exit 0 = every check passed, 1 = at least one failed,
2 = an input file could not be read as the template it is supposed to follow.

Python 3.9+, standard library only.
"""

import argparse
import re
import sys

USER_QUESTION_LIMIT = 10


def is_external(cell):
    """True if a pass-1 `Type` puts the component outside the boundary.

    A token test, not a substring one: the Type's first word is `external`, or the Type
    carries the token `(external)`. So `External system` and `actor (external)` are
    outside; `non-external store`, `internal/external bridge`, `external-facing gateway`
    and `externally reached` are ours to build.
    """
    words = cell.strip().lower().split()
    return bool(words) and (words[0] == "external" or "(external)" in words)


# ---------------------------------------------------------------- parsing

def split_row(line):
    """Split one Markdown table row into cells. A backslash escapes the next char."""
    cells, cur, esc = [], [], False
    for ch in line.strip():
        if esc:
            cur.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == "|":
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    cells.append("".join(cur).strip())
    if cells and cells[0] == "":
        cells.pop(0)
    if cells and cells[-1] == "":
        cells.pop()
    return cells


def is_separator(line):
    return bool(re.fullmatch(r"\|?[\s|:-]*-[\s|:-]*\|?", line.strip())) and "-" in line


def tables(text):
    """Yield (header_cells, [row_cells, ...]) for every Markdown table in the text."""
    lines = text.splitlines()
    i = 0
    while i < len(lines) - 1:
        if lines[i].lstrip().startswith("|") and is_separator(lines[i + 1]):
            header = [c.lower() for c in split_row(lines[i])]
            rows, j = [], i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                if not is_separator(lines[j]):
                    rows.append(split_row(lines[j]))
                j += 1
            yield header, rows
            i = j
        else:
            i += 1


def read_table(path, required, what):
    """Return [{column: value}] for the table in `path` holding every required column."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print("error: cannot read %s: %s" % (path, exc), file=sys.stderr)
        sys.exit(2)
    for header, rows in tables(text):
        if all(col in header for col in required):
            out = []
            for cells in rows:
                cells = cells + [""] * (len(header) - len(cells))
                out.append(dict(zip(header, cells)))
            return out
    print("error: no %s table in %s (expected columns: %s)"
          % (what, path, ", ".join(required)), file=sys.stderr)
    sys.exit(2)


PLACEHOLDERS = ("", "-", "?", "none", "tbd")


def real_id(cell):
    """True if the cell holds a real id, not a placeholder. The one such test in this file.

    Blank, `-`, `?`, `none` and `TBD` (any letter case) name nothing, so nothing that
    counts, deduplicates or cross-references ids may treat them as one.
    """
    return cell.strip().lower() not in PLACEHOLDERS


def ids(cell):
    """Real ids in a cell: comma, semicolon or whitespace separated."""
    return [tok for tok in re.split(r"[,;\s]+", cell.strip()) if real_id(tok)]


def blank(cell):
    return not real_id(cell)


def is_blocked(step):
    return step["blocked"].strip().lower() in ("yes", "blocked", "true")


# ---------------------------------------------------------------- checks

class Result:
    def __init__(self):
        self.lines = []
        self.failed = False

    def add(self, name, ok, summary, offenders=()):
        self.lines.append("check %s: %s — %s" % (name, "PASS" if ok else "FAIL", summary))
        for off in offenders:
            self.lines.append("  - %s" % off)
        if not ok:
            self.failed = True


def run(inventory, interfaces, gaps, packages, ordering):
    # An id restated in pass 1 is one component: de-duplicate, keeping the first order.
    components = list(dict.fromkeys(r["id"] for r in inventory if real_id(r["id"])))
    # A component whose Type says `external` sits outside the boundary: nobody builds it,
    # so checks 1 and 2 exempt it (as a component and as an interface endpoint). A restated
    # id is external only if every one of its rows says so.
    external = {c for c in components
                if all(is_external(r.get("type", "")) for r in inventory if r["id"] == c)}
    res = Result()

    # Coverage accumulates per row: a restated `WP` or `Step` id is two rows, not one.
    covered = set()
    for r in packages:
        covered.update(ids(r["components"]))
    wave1 = []
    for r in ordering:
        covered.update(ids(r["components"]))
        if r["wave"].strip().lower() in ("1", "wave 1"):
            wave1.append(r)

    # 1 — every component has at least one package or step
    internal = [c for c in components if c not in external]
    missing = [c for c in internal if c not in covered]
    res.add("1 component coverage", not missing,
            "%d of %d non-external components appear in a package or step; %d external exempt"
            % (len(internal) - len(missing), len(internal), len(external)),
            ["component %s is in no package and no step" % c for c in missing])
    unknown = sorted(covered - set(components))
    if unknown:
        res.add("1b known ids", False,
                "%d id(s) named by a package or step are not in the inventory" % len(unknown),
                ["unknown id %s" % u for u in unknown])
    else:
        res.add("1b known ids", True, "every id named by a package or step is in the inventory")

    # 2 — every interface has a producer and a consumer somewhere in the plan (any package
    # or step, so a later-wave interface is covered). A plan with packages but no wave-1
    # steps is caught by check 3, not here. An endpoint the inventory does not know is a
    # pass-3 defect and is named as one. An interface between two externals builds nothing:
    # it is exempt and not counted as built.
    bad, built, ext_only = [], 0, 0
    for r in interfaces:
        ends = {role: ids(r[role]) for role in ("producer", "consumer")}
        if all(ends.values()) and all(e in external for v in ends.values() for e in v):
            ext_only += 1
            continue
        ends_built = True
        for role, endpoints in ends.items():
            if not endpoints:
                bad.append("interface %s has no %s" % (r["id"], role))
                ends_built = False
            for endpoint in endpoints:
                if endpoint in external:
                    continue
                if endpoint not in components:
                    bad.append("interface %s: %s %s is not in the inventory (fix it in pass 3)"
                               % (r["id"], role, endpoint))
                    ends_built = False
                elif endpoint not in covered:
                    bad.append("interface %s: %s %s is in no package and no step"
                               % (r["id"], role, endpoint))
                    ends_built = False
        if ends_built:
            built += 1
    res.add("2 interface endpoints", not bad,
            "%d of %d interfaces have both endpoints built; %d external-to-external exempt"
            % (built, len(interfaces) - ext_only, ext_only),
            bad)

    # 3 — there is a wave 1, and every wave-1 step has an acceptance check
    no_check = [r["step"] for r in wave1 if blank(r["acceptance"])]
    if not wave1:
        res.add("3 wave-1 acceptance", False, "no wave-1 step in the ordering",
                ["pass 6 names no step in wave 1, so nothing is committed first"])
    else:
        res.add("3 wave-1 acceptance", not no_check,
                "%d of %d wave-1 steps carry an acceptance check"
                % (len(wave1) - len(no_check), len(wave1)),
                ["step %s has no acceptance check" % s for s in no_check])
    blocked = [r["step"] for r in wave1 if is_blocked(r)]
    if blocked:
        # advisory, not a failure: the skeleton cannot run end to end until these clear
        res.lines.append("  advisory: %d of %d wave-1 steps are BLOCKED (%s); the walking "
                         "skeleton cannot run end to end until they clear"
                         % (len(blocked), len(wave1), ", ".join(blocked)))

    # 4 — no wave-1 step depends on an unresolved USER gap unless labelled BLOCKED
    open_user = {r["id"] for r in gaps
                 if r["class"].strip().upper() == "USER" and real_id(r["id"])
                 and r["status"].strip().lower() != "resolved"}
    # A step id in the `Gaps` cell names an upstream step: depending on a BLOCKED one
    # blocks this one too.
    blocked_steps = {r["step"] for r in wave1 if is_blocked(r)}
    # Anything else in the cell must still name something this plan knows: a gap id from
    # pass 4 or a wave-1 step id. A typo would otherwise silently name nothing and turn
    # the blocking above off, so it is a failure, not silence.
    known_refs = {r["id"] for r in gaps if real_id(r["id"])} | {r["step"] for r in wave1}
    offenders, without_blocked, bad_refs = [], set(), 0
    for r in wave1:
        unknown_refs = [g for g in ids(r["gaps"]) if g not in known_refs]
        if unknown_refs:
            bad_refs += len(unknown_refs)
            offenders.append(
                "step %s: Gaps names %s, which is neither a pass-4 gap id nor a wave-1 step "
                "id (fix it in pass 6: name a real gap or step, or leave the cell `-`)"
                % (r["step"], ", ".join(unknown_refs)))
        if is_blocked(r):
            continue
        depends = [g for g in ids(r["gaps"]) if g in open_user]
        if depends:
            without_blocked.add(r["step"])
            offenders.append("step %s depends on unresolved USER gap %s and is not labelled BLOCKED"
                             % (r["step"], ", ".join(depends)))
        upstream = [g for g in ids(r["gaps"]) if g in blocked_steps]
        if upstream:
            without_blocked.add(r["step"])
            offenders.append("step %s depends on BLOCKED step %s and is not labelled BLOCKED"
                             % (r["step"], ", ".join(upstream)))
    summary = ("%d unresolved USER gap(s); %d wave-1 step(s) depend on one without BLOCKED"
               % (len(open_user), len(without_blocked)))
    if bad_refs:
        summary += "; %d Gaps reference(s) name nothing in the plan" % bad_refs
    res.add("4 wave-1 user gaps", not offenders, summary, offenders)

    # 5 — USER questions <= 10. A restated gap id is one question, not two; a placeholder
    # id cannot be deduplicated, so each such USER row is its own question.
    user_rows = [r for r in gaps if r["class"].strip().upper() == "USER"]
    user_count = len({r["id"] for r in user_rows if real_id(r["id"])}) \
        + len([r for r in user_rows if not real_id(r["id"])])
    res.add("5 user question budget", user_count <= USER_QUESTION_LIMIT,
            "%d USER question(s), limit %d" % (user_count, USER_QUESTION_LIMIT))

    classes = {}
    for r in gaps:
        classes[r["class"].strip().upper()] = classes.get(r["class"].strip().upper(), 0) + 1
    res.lines.append("counts (distinct non-blank ids for components and packages, "
                     "table rows otherwise): "
                     "components %d · interfaces %d · gaps %d (%s) · packages %d · wave-1 steps %d"
                     % (len(components), len(interfaces), len(gaps),
                        ", ".join("%s %d" % kv for kv in sorted(classes.items())),
                        len({r["wp"] for r in packages if real_id(r["wp"])}), len(wave1)))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pass 7 checklist over the pass 1-6 artifacts.")
    ap.add_argument("--inventory", required=True, help="pass 1/2 component inventory")
    ap.add_argument("--interfaces", required=True, help="pass 3 interface list")
    ap.add_argument("--gaps", required=True, help="pass 4 gap register")
    ap.add_argument("--packages", required=True, help="pass 5 work packages")
    ap.add_argument("--ordering", required=True, help="pass 6 ordering and wave-1 steps")
    args = ap.parse_args(argv)

    res = run(
        read_table(args.inventory, ["id"], "component inventory"),
        read_table(args.interfaces, ["id", "producer", "consumer"], "interface"),
        read_table(args.gaps, ["id", "class", "status"], "gap register"),
        read_table(args.packages, ["wp", "components"], "work package"),
        read_table(args.ordering, ["step", "wave", "components", "gaps", "blocked", "acceptance"],
                   "wave-1 step"),
    )
    print("\n".join(res.lines))
    return 1 if res.failed else 0


if __name__ == "__main__":
    sys.exit(main())
