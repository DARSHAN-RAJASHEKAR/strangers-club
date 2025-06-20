# app/api/endpoints/messages.py
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from uuid import UUID
import json

from app.db.base import get_db
from app.auth.oauth import get_current_active_user, get_current_user
from app.crud import message as crud_message
from app.crud import channel as crud_channel
from app.crud import group as crud_group
from app.schemas.message import Message, MessageCreate, MessageUpdate
from app.schemas.user import User

router = APIRouter()

# Class to manage WebSocket connections for chat
class ConnectionManager:
    def __init__(self):
        # channel_id -> list of WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel_id: str):
        await websocket.accept()
        if channel_id not in self.active_connections:
            self.active_connections[channel_id] = []
        self.active_connections[channel_id].append(websocket)

    def disconnect(self, websocket: WebSocket, channel_id: str):
        if channel_id in self.active_connections:
            if websocket in self.active_connections[channel_id]:
                self.active_connections[channel_id].remove(websocket)
            if not self.active_connections[channel_id]:
                del self.active_connections[channel_id]

    async def broadcast(self, message: dict, channel_id: str):
        if channel_id in self.active_connections:
            for connection in self.active_connections[channel_id]:
                await connection.send_text(json.dumps(message))

manager = ConnectionManager()

@router.get("/channel/{channel_id}", response_model=List[Message])
async def read_messages(
    channel_id: UUID,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get messages for a specific channel.
    """
    # Check if user is a member of the group that owns the channel
    channel = await crud_channel.get_channel(db, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    group = await crud_group.get_group(db, channel.group_id)
    if not group or current_user.id not in [member.id for member in group.members]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    messages = await crud_message.get_messages_by_channel(db, channel_id, skip=skip, limit=limit)
    # Reverse the order to get oldest first
    messages.reverse()
    return messages

@router.post("/channel/{channel_id}", response_model=Message)
async def create_message(
    channel_id: UUID,
    message_in: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new message in a channel.
    """
    # Check if user is a member of the group that owns the channel
    channel = await crud_channel.get_channel(db, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    group = await crud_group.get_group(db, channel.group_id)
    if not group or current_user.id not in [member.id for member in group.members]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Override channel_id from path parameter
    message_data = message_in.model_dump()
    message_data["channel_id"] = channel_id
    
    message = await crud_message.create_message(
        db, MessageCreate(**message_data), author_id=current_user.id
    )
    
    # Broadcast the message to all connected WebSocket clients
    message_dict = {
        "id": str(message.id),
        "content": message.content,
        "author": {
            "id": str(message.author_id),
            "username": current_user.username
        },
        "channel_id": str(message.channel_id),
        "created_at": message.created_at.isoformat()
    }
    await manager.broadcast(message_dict, str(channel_id))
    
    return message

@router.put("/{message_id}", response_model=Message)
async def update_message(
    message_id: UUID,
    message_in: MessageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update a message.
    """
    message = await crud_message.get_message(db, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Check if user is the author of the message
    if message.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the author can update the message")
    
    message = await crud_message.update_message(db, db_message=message, message_in=message_in)
    
    # Broadcast the update to all connected WebSocket clients
    update_dict = {
        "type": "message_update",
        "id": str(message.id),
        "content": message.content,
        "updated_at": message.updated_at.isoformat() if message.updated_at else None
    }
    await manager.broadcast(update_dict, str(message.channel_id))
    
    return message

@router.delete("/{message_id}", response_model=Message)
async def delete_message(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a message.
    """
    message = await crud_message.get_message(db, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Check if user is the author of the message or the group owner
    channel = await crud_channel.get_channel(db, message.channel_id)
    group = await crud_group.get_group(db, channel.group_id)
    
    if message.author_id != current_user.id and group.owner_id != current_user.id:
        raise HTTPException(
            status_code=403, 
            detail="Only the author or group owner can delete the message"
        )
    
    channel_id = message.channel_id
    message = await crud_message.delete_message(db, message_id=message_id)
    
    # Broadcast the deletion to all connected WebSocket clients
    delete_dict = {
        "type": "message_delete",
        "id": str(message_id)
    }
    await manager.broadcast(delete_dict, str(channel_id))
    
    return message

@router.websocket("/ws/{channel_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    channel_id: str,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint for real-time messaging.
    """
    try:
        # Authenticate the user
        user = await get_current_user(token=token, db=db)
        
        # Check if user is a member of the group that owns the channel
        channel = await crud_channel.get_channel(db, UUID(channel_id))
        if not channel:
            await websocket.close(code=1008, reason="Channel not found")
            return
        
        group = await crud_group.get_group(db, channel.group_id)
        if not group or user.id not in [member.id for member in group.members]:
            await websocket.close(code=1008, reason="Access denied")
            return
        
        # Accept the connection
        await manager.connect(websocket, channel_id)
        
        # Send connection established message
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "user": user.username,
            "channel_id": channel_id
        }))
        
        try:
            while True:
                # Wait for messages from the client
                data = await websocket.receive_text()
                
                # Process the message
                try:
                    message_data = json.loads(data)
                    
                    # Create a new message in the database
                    message_in = MessageCreate(
                        content=message_data.get("content", ""),
                        channel_id=UUID(channel_id)
                    )
                    
                    message = await crud_message.create_message(
                        db, message_in, author_id=user.id
                    )
                    
                    # Broadcast the message to all connected clients
                    message_dict = {
                        "type": "new_message",
                        "id": str(message.id),
                        "content": message.content,
                        "author": {
                            "id": str(message.author_id),
                            "username": user.username
                        },
                        "channel_id": str(message.channel_id),
                        "created_at": message.created_at.isoformat()
                    }
                    await manager.broadcast(message_dict, channel_id)
                    
                except Exception as e:
                    # Send error message to the client
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": str(e)
                    }))
                    
        except WebSocketDisconnect:
            # Handle client disconnect
            manager.disconnect(websocket, channel_id)
            
            # Broadcast user left message
            await manager.broadcast({
                "type": "user_disconnected",
                "user": user.username,
                "channel_id": channel_id
            }, channel_id)
            
    except Exception as e:
        # Handle authentication or other errors
        try:
            await websocket.close(code=1008, reason=str(e))
        except:
            pass