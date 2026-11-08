import unittest
from worker.clean import validate_teacher_reply, deduplicate_records


class DataCleaningTests(unittest.TestCase):

    def test_valid_teacher_reply(self):
        cmd = "set an alarm for seven am"
        raw = '{"intent": "alarm_set", "date": null, "time": "seven am", "place": null}'
        data, err = validate_teacher_reply(raw, cmd)
        self.assertIsNone(err)
        self.assertEqual(data["time"], "seven am")

    def test_reject_invalid_json(self):
        cmd = "what is the weather"
        raw = '{"intent": "weather_query", broken...'
        data, err = validate_teacher_reply(raw, cmd)
        self.assertEqual(err, "invalid_json")

    def test_reject_wrong_keys(self):
        cmd = "what time is it"
        raw = '{"intent": "datetime_query", "date": null, "time": null}'
        data, err = validate_teacher_reply(raw, cmd)
        self.assertEqual(err, "wrong_keys")

    def test_reject_invalid_intent(self):
        cmd = "open browser"
        raw = '{"intent": "open_app", "date": null, "time": null, "place": null}'
        data, err = validate_teacher_reply(raw, cmd)
        self.assertEqual(err, "invalid_intent")

    def test_reject_hallucinated_slot(self):
        cmd = "what is the weather"
        raw = '{"intent": "weather_query", "date": null, "time": null, "place": "paris"}'
        data, err = validate_teacher_reply(raw, cmd)
        self.assertEqual(err, "invalid_slot")

    def test_deduplication_keeps_smallest_id(self):
        records = [
            {"id": "C0050", "text": "set alarm for six am", "intent": "alarm_set"},
            {"id": "C0010", "text": "set alarm for six am", "intent": "alarm_set"},
            {"id": "C0025", "text": "what time is it", "intent": "datetime_query"},
        ]
        retained, dup_count = deduplicate_records(records)
        self.assertEqual(dup_count, 1)
        self.assertEqual(len(retained), 2)
        # Should keep C0010 over C0050
        ids = [r["id"] for r in retained]
        self.assertIn("C0010", ids)
        self.assertNotIn("C0050", ids)


if __name__ == "__main__":
    unittest.main()
