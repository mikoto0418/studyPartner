from datetime import datetime, date
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

class RoleBase(BaseModel):
    code: str = Field(..., description="角色编码")
    name: str = Field(..., description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")

class RoleOut(RoleBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class StudentProfileBase(BaseModel):
    student_id: Optional[str] = Field(None, description="学号")
    grade: Optional[str] = Field(None, description="年级")
    major: Optional[str] = Field(None, description="专业")
    research_direction: Optional[str] = Field(None, description="研究方向")
    enrollment_date: Optional[date] = Field(None, description="入学日期")
    bio: Optional[str] = Field(None, description="个人简介")
    extra_info: Optional[dict] = Field(None, description="扩展信息")

class StudentProfileCreate(StudentProfileBase):
    pass

class StudentProfileUpdate(StudentProfileBase):
    pass

class StudentProfileOut(StudentProfileBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    username: str = Field(..., description="用户名")
    email: EmailStr = Field(..., description="电子邮箱")
    nickname: Optional[str] = Field(None, description="昵称")
    phone: Optional[str] = Field(None, description="联系电话")
    status: str = Field("active", description="状态: active, inactive, disabled")

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="密码")
    role_codes: List[str] = Field(default=["student"], description="角色编码列表")

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    nickname: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    status: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6, description="重置密码")

class UserOut(UserBase):
    id: UUID
    avatar_url: Optional[str] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    roles: List[RoleOut] = []
    student_profile: Optional[StudentProfileOut] = None

    class Config:
        from_attributes = True
