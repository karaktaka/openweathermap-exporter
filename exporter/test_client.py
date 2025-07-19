import unittest
from unittest.mock import patch, mock_open
from exporter.client import parse_config, parse_args, set_logging_level, shutdown
import logging
import signal


class TestClient(unittest.TestCase):

    @patch("builtins.open", new_callable=mock_open, read_data="interval: 600\nloglevel: INFO\nlisten_port: 9126")
    def test_parse_config_valid(self, mock_file):
        config = parse_config("config.yaml")
        self.assertEqual(config["interval"], 600)
        self.assertEqual(config["loglevel"], "INFO")
        self.assertEqual(config["listen_port"], 9126)

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_parse_config_file_not_found(self, mock_file):
        config = parse_config("nonexistent.yaml")
        self.assertIsNone(config)

    @patch("builtins.open", new_callable=mock_open, read_data="invalid_yaml: [")
    def test_parse_config_invalid_yaml(self, mock_file):
        with self.assertRaises(Exception):
            parse_config("invalid.yaml")

    def test_parse_args(self):
        test_args = ["client.py", "-f", "config.yaml", "-v"]
        with patch("sys.argv", test_args):
            args = parse_args()
            self.assertEqual(args.config_file[0], "config.yaml")
            self.assertEqual(args.verbosity, 1)

    def test_set_logging_level(self):
        logger = set_logging_level(2, "WARNING")
        self.assertEqual(logger.level, logging.INFO)

    def test_shutdown(self):
        import exporter.client

        exporter.client.running = True
        shutdown(signal.SIGTERM)
        self.assertFalse(exporter.client.running)


if __name__ == "__main__":
    unittest.main()
