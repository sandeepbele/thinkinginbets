import unittest

from thinkinginbets.data_sources import data_source_statuses


class DataSourcesTest(unittest.TestCase):
    def test_reports_missing_and_present_credentials_without_values(self) -> None:
        statuses = {
            status.name: status
            for status in data_source_statuses(
                {
                    "KALSHI_API_KEY_ID": "key-id",
                    "KALSHI_PRIVATE_KEY_PATH": "/tmp/key.pem",
                    "POLYMARKET_API_KEY": "key",
                }
            )
        }

        self.assertEqual(statuses["kalshi"].credential_status, "present")
        self.assertEqual(statuses["polymarket"].credential_status, "partial")
        self.assertEqual(statuses["statsbomb_open_data"].credential_status, "not_required")


if __name__ == "__main__":
    unittest.main()
