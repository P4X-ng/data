"""
WebSocket endpoint for cluster auto-discovery
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import logging
import json
from app.cluster.auto_discovery import AutoDiscoveryWebSocket

logger = logging.getLogger(__name__)

router = APIRouter()

# Global discovery handler
discovery_handler = AutoDiscoveryWebSocket()

@router.websocket("/ws/discovery")
async def discovery_websocket(websocket: WebSocket):
    """WebSocket endpoint for cluster auto-discovery"""
    await websocket.accept()
    logger.info("Discovery WebSocket connection established")
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                # Handle the message using discovery handler
                await discovery_handler.handle_message(websocket, message)
                
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
            except Exception as e:
                logger.error(f"Error handling discovery message: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
                
    except WebSocketDisconnect:
        logger.info("Discovery WebSocket disconnected")
        # Clean up any active scans for this connection
        for task in discovery_handler.active_scans.values():
            task.cancel()
        discovery_handler.active_scans.clear()
    except Exception as e:
        logger.error(f"Discovery WebSocket error: {e}")
        await websocket.close()

def register_discovery_routes(app):
    """Register discovery routes with the FastAPI app"""
    app.include_router(router)