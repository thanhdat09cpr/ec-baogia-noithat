import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from lib_boq import to_number  # noqa: E402


class ToNumberTest(unittest.TestCase):
    def test_vietnamese_thousand_separators(self):
        cases = {
            "12.500": 12500.0,
            "2.500.000": 2500000.0,
            "12,500": 12500.0,
            "2,500,000": 2500000.0,
            "1.234.567": 1234567.0,
            "1,234,567": 1234567.0,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(to_number(raw), expected)

    def test_short_decimal_values(self):
        cases = {
            "12,5": 12.5,
            "12.50": 12.5,
            "1234,56": 1234.56,
            "1234.56": 1234.56,
            "-12,5": -12.5,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(to_number(raw), expected)

    def test_rejects_ambiguous_long_decimal_values(self):
        self.assertIsNone(to_number("1.2345"))
        self.assertIsNone(to_number("1234,567"))

    def test_keeps_existing_machine_float_artifacts(self):
        self.assertAlmostEqual(to_number("7533000.000000001"), 7533000.000000001)
        self.assertAlmostEqual(to_number("22854149.999999996"), 22854149.999999996)


if __name__ == "__main__":
    unittest.main()
