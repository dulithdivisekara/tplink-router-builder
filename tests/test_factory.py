"""Unit tests for RouterClientFactory model detection."""

import unittest
from unittest.mock import patch, MagicMock
from tplink_router.clients.factory import RouterClientFactory
from tplink_router.clients.mr_client import TPLinkMRClient
from tplink_router.clients.broad_client import TPLinkBroadbandClient


class TestRouterClientFactory(unittest.TestCase):

    @patch("requests.get")
    def test_detect_mr_series(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = "<html><script>var modelName='Archer MR200';</script></html>"
        mock_get.return_value = mock_resp

        family = RouterClientFactory.detect_model_family("http://192.168.1.1")
        self.assertEqual(family, "mr")

    @patch("requests.get")
    def test_detect_broadband_series(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = "<html><title>Archer AX53</title></html>"
        mock_get.return_value = mock_resp

        family = RouterClientFactory.detect_model_family("http://192.168.0.1")
        self.assertEqual(family, "broadband")

    def test_factory_instantiation(self):
        client_mr = RouterClientFactory.get_client("http://192.168.1.1", "secret", force_family="mr")
        self.assertIsInstance(client_mr, TPLinkMRClient)

        client_broad = RouterClientFactory.get_client("http://192.168.0.1", "secret", force_family="broadband")
        self.assertIsInstance(client_broad, TPLinkBroadbandClient)


if __name__ == "__main__":
    unittest.main()
