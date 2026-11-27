import secrets
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import httpx
from pydantic import SecretStr

from app.config import settings
from app.main import app
from app.services import engine_identity
from app.services.jwt_service import jwt_service


class EngineAdminTests(unittest.TestCase):
    def test_admin_console_and_api_check_verified_member(self):
        origin = "https://formrefine.ai"

        def issuer(request):
            self.assertEqual(str(request.url), origin + "/_auth/me")
            cookie = request.headers.get("cookie")
            member_id = {"test=owner": "owner", "test=visitor": "visitor"}.get(cookie)
            return httpx.Response(200, json={
                "logged_in": bool(member_id),
                "member": {"id": member_id, "role": "admin"},
            })

        client = TestClient(app, base_url=origin, follow_redirects=False)
        async_client = httpx.AsyncClient

        def fake_issuer(**kwargs):
            return async_client(transport=httpx.MockTransport(issuer), **kwargs)

        admin_api = "/api/v1/admin/operations"
        owner = {"Cookie": "test=owner"}
        visitor = {"Cookie": "test=visitor"}
        with patch.object(settings, "engine_auth_origin", origin), patch.object(
            settings, "engine_admin_member_id", "owner"
        ), patch.object(engine_identity.httpx, "AsyncClient", side_effect=fake_issuer):
            login = client.get("/admin")
            self.assertEqual(login.status_code, 303)
            self.assertEqual(login.headers["location"], origin + "/_auth/google/start?next=%2Fadmin")
            self.assertEqual(login.headers["x-robots-tag"], "noindex, nofollow")
            self.assertEqual(client.get(admin_api).status_code, 401)

            local_admin = jwt_service.create_token({"id": "admin", "is_local": True, "role": "admin"})
            forged = {**visitor, "Authorization": "Bearer " + local_admin, "X-Admin": "true"}
            self.assertEqual(client.get("/admin", headers=forged).status_code, 403)
            self.assertEqual(client.get(admin_api, headers=forged).status_code, 403)
            self.assertEqual(client.post("/api/v1/admin/users/member/credits",
                                         headers={**owner, "Origin": "https://other.example"}).status_code, 403)
            self.assertEqual(client.post("/api/v1/auth/local-login").status_code, 404)

            console = client.get("/admin", headers=owner)
            self.assertEqual(console.status_code, 200)
            self.assertIn("data-engine-admin", console.text)
            self.assertIn("no-store", console.headers["cache-control"])
            self.assertEqual(client.get(admin_api, headers=owner).status_code, 200)
            with patch.object(settings, "engine_admin_member_id", ""):
                self.assertEqual(client.get(admin_api, headers=owner).status_code, 404)

    def test_password_login_uses_an_admin_only_session(self):
        origin = "https://formrefine.ai"
        session = "/api/v1/admin/session"
        operations = "/api/v1/admin/operations"
        password = secrets.token_urlsafe(32)
        username = "admin"
        credentials = {"username": username, "password": password}
        headers = {"Origin": origin}
        legacy_token = jwt_service.create_token({"id": username, "role": "admin", "is_local": True})
        client = TestClient(app, base_url=origin, follow_redirects=False)

        with patch.object(settings, "engine_auth_origin", origin), patch.object(
            settings, "engine_admin_password", SecretStr(password)
        ):
            page = client.get("/admin")
            self.assertEqual(page.status_code, 200)
            self.assertIn('data-engine-password-admin', page.text)
            self.assertIn("no-store", page.headers["cache-control"])
            self.assertIn("noindex", page.headers["x-robots-tag"])

            self.assertEqual(client.get(session).status_code, 401)
            self.assertEqual(client.get(operations, headers={"Authorization": "Bearer " + legacy_token}).status_code, 401)
            self.assertEqual(client.post(session, json=credentials).status_code, 403)
            self.assertEqual(client.post(session, json={**credentials, "password": "wrong"}, headers=headers).status_code, 401)
            self.assertEqual(client.post("/api/v1/auth/local-login", json=credentials, headers=headers).status_code, 404)

            result = client.post(session, json=credentials, headers=headers)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json(), {"success": True})
            cookie = result.headers["set-cookie"].lower()
            for directive in ("httponly", "secure", "samesite=strict", "path=/api/v1/admin"):
                self.assertIn(directive, cookie)

            self.assertEqual(client.get(session).status_code, 200)
            self.assertEqual(client.get(operations).status_code, 200)
            self.assertEqual(client.get("/api/v1/videos/history").status_code, 401)
            self.assertEqual(client.delete(session, headers={"Origin": "https://other.example"}).status_code, 403)
            with patch.object(settings, "engine_admin_password", SecretStr(secrets.token_urlsafe(32))):
                self.assertEqual(client.get(session).status_code, 401)
            self.assertEqual(client.delete(session, headers=headers).status_code, 200)
            self.assertEqual(client.get(session).status_code, 401)
