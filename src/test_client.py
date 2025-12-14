import logging
import signal
import unittest
from unittest.mock import mock_open, patch

from client import configure_logging, parse_args, parse_config, shutdown


class TestClient(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.logger = logging.getLogger("test_logger")
        # Reset handlers before each test
        self.logger.handlers = []

    def tearDown(self):
        """Clean up after tests."""
        # Clean up logging handlers
        logging.getLogger("test_logger").handlers = []
        # Reset running state
        import client

        client.RUNNING = True

    @patch("builtins.open", new_callable=mock_open, read_data="interval: 600\nloglevel: INFO\nlisten_port: 9126")
    def test_parse_config_valid(self, mock_file):
        config = parse_config(mock_file)
        self.assertIsInstance(config, dict)
        self.assertEqual(config["interval"], 600)
        self.assertEqual(config["loglevel"], "INFO")
        self.assertEqual(config["listen_port"], 9126)

    def test_parse_args_with_config(self):
        with patch("sys.argv", ["client.py", "-c", "config.yaml", "-v"]):
            args = parse_args()
            self.assertEqual(args.config_file, "config.yaml")
            self.assertEqual(args.verbosity, 1)

    def test_parse_args_without_config(self):
        with patch("sys.argv", ["client.py"]):
            args = parse_args()
            self.assertIsNone(args.config_file)
            self.assertEqual(args.verbosity, 0)

    def test_set_logger(self):
        custom_logger = logging.getLogger("test_logger")
        log = configure_logging(custom_logger, "INFO")
        self.assertEqual(log.level, logging.INFO)
        self.assertEqual(log, custom_logger)

    def test_set_logging_level(self):
        logger = logging.getLogger("test_logger")
        log = configure_logging(logger, "INFO")
        self.assertEqual(log.level, logging.INFO)

    def test_shutdown(self):
        import client

        client.RUNNING = True
        shutdown(signal.SIGTERM)
        self.assertFalse(client.RUNNING)

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="api_key: test_key\nlocations:\n  - name: Berlin\n    lat: 52.52\n    lon: 13.41",
    )
    def test_parse_config_with_locations(self, mock_file):
        config = parse_config(mock_file)
        self.assertIsInstance(config, dict)
        self.assertEqual(config["api_key"], "test_key")
        self.assertIsInstance(config["locations"], list)
        self.assertEqual(len(config["locations"]), 1)
        self.assertEqual(config["locations"][0]["name"], "Berlin")
        self.assertEqual(config["locations"][0]["lat"], 52.52)
        self.assertEqual(config["locations"][0]["lon"], 13.41)

    @patch("builtins.open", new_callable=mock_open, read_data="api_key: null\nlocations: []")
    def test_parse_config_minimal(self, mock_file):
        config = parse_config(mock_file)
        self.assertIsInstance(config, dict)
        self.assertIsNone(config["api_key"])
        self.assertEqual(config["locations"], [])


if __name__ == "__main__":
    unittest.main()
