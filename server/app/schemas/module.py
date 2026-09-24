from typing import Optional

from pydantic import BaseModel


class ModuleOut(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    enabled: bool = True
    visible: bool = True


class ModuleUpdate(BaseModel):
    enabled: Optional[bool] = None
    visible: Optional[bool] = None