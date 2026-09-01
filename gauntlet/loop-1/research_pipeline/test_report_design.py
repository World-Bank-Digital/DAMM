import re
import unittest

from research_pipeline import report_design as R


class ReportDesignTest(unittest.TestCase):
    def test_document_is_offline_printable_and_escapes_metadata(self):
        html = R.document(
            title="Country <diagnostic>",
            country="Nigeria & partners",
            subtitle="Evidence-backed working paper",
            status="Draft — post-completion review pending",
            metadata=(("Assessment", "2026 <current>"),),
            body=R.section("Executive perspective", R.paragraph("Safe & specific")),
        )

        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertIn("@media print", html)
        self.assertIn("Nigeria &amp; partners", html)
        self.assertIn("Country &lt;diagnostic&gt;", html)
        self.assertIn("2026 &lt;current&gt;", html)
        self.assertIn("Safe &amp; specific", html)
        self.assertNotIn("<current>", html)
        self.assertNotRegex(html, r"(?:src|href)=[\"']https?://")
        self.assertIn("thead{display:table-header-group}", html)
        self.assertNotIn(".chart,.card,table,tr{break-inside:avoid}", html)
        self.assertIn(".notice,.cards,.short-table,.keep-together{break-inside:avoid}", html)
        self.assertIn("overflow-wrap:anywhere", html)
        self.assertIn(".table-wrap{overflow:visible}", html)
        self.assertIn("print-color-adjust:exact", html)

    def test_short_tables_are_kept_together_for_print(self):
        compact = R.table(("Guardrail",), ((f"Rule {index}",) for index in range(4)))
        long = R.table(("Evidence",), ((f"Row {index}",) for index in range(8)))

        self.assertIn('class="table-wrap short-table"', compact)
        self.assertIn('class="table-wrap"', long)
        self.assertNotIn('class="table-wrap short-table"', long)
        self.assertIn('<caption class="sr-only">Table columns: Guardrail</caption>', compact)
        self.assertIn('<th scope="col">Guardrail</th>', compact)

    def test_related_section_lead_can_be_kept_with_its_figure(self):
        grouped = R.keep_together(R.notice("Binding rule", "Measured"), "<figure>Chart</figure>")

        self.assertEqual(
            grouped,
            '<div class="keep-together"><div class="notice "><strong>Binding rule</strong>'
            'Measured</div><figure>Chart</figure></div>',
        )
        document = R.document(
            title="Foresight",
            country="Nigeria",
            subtitle="Test",
            status="Draft",
            body=grouped,
        )
        self.assertIn(".keep-together{break-inside:avoid}", document)

    def test_composition_bar_is_deterministic_accessible_and_names_missing_data(self):
        first = R.composition_bar_svg(
            "Evidence composition",
            (("Primary", 6), ("Secondary", 3), ("Unrated", 1)),
            missing=2,
        )
        second = R.composition_bar_svg(
            "Evidence composition",
            (("Primary", 6), ("Secondary", 3), ("Unrated", 1)),
            missing=2,
        )

        self.assertEqual(first, second)
        self.assertIn("role=\"img\"", first)
        self.assertIn("Evidence composition", first)
        self.assertIn("Missing / unclassified", first)
        self.assertIn("12 total", first)

    def test_timeline_marks_proposals_without_presenting_them_as_findings(self):
        chart = R.milestone_timeline_svg(
            "Backcast milestones",
            (
                {"year": 2030, "label": "Scale trusted services", "candidate": False},
                {"year": 2028, "label": "Validate candidate measure", "candidate": True},
            ),
        )

        self.assertLess(chart.index("2028"), chart.index("2030"))
        self.assertIn("Proposed / unratified", chart)
        self.assertIn("candidate milestone", chart)

    def test_timeline_viewbox_contains_every_milestone(self):
        chart = R.milestone_timeline_svg(
            "Long backcast",
            tuple(
                {"year": 2026 + index, "label": f"Milestone {index}", "candidate": False}
                for index in range(14)
            ),
        )

        height = int(re.search(r'viewBox="0 0 760 (\d+)"', chart).group(1))
        last_y = max(int(value) for value in re.findall(r'cy="(\d+)"', chart))
        self.assertGreaterEqual(height, last_y + 32)

    def test_long_visual_labels_are_bounded_but_preserved_in_titles(self):
        label = "A very long investment title " * 8
        timeline = R.milestone_timeline_svg(
            "Long label",
            ({"year": 2030, "label": label, "candidate": True},),
        )
        ranges = R.range_bar_svg(
            "Long range",
            ({"label": label, "currency": "USD", "low": 123456789,
              "high": 987654321},),
        )

        self.assertIn(f"<title>{label}</title>", timeline)
        self.assertIn("…", timeline)
        self.assertIn(
            f"<title>{label.strip()}: 123,456,789–987,654,321 USD</title>", ranges
        )
        self.assertIn('text-anchor="end"', ranges)
        self.assertNotIn(">123,456,789–987,654,321<", ranges)

    def test_range_chart_separates_currencies_and_omits_unquantified_values(self):
        chart = R.range_bar_svg(
            "Preliminary cost ranges",
            (
                {"label": "Option A", "currency": "USD", "low": 10, "high": 20},
                {"label": "Option B", "currency": "NGN", "low": 100, "high": 300},
                {"label": "Option C", "currency": "USD", "low": None, "high": None},
            ),
        )

        self.assertIn("USD — independently scaled", chart)
        self.assertIn("NGN — independently scaled", chart)
        self.assertIn("Option A", chart)
        self.assertIn("Option B", chart)
        self.assertNotIn("Option C", chart)
        self.assertIn("not a ranking", chart)


if __name__ == "__main__":
    unittest.main()
