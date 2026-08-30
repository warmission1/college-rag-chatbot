from typing import Optional, List, Dict, Any
from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from pymongo.database import Database
from backend.app.core.database import get_db
from backend.app.core.errors import AuthRequiredError, ForbiddenError
from backend.app.auth.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    authorization: Optional[str] = Header(None),
    db: Database = Depends(get_db),
) -> Dict[str, Any]:
    jwt_token = token
    if not jwt_token and authorization and authorization.startswith("Bearer "):
        jwt_token = authorization.split(" ")[1]
        
    if not jwt_token:
        raise AuthRequiredError("Authorization header or Bearer token is missing")
    
    user_id = decode_access_token(jwt_token)
    if not user_id:
        raise AuthRequiredError("Invalid, expired, or malformed authentication token")
    
    user = db.users.find_one({"id": user_id})
    if not user:
        raise AuthRequiredError("User account no longer exists")
    
    if user.get("status") != "active":
        raise ForbiddenError("User account has been suspended")
    
    return user


def require_roles(allowed_roles: List[str]):
    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        role = current_user.get("role", "user")
        if role not in allowed_roles and role != "super-admin":
            raise ForbiddenError(f"Action requires one of roles: {', '.join(allowed_roles)}")
        return current_user
    return role_checker


def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    role = current_user.get("role", "user")
    if role not in ["admin", "super-admin"]:
        raise ForbiddenError("Administrator access required")
    return current_user
