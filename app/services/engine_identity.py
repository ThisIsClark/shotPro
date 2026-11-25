"""Verify a FormRefine session with the configured GeFeiSites issuer."""
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException, Request

from ..config import settings


async def verify_engine_member(request: Request) -> dict:
    issuer = settings.engine_session_origin
    origin = request.headers.get("origin")
    if (origin and origin != issuer) or (request.method not in {"GET", "HEAD"} and origin != issuer):
        raise HTTPException(403, "Request must originate from the configured FormRefine site.")
    cookie = request.headers.get("cookie")
    if not cookie:
        raise HTTPException(401, "Sign in on FormRefine.")
    try:
        # The destination is the session issuer. Never derive it from the incoming Host.
        async with httpx.AsyncClient(timeout=5, follow_redirects=False, trust_env=False) as client:
            response = await client.get(issuer + "/_auth/me", headers={"Cookie": cookie})
        if response.status_code in (401, 403):
            raise HTTPException(401, "Google session expired.")
        response.raise_for_status()
        identity = response.json()
        if not isinstance(identity, dict):
            raise ValueError("Unexpected session response")
        if identity.get("logged_in") is not True:
            raise HTTPException(401, "Sign in on FormRefine.")
        member = identity.get("member")
        subject = member.get("id") if isinstance(member, dict) else None
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("Missing stable member identifier")
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Could not verify your session.") from exc
    hostname = urlsplit(issuer).hostname
    # Existing staging reports already use this prefix.
    namespace = "gefei-staging" if hostname == "staging.formrefine.ai" else "gefei:" + hostname
    return {"id": namespace + ":" + subject, "provider": "gefei", "role": "user", "subject": subject}
