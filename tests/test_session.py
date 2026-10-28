"""Unit tests for SafeSession atomic single-admin locking/logout context manager."""

import unittest
from tplink_router.core.session import SafeSession


class DummyClient:
    def __init__(self):
        self.is_logged_in = False
        self.login_count = 0
        self.logout_count = 0

    def login(self):
        self.is_logged_in = True
        self.login_count += 1

    def logout(self):
        self.is_logged_in = False
        self.logout_count += 1


class TestSafeSession(unittest.TestCase):

    def test_session_lifecycle(self):
        client = DummyClient()
        self.assertFalse(client.is_logged_in)

        with SafeSession(client) as session:
            self.assertTrue(client.is_logged_in)
            self.assertEqual(client.login_count, 1)
            self.assertEqual(session, client)

        self.assertFalse(client.is_logged_in)
        self.assertEqual(client.logout_count, 1)

    def test_session_logout_on_exception(self):
        client = DummyClient()
        with self.assertRaises(ValueError):
            with SafeSession(client):
                self.assertTrue(client.is_logged_in)
                raise ValueError("Simulated network timeout during command")

        # Must be logged out even if command threw exception
        self.assertFalse(client.is_logged_in)
        self.assertEqual(client.logout_count, 1)


if __name__ == "__main__":
    unittest.main()
