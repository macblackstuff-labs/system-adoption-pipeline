"""Tests for interface_matrix.py. Run: python3 scripts/test_interface_matrix.py"""

import os
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "interface_matrix.py")

FRONTMATTER = """---
status: inbox
tldr: a vault note
---

Some prose that must be ignored.

"""

COMPONENTS = """## Components

| Component | Kind | Notes |
|---|---|---|
| Ingest |  | pulls raw events |
| Scorer |  | ranks events |
| Store |  | persistence |
| Analyst | external | a human |

"""

COMPONENTS_SUPERSEDED = """## Components

| Component | Kind | Notes | Status |
|---|---|---|---|
| Ingest |  | pulls raw events |  |
| Scorer |  | ranks events |  |
| Store |  | persistence | superseded 2026-09-26: replaced by Lake |
| Analyst | external | a human |

"""

COMPONENTS_REDECLARED = """## Components

| Component | Kind | Notes | Status |
|---|---|---|---|
| Ingest |  | pulls raw events |  |
| Scorer |  | ranks events |  |
| Store |  | old persistence | superseded 2026-09-26: replaced |
| Store |  | new persistence |  |
| Analyst | external | a human |

"""

STATUS_HEAD = (
    "| Producer | Consumer | Flows | Format | Trigger | Owner | Source | Status |\n"
    "|---|---|---|---|---|---|---|---|\n"
)


def run(text, *args):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
        fh.write(text)
        path = fh.name
    try:
        proc = subprocess.run(
            [sys.executable, SCRIPT, path, *args],
            capture_output=True,
            text=True,
        )
    finally:
        os.unlink(path)
    return proc


def doc(interface_rows, components=COMPONENTS, frontmatter=FRONTMATTER):
    head = "| Producer | Consumer | Flows | Format | Trigger | Owner | Source |\n|---|---|---|---|---|---|---|\n"
    return frontmatter + components + "## Interfaces\n\n" + head + interface_rows


def doc_status(interface_rows, components=COMPONENTS):
    """Same layout as doc(), but both tables may carry a Status column."""
    return FRONTMATTER + components + "## Interfaces\n\n" + STATUS_HEAD + interface_rows


class TestErrors(unittest.TestCase):
    def test_unknown_component_exits_1_with_line(self):
        proc = run(doc("| Ingest | Nope | rows | csv | cron | me | S:L1 |\n"))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Nope", proc.stderr)
        self.assertIn("line 21", proc.stderr)

    def test_duplicate_component_exits_1_with_line(self):
        components = COMPONENTS.replace("| Store |  | persistence |", "| Store |  | persistence |\n| Ingest |  | again |")
        proc = run(doc("", components=components))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Ingest", proc.stderr)
        self.assertIn("line 15", proc.stderr)

    def test_empty_component_name_exits_1_with_line(self):
        components = COMPONENTS.replace("| Store |  | persistence |", "|  |  | nameless |")
        proc = run(doc("", components=components))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("line 14", proc.stderr)

    def test_missing_required_column_exits_1(self):
        head = "| Producer | Consumer | Flows | Format | Owner | Source |\n|---|---|---|---|---|---|\n"
        text = FRONTMATTER + COMPONENTS + "## Interfaces\n\n" + head
        proc = run(text + "| Ingest | Store | rows | csv | me | S:L1 |\n")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("trigger", proc.stderr.lower())

    def test_components_table_missing_notes_diagnosed_as_missing_notes(self):
        components = (
            "| Component | Kind | Trigger | Format | Owner | Source |\n"
            "|---|---|---|---|---|---|\n| Ingest |  |  |  |  |  |\n\n"
        )
        proc = run(doc("", components=components))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("notes", proc.stderr)
        self.assertNotIn("producer", proc.stderr)

    def test_second_interfaces_table_exits_1_naming_both(self):
        proc = run(doc(
            "| Ingest | Store | rows | csv | cron | me | S:L1 |\n"
            "\n"
            "| Producer | Consumer | Flows | Format | Trigger | Owner | Source |\n"
            "|---|---|---|---|---|---|---|\n"
            "| Scorer | Store | scores | csv | cron | me |  |\n"
        ))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("line 19", proc.stderr)
        self.assertIn("line 23", proc.stderr)

    def test_second_components_table_exits_1_naming_both(self):
        components = COMPONENTS + "| Component | Kind | Notes |\n|---|---|---|\n| Extra |  | late |\n\n"
        proc = run(doc("", components=components))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("line 10", proc.stderr)
        self.assertIn("line 17", proc.stderr)

    def test_question_row_validates_the_named_endpoint(self):
        proc = run(doc("| ? | TYPO | rows | csv | cron | me |  |\n"))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("TYPO", proc.stderr)
        self.assertIn("line 21", proc.stderr)

    def test_negative_sample_rejected(self):
        proc = run(doc("| Ingest | Store | rows | csv | cron | me | S:L1 |\n"), "--sample", "-1")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("sample", proc.stderr)

    def test_valid_input_exits_0(self):
        proc = run(doc("| Ingest | Store | rows | csv | cron | me | S:L1 |\n"))
        self.assertEqual(proc.returncode, 0, proc.stderr)


class TestParsing(unittest.TestCase):
    def test_escaped_pipe_is_one_cell(self):
        proc = run(doc(
            "| Ingest | Store | x \\| y | json | cron | me |  |\n"
            "| ? | Scorer | x \\| y | json | cron | me |  |\n"
        ))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("specified interfaces: 1", proc.stdout)
        self.assertIn("interfaces with gaps: 0", proc.stdout)
        cands = proc.stdout.split("## 2.")[1].split("## 3.")[0]
        self.assertIn("| x \\| y |", cands)

    def test_adjacent_tables_not_merged(self):
        text = (
            FRONTMATTER
            + "| Component | Kind | Notes |\n|---|---|---|\n| Ingest |  | pulls |\n"
            + "| Producer | Consumer | Flows | Format | Trigger | Owner | Source |\n"
            + "|---|---|---|---|---|---|---|\n"
            + "| Ingest | Nope | rows | csv | cron | me | S:L1 |\n"
        )
        proc = run(text)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("unknown consumer", proc.stderr)
        self.assertIn("'Nope'", proc.stderr)

    def test_reordered_interface_columns_parse_identically(self):
        canonical = run(doc("| Ingest | Store | rows | csv | cron | me | S:L1 |\n"))
        head = "| Source | Owner | Trigger | Format | Flows | Consumer | Producer |\n|---|---|---|---|---|---|---|\n"
        text = FRONTMATTER + COMPONENTS + "## Interfaces\n\n" + head
        reordered = run(text + "| S:L1 | me | cron | csv | rows | Store | Ingest |\n")
        self.assertEqual(reordered.returncode, 0, reordered.stderr)
        self.assertEqual(reordered.stdout, canonical.stdout)


    def test_misnamed_producer_column_exits_1(self):
        head = "| From | Consumer | Flows | Format | Trigger | Owner |\n|---|---|---|---|---|---|\n"
        proc = run(FRONTMATTER + COMPONENTS + head + "| Ingest | Store | rows | csv | cron | me |\n")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("producer", proc.stderr)
        self.assertIn("line 17", proc.stderr)

    def test_misnamed_component_column_exits_1(self):
        components = "| Name | Kind | Notes |\n|---|---|---|\n| Ingest |  | pulls |\n\n"
        proc = run(doc("", components=components))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("component", proc.stderr)
        self.assertIn("line 8", proc.stderr)

    def test_missing_interfaces_table_exits_1(self):
        proc = run(FRONTMATTER + COMPONENTS)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("Interfaces", proc.stderr)
        self.assertIn("producer", proc.stderr)

    def test_unrelated_table_is_ignored(self):
        extra = "| Fruit | Colour |\n|---|---|\n| apple | red |\n\n"
        proc = run(doc("| Ingest | Store | rows | csv | cron | me | S:L1 |\n", components=COMPONENTS + extra))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("apple", proc.stdout)
        self.assertNotIn("warning", proc.stderr)

    def test_header_only_tables_are_valid(self):
        proc = run(doc("", components="| Component | Kind | Notes |\n|---|---|---|\n\n"))
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_doubled_backslash_keeps_delimiter(self):
        # `C:\\| csv` is the cell `C:\` followed by the delimiter and the cell `csv`.
        proc = run(doc(
            "| Ingest | Store | C:\\\\| csv | cron | me |  |\n"
            "| ? | Store | C:\\\\| csv | cron | me |  |\n"
        ))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("specified interfaces: 1", proc.stdout)
        self.assertIn("interfaces with gaps: 0", proc.stdout)
        cands = proc.stdout.split("## 2.")[1].split("## 3.")[0]
        self.assertIn("| line 22 | ? | Store | C:\\ |", cands)

    def test_orphan_row_warns_and_exits_0(self):
        proc = run(doc(
            "| Ingest | Store | rows | csv | cron | me | S:L1 |\n"
            "\n"
            "| Scorer | Store | scores | csv | cron | me | S:L1 |\n"
        ))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("warning: line 23: table row outside any table ignored", proc.stderr)
        self.assertIn("specified interfaces: 1", proc.stdout)

    def test_misnamed_components_table_warns_with_its_line(self):
        extra = "| Componnt | Kindd | Class | Notes | Status |\n|---|---|---|---|---|\n| Ghost | | | typo'd header | |\n\n"
        text = doc("| Ingest | Store | rows | csv | cron | me | S:L1 |\n",
                   components=COMPONENTS + extra)
        proc = run(text)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("warning: line %d:" % lineno(text, "| Componnt |"), proc.stderr)
        self.assertNotIn("Ghost", proc.stdout)
        self.assertIn("components: 4 (3 internal, 1 external)", proc.stdout)

    def test_sole_misnamed_components_table_still_exits_1(self):
        proc = run(doc("", components="| Componnt | Kindd | Class | Notes | Status |\n|---|---|---|---|---|\n| Ghost | | | x | |\n\n"))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("no Components table found", proc.stderr)

    def test_foreign_disposition_table_does_not_warn(self):
        foreign = "| Disposition | Reason |\n|---|---|\n| keep | because |\n\n"
        proc = run(doc("| Ingest | Store | rows | csv | cron | me | S:L1 |\n",
                       components=COMPONENTS + foreign))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("warning", proc.stderr)

    def test_correctly_named_tables_do_not_warn(self):
        proc = run(doc("| Ingest | Store | rows | csv | cron | me | S:L1 |\n"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("warning", proc.stderr)


class TestExternalKind(unittest.TestCase):
    """`Kind` uses check_plan's rule: first word `external`, or the token `(external)`."""

    def kind(self, value):
        components = COMPONENTS.replace("| Analyst | external | a human |",
                                        "| Analyst | %s | a human |" % value)
        proc = run(doc("", components=components))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def test_external_kinds(self):
        for value in ("actor (external)", "External", "external service", "external"):
            with self.subTest(value=value):
                self.assertIn("components: 4 (3 internal, 1 external)", self.kind(value))

    def test_internal_kinds(self):
        for value in ("externalize", "internal", "(externalish)"):
            with self.subTest(value=value):
                self.assertIn("components: 4 (4 internal, 0 external)", self.kind(value))


class TestReport(unittest.TestCase):
    def test_frontmatter_and_prose_ignored(self):
        proc = run(doc("| Ingest | Store | rows | csv | cron | me | S:L1 |\n"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("tldr", proc.stdout)
        self.assertIn("components: 4 (3 internal, 1 external)", proc.stdout)

    def test_none_is_stated_not_unstated(self):
        proc = run(doc(
            "| Ingest | Store | rows | csv | cron | me | S:L1 |\n"
            "| Ingest | Scorer | none |  |  |  |  |\n"
        ))
        self.assertIn("explicit none: 1", proc.stdout)
        self.assertNotIn("Ingest -> Scorer", proc.stdout.split("## 7.")[1])

    def test_gap_lists_missing_attributes(self):
        proc = run(doc("| Ingest | Store | rows |  | ? | me |  |\n"))
        self.assertIn("interfaces with gaps: 1", proc.stdout)
        gaps = proc.stdout.split("## 3.")[1].split("## 4.")[0]
        self.assertIn("Format", gaps)
        self.assertIn("Trigger", gaps)
        self.assertNotIn("Owner", gaps)

    def test_question_endpoint_is_missing_component_candidate(self):
        proc = run(doc(
            "| ? | Scorer | rows | csv | cron | me | S:L1 |\n"
            "| Ingest | Store | rows | csv | cron | me | S:L1 |\n"
        ))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("missing-component candidates: 1", proc.stdout)
        cands = proc.stdout.split("## 2.")[1].split("## 3.")[0]
        self.assertIn("line 21", cands)
        self.assertIn("specified interfaces: 1", proc.stdout)

    def test_self_loop_reported_separately(self):
        proc = run(doc(
            "| Ingest | Ingest | retry | csv | cron | me | S:L1 |\n"
            "| Ingest | Store | rows | csv | cron | me | S:L1 |\n"
        ))
        loops = proc.stdout.split("## 5.")[1].split("## 6.")[0]
        self.assertIn("Self-dependencies", loops)
        self.assertIn("Ingest", loops)
        self.assertIn("feedback loops: 0", proc.stdout)

    def test_two_node_loop(self):
        proc = run(doc(
            "| Store | Scorer | batches | csv | cron | me | S:L1 |\n"
            "| Scorer | Store | scores | csv | cron | me | S:L1 |\n"
            "| Ingest | Store | rows | csv | cron | me | S:L1 |\n"
        ))
        self.assertIn("feedback loops: 1", proc.stdout)
        loops = proc.stdout.split("## 5.")[1].split("## 6.")[0]
        self.assertIn("Scorer", loops)
        self.assertIn("Store", loops)

    def test_boundary_and_isolated_internal(self):
        proc = run(doc("| Ingest | Store | rows | csv | cron | me | S:L1 |\n"))
        b = proc.stdout.split("## 4.")[1].split("## 5.")[0]
        self.assertIn("Scorer", b)  # isolated internal
        self.assertIn("Store", b)  # output nothing consumes
        self.assertIn("Ingest", b)  # nothing feeds it
        self.assertNotIn("Analyst", b)  # external exempt

    def test_external_pairs_excluded_from_unstated(self):
        components = COMPONENTS + "| Vendor | external | outside |\n"
        proc = run(doc("| Ingest | Store | rows | csv | cron | me | S:L1 |\n", components=components))
        u = proc.stdout.split("## 7.")[1].split("## 8.")[0]
        self.assertNotIn("Analyst -> Vendor", u)
        self.assertNotIn("Vendor -> Analyst", u)

    def test_showing_n_of_m(self):
        proc = run(doc("| Ingest | Store | rows | csv | cron | me | S:L1 |\n"), "--sample", "2")
        u = proc.stdout.split("## 7.")[1].split("## 8.")[0]
        self.assertIn("showing 2 of ", u)
        proc_all = run(doc("| Ingest | Store | rows | csv | cron | me | S:L1 |\n"), "--sample", "0")
        u_all = proc_all.stdout.split("## 7.")[1].split("## 8.")[0]
        self.assertIn("showing 11 of 11", u_all)

    def test_matrix_legend_and_marks(self):
        proc = run(doc(
            "| Ingest | Store | rows | csv | cron | me | S:L1 |\n"
            "| Store | Scorer | batches |  | cron | me |  |\n"
            "| Ingest | Scorer | none |  |  |  |  |\n"
            "| Ingest | Ingest | retry | csv | cron | me | S:L1 |\n"
        ))
        m = proc.stdout.split("## 8.")[1]
        self.assertIn("`X` specified", m)
        self.assertIn("`g` gap", m)
        self.assertIn("`-` none", m)
        self.assertIn("`S` self", m)
        for mark in ("X", "g", "-", "S"):
            self.assertIn(" %s " % mark, m)

    def test_below_diagonal_only_inside_loops(self):
        # Store <-> Scorer is a loop; Scorer -> Store is the feedback edge.
        proc = run(doc(
            "| Ingest | Store | rows | csv | cron | me | S:L1 |\n"
            "| Store | Scorer | batches | csv | cron | me | S:L1 |\n"
            "| Scorer | Store | scores | csv | cron | me | S:L1 |\n"
            "| Store | Analyst | digest | csv | cron | me | S:L1 |\n"
        ))
        self.assertEqual(proc.returncode, 0, proc.stderr)

        loops = []
        for line in proc.stdout.split("## 5.")[1].split("## 6.")[0].splitlines():
            m = re.match(r"- loop \d+ \(\d+ members\): (.+)", line)
            if m:
                loops.append({n.strip() for n in m.group(1).split(",")})
        self.assertTrue(loops, "expected a feedback loop in this input")

        block = proc.stdout.split("## 8.")[1].split("```")[1].splitlines()
        header = block[1]
        width = len(header) - len(header.lstrip()) - 4
        order, marks = [], []
        for line in block[2:]:
            if not line.strip():
                continue
            order.append(line[4:4 + width].strip())
            rest = line[4 + width:]
            marks.append([rest[k * 3 + 1] for k in range(len(rest) // 3)])

        below = [
            (order[i], order[j])
            for i, row in enumerate(marks)
            for j, mark in enumerate(row)
            if i > j and mark not in (" ", ".")
        ]
        self.assertTrue(below, "expected at least one below-diagonal mark")
        for a, b in below:
            self.assertTrue(
                any(a in loop and b in loop for loop in loops),
                "below-diagonal mark %s -> %s lies outside a loop block" % (a, b),
            )

    def test_none_mark_below_diagonal_exits_0(self):
        # Store sorts after Ingest, so the `none` mark lands below the diagonal.
        proc = run(doc(
            "| Ingest | Store | rows | csv | cron | me | S:L1 |\n"
            "| Store | Ingest | none |  |  |  |  |\n"
        ))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("explicit none: 1", proc.stdout)

    def test_superseded_interface_is_not_a_candidate(self):
        proc = run(doc_status(
            "| ? | Scorer | rows | csv | cron | me | S:L1 | superseded 2026-09-26: replaced |\n"
            "| Ingest | Store | rows | csv | cron | me | S:L1 |  |\n"
        ))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("missing-component candidates: 0", proc.stdout)
        self.assertIn("specified interfaces: 1", proc.stdout)

    def test_superseded_component_referenced_by_active_row_exits_1(self):
        proc = run(doc_status(
            "| Ingest | Store | rows | csv | cron | me | S:L1 |  |\n",
            components=COMPONENTS_SUPERSEDED,
        ))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("Store", proc.stderr)
        self.assertIn("line 21", proc.stderr)

    def test_superseded_rows_counted(self):
        proc = run(doc_status(
            "| Ingest | Scorer | rows | csv | cron | me | S:L1 |  |\n"
            "| Ingest | Scorer | rows | csv | cron | me | S:L1 | Superseded 2026-09-26: redone |\n",
            components=COMPONENTS_SUPERSEDED,
        ))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("superseded rows: 2 (interfaces 1, components 1)", proc.stdout)
        self.assertIn("components: 3 (2 internal, 1 external)", proc.stdout)

    def test_superseded_then_active_component_of_same_name_is_allowed(self):
        proc = run(doc_status(
            "| Ingest | Store | rows | csv | cron | me | S:L1 |  |\n",
            components=COMPONENTS_REDECLARED,
        ))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("components: 4 (3 internal, 1 external)", proc.stdout)
        self.assertIn("specified interfaces: 1", proc.stdout)
        self.assertIn("superseded rows: 1 (interfaces 0, components 1)", proc.stdout)

    def test_active_then_superseded_component_of_same_name_is_allowed(self):
        components = COMPONENTS_REDECLARED.replace(
            "| Store |  | old persistence | superseded 2026-09-26: replaced |\n"
            "| Store |  | new persistence |  |\n",
            "| Store |  | new persistence |  |\n"
            "| Store |  | old persistence | superseded 2026-09-26: replaced |\n",
        )
        proc = run(doc_status(
            "| Ingest | Store | rows | csv | cron | me | S:L1 |  |\n",
            components=components,
        ))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("components: 4 (3 internal, 1 external)", proc.stdout)
        self.assertIn("specified interfaces: 1", proc.stdout)

    def test_superseded_component_rows_are_counted_not_names(self):
        components = COMPONENTS_REDECLARED.replace(
            "| Store |  | new persistence |  |\n",
            "| Store |  | older persistence | superseded 2026-09-25: replaced |\n"
            "| Store |  | new persistence |  |\n",
        )
        proc = run(doc_status("", components=components))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("superseded rows: 2 (interfaces 0, components 2)", proc.stdout)
        self.assertIn("components: 4 (3 internal, 1 external)", proc.stdout)

    def test_two_active_rows_of_one_name_exit_1_naming_both_active_lines(self):
        components = COMPONENTS_REDECLARED.replace(
            "| Store |  | old persistence | superseded 2026-09-26: replaced |\n"
            "| Store |  | new persistence |  |\n",
            "| Store |  | first persistence |  |\n"
            "| Store |  | old persistence | superseded 2026-09-26: replaced |\n"
            "| Store |  | new persistence |  |\n",
        )
        proc = run(doc_status("", components=components))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("duplicate component 'Store'", proc.stderr)
        self.assertIn("at line 16", proc.stderr)
        self.assertIn("first at line 14", proc.stderr)
        self.assertNotIn("line 15", proc.stderr)

    def test_component_with_only_superseded_rows_still_retired(self):
        components = COMPONENTS_REDECLARED.replace(
            "| Store |  | new persistence |  |\n",
            "| Store |  | older persistence | superseded 2026-09-25: replaced |\n",
        )
        proc = run(doc_status(
            "| Ingest | Store | rows | csv | cron | me | S:L1 |  |\n",
            components=components,
        ))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("superseded component 'Store'", proc.stderr)
        self.assertIn("retired at line 15", proc.stderr)

    def test_matrix_headers_stay_aligned_at_120_components(self):
        rows = "".join("| C%03d |  | filler |\n" % n for n in range(120))
        components = "| Component | Kind | Notes |\n|---|---|---|\n" + rows + "\n"
        proc = run(doc("| C000 | C001 | rows | csv | cron | me |  |\n", components=components), "--sample", "1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        block = proc.stdout.split("## 8.")[1].split("```")[1].splitlines()
        header, first = block[1], block[2]
        indent = len(header) - len(header.lstrip())
        cw = 4  # widest number is "120", plus one separating space
        self.assertEqual(len(header) - indent, 120 * cw)
        for k in range(120):
            self.assertEqual(header[indent + k * cw:indent + (k + 1) * cw], str(k + 1).ljust(cw))
        self.assertEqual(first[indent:indent + cw].strip(), ".")

    def test_deterministic_across_runs(self):
        d = doc(
            "| Store | Scorer | batches | csv | cron | me | S:L1 |\n"
            "| Scorer | Store | scores | csv | cron | me | S:L1 |\n"
            "| Ingest | Store | rows | csv | cron | me | S:L1 |\n"
            "| ? | Analyst | digest | csv | cron | me |  |\n"
        )
        self.assertEqual(run(d).stdout, run(d).stdout)


def plain_doc(internal, ext=(), rows=""):
    """Components table of bare names; external rows are silenced with `none`."""
    comps = "| Component | Kind | Notes |\n|---|---|---|\n"
    comps += "".join("| %s |  | c |\n" % n for n in internal)
    comps += "".join("| %s | external | e |\n" % n for n in ext)
    comps += "\n"
    silence = "".join(
        "| %s | %s | none |  |  |  |  |\n" % (e, i) for e in ext for i in internal
    )
    return doc(silence + rows, components=comps)


def unstated_lines(stdout):
    body = stdout.split("## 7.")[1].split("## 8.")[0]
    return [ln for ln in body.splitlines() if ln.startswith("- ")]


def partitioned_order(stdout):
    body = stdout.split("## 6.")[1].split("## 7.")[0]
    return [
        ln.split(". ", 1)[1].replace(" (loop)", "")
        for ln in body.splitlines()
        if re.match(r"^\d+\. ", ln)
    ]


class TestSampleSpread(unittest.TestCase):
    def test_every_producer_row_appears_when_sample_covers_them(self):
        # 3 internal rows, each with 6 unstated pairs; N == P == 3.
        proc = run(plain_doc(["A", "B", "C"], ["X1", "X2", "X3", "X4"]), "--sample", "3")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = unstated_lines(proc.stdout)
        self.assertEqual(len(lines), 3, lines)
        self.assertEqual(
            sorted(ln[2:].split(" -> ")[0] for ln in lines), ["A", "B", "C"]
        )

    def test_sampled_rows_spread_when_sample_below_row_count(self):
        internal = ["A%d" % n for n in range(8)]
        proc = run(
            plain_doc(internal, rows="| A0 | A1 | rows | csv | cron | me | S:L1 |\n"),
            "--sample",
            "3",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        order = partitioned_order(proc.stdout)
        picked = [ln[2:].split(" -> ")[0] for ln in unstated_lines(proc.stdout)]
        self.assertEqual(len(picked), 3, picked)
        idx = [order.index(p) for p in picked]
        # evenly spaced rows t*8//3 = 0, 2, 5 — not the first three rows
        self.assertEqual(idx, [0, 2, 5])

    def test_single_pick_rows_spread_across_columns(self):
        proc = run(
            plain_doc(
                ["A", "B", "C", "D"],
                rows="| A | B | rows | csv | cron | me | S:L1 |\n",
            ),
            "--sample",
            "4",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = unstated_lines(proc.stdout)
        self.assertEqual(
            lines,
            # partitioned order A,C,D,B (A -> B is stated); m = 2,3,3,3, q = 1 each,
            # so each row picks its consumer at position i*m_i//4
            ["- A -> C", "- C -> A", "- D -> C", "- B -> D"],
        )
        self.assertGreater(len({ln.split(" -> ")[1] for ln in lines}), 1)

    def test_sample_output_independent_of_hash_seed(self):
        text = plain_doc(
            ["A%d" % n for n in range(8)],
            ["X1", "X2"],
            rows="| A0 | A1 | rows | csv | cron | me | S:L1 |\n",
        )
        outs = []
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write(text)
            path = fh.name
        try:
            for seed in ("0", "1", "4242", "random"):
                env = dict(os.environ, PYTHONHASHSEED=seed)
                proc = subprocess.run(
                    [sys.executable, SCRIPT, path, "--sample", "7"],
                    capture_output=True,
                    text=True,
                    env=env,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                outs.append(proc.stdout)
        finally:
            os.unlink(path)
        self.assertEqual(len(set(outs)), 1)


COMPONENTS_CLASS = """## Components

| Component | Kind | Notes | Class |
|---|---|---|---|
| Ingest |  | pulls raw events | ING |
| Scorer |  | ranks events | AGT |
| Store |  | persistence | ING |
| Analyst | external | a human | HUM |

"""

RULES_HEAD = "| Producer class | Consumer class | Disposition | Reason |\n|---|---|---|---|\n"
RULES_HEAD_STATUS = (
    "| Producer class | Consumer class | Disposition | Reason | Status |\n"
    "|---|---|---|---|---|\n"
)


def doc_rules(interface_rows, rule_rows, head=RULES_HEAD, components=COMPONENTS_CLASS):
    return doc(interface_rows, components=components) + "\n## Rules\n\n" + head + rule_rows


def lineno(text, needle):
    for n, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return n
    raise AssertionError("not in text: %s" % needle)


IFACE = "| Ingest | Store | rows | csv | cron | me | S:L1 |\n"


class TestClassRules(unittest.TestCase):
    def test_none_rule_removes_pairs_and_reports_the_count(self):
        proc = run(doc_rules(IFACE, "| ING | AGT | none | ingest never feeds agents |\n"), "--sample", "0")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        pairs = proc.stdout.split("## 7.")[1].split("## 8.")[0]
        self.assertNotIn("Ingest -> Scorer", pairs)
        self.assertNotIn("Store -> Scorer", pairs)
        rules = proc.stdout.split("## 9.")[1]
        self.assertIn("| ING | AGT | none | 2 |", rules)
        self.assertIn("none by rule: 2", rules)

    def test_review_rule_wins_over_none(self):
        proc = run(doc_rules(
            IFACE,
            "| ING | AGT | none | ingest never feeds agents |\n"
            "| ING | * | review | look at these anyway |\n",
        ), "--sample", "0")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        pairs = proc.stdout.split("## 7.")[1].split("## 8.")[0]
        self.assertIn("- Ingest -> Scorer", pairs)

    def test_overridden_wildcard_none_shows_settled_below_matched(self):
        text = doc_rules(
            IFACE,
            "| * | * | none | everything is settled |\n"
            "| ING | AGT | review | except ingest into agents |\n",
        )
        proc = run(text, "--sample", "0")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rules = proc.stdout.split("## 9.")[1]
        wild = [ln for ln in rules.splitlines() if ln.startswith("| line %d |" % lineno(text, "| * | * |"))][0]
        # 11 unstated pairs match the wildcard, 2 of them (Ingest/Store -> Scorer) are
        # overridden to review, so the wildcard settled 9 of the 11 it matched
        self.assertIn("| none | 9 | 11 |", wild)
        review = [ln for ln in rules.splitlines() if ln.startswith("| line %d |" % lineno(text, "| ING | AGT |"))][0]
        self.assertIn("| review | 0 | 2 |", review)
        self.assertIn("none by rule: 9", rules)

    def test_dead_rule_is_reported(self):
        text = doc_rules(IFACE, "| HUM | HUM | none | humans do not talk to humans |\n")
        proc = run(text, "--sample", "0")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rules = proc.stdout.split("## 9.")[1]
        self.assertIn("dead rules", rules)
        self.assertIn("line %d" % lineno(text, "| HUM | HUM |"), rules)

    def test_none_rule_matching_an_explicit_interface_is_listed(self):
        text = doc_rules(IFACE, "| ING | ING | none | storage is not chatty |\n")
        proc = run(text, "--sample", "0")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        conflicts = proc.stdout.split("## 9.")[1].split("explicit interface")[1]
        self.assertIn("| Ingest | Store |", conflicts)

    def test_unknown_disposition_exits_1_with_the_line(self):
        text = doc_rules(IFACE, "| ING | AGT | maybe | unsure |\n")
        proc = run(text)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("maybe", proc.stderr)
        self.assertIn("line %d" % lineno(text, "maybe"), proc.stderr)

    def test_rule_naming_an_unknown_class_exits_1_with_the_line(self):
        text = doc_rules(IFACE, "| NOPE | AGT | none | typo |\n")
        proc = run(text)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("NOPE", proc.stderr)
        self.assertIn("line %d" % lineno(text, "NOPE"), proc.stderr)

    def test_superseded_rule_row_is_inert(self):
        proc = run(doc_rules(
            IFACE,
            "| ING | AGT | none | retired | superseded 2026-09-26: wrong |\n",
            head=RULES_HEAD_STATUS,
        ), "--sample", "0")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("- Ingest -> Scorer", proc.stdout.split("## 7.")[1].split("## 8.")[0])
        self.assertIn("No active rules", proc.stdout.split("## 9.")[1])

    def test_no_rules_table_means_no_rules_section(self):
        proc = run(doc(IFACE))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("## 9.", proc.stdout)

    def test_foreign_disposition_table_is_not_the_rules_table(self):
        plain = run(doc(IFACE))
        self.assertEqual(plain.returncode, 0, plain.stderr)
        foreign = "\n## Someone else's notes\n\n| Disposition | Reason |\n|---|---|\n| keep | because |\n"
        proc = run(doc(IFACE) + foreign)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, plain.stdout)
        self.assertNotIn("## 9.", proc.stdout)

    def test_foreign_half_class_table_is_not_the_rules_table(self):
        plain = run(doc(IFACE))
        self.assertEqual(plain.returncode, 0, plain.stderr)
        foreign = "\n## Someone else's notes\n\n| Producer class | Reason |\n|---|---|\n| ING | because |\n"
        proc = run(doc(IFACE) + foreign)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, plain.stdout)
        self.assertNotIn("## 9.", proc.stdout)

    def test_empty_rules_table_still_prints_the_section(self):
        components = COMPONENTS_CLASS.replace("| persistence | ING |", "| persistence |  |")
        proc = run(doc_rules(IFACE, "", components=components), "--sample", "0")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rules = proc.stdout.split("## 9.")[1]
        self.assertIn("No active rules", rules)
        self.assertIn("Store", rules.split("unclassed")[1].splitlines()[0])

    def test_wildcard_skips_unclassed_components_and_names_them(self):
        components = COMPONENTS_CLASS.replace("| persistence | ING |", "| persistence |  |")
        text = doc_rules(IFACE, "| * | * | none | everything is settled |\n", components=components)
        proc = run(text, "--sample", "0")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        pairs = proc.stdout.split("## 7.")[1].split("## 8.")[0]
        self.assertIn("- Store -> Scorer", pairs)
        self.assertIn("- Scorer -> Store", pairs)
        self.assertNotIn("- Ingest -> Scorer", pairs)
        rules = proc.stdout.split("## 9.")[1]
        self.assertIn("unclassed", rules)
        self.assertIn("Store", rules.split("unclassed")[1].splitlines()[0])


ACTIVE_IFACE = "| Ingest | Scorer | rows | csv | cron | me | S:L1 |  |\n"

SOURCE = "alpha line\nbeta line\ngamma line\ndelta line\n\nzeta line\n"


def run_source(text, source_text, *args):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write(source_text)
        src = fh.name
    try:
        return run(text, "--source", src, *args)
    finally:
        os.unlink(src)


class TestSourceCoverage(unittest.TestCase):
    def test_uncited_spans_and_counts(self):
        proc = run_source(doc("| Ingest | Store | rows | csv | cron | me | S:L1,3-4 |\n"), SOURCE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        cov = proc.stdout.split("## 10.")[1]
        self.assertIn("6 lines", cov)
        self.assertIn("3 cited", cov)
        self.assertIn("2 uncited", cov)
        self.assertIn("| L2 | beta line |", cov)
        self.assertIn("| L6 | zeta line |", cov)

    def test_blank_lines_do_not_split_a_span(self):
        proc = run_source(doc("| Ingest | Store | rows | csv | cron | me | S:L1 |\n"), SOURCE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        cov = proc.stdout.split("## 10.")[1]
        self.assertIn("| L2-6 | beta line |", cov)

    def test_first_80_characters_only(self):
        long_line = "x" * 200 + "\n"
        proc = run_source(doc("| Ingest | Store | rows | csv | cron | me | S:L2 |\n"), long_line + "cited\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        cov = proc.stdout.split("## 10.")[1]
        self.assertIn("| L1 | %s |" % ("x" * 80), cov)
        self.assertNotIn("x" * 81, cov)

    def test_citation_past_the_last_line_exits_1(self):
        proc = run_source(doc("| Ingest | Store | rows | csv | cron | me | S:L99 |\n"), SOURCE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("L99", proc.stderr)

    def test_superseded_row_citations_do_not_count_as_cited(self):
        proc = run_source(doc_status(
            "| Ingest | Store | rows | csv | cron | me | S:L1 |  |\n"
            "| Ingest | Scorer | rows | csv | cron | me | S:L2 | superseded 2026-09-26: gone |\n"
        ), SOURCE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        cov = proc.stdout.split("## 10.")[1]
        self.assertIn("| L2-6 | beta line |", cov)

    def test_superseded_interface_citation_past_eof_exits_1(self):
        # a superseded row covers nothing, but its citations are still range-checked
        text = doc_status(
            "| Ingest | Store | rows | csv | cron | me | S:L1 |  |\n"
            "| Ingest | Scorer | rows | csv | cron | me | S:L99 | superseded 2026-09-26: gone |\n"
        )
        proc = run_source(text, SOURCE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("L99", proc.stderr)
        self.assertIn("line %d" % lineno(text, "S:L99"), proc.stderr)

    def test_superseded_interface_citation_l0_exits_1(self):
        text = doc_status(
            "| Ingest | Scorer | rows | csv | cron | me | S:L0 | superseded 2026-09-26: gone |\n"
        )
        proc = run_source(text, SOURCE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("start at 1", proc.stderr)
        self.assertIn("line %d" % lineno(text, "S:L0"), proc.stderr)

    def test_superseded_interface_reversed_range_exits_1(self):
        text = doc_status(
            "| Ingest | Scorer | rows | csv | cron | me | S:L9-7 | superseded 2026-09-26: gone |\n"
        )
        proc = run_source(text, SOURCE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("L9-7", proc.stderr)
        self.assertIn("line %d" % lineno(text, "S:L9-7"), proc.stderr)

    def test_superseded_component_citation_past_eof_exits_1(self):
        components = COMPONENTS_SUPERSEDED.replace("| persistence |", "| persistence (S:L99) |")
        text = doc_status(ACTIVE_IFACE, components=components)
        proc = run_source(text, SOURCE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("L99", proc.stderr)
        self.assertIn("line %d" % lineno(text, "S:L99"), proc.stderr)

    def test_superseded_component_citation_l0_exits_1(self):
        components = COMPONENTS_SUPERSEDED.replace("| persistence |", "| persistence (S:L0) |")
        text = doc_status(ACTIVE_IFACE, components=components)
        proc = run_source(text, SOURCE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("start at 1", proc.stderr)
        self.assertIn("line %d" % lineno(text, "S:L0"), proc.stderr)

    def test_superseded_component_reversed_range_exits_1(self):
        components = COMPONENTS_SUPERSEDED.replace("| persistence |", "| persistence (S:L9-7) |")
        text = doc_status(ACTIVE_IFACE, components=components)
        proc = run_source(text, SOURCE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("L9-7", proc.stderr)
        self.assertIn("line %d" % lineno(text, "S:L9-7"), proc.stderr)

    def test_valid_superseded_component_citation_leaves_the_line_uncited(self):
        components = COMPONENTS_SUPERSEDED.replace("| persistence |", "| persistence (S:L3) |")
        proc = run_source(doc_status(ACTIVE_IFACE, components=components), SOURCE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        cov = proc.stdout.split("## 10.")[1]
        self.assertIn("1 cited", cov)
        self.assertIn("| L2-6 | beta line |", cov)

    def test_component_cells_are_scanned_but_rule_reasons_are_not(self):
        # a rule's Reason justifies the rule; nothing models the line it cites, so L6
        # stays uncited
        components = COMPONENTS_CLASS.replace("| pulls raw events | ING |", "| pulls raw events (S:L2) | ING |")
        proc = run_source(
            doc_rules("| Ingest | Store | rows | csv | cron | me | S:L1 |\n",
                      "| ING | AGT | none | see L6 |\n", components=components),
            SOURCE,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        cov = proc.stdout.split("## 10.")[1]
        self.assertIn("2 cited", cov)
        self.assertIn("3 uncited", cov)
        self.assertIn("| L3-6 | gamma line |", cov)

    def test_rule_reason_citation_past_eof_exits_1(self):
        # a Rules citation covers nothing, but it is still range-checked: a Reason
        # pointing past the source is a wrong citation, not a free pass
        text = doc_rules(IFACE, "| ING | AGT | none | see L99 |\n")
        proc = run_source(text, SOURCE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("L99", proc.stderr)
        self.assertIn("line %d" % lineno(text, "see L99"), proc.stderr)

    def test_rule_reason_citation_l0_exits_1(self):
        text = doc_rules(IFACE, "| ING | AGT | none | see L0 |\n")
        proc = run_source(text, SOURCE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("start at 1", proc.stderr)
        self.assertIn("line %d" % lineno(text, "see L0"), proc.stderr)

    def test_reversed_range_exits_1_with_the_row_line(self):
        text = doc("| Ingest | Store | rows | csv | cron | me | S:L9-7 |\n")
        proc = run_source(text, SOURCE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("L9-7", proc.stderr)
        self.assertIn("line %d" % lineno(text, "S:L9-7"), proc.stderr)

    def test_citation_l0_says_line_numbers_start_at_1(self):
        proc = run_source(doc("| Ingest | Store | rows | csv | cron | me | S:L0 |\n"), SOURCE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("L0", proc.stderr)
        self.assertIn("start at 1", proc.stderr)
        self.assertNotIn("beyond", proc.stderr)

    def test_no_source_flag_means_no_coverage_section(self):
        proc = run(doc(IFACE))
        self.assertNotIn("## 10.", proc.stdout)

    def test_report_survives_a_non_utf8_console(self):
        # Windows consoles default to legacy codepages (cp437 has no em-dash) and
        # pipes can be ASCII; the script must reconfigure stdout to UTF-8 rather
        # than crash mid-report with UnicodeEncodeError. The em-dash lives in the
        # --source coverage section, so this drives that path (fails without the
        # reconfigure in main()).
        src = os.path.join(tempfile.mkdtemp(), "inventory.md")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(doc(IFACE) + "\nsome uncited prose below the tables\n")
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import sys, io, os, runpy\n"
                    'sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="cp437",'
                    ' errors="strict")\n'
                    'script = os.path.abspath(sys.argv[1])\n'
                    'sys.argv = ["interface_matrix.py", sys.argv[2],'
                    ' "--source", sys.argv[2]]\n'
                    'runpy.run_path(script, run_name="__main__")\n',
                    SCRIPT,
                    src,
                ],
                capture_output=True,
                text=True,
            )
        finally:
            os.unlink(src)
            os.rmdir(os.path.dirname(src))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Nothing cites these spans", proc.stdout)
        self.assertNotIn("UnicodeEncodeError", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
