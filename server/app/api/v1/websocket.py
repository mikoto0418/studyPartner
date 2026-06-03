from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import jwt, JWTError
from app.config import settings
from app.core.websocket_manager import manager
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    user_id = None
    try:
        # Validate JWT token
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("WebSocket connect rejected: sub claim missing in token")
            await websocket.close(code=4008) # Policy Violation
            return
    except JWTError as e:
        logger.warning(f"WebSocket auth failed (JWT error): {e}")
        await websocket.close(code=4008)
        return
    except Exception as e:
        logger.error(f"WebSocket unexpected auth error: {e}")
        await websocket.close(code=4008)
        return

    await manager.connect(user_id, websocket)
    try:
        while True:
            # We can wait for data, or handle heartbeats
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(user_id, websocket)
