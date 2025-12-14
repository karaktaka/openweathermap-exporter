import logging
import signal
import unittest
from unittest.mock import MagicMock, mock_open, patch

import yaml

from src.client import configure_logging, parse_args, parse_config, shutdown


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
        import src.client

        src.client.RUNNING = True

    @patch("builtins.open", new_callable=mock_open, read_data="interval: 600\nloglevel: INFO\nlisten_port: 9126")
    def test_parse_config_valid(self, mock_file):
        config = parse_config("../src/config.yaml")
        self.assertIsInstance(config, dict)
        self.assertEqual(config["interval"], 600)
        self.assertEqual(config["loglevel"], "INFO")
        self.assertEqual(config["listen_port"], 9126)

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_parse_config_file_not_found(self, mock_file):
        with self.assertRaises(FileNotFoundError):
            parse_config("nonexistent.yaml")

    @patch("builtins.open", new_callable=mock_open, read_data="invalid_yaml: [")
    def test_parse_config_invalid_yaml(self, mock_file):
        with self.assertRaises(yaml.YAMLError):
            parse_config("invalid.yaml")

    @patch("builtins.open", new_callable=mock_open, read_data="")
    def test_parse_config_empty(self, mock_file):
        with self.assertRaises(ValueError) as context:
            parse_config("empty.yaml")
        self.assertEqual(str(context.exception), "Configuration file is empty")

    def test_parse_args_with_config(self):
        with patch("sys.argv", ["client.py", "-f", "config.yaml", "-v"]):
            args = parse_args()
            self.assertEqual(args.config_file, "config.yaml")
            self.assertEqual(args.verbosity, 1)

    def test_parse_args_without_config(self):
        with patch("sys.argv", ["client.py"]):
            args = parse_args()
            self.assertIsNone(args.config_file)
            self.assertEqual(args.verbosity, 0)

    def test_set_logging_level_with_verbosity(self):
        logger = configure_logging(2, "WARNING")
        self.assertEqual(logger.level, logging.INFO)

    def test_set_logging_level_without_verbosity(self):
        logger = configure_logging(0, "INFO")
        self.assertEqual(logger.level, logging.INFO)

    def test_set_logging_level_custom_logger(self):
        custom_logger = logging.getLogger("test_logger")
        logger = configure_logging(1, "INFO", custom_logger)
        self.assertEqual(logger.level, logging.WARNING)
        self.assertEqual(logger, custom_logger)

    def test_shutdown(self):
        import src.client

        src.client.RUNNING = True
        shutdown(signal.SIGTERM)
        self.assertFalse(src.client.RUNNING)

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="api_key: test_key\nlocations:\n  - name: Berlin\n    lat: 52.52\n    lon: 13.41",
    )
    def test_parse_config_with_locations(self, mock_file):
        config = parse_config("../src/config.yaml")
        self.assertIsInstance(config, dict)
        self.assertEqual(config["api_key"], "test_key")
        self.assertIsInstance(config["locations"], list)
        self.assertEqual(len(config["locations"]), 1)
        self.assertEqual(config["locations"][0]["name"], "Berlin")
        self.assertEqual(config["locations"][0]["lat"], 52.52)
        self.assertEqual(config["locations"][0]["lon"], 13.41)

    @patch("builtins.open", new_callable=mock_open, read_data="api_key: null\nlocations: []")
    def test_parse_config_minimal(self, mock_file):
        config = parse_config("../src/config.yaml")
        self.assertIsInstance(config, dict)
        self.assertIsNone(config["api_key"])
        self.assertEqual(config["locations"], [])


if __name__ == "__main__":
    unittest.main()
