import unittest

from tools.score import parse_prediction, score


class ScoreTests(unittest.TestCase):

    def test_valid_prediction(self):
        raw = '{"intent":"book","date":null,"time":null,"place":null}'
        self.assertIsNotNone(parse_prediction(raw))

    def test_invalid_json(self):
        self.assertIsNone(parse_prediction("not json"))

    def test_wrong_keys(self):
        raw = '{"intent":"book","date":null,"time":null}'
        self.assertIsNone(parse_prediction(raw))

    def test_score_perfect_prediction(self):
        gold = [{
            "id": "T1",
            "intent": "book",
            "date": None,
            "time": None,
            "place": None
        }]
        predictions = [{
            "id": "T1",
            "prediction":
                '{"intent":"book","date":null,"time":null,"place":null}'
        }]

        result = score(predictions, gold)
        self.assertEqual(result["json_validity"], 100.0)
        self.assertEqual(result["full_frame"], 100.0)


if __name__ == "__main__":
    unittest.main()
