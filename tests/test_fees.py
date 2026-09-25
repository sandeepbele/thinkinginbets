import unittest

from thinkinginbets.fees import KalshiFeeModel


class KalshiFeeModelTest(unittest.TestCase):
    def test_taker_fee_uses_general_formula_rounded_up_to_cent(self) -> None:
        fee = KalshiFeeModel().taker_fee_cents(price_cents=75, quantity=100)

        self.assertEqual(fee, 132)


if __name__ == "__main__":
    unittest.main()
