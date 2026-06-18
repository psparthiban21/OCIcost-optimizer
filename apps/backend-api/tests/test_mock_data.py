import unittest

from oci_cost_optimizer.mock_data import answer_mock_copilot, create_mock_cost_optimizer_data


class MockDataTest(unittest.TestCase):
    def test_dashboard_contract(self) -> None:
        data = create_mock_cost_optimizer_data({"service": "all", "region": "all"})

        self.assertEqual(data["meta"]["mode"], "mock")
        self.assertEqual(len(data["resources"]), 71)
        self.assertGreater(data["summary"]["currentRunRate"], 0)
        self.assertGreater(data["summary"]["identifiedSavings"], 0)
        self.assertGreater(len(data["recommendations"]), 0)

    def test_filters_apply_to_resources(self) -> None:
        data = create_mock_cost_optimizer_data({"service": "Compute", "region": "all"})

        self.assertTrue(data["resources"])
        self.assertEqual({"Compute"}, {resource["service"] for resource in data["resources"]})

    def test_copilot_returns_savings_answer(self) -> None:
        answer = answer_mock_copilot("Where can I save the most?", {"service": "all", "region": "all"})

        self.assertIn("Potential savings", answer)
        self.assertIn("Biggest wins", answer)


if __name__ == "__main__":
    unittest.main()
