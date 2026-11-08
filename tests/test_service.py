import json
import unittest
from service.validator import validate_against_schema


class ServiceValidationTests(unittest.TestCase):

    def test_valid_four_key_payload(self):
        valid_json = '{"intent": "weather_query", "date": null, "time": null, "place": "london"}'
        result = validate_against_schema(valid_json)
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], "weather_query")
        self.assertEqual(result["place"], "london")

    def test_missing_keys_rejected(self):
        incomplete_json = '{"intent": "alarm_set", "date": "tomorrow"}'
        result = validate_against_schema(incomplete_json)
        self.assertIsNone(result)

    def test_extra_keys_rejected(self):
        extra_keys_json = '{"intent": "alarm_set", "date": null, "time": "seven am", "place": null, "extra": 123}'
        result = validate_against_schema(extra_keys_json)
        self.assertIsNone(result)

    def test_invalid_intent_rejected(self):
        unknown_intent = '{"intent": "order_pizza", "date": null, "time": null, "place": null}'
        result = validate_against_schema(unknown_intent)
        self.assertIsNone(result)

    def test_non_string_slot_rejected(self):
        numeric_slot = '{"intent": "alarm_set", "date": 2024, "time": null, "place": null}'
        result = validate_against_schema(numeric_slot)
        self.assertIsNone(result)

    def test_malformed_json_rejected(self):
        not_json = '{"intent": "weather_query", "date":'
        result = validate_against_schema(not_json)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
