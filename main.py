from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import asyncio
from datetime import datetime

from config import config
from llm_service import llm_service
from mcp_client import mcp_manager

app = FastAPI(title="AI Chat with MCP Integration", version="1.0.0")

# Настройка шаблонов
templates = Jinja2Templates(directory="templates")

# Модели данных
class ChatMessage(BaseModel):
    message: str
    timestamp: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    timestamp: str
    mcp_context: Optional[Dict[str, Any]] = None
    available_servers: List[str] = []

# Глобальное хранилище сообщений чата
chat_history: List[Dict[str, Any]] = []

# WebSocket соединения
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Удаляем неактивные соединения
                self.active_connections.remove(connection)

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def get_chat_page(request: Request):
    """Главная страница чата"""
    return templates.TemplateResponse("chat.html", {"request": request})

@app.post("/api/chat", response_model=ChatResponse)
async def send_message(message: ChatMessage):
    """API endpoint для отправки сообщений"""
    try:
        # Обрабатываем сообщение через LLM с MCP
        result = await llm_service.process_message_with_mcp(message.message)
        
        # Сохраняем сообщение в историю
        chat_entry = {
            "user_message": message.message,
            "ai_response": result["response"],
            "timestamp": datetime.now().isoformat(),
            "mcp_context": result.get("mcp_context"),
            "available_servers": result.get("available_servers", [])
        }
        chat_history.append(chat_entry)
        
        # Ограничиваем историю последними 100 сообщениями
        if len(chat_history) > 100:
            chat_history.pop(0)
        
        return ChatResponse(
            response=result["response"],
            timestamp=chat_entry["timestamp"],
            mcp_context=result.get("mcp_context"),
            available_servers=result.get("available_servers", [])
        )
    
    except Exception as e:
        return ChatResponse(
            response=f"Произошла ошибка: {str(e)}",
            timestamp=datetime.now().isoformat()
        )

@app.get("/api/chat/history")
async def get_chat_history():
    """Получает историю чата"""
    return {"history": chat_history}

@app.get("/api/mcp/tools")
async def get_mcp_tools():
    """Получает список всех доступных инструментов MCP серверов"""
    try:
        all_tools = await mcp_manager.get_all_tools()
        return {"tools": all_tools}
    except Exception as e:
        return {"error": f"Ошибка получения инструментов: {str(e)}"}

@app.get("/api/mcp/tools/{server_name}")
async def get_server_tools(server_name: str):
    """Получает список инструментов конкретного MCP сервера"""
    try:
        tools = await mcp_manager.list_server_tools(server_name)
        return {"server": server_name, "tools": tools}
    except Exception as e:
        return {"error": f"Ошибка получения инструментов сервера {server_name}: {str(e)}"}

@app.post("/api/mcp/call")
async def call_mcp_tool(request: Dict[str, Any]):
    """Вызывает инструмент MCP сервера"""
    try:
        server_name = request.get("server")
        tool_name = request.get("tool")
        arguments = request.get("arguments", {})
        
        if not server_name or not tool_name:
            return {"error": "Необходимо указать server и tool"}
        
        result = await mcp_manager.call_tool(server_name, tool_name, arguments)
        return {"result": result}
    except Exception as e:
        return {"error": f"Ошибка вызова инструмента: {str(e)}"}

@app.get("/api/mcp/info/{server_name}")
async def get_server_info(server_name: str):
    """Получает информацию о MCP сервере"""
    try:
        info = await mcp_manager.get_server_info(server_name)
        return {"server": server_name, "info": info}
    except Exception as e:
        return {"error": f"Ошибка получения информации о сервере {server_name}: {str(e)}"}

@app.get("/api/mcp/status")
async def get_mcp_status():
    """Получает статус MCP серверов"""
    available_servers = await mcp_manager.get_available_servers()
    return {"available_servers": available_servers}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint для real-time чата"""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Обрабатываем сообщение
            result = await llm_service.process_message_with_mcp(message_data["message"])
            
            # Сохраняем в историю
            chat_entry = {
                "user_message": message_data["message"],
                "ai_response": result["response"],
                "timestamp": datetime.now().isoformat(),
                "mcp_context": result.get("mcp_context"),
                "available_servers": result.get("available_servers", [])
            }
            chat_history.append(chat_entry)
            
            # Отправляем ответ обратно через WebSocket
            response_data = {
                "response": result["response"],
                "timestamp": chat_entry["timestamp"],
                "mcp_context": result.get("mcp_context"),
                "available_servers": result.get("available_servers", [])
            }
            
            await manager.send_personal_message(json.dumps(response_data, ensure_ascii=False), websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/config")
async def get_config():
    """Получает конфигурацию (без секретных данных)"""
    llm_config = config.get_llm_config()
    mcp_config = config.get_mcp_config()
    
    # Скрываем секретные данные
    safe_config = {
        "llm": {
            "provider": llm_config.get("provider"),
            "model": llm_config.get("model"),
            "base_url": llm_config.get("base_url")
        },
        "mcp_servers": {
            name: {
                "enabled": server_config.get("enabled"),
                "host": server_config.get("host"),
                "port": server_config.get("port")
            }
            for name, server_config in mcp_config.items()
        }
    }
    
    return safe_config

if __name__ == "__main__":
    import uvicorn
    server_config = config.get_server_config()
    uvicorn.run(
        "main:app",
        host=server_config.get("host", "0.0.0.0"),
        port=server_config.get("port", 8000),
        reload=server_config.get("debug", True)
    )
