"""Unit tests for kiosk PIN HMAC helpers."""

from __future__ import annotations

import os
import unittest
import uuid

from app.security.pins import hash_pin, validate_pin

# Settings require env before import.
os.environ.setdefault(
    "CERES_IDENTITY_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ceres_identity",
)
os.environ.setdefault("CERES_IDENTITY_REDIS_URL", "redis://127.0.0.1:6379/0")
os.environ.setdefault(
    "CERES_IDENTITY_REFRESH_JWT_SECRET",
    "unit-test-refresh-jwt-secret-at-least-thirty-two",
)
os.environ.setdefault(
    "CERES_IDENTITY_INTERNAL_API_KEY",
    "unit-test-internal-api-key-at-least-thirty-two-characters",
)


class PinHmacTests(unittest.TestCase):
    def test_validate_rejects_non_four_digits(self) -> None:
        with self.assertRaises(ValueError):
            validate_pin("123")
        with self.assertRaises(ValueError):
            validate_pin("12345")
        with self.assertRaises(ValueError):
            validate_pin("12ab")

    def test_hash_is_stable_and_64_hex(self) -> None:
        site_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        a = hash_pin("1234", site_id=site_id)
        b = hash_pin("1234", site_id=site_id)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in a))

    def test_different_pins_differ(self) -> None:
        site_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        self.assertNotEqual(
            hash_pin("1234", site_id=site_id),
            hash_pin("4321", site_id=site_id),
        )

    def test_same_pin_different_sites_differ(self) -> None:
        site_a = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        site_b = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
        self.assertNotEqual(
            hash_pin("1234", site_id=site_a),
            hash_pin("1234", site_id=site_b),
        )
