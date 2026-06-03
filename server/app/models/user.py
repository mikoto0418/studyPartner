from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Table, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, Base
import uuid

# UserRole association table (junction table) as a class or Table.
# The database-design.md has it as a proper model with primary key:
# "user_roles { UUID id PK, UUID user_id FK, UUID role_id FK, TIMESTAMPTZ created_at }"
class UserRole(Base):
    __tablename__ = "user_roles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    from sqlalchemy.sql import func
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class Role(BaseModel):
    __tablename__ = "roles"
    
    code = Column(String(50), unique=True, nullable=False, index=True) # e.g. admin, teacher, student
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    
    # Relationships
    users = relationship("User", secondary="user_roles", back_populates="roles")

class User(BaseModel):
    __tablename__ = "users"
    
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(100), nullable=True)
    avatar_url = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    status = Column(String(50), default="active", nullable=False) # active, inactive, disabled
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    roles = relationship("Role", secondary="user_roles", back_populates="users", lazy="joined")
    student_profile = relationship("StudentProfile", uselist=False, back_populates="user", cascade="all, delete-orphan")
    
    @property
    def role_codes(self) -> list[str]:
        return [r.code for r in self.roles]

class StudentProfile(BaseModel):
    __tablename__ = "student_profiles"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    student_id = Column(String(100), nullable=True) # 学号
    grade = Column(String(50), nullable=True) # 年级
    major = Column(String(100), nullable=True) # 专业
    research_direction = Column(String(150), nullable=True) # 研究方向
    enrollment_date = Column(Date, nullable=True) # 入学日期
    bio = Column(String, nullable=True) # 个人简介 / 描述
    extra_info = Column(JSONB, nullable=True) # 扩展配置
    
    # Relationships
    user = relationship("User", back_populates="student_profile")
