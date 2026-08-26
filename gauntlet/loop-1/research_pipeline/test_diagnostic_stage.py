#!/usr/bin/env python3

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import diagnostic_stage as D


class DiagnosticStageTest(unittest.TestCase):
    def test_reviewer_is_from_an_independent_vendor_family(self):
        for primary in ("anthropic/model", "openai/model", "gemini/model"):
            reviewer = D.independent_reviewer(primary)
            self.assertNotEqual(D.vendor_family(primary), D.vendor_family(reviewer))

    def test_family_reads_the_vendor_prefix(self):
        self.assertEqual(D.vendor_family("openai/gpt-test"), "openai")
        self.assertEqual(D.vendor_family(None), "")


if __name__ == "__main__":
    unittest.main()
