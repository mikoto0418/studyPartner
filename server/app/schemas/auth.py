from pydantic import BaseModel, Field
from app.schemas.user import UserOut

class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")

class TokenOut(BaseModel):
    access_token: str = Field(..., description="Access Token")
    refresh_token: str = Field(..., description="Refresh Token")
    token_type: str = Field("Bearer", description="Token 类型")
    expires_in: int = Field(..., description="过期时间(秒)")
    user: UserOut = Field(..., description="用户信息")

class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh Token")

class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, description="新密码")

class SendCodeRequest(BaseModel):
    email: str = Field(..., description="目标邮箱")
    action_type: str = Field(..., description="操作类型: register | reset_password")

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: str = Field(..., description="电子邮箱")
    password: str = Field(..., min_length=6, description="密码")
    role: str = Field("student", description="角色: student | teacher")
    code: str = Field(..., min_length=6, max_length=6, description="6位数字验证码")

class ResetPasswordRequest(BaseModel):
    email: str = Field(..., description="电子邮箱")
    new_password: str = Field(..., min_length=6, description="新密码")
    code: str = Field(..., min_length=6, max_length=6, description="6位数字验证码")

