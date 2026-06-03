from typing import Generic, TypeVar, Optional, List
from pydantic import BaseModel, Field

T = TypeVar("T")

class BaseResponse(BaseModel, Generic[T]):
    code: int = Field(0, description="业务状态码，0表示成功，非0表示异常")
    message: str = Field("success", description="状态描述信息")
    data: Optional[T] = Field(None, description="业务数据")

    @classmethod
    def success(cls, data: Optional[T] = None, message: str = "success") -> "BaseResponse[T]":
        return cls(code=0, message=message, data=data)

    @classmethod
    def error(cls, code: int, message: str, data: Optional[T] = None) -> "BaseResponse[T]":
        return cls(code=code, message=message, data=data)

class PageData(BaseModel, Generic[T]):
    items: List[T] = Field(..., description="数据列表")
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")
    total_pages: int = Field(..., description="总页数")

    @classmethod
    def create(cls, items: List[T], total: int, page: int, page_size: int) -> "PageData[T]":
        import math
        total_pages = math.ceil(total / page_size) if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
