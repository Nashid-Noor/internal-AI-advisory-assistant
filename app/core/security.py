
from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class UserRole(str, Enum):
    
    ANALYST = "analyst"
    CONSULTANT = "consultant"
    PARTNER = "partner"
    
    @property
    def access_level(self) -> int:
        levels = {
            UserRole.ANALYST: 1,
            UserRole.CONSULTANT: 2,
            UserRole.PARTNER: 3,
        }
        return levels[self]
    
    def can_access(self, required_role: "UserRole") -> bool:
        return self.access_level >= required_role.access_level
    
    @classmethod
    def from_string(cls, role_str: str) -> "UserRole":
        try:
            return cls(role_str.lower())
        except ValueError:
            # Default to analyst for unknown roles (most restrictive)
            return cls.ANALYST


@dataclass
class User:
    
    user_id: str
    role: UserRole
    email: str | None = None
    name: str | None = None
    
    def can_access_role(self, required_role: UserRole) -> bool:
        return self.role.can_access(required_role)


# Document access level mapping
# Maps document types/categories to minimum required role
DOCUMENT_ACCESS_LEVELS: dict[str, UserRole] = {
    # Public documents - accessible by all
    "playbook": UserRole.ANALYST,
    "guideline": UserRole.ANALYST,
    "template": UserRole.ANALYST,
    "training": UserRole.ANALYST,
    
    # Consultant-level documents
    "client_summary": UserRole.CONSULTANT,
    "engagement": UserRole.CONSULTANT,
    "proposal": UserRole.CONSULTANT,
    
    # Partner-level documents
    "partner_memo": UserRole.PARTNER,
    "fee_structure": UserRole.PARTNER,
    "strategic_plan": UserRole.PARTNER,
    "confidential": UserRole.PARTNER,
}


def get_document_access_level(document_type: str) -> UserRole:
    return DOCUMENT_ACCESS_LEVELS.get(document_type.lower(), UserRole.ANALYST)


def get_accessible_document_types(user_role: UserRole) -> list[str]:
    return [
        doc_type
        for doc_type, required_role in DOCUMENT_ACCESS_LEVELS.items()
        if user_role.can_access(required_role)
    ]


async def verify_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header()] = None,
) -> str:
    if not settings.auth_enabled:
        return "development-mode"
    
    if not x_api_key:
        logger.warning(
            "Authentication failed: missing API key",
            client_ip=request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include X-API-Key header.",
        )
    
    if x_api_key != settings.api_key:
        logger.warning(
            "Authentication failed: invalid API key",
            client_ip=request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )
    
    return x_api_key


async def get_current_user(
    request: Request,
    api_key: Annotated[str, Depends(verify_api_key)],
    x_user_id: Annotated[str, Header()] = "dev-user",
    x_user_role: Annotated[str, Header()] = "analyst",
    x_user_email: Annotated[str | None, Header()] = None,
) -> User:
    role = UserRole.from_string(x_user_role)
    
    user = User(
        user_id=x_user_id,
        role=role,
        email=x_user_email,
    )
    
    logger.info(
        "User authenticated",
        user_id=user.user_id,
        role=user.role.value,
    )
    
    return user


def require_role(required_role: UserRole):
    async def role_checker(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if not user.can_access_role(required_role):
            logger.warning(
                "Authorization failed: insufficient role",
                user_id=user.user_id,
                user_role=user.role.value,
                required_role=required_role.value,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires '{required_role.value}' role, but you have '{user.role.value}'",
            )
        return user
    
    return role_checker


def get_role_filter(user_role: UserRole) -> list[str]:
    return get_accessible_document_types(user_role)


class RoleBasedFilter:
    
    def __init__(self, user_role: UserRole) -> None:
        self.user_role = user_role
        self.accessible_types = get_accessible_document_types(user_role)
    
    def get_qdrant_filter(self) -> dict:
        from qdrant_client.models import FieldCondition, Filter, MatchAny
        
        return Filter(
            must=[
                FieldCondition(
                    key="document_type",
                    match=MatchAny(any=self.accessible_types),
                )
            ]
        )
    
    def can_access_document(self, document_type: str) -> bool:
        return document_type.lower() in self.accessible_types
