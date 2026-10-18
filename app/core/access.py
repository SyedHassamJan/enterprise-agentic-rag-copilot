"""Role-based access control (RBAC) for retrieval, and document lifecycle filtering.

Every chunk carries two metadata fields set at ingestion:
  access  - who may read it: "all", "managers", "hr_staff" or "it_staff"
  status  - "current" or "superseded"

Permissions are enforced INSIDE the vector search as a Pinecone metadata filter, so chunks a
user may not read are never retrieved, never reach the LLM prompt, and therefore cannot leak
into an answer, even through prompt injection.

Identity here is a demo user picker. In production the role would come from the SSO / OIDC
token's group claims, never from the client.
"""
from dataclasses import dataclass

ACCESS_LEVELS = ("all", "managers", "hr_staff", "it_staff")

ROLE_ACCESS: dict[str, tuple[str, ...]] = {
    "employee": ("all",),
    "manager": ("all", "managers"),
    "hr_staff": ("all", "managers", "hr_staff"),
    "it_admin": ("all", "it_staff"),
}


@dataclass(frozen=True)
class User:
    username: str
    name: str
    role: str


DEMO_USERS: dict[str, User] = {
    u.username: u
    for u in (
        User("alex", "Alex Chen", "employee"),
        User("maria", "Maria Lopez", "manager"),
        User("priya", "Priya Shah", "hr_staff"),
        User("sam", "Sam Okafor", "it_admin"),
    )
}
DEFAULT_USER = "alex"


def get_user(username: str | None) -> User:
    return DEMO_USERS.get((username or DEFAULT_USER).lower(), DEMO_USERS[DEFAULT_USER])


def retrieval_filter(role: str) -> dict:
    """Pinecone metadata filter: readable by this role AND not superseded."""
    levels = list(ROLE_ACCESS.get(role, ROLE_ACCESS["employee"]))
    return {"$and": [{"access": {"$in": levels}}, {"status": {"$ne": "superseded"}}]}
