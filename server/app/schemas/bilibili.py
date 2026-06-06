from datetime import datetime, date
from typing import Optional, List, Any
from uuid import UUID
from pydantic import BaseModel, Field

class BilibiliResourceBase(BaseModel):
    bvid: str = Field(..., max_length=32, description="B站视频 BV 号")
    title: str = Field(..., max_length=255, description="视频标题")
    description: Optional[str] = Field(None, description="视频描述")
    cover_url: Optional[str] = Field(None, max_length=512, description="封面图链接")
    author_name: Optional[str] = Field(None, max_length=128, description="UP主名字")
    total_episodes: int = Field(1, description="总集数")
    total_duration: Optional[int] = Field(None, description="总时长（秒）")
    category: Optional[str] = Field(None, max_length=64, description="分类")
    episodes_info: Optional[List[Any]] = Field(None, description="分集信息")
    is_shared: bool = Field(False, description="是否公开共享")

class BilibiliResourceCreate(BilibiliResourceBase):
    pass

class BilibiliResourceOut(BilibiliResourceBase):
    id: UUID
    creator_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class BilibiliWatchLogCreate(BaseModel):
    resource_id: UUID = Field(..., description="B站资源ID")
    event_type: str = Field(..., description="事件类型：open, heartbeat, pause, close, manual_complete")
    episode_number: int = Field(1, description="当前播放的分集编号")
    watch_duration: int = Field(0, description="观看时长增量（秒）")
    is_completed: bool = Field(False, description="是否手动标记完成")

class BilibiliWatchLogOut(BaseModel):
    id: UUID
    user_id: UUID
    resource_id: UUID
    event_type: str
    episode_number: int
    watch_duration: int
    is_completed: bool
    created_at: datetime

    class Config:
        from_attributes = True

class StudyTimeHeartbeatReq(BaseModel):
    session_id: str = Field(..., description="前端会话唯一标识 UUID")
    duration_seconds: int = Field(30, description="心跳间隔时长（秒）")
    source: str = Field("platform", description="来源: platform, bilibili")

class HeatmapPointOut(BaseModel):
    date: str = Field(..., description="日期, 格式 YYYY-MM-DD")
    count: int = Field(..., description="活跃计数/学情权重积分")


class BilibiliMetaOut(BaseModel):
    bvid: str
    title: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    author_name: Optional[str] = None
    total_episodes: int = 1
    total_duration: Optional[int] = None
    episodes_info: Optional[List[Any]] = None

class BilibiliWatchStatOut(BaseModel):
    resource_id: UUID
    resource_title: str
    episode_number: int
    start_time: datetime
    end_time: datetime
    watch_seconds: int
    pause_count: int
    completed: bool = False
