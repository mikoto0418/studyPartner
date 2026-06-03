import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, declared_attr

class Base(DeclarativeBase):
    """
    SQLAlchemy Declarative Base with dynamic table name mapping.
    """
    id: any
    
    @declared_attr.directive
    def __tablename__(cls) -> str:
        # Generate table name from class name: StudentProfile -> student_profiles
        name = cls.__name__
        import re
        parts = re.findall('[A-Z][a-z0-9]*', name)
        # Convert CamelCase to snake_case and make plural
        base_name = '_'.join(parts).lower()
        if base_name.endswith('y'):
            return base_name[:-1] + 'ies'
        elif base_name.endswith('s'):
            return base_name + 'es'
        return base_name + 's'

class TimestampMixin:
    """
    Mixin for created_at, updated_at, and deleted_at (soft delete) timestamps.
    """
    created_at = Column(
        DateTime(timezone=True),
        server_default=text("TIMEZONE('utc', NOW())"),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=text("TIMEZONE('utc', NOW())"),
        onupdate=text("TIMEZONE('utc', NOW())"),
        nullable=False
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

class BaseModel(Base, TimestampMixin):
    """
    Base model class with UUID primary key.
    """
    __abstract__ = True
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
