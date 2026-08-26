#!/usr/bin/env python3
"""Contract-level checks for the canonical DAR workflow.

These checks deliberately use only the Python standard library. The DAMM repository can
therefore reject a workflow that reintroduces a human gate or loses a required stage before
any application build or optional JSON Schema package is available.
"""

import json
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
CONTRACT_PATH = HERE / "dar-workflow-v1.json"
SCHEMA_PATH = HERE / "dar-workflow-v1.schema.json"

STAGE_IDS = [
    "damm_diagnostic",
    "country_research",
    "ai_digital_agriculture",
    "international_lessons",
    "strategic_foresight",
    "investment_options",
    "draft_dar",
    "export_package",
]


class WorkflowContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT_PATH.read_text())
        cls.schema = json.loads(SCHEMA_PATH.read_text())

    def test_identity_and_exact_stage_order(self):
        contract = self.contract
        self.assertEqual(contract["schema_version"], "damm.dar-workflow/v1")
        self.assertEqual(contract["workflow_id"], "dar-canonical-v1")
        self.assertEqual([s["id"] for s in contract["stages"]], STAGE_IDS)
        self.assertEqual([s["ordinal"] for s in contract["stages"]], list(range(1, 9)))

    def test_dependencies_are_strictly_backward_and_resolvable(self):
        position = {stage_id: index for index, stage_id in enumerate(STAGE_IDS)}
        for stage in self.contract["stages"]:
            for dependency in stage["depends_on"]:
                self.assertIn(dependency, position)
                self.assertLess(position[dependency], position[stage["id"]])
        self.assertEqual(
            self.contract["stages"][6]["depends_on"],
            STAGE_IDS[:6],
            "the Draft DAR must integrate every analytical stage",
        )

    def test_active_workflow_has_no_required_human_action(self):
        policy = self.contract["execution_policy"]
        self.assertTrue(policy["single_launch"])
        self.assertTrue(policy["immutable_input_snapshot"])
        self.assertEqual(policy["required_human_actions_during_run"], [])
        self.assertEqual(
            policy["missing_optional_input_policy"], "autonomous_research_fallback"
        )
        self.assertEqual(
            policy["budget_policy"],
            "preauthorized_ceiling_with_fixed_protected_allocations",
        )
        self.assertEqual(
            policy["fixed_stage_budget_allocations"],
            {
                "damm_diagnostic": 0.45,
                "country_research": 0.075,
                "ai_digital_agriculture": 0.10,
                "international_lessons": 0.075,
                "strategic_foresight": 0.10,
                "investment_options": 0.05,
                "draft_dar": 0.15,
                "export_package": 0.00,
            },
        )
        self.assertAlmostEqual(
            sum(policy["fixed_stage_budget_allocations"].values()), 1.0
        )
        self.assertNotIn("paused", policy["allowed_active_states"])
        self.assertNotIn("awaiting_human", policy["allowed_active_states"])
        self.assertTrue(policy["post_completion_review_only"])
        self.assertTrue(all(not s["human_input_required"] for s in self.contract["stages"]))

    def test_country_is_only_required_launch_input_and_uploads_are_optional(self):
        self.assertEqual(self.contract["required_launch_inputs"], ["country"])
        optional_ids = {item["id"] for item in self.contract["optional_launch_inputs"]}
        self.assertEqual(
            optional_ids,
            {
                "country_context_documents",
                "ai_documents",
                "international_strategy_documents",
                "foresight_documents",
                "investment_documents",
            },
        )
        for stage in self.contract["stages"]:
            self.assertTrue(set(stage["optional_inputs"]).issubset(optional_ids))
            self.assertTrue(stage["fallback_when_optional_inputs_absent"].strip())

    def test_ai_stage_is_separate_and_complete(self):
        ai = self.contract["stages"][2]
        self.assertEqual(
            ai["required_sections"], ["as_is", "peer_experience", "recommended_agenda"]
        )
        self.assertIn("ai_assessment_report", ai["required_artifacts"])
        self.assertIn("source_inventory", ai["required_artifacts"])

    def test_required_export_formats_and_post_completion_review(self):
        self.assertEqual(
            self.contract["export_profiles"],
            {
                "narrative": ["md", "docx", "pdf", "html"],
                "structured": ["xlsx", "csv", "json"],
                "package": ["zip", "json"],
            },
        )
        review = self.contract["post_completion"]
        self.assertEqual(review["review_available_after_stage"], "export_package")
        self.assertFalse(review["review_required_to_generate_draft"])
        self.assertTrue(review["review_required_for_final_or_publication"])

    def test_schema_itself_pins_human_free_invariants(self):
        policy = self.schema["$defs"]["executionPolicy"]["properties"]
        stage = self.schema["$defs"]["stage"]["properties"]
        self.assertEqual(policy["required_human_actions_during_run"]["maxItems"], 0)
        self.assertEqual(
            policy["budget_policy"]["const"],
            "preauthorized_ceiling_with_fixed_protected_allocations",
        )
        self.assertEqual(
            policy["fixed_stage_budget_allocations"]["const"],
            self.contract["execution_policy"]["fixed_stage_budget_allocations"],
        )
        self.assertEqual(stage["human_input_required"]["const"], False)
        self.assertEqual(self.schema["properties"]["stages"]["minItems"], 8)
        self.assertEqual(self.schema["properties"]["stages"]["maxItems"], 8)


if __name__ == "__main__":
    unittest.main()
