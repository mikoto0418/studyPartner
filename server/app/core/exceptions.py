from typing import Any, Dict, Optional
from fastapi import HTTPException, status

class CustomException(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.code = code
        self.message = message
        self.data = data

class AuthError(CustomException):
    def __init__(self, message: str = "认证失败", code: str = "AUTH_ERROR", data: Optional[Any] = None):
        super().__init__(
            status_code=status_code.HTTP_401_UNAUTHORIZED,
            code=code,
            message=message,
            data=data,
            headers={"WWW-Authenticate": "Bearer"},
        )

class PermissionDenied(CustomException):
    def __init__(self, message: str = "权限不足", code: str = "PERMISSION_DENIED"):
        super().__init__(
            status_code=status_code.HTTP_403_FORBIDDEN,
            code=code,
            message=message
        )

class NotFoundError(CustomException):
    def __init__(self, message: str = "资源不存在", code: str = "NOT_FOUND"):
        super().__init__(
            status_code=status_code.HTTP_404_NOT_FOUND,
            code=code,
            message=message
        )

class ValidationError(CustomException):
    def __init__(self, message: str = "数据验证失败", code: str = "VALIDATION_ERROR", data: Optional[Any] = None):
        super().__init__(
            status_code=status_code.HTTP_400_BAD_REQUEST,
            code=code,
            message=message,
            data=data
        )

class BusinessError(CustomException):
    def __init__(self, message: str, code: str = "BUSINESS_ERROR", data: Optional[Any] = None):
        super().__init__(
            status_code=status_code.HTTP_400_BAD_REQUEST,
            code=code,
            message=message,
            data=data
        )
