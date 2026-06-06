import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import BaseResponse

router = APIRouter()
logger = logging.getLogger(__name__)

BILIBILI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}


async def fetch_bilibili_json(url: str, params: dict) -> dict:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(20.0, connect=10.0),
        follow_redirects=True,
        headers=BILIBILI_HEADERS,
    ) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()

    if payload.get("code") != 0:
        logger.warning("Bilibili API failed: url=%s params=%s payload=%s", url, params, payload)
        raise HTTPException(status_code=502, detail=payload.get("message") or "Bilibili API failed")
    return payload.get("data") or {}


async def resolve_html5_mp4_url(bvid: str, episode: int, qn: int) -> str:
    pages = await fetch_bilibili_json(
        "https://api.bilibili.com/x/player/pagelist",
        {"bvid": bvid},
    )
    if not isinstance(pages, list) or not pages:
        raise HTTPException(status_code=404, detail="Bilibili video pages not found")

    page_info = next((item for item in pages if int(item.get("page", 0)) == episode), pages[0])
    cid = page_info.get("cid")
    if not cid:
        raise HTTPException(status_code=404, detail="Bilibili cid not found")

    play_data = await fetch_bilibili_json(
        "https://api.bilibili.com/x/player/playurl",
        {
            "bvid": bvid,
            "cid": cid,
            "qn": qn,
            "fnval": 0,
            "fourk": 0,
            "platform": "html5",
        },
    )
    durls = play_data.get("durl") or []
    if not durls or not durls[0].get("url"):
        raise HTTPException(status_code=502, detail="Bilibili play url not found")
    return durls[0]["url"]


async def close_stream(upstream: httpx.Response, client: httpx.AsyncClient) -> None:
    await upstream.aclose()
    await client.aclose()


@router.get("/stream-info", response_model=BaseResponse[dict], summary="解析 B 站原页播放源")
async def get_stream_info(
    bvid: str = Query(..., description="B站 BV 号"),
    episode: int = Query(1, ge=1, description="分 P 序号"),
    current_user: User = Depends(get_current_user),
):
    await resolve_html5_mp4_url(bvid, episode, 16)
    return BaseResponse.success(
        data={
            "type": "mp4-proxy",
            "src": f"/bilibili/stream?bvid={bvid}&episode={episode}&qn=16",
        },
        message="解析成功",
    )


@router.get("/stream", summary="代理 B 站视频流用于原页播放")
async def stream_bilibili_video(
    bvid: str = Query(..., description="B站 BV 号"),
    episode: int = Query(1, ge=1, description="分 P 序号"),
    qn: int = Query(16, description="清晰度，默认 360P MP4"),
    range_header: Optional[str] = Header(None, alias="Range"),
):
    video_url = await resolve_html5_mp4_url(bvid, episode, qn)
    headers = dict(BILIBILI_HEADERS)
    headers["Referer"] = f"https://www.bilibili.com/video/{bvid}/"
    if range_header:
        headers["Range"] = range_header

    client = httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=10.0),
        follow_redirects=True,
        headers=headers,
    )
    try:
        request = client.build_request("GET", video_url)
        upstream = await client.send(request, stream=True)
    except Exception:
        await client.aclose()
        raise

    response_headers = {
        "Accept-Ranges": upstream.headers.get("accept-ranges", "bytes"),
        "Content-Type": upstream.headers.get("content-type", "video/mp4"),
        "Cache-Control": "no-store",
    }
    for header_name in ("content-length", "content-range"):
        if header_name in upstream.headers:
            response_headers[header_name.title()] = upstream.headers[header_name]

    return StreamingResponse(
        upstream.aiter_bytes(),
        status_code=upstream.status_code,
        media_type=response_headers["Content-Type"],
        headers=response_headers,
        background=BackgroundTask(close_stream, upstream, client),
    )
