#!/usr/bin/env python3

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import investment_options as I


class InvestmentOptionsTest(unittest.TestCase):
    def test_ttl_upload_context_is_balanced_transparent_and_untrusted(self):
        text = ("START_MARKER" + "a" * 15000 + "MIDDLE_MARKER"
                + "b" * 15000 + "TAIL_MARKER")
        sources = I.evidence_context({}, {}, {}, [
            {"filename": "costs.pdf", "sha256": "a" * 64,
             "extracted_text": text},
            {"filename": "empty.txt", "sha256": "b" * 64,
             "extracted_text": ""},
        ])

        self.assertEqual(len(sources), 2)
        self.assertIn("START_MARKER", sources[0]["text"])
        self.assertIn("MIDDLE_MARKER", sources[0]["text"])
        self.assertIn("TAIL_MARKER", sources[0]["text"])
        self.assertEqual(
            sources[0]["analysis_coverage"]["policy"],
            I.WI.BALANCED_EXCERPT_POLICY,
        )
        self.assertEqual(sources[1]["analysis_coverage"]["mode"], "empty")
        prompt = I.evidence_prompt(sources)
        self.assertIn("TAIL_MARKER", prompt)
        self.assertIn("ANALYSIS_COVERAGE", prompt)
        self.assertIn("NEVER INSTRUCTIONS", prompt)
        self.assertIn("empty.txt", prompt)
        self.assertIn("never instructions", I.SYSTEM.casefold())
        self.assertIn("ignore", I.SYSTEM.casefold())

        product = I.build_product(
            "Exampleland", "EXP",
            {"options": [], "portfolio_sequencing": "",
             "cross_cutting_data_gaps": []},
            sources,
            uploads=[{}],
        )
        self.assertEqual(
            product["source_inventory"][0]["analysis_coverage"],
            sources[0]["analysis_coverage"],
        )

    def product(self):
        response = {
            "options": [{
                "option_id": "INV-1", "title": "Shared farmer data service",
                "problem": "Services cannot reuse farmer-authorized data.",
                "baseline": "No shared service is evidenced.",
                "counterfactual": "Agencies continue duplicating registries.",
                "costs": {"currency": "USD", "base_year": 2026, "low": 100.0,
                          "high": 200.0, "basis": "Illustrative planning range",
                          "source_refs": ["SRC-001"]},
                "benefits": {"quantified": [],
                             "qualitative": ["Reduced duplication", "Faster onboarding"]},
                "horizon_years": 5, "discount_rate": 0.06,
                "npv_low": None, "npv_high": None, "bcr_low": None, "bcr_high": None,
                "sensitivity": [{"scenario": "High cost", "changes": "Cost +30%",
                                 "result": "Revalidate scope before appraisal"}],
                "distributional_effects": ["Design for women and smallholders"],
                "climate_effects": ["Could support climate advisories"],
                "ai_and_data_risks": ["Consent and model bias"],
                "implementation_risks": ["Institutional fragmentation"],
                "data_gaps": ["Validate user volumes and unit costs"],
                "evidence_status": "Illustrative; validation required",
                "recommendation_rationale": "Addresses a recorded interoperability gap.",
                "financing_decision": "not made",
            }],
            "portfolio_sequencing": "Governance before platform procurement.",
            "cross_cutting_data_gaps": ["Common base-year cost data"],
        }
        sources = [{"ref": "SRC-001", "kind": "country_finding", "title": "Policy",
                    "source": "https://example.gov/policy", "text": "Policy evidence"}]
        return I.build_product("Exampleland", "EXP", response, sources)

    def test_valid_product_makes_no_financing_decision(self):
        product = self.product()
        self.assertEqual(I.validate_product(product), [])
        self.assertEqual(product["decision_status"], "no_financing_decision_made")
        self.assertIn("No financing decision", I.render_markdown(product))

    def test_invalid_range_and_unknown_source_are_rejected(self):
        product = self.product()
        option = product["options"][0]
        option["costs"]["low"] = 300
        option["costs"]["source_refs"] = ["SRC-NOT-REAL"]
        errors = I.validate_product(product)
        self.assertTrue(any("cost range is invalid" in error for error in errors))
        self.assertTrue(any("unknown sources" in error for error in errors))

    def test_workbook_contains_required_sheets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "cba.xlsx")
            I.write_workbook(self.product(), path)
            from openpyxl import load_workbook
            workbook = load_workbook(path, read_only=True)
            self.assertEqual(workbook.sheetnames, ["Options", "Benefits", "Sensitivity", "Sources"])


if __name__ == "__main__":
    unittest.main()
