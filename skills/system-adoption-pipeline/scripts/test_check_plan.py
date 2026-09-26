#!/usr/bin/env python3
"""Self-check for check_plan.py. Run: python3 scripts/test_check_plan.py"""

import io
import os
import contextlib
import tempfile
import unittest

import check_plan

INVENTORY = """## Components

| Id | Type | Purpose | Source |
|---|---|---|---|
| C1 | agent | scores leads | S:L4 |
| C2 | store | keeps records | S:L9 |
"""

INTERFACES = """## Interfaces

| Id | Producer | Consumer | Flows | Format | Trigger | Owner | Source |
|---|---|---|---|---|---|---|---|
| IF1 | C2 | C1 | records | ndjson | nightly | ops | S:L9 |
"""

GAPS = """## Gap register

| Id | Gap | Class | Disposition | Status |
|---|---|---|---|---|
| G1 | which account | USER | ask the adopter | open |
| G2 | file format | DEFAULT | ndjson; revisit if volume grows | resolved |
"""

PACKAGES = """## Packages

| WP | Name | Components | Owner | Inputs | Outputs | Dependencies | Acceptance |
|---|---|---|---|---|---|---|---|
| WP1 | Store | C2 | ops | exports | records | none | records land |
| WP2 | Scorer | C1 | ops | records | scores | WP1 | scores land |
"""

ORDERING = """## Waves

| Wave | Packages | Detail |
|---|---|---|
| 1 | WP1, WP2 | atomic steps |

## Wave 1 steps

| Step | Wave | Action | Components | Interfaces | Gaps | Blocked | Acceptance |
|---|---|---|---|---|---|---|---|
| S1 | 1 | Create the store | C2 | IF1 |  | no | folder exists |
| S2 | 1 | Run the scorer once | C1 | IF1 | G2 | no | one score written |
"""


def write(tmp, name, text):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


class CheckPlanTests(unittest.TestCase):
    def run_plan(self, **overrides):
        files = dict(inventory=INVENTORY, interfaces=INTERFACES, gaps=GAPS,
                     packages=PACKAGES, ordering=ORDERING)
        files.update(overrides)
        with tempfile.TemporaryDirectory() as tmp:
            argv = []
            for key, text in files.items():
                argv += ["--%s" % key, write(tmp, "%s.md" % key, text)]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = check_plan.main(argv)
            return code, out.getvalue()

    # --- the happy path
    def test_clean_plan_passes(self):
        code, out = self.run_plan()
        self.assertEqual(code, 0, out)
        self.assertNotIn("FAIL", out)

    def test_counts_line_reports_totals(self):
        _, out = self.run_plan()
        self.assertIn("components 2", out)
        self.assertIn("interfaces 1", out)
        self.assertIn("packages 2", out)
        self.assertIn("wave-1 steps 2", out)
        self.assertIn("USER 1", out)

    # --- check 1
    def test_component_in_no_package_or_step_fails(self):
        inv = INVENTORY + "| C3 | store | orphan | S:L20 |\n"
        code, out = self.run_plan(inventory=inv)
        self.assertEqual(code, 1)
        self.assertIn("check 1 component coverage: FAIL", out)
        self.assertIn("C3", out)

    def test_component_covered_by_step_only_passes(self):
        inv = INVENTORY + "| C3 | store | step only | S:L20 |\n"
        ordering = ORDERING + "| S3 | 1 | Create C3 | C3 |  |  | no | exists |\n"
        code, out = self.run_plan(inventory=inv, ordering=ordering)
        self.assertEqual(code, 0, out)

    def test_package_naming_unknown_component_fails(self):
        pkgs = PACKAGES + "| WP3 | Ghost | C9 | ops | x | y | none | z |\n"
        code, out = self.run_plan(packages=pkgs)
        self.assertEqual(code, 1)
        self.assertIn("unknown id C9", out)

    # --- check 2
    def test_interface_endpoint_not_built_fails(self):
        inv = INVENTORY + "| C4 | store | unbuilt | S:L30 |\n"
        ifaces = INTERFACES + "| IF2 | C1 | C4 | scores | csv | daily | ops | S:L30 |\n"
        code, out = self.run_plan(inventory=inv, interfaces=ifaces)
        self.assertEqual(code, 1)
        self.assertIn("check 2 interface endpoints: FAIL", out)
        self.assertIn("IF2: consumer C4", out)

    def test_interface_with_unknown_endpoint_marker_fails(self):
        ifaces = INTERFACES + "| IF2 | ? | C1 | digest | ? | ? | ? |  |\n"
        code, out = self.run_plan(interfaces=ifaces)
        self.assertEqual(code, 1)
        self.assertIn("IF2 has no producer", out)

    def test_step_covered_interface_count_reported(self):
        _, out = self.run_plan()
        self.assertIn("1 of 1 interfaces have both endpoints built", out)
        self.assertNotIn("by named steps", out)

    def test_check_2_count_is_never_negative(self):
        ifaces = INTERFACES.replace("| IF1 | C2 | C1 |", "| IF1 | ? | C9 |")
        code, out = self.run_plan(interfaces=ifaces)
        self.assertEqual(code, 1, out)
        self.assertIn("check 2 interface endpoints: FAIL", out)
        self.assertIn("0 of 1 interfaces have both endpoints built", out)

    # --- check 3
    def test_wave1_step_without_acceptance_fails(self):
        ordering = ORDERING + "| S3 | 1 | Do a thing | C1 |  |  | no |  |\n"
        code, out = self.run_plan(ordering=ordering)
        self.assertEqual(code, 1)
        self.assertIn("check 3 wave-1 acceptance: FAIL", out)
        self.assertIn("step S3", out)

    def test_later_wave_step_without_acceptance_is_ignored(self):
        ordering = ORDERING + "| S9 | 3 | Later package work | C1 |  |  | no |  |\n"
        code, out = self.run_plan(ordering=ordering)
        self.assertEqual(code, 0, out)

    # --- check 4
    def test_wave1_step_on_open_user_gap_needs_blocked(self):
        ordering = ORDERING + "| S3 | 1 | Open the account | C1 |  | G1 | no | account exists |\n"
        code, out = self.run_plan(ordering=ordering)
        self.assertEqual(code, 1)
        self.assertIn("check 4 wave-1 user gaps: FAIL", out)
        self.assertIn("G1", out)

    def test_blocked_label_clears_check_4(self):
        ordering = ORDERING + "| S3 | 1 | Open the account | C1 |  | G1 | yes | account exists |\n"
        code, out = self.run_plan(ordering=ordering)
        self.assertEqual(code, 0, out)

    def test_resolved_user_gap_does_not_block(self):
        gaps = GAPS.replace("| G1 | which account | USER | ask the adopter | open |",
                            "| G1 | which account | USER | ask the adopter | resolved |")
        ordering = ORDERING + "| S3 | 1 | Open the account | C1 |  | G1 | no | account exists |\n"
        code, out = self.run_plan(gaps=gaps, ordering=ordering)
        self.assertEqual(code, 0, out)

    # --- check 5
    def test_eleven_user_questions_fail(self):
        extra = "".join("| U%d | q%d | USER | ask | open |\n" % (i, i) for i in range(2, 13))
        code, out = self.run_plan(gaps=GAPS + extra)
        self.assertEqual(code, 1)
        self.assertIn("check 5 user question budget: FAIL", out)
        self.assertIn("12 USER question(s), limit 10", out)

    def test_ten_user_questions_pass(self):
        extra = "".join("| U%d | q%d | USER | ask | open |\n" % (i, i) for i in range(2, 11))
        code, out = self.run_plan(gaps=GAPS + extra)
        self.assertEqual(code, 0, out)

    def test_eleven_rows_of_one_user_id_pass(self):
        # One restated question is one question: the budget counts distinct ids.
        extra = "".join("| G1 | which account, restated %d | USER | ask | open |\n" % i
                        for i in range(1, 11))
        code, out = self.run_plan(gaps=GAPS + extra)
        self.assertEqual(code, 0, out)
        self.assertIn("1 USER question(s), limit 10", out)

    def test_twelve_blank_id_user_rows_fail(self):
        # A blank Id cannot be deduplicated: each such row is its own question.
        extra = "".join("|  | q%d | USER | ask | open |\n" % i for i in range(1, 13))
        code, out = self.run_plan(gaps=GAPS + extra)
        self.assertEqual(code, 1, out)
        self.assertIn("check 5 user question budget: FAIL", out)
        self.assertIn("13 USER question(s), limit 10", out)

    def test_ten_blank_id_user_rows_pass(self):
        extra = "".join("|  | q%d | USER | ask | open |\n" % i for i in range(1, 10))
        code, out = self.run_plan(gaps=GAPS + extra)
        self.assertEqual(code, 0, out)
        self.assertIn("10 USER question(s), limit 10", out)

    def test_blank_and_repeated_ids_counted_together(self):
        # G1 restated twice is one question; two blank-id rows are two more.
        extra = ("| G1 | which account, restated | USER | ask | open |\n"
                 "| G1 | which account, again | USER | ask | open |\n"
                 "|  | q a | USER | ask | open |\n"
                 "|  | q b | USER | ask | open |\n")
        code, out = self.run_plan(gaps=GAPS + extra)
        self.assertEqual(code, 0, out)
        self.assertIn("3 USER question(s), limit 10", out)

    # --- check 2, built by steps
    def test_packages_without_wave1_steps_fail_check_2(self):
        ordering = """## Wave 1 steps

| Step | Wave | Action | Components | Interfaces | Gaps | Blocked | Acceptance |
|---|---|---|---|---|---|---|---|
| S9 | 2 | Later work | C1 C2 |  |  | no | later |
"""
        code, out = self.run_plan(ordering=ordering)
        self.assertEqual(code, 1, out)
        self.assertIn("check 2 interface endpoints: FAIL", out)

    def test_comma_list_endpoint_is_parsed_as_ids(self):
        ifaces = INTERFACES.replace("| IF1 | C2 | C1 |", "| IF1 | C2, C1 | C1 |")
        code, out = self.run_plan(interfaces=ifaces)
        self.assertEqual(code, 0, out)

    def test_external_component_is_exempt_from_checks_1_and_2(self):
        inv = INVENTORY + "| H1 | actor (external) | a human | S:L60 |\n"
        ifaces = INTERFACES + "| IF2 | C1 | H1 | digest | md | weekly | ops | S:L60 |\n"
        code, out = self.run_plan(inventory=inv, interfaces=ifaces)
        self.assertEqual(code, 0, out)

    def test_external_facing_type_is_not_exempt(self):
        inv = INVENTORY + "| C5 | external-facing gateway | fronts the api | S:L70 |\n"
        code, out = self.run_plan(inventory=inv)
        self.assertEqual(code, 1, out)
        self.assertIn("component C5 is in no package and no step", out)

    def test_external_system_type_is_exempt(self):
        inv = INVENTORY + "| X1 | External system | someone else's crm | S:L80 |\n"
        code, out = self.run_plan(inventory=inv)
        self.assertEqual(code, 0, out)
        self.assertIn("1 external exempt", out)

    def test_external_token_rule(self):
        exempt = ["external", "External system", "actor (external)", "EXTERNAL API"]
        internal = ["non-external store", "internal/external bridge",
                    "external-facing gateway", "externally reached"]
        for kind in exempt:
            with self.subTest(type=kind):
                inv = INVENTORY + "| X9 | %s | outside the boundary | S:L90 |\n" % kind
                code, out = self.run_plan(inventory=inv)
                self.assertEqual(code, 0, out)
                self.assertIn("1 external exempt", out)
        for kind in internal:
            with self.subTest(type=kind):
                inv = INVENTORY + "| X9 | %s | ours to build | S:L90 |\n" % kind
                code, out = self.run_plan(inventory=inv)
                self.assertEqual(code, 1, out)
                self.assertIn("component X9 is in no package and no step", out)

    def test_duplicate_inventory_id_is_counted_once(self):
        inv = INVENTORY + "| C2 | store | the same store, restated | S:L9 |\n"
        code, out = self.run_plan(inventory=inv)
        self.assertEqual(code, 0, out)
        self.assertIn("components 2", out)
        self.assertIn("2 of 2 non-external components", out)

    def test_id_with_one_internal_row_is_not_exempt(self):
        inv = (INVENTORY + "| X1 | External system | someone else's crm | S:L80 |\n"
                           "| X1 | store | and ours to build | S:L81 |\n")
        code, out = self.run_plan(inventory=inv)
        self.assertEqual(code, 1, out)
        self.assertIn("component X1 is in no package and no step", out)

    def test_duplicate_wp_keeps_first_row_unknown_id(self):
        pkgs = (PACKAGES + "| WP3 | Ghost | C9 | ops | x | y | none | z |\n"
                           "| WP3 | Ghost restated | C1 | ops | x | y | none | z |\n")
        code, out = self.run_plan(packages=pkgs)
        self.assertEqual(code, 1, out)
        self.assertIn("unknown id C9", out)

    def test_duplicate_wp_keeps_first_row_coverage(self):
        inv = INVENTORY + "| C3 | store | covered by a restated WP | S:L20 |\n"
        pkgs = (PACKAGES + "| WP3 | Extra | C3 | ops | x | y | none | z |\n"
                           "| WP3 | Extra restated | C1 | ops | x | y | none | z |\n")
        code, out = self.run_plan(inventory=inv, packages=pkgs)
        self.assertEqual(code, 0, out)

    def test_duplicate_step_keeps_first_row_unknown_id(self):
        ordering = (ORDERING + "| S3 | 1 | Ghost | C9 |  |  | no | exists |\n"
                               "| S3 | 1 | Ghost restated | C1 |  |  | no | exists |\n")
        code, out = self.run_plan(ordering=ordering)
        self.assertEqual(code, 1, out)
        self.assertIn("unknown id C9", out)

    def test_duplicate_step_keeps_first_row_coverage(self):
        inv = INVENTORY + "| C3 | store | covered by a restated step | S:L20 |\n"
        ordering = (ORDERING + "| S3 | 1 | Create C3 | C3 |  |  | no | exists |\n"
                               "| S3 | 1 | Create C3 restated | C1 |  |  | no | exists |\n")
        code, out = self.run_plan(inventory=inv, ordering=ordering)
        self.assertEqual(code, 0, out)

    def test_duplicate_wp_counted_once_in_counts(self):
        pkgs = PACKAGES + "| WP2 | Scorer restated | C1 | ops | x | y | none | z |\n"
        code, out = self.run_plan(packages=pkgs)
        self.assertEqual(code, 0, out)
        self.assertIn("packages 2", out)

    def test_duplicate_wp_second_row_unknown_id(self):
        pkgs = (PACKAGES + "| WP3 | Ghost | C1 | ops | x | y | none | z |\n"
                           "| WP3 | Ghost restated | C9 | ops | x | y | none | z |\n")
        code, out = self.run_plan(packages=pkgs)
        self.assertEqual(code, 1, out)
        self.assertIn("unknown id C9", out)

    def test_duplicate_wp_second_row_coverage(self):
        inv = INVENTORY + "| C3 | store | covered by a restated WP | S:L20 |\n"
        pkgs = (PACKAGES + "| WP3 | Extra | C1 | ops | x | y | none | z |\n"
                           "| WP3 | Extra restated | C3 | ops | x | y | none | z |\n")
        code, out = self.run_plan(inventory=inv, packages=pkgs)
        self.assertEqual(code, 0, out)

    def test_duplicate_step_second_row_unknown_id(self):
        ordering = (ORDERING + "| S3 | 1 | Ghost | C1 |  |  | no | exists |\n"
                               "| S3 | 1 | Ghost restated | C9 |  |  | no | exists |\n")
        code, out = self.run_plan(ordering=ordering)
        self.assertEqual(code, 1, out)
        self.assertIn("unknown id C9", out)

    def test_duplicate_step_second_row_coverage(self):
        inv = INVENTORY + "| C3 | store | covered by a restated step | S:L20 |\n"
        ordering = (ORDERING + "| S3 | 1 | Create C1 | C1 |  |  | no | exists |\n"
                               "| S3 | 1 | Create C3 | C3 |  |  | no | exists |\n")
        code, out = self.run_plan(inventory=inv, ordering=ordering)
        self.assertEqual(code, 0, out)

    def test_id_with_internal_first_row_is_not_exempt(self):
        inv = (INVENTORY + "| X1 | store | ours to build | S:L80 |\n"
                           "| X1 | External system | restated as external | S:L81 |\n")
        code, out = self.run_plan(inventory=inv)
        self.assertEqual(code, 1, out)
        self.assertIn("component X1 is in no package and no step", out)

    def test_wave_label_with_word_wave_counts_as_wave_1(self):
        ordering = ORDERING.replace("| S1 | 1 |", "| S1 | Wave 1 |")
        code, out = self.run_plan(ordering=ordering)
        self.assertEqual(code, 0, out)
        self.assertIn("wave-1 steps 2", out)

    # --- check 3
    def test_none_and_tbd_acceptance_fail(self):
        ordering = ORDERING + "| S3 | 1 | A thing | C1 |  |  | no | None |\n" \
                              "| S4 | 1 | Another | C1 |  |  | no | tbd |\n"
        code, out = self.run_plan(ordering=ordering)
        self.assertEqual(code, 1, out)
        self.assertIn("step S3 has no acceptance check", out)
        self.assertIn("step S4 has no acceptance check", out)

    def test_plan_with_no_wave1_step_fails_check_3(self):
        ordering = """## Wave 1 steps

| Step | Wave | Action | Components | Interfaces | Gaps | Blocked | Acceptance |
|---|---|---|---|---|---|---|---|
| S9 | 2 | Later work | C1 C2 |  |  | no | later |
"""
        code, out = self.run_plan(ordering=ordering)
        self.assertEqual(code, 1, out)
        self.assertIn("check 3 wave-1 acceptance: FAIL", out)
        self.assertIn("no wave-1 step", out)

    # --- the shipped templates
    def test_shipped_templates_pass(self):
        here = os.path.dirname(os.path.abspath(__file__))
        tpl = os.path.join(os.path.dirname(here), "assets", "templates")
        argv = ["--inventory", os.path.join(tpl, "01-inventory.md"),
                "--interfaces", os.path.join(tpl, "03-interfaces.md"),
                "--gaps", os.path.join(tpl, "04-gap-register.md"),
                "--packages", os.path.join(tpl, "05-work-packages.md"),
                "--ordering", os.path.join(tpl, "06-ordering.md")]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = check_plan.main(argv)
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("2 of 2 non-external components appear in a package or step; "
                      "1 external exempt", out.getvalue())

    # --- parsing
    def test_missing_table_exits_2(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as ctx:
            self.run_plan(packages="# no tables here\n")
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("no work package table", err.getvalue())

    def test_missing_file_exits_2(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as ctx:
            check_plan.read_table("/nonexistent/nope.md", ["id"], "component inventory")
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("cannot read", err.getvalue())

    def test_escaped_pipe_stays_in_cell(self):
        ordering = ORDERING.replace("one score written", r"score \| audit line present")
        code, out = self.run_plan(ordering=ordering)
        self.assertEqual(code, 0, out)

    def test_columns_may_be_reordered_and_recased(self):
        pkgs = """| Components | WP | Owner |
|---|---|---|
| C1 C2 | WP1 | ops |
"""
        code, out = self.run_plan(packages=pkgs)
        self.assertEqual(code, 0, out)

    # --- one predicate for "is this a real id"
    def test_twelve_placeholder_id_user_rows_fail(self):
        # `-`, `?`, `none` and `TBD` are not ids: each such row is its own question.
        marks = ["-", "?", "none", "TBD"]
        extra = "".join("| %s | q%d | USER | ask | open |\n" % (marks[i % 4], i)
                        for i in range(1, 13))
        code, out = self.run_plan(gaps=GAPS + extra)
        self.assertEqual(code, 1, out)
        self.assertIn("check 5 user question budget: FAIL", out)
        self.assertIn("13 USER question(s), limit 10", out)

    def test_ten_placeholder_id_user_rows_pass(self):
        marks = ["-", "?", "none", "TBD"]
        extra = "".join("| %s | q%d | USER | ask | open |\n" % (marks[i % 4], i)
                        for i in range(1, 10))
        code, out = self.run_plan(gaps=GAPS + extra)
        self.assertEqual(code, 0, out)
        self.assertIn("10 USER question(s), limit 10", out)

    def test_placeholder_id_user_gap_is_not_an_open_gap(self):
        # A `-` in a step's Gaps cell names no gap, so a `-`-id gap is not one either.
        gaps = GAPS + "| - | which region | USER | ask the adopter | open |\n"
        ordering = ORDERING + "| S3 | 1 | Pick the region | C1 |  | - | no | region set |\n"
        code, out = self.run_plan(gaps=gaps, ordering=ordering)
        self.assertEqual(code, 0, out)
        self.assertIn("1 unresolved USER gap(s)", out)

    def test_placeholder_inventory_id_is_not_a_component(self):
        inv = INVENTORY + "| - | store | no id yet | S:L20 |\n"
        code, out = self.run_plan(inventory=inv)
        self.assertEqual(code, 0, out)
        self.assertIn("components 2", out)

    def test_placeholder_wp_id_is_not_a_package(self):
        pkgs = PACKAGES + "| TBD | Unnamed | C1 | ops | x | y | none | z |\n"
        code, out = self.run_plan(packages=pkgs)
        self.assertEqual(code, 0, out)
        self.assertIn("packages 2", out)

    def test_counts_label_names_its_units(self):
        inv = (INVENTORY + "| C2 | store | the same store, restated | S:L9 |\n"
                           "|  | store | no id yet | S:L21 |\n")
        code, out = self.run_plan(inventory=inv)
        self.assertEqual(code, 0, out)
        self.assertIn("counts (distinct non-blank ids for components and packages, "
                      "table rows otherwise)", out)
        self.assertIn("components 2", out)

    def test_short_row_is_padded(self):
        ordering = ORDERING + "| S3 | 1 | Short row | C1 |\n"
        code, out = self.run_plan(ordering=ordering)
        self.assertEqual(code, 1)
        self.assertIn("step S3 has no acceptance check", out)


if __name__ == "__main__":
    unittest.main(verbosity=1)
