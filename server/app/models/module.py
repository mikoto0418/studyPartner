from sqlalchemy import Boolean, Column, String
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import BaseModel


class FeatureModule(BaseModel):
    __tablename__ = "feature_modules"

    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    visible = Column(Boolean, default=True, nullable=False)
    roles = Column(JSONB, nullable=True)