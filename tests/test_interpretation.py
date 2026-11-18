import unittest
from services.api.interpretation import interpret


class InterpretationTests(unittest.TestCase):
    def test_intuition_without_full_proof_is_not_a_logic_failure(self):
        result = interpret(dict(mode="intuition", quote="我直觉看好这家公司", logic={}), "我直觉看好这家公司")
        self.assertEqual(result["logic"]["status"], "not_assessed")
        self.assertEqual(result["logic"]["bonus_points"], 0)
        self.assertFalse(result["penalize_missing_rationale"])

    def test_coherent_logic_earns_separate_bonus(self):
        text = "订单持续增长。产能也在提升。因此我看好明年业绩。"
        result = interpret(dict(mode="directional_view", quote=text, logic=dict(
            status="coherent", reason="所述订单和产能是作者的论证链条。",
            quotes=["订单持续增长。", "因此我看好明年业绩。"])), text)
        self.assertEqual(result["logic"]["bonus_points"], 1)
        self.assertFalse(result["logic"]["changes_factual_verdict"])

    def test_invented_logic_premise_is_rejected(self):
        text = "订单持续增长。因此我看好明年业绩。"
        with self.assertRaises(ValueError):
            interpret(dict(logic=dict(status="contradictory", reason="假设未发生。",
                                     quotes=["订单持续增长。", "股价保证上涨十倍。"])), text)

    def test_condition_cannot_be_invented(self):
        with self.assertRaises(ValueError):
            interpret(dict(mode="conditional", condition_quotes=["前提是美联储降息。"]), "我看好业绩。")

    def test_unmet_condition_is_not_a_missed_unconditional_forecast(self):
        text = "如果明年降息，我看好成长股。"
        result = interpret(dict(mode="conditional", condition_quotes=["如果明年降息"],
                                condition_state="not_met"), text)
        self.assertFalse(result["allow_outcome_verdict"])
        self.assertEqual(result["condition_state"], "not_met")

    def test_scenario_is_not_a_promise(self):
        result = interpret(dict(mode="scenario", quote="一种可能是双方谈判。"), "一种可能是双方谈判。")
        self.assertFalse(result["allow_outcome_verdict"])

    def test_single_assertion_is_not_a_reasoning_chain(self):
        text = "我觉得这家公司的前景不错。"
        result = interpret(dict(logic=dict(status="coherent", reason="逻辑自洽。", quotes=[text])), text)
        self.assertEqual(result["logic"]["bonus_points"], 0)
