"""Identity for the dedicated FormRefine staging backend, behind its same-origin proxy."""
import httpx
from fastapi import HTTPException, Request

ORIGIN = "https://staging.formrefine.ai"


async def staging_member(request: Request) -> dict:
    origin = request.headers.get("origin")
    if (origin and origin != ORIGIN) or (request.method not in {"GET", "HEAD"} and origin != ORIGIN):
        raise HTTPException(403, "Request must originate from the staging site.")
    cookie = request.headers.get("cookie")
    if not cookie:
        raise HTTPException(401, "Sign in on FormRefine Staging.")
    try:
        # The destination is the session issuer. Never derive it from the incoming Host.
        async with httpx.AsyncClient(timeout=5, follow_redirects=False, trust_env=False) as client:
            response = await client.get(ORIGIN + "/_auth/me", headers={"Cookie": cookie})
        if response.status_code in (401, 403):
            raise HTTPException(401, "Google session expired.")
        response.raise_for_status()
        identity = response.json()
        if not isinstance(identity, dict):
            raise ValueError("Unexpected session response")
        if identity.get("logged_in") is not True:
            raise HTTPException(401, "Sign in on FormRefine Staging.")
        member = identity.get("member")
        subject = member.get("id") if isinstance(member, dict) else None
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("Missing stable member identifier")
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Could not verify the staging session.") from exc
    return {"id": "gefei-staging:" + subject, "provider": "gefei-staging", "role": "user"}
