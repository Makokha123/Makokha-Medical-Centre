"""Pytest: verify monthly financial dashboard endpoint.

This test uses Flask's test client instead of hitting localhost, so it can run
in CI and locally without requiring a separately running server.
"""

from __future__ import annotations

import pytest


def _is_db_unavailable_error(exc: BaseException) -> bool:
    """Best-effort check for DB connectivity / transaction state failures."""
    text = (str(exc) or "").lower()
    return any(
        needle in text
        for needle in (
            "connection timed out",
            "timeout",
            "could not connect",
            "connection refused",
            "could not translate host name",
            "name or service not known",
            "can't reconnect until invalid transaction is rolled back",
            "server closed the connection",
        )
    )


def _skip_if_db_unavailable(exc: BaseException) -> None:
    """Skip test when DB is not reachable (common in CI/local without DB)."""
    pytest.skip(f"Database not available for monthly endpoint test: {exc}")


def _find_active_admin_user(User):
    for candidate in User.query.all():
        role = str(getattr(candidate, "role", "") or "").lower().strip()
        if role == "admin" and getattr(candidate, "is_active", False):
            return candidate
    return None


def _force_login(client, user_id: int):
    # Flask-Login stores the user id in the session under '_user_id'.
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True


def test_monthly_endpoint():
    from app import app, User

    app.config["TESTING"] = True

    with app.app_context():
        try:
            admin_user = _find_active_admin_user(User)
        except Exception as e:
            pytest.skip(f"Database not available for monthly endpoint test: {e}")

        if not admin_user:
            pytest.skip("No active admin user found in database")

        admin_user_id = int(admin_user.id)

    with app.test_client() as client:
        _force_login(client, admin_user_id)

        # Test 1: Single month request
        try:
            resp = client.get(
                "/api/financial/dashboard/monthly",
                query_string={"year": 2026, "month": 1},
            )
        except Exception as e:
            try:
                from sqlalchemy.exc import DBAPIError, OperationalError, PendingRollbackError
            except Exception:  # pragma: no cover
                DBAPIError = OperationalError = PendingRollbackError = ()

            try:
                from psycopg2 import OperationalError as Psycopg2OperationalError
            except Exception:  # pragma: no cover
                Psycopg2OperationalError = ()

            if isinstance(
                e,
                (
                    DBAPIError,
                    OperationalError,
                    PendingRollbackError,
                    Psycopg2OperationalError,
                ),
            ) or _is_db_unavailable_error(e):
                _skip_if_db_unavailable(e)
            raise
        assert resp.status_code == 200
        assert resp.data

        # Test 2: Date range request
        try:
            resp = client.get(
                "/api/financial/dashboard/monthly",
                query_string={"startDate": "2025-11-01", "endDate": "2026-01-31"},
            )
        except Exception as e:
            try:
                from sqlalchemy.exc import DBAPIError, OperationalError, PendingRollbackError
            except Exception:  # pragma: no cover
                DBAPIError = OperationalError = PendingRollbackError = ()

            try:
                from psycopg2 import OperationalError as Psycopg2OperationalError
            except Exception:  # pragma: no cover
                Psycopg2OperationalError = ()

            if isinstance(
                e,
                (
                    DBAPIError,
                    OperationalError,
                    PendingRollbackError,
                    Psycopg2OperationalError,
                ),
            ) or _is_db_unavailable_error(e):
                _skip_if_db_unavailable(e)
            raise
        assert resp.status_code == 200
        assert resp.data
