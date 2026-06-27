from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header

# Demo auth. A real legal deployment needs SSO/JWKS + RLS; this seam is where that drops in
# (architecture.md §10). We default to the supervising partner; the associate view passes a header.
PARTNER = "partner@firm.example"


@dataclass
class CurrentUser:
    id: str
    email: str
    role: str  # "partner" | "associate"


def get_current_user(
    x_user_email: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
) -> CurrentUser:
    email = x_user_email or PARTNER
    role = x_user_role or ("partner" if email == PARTNER else "associate")
    return CurrentUser(id=email, email=email, role=role)
