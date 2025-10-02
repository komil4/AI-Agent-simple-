import asyncio
import json
import httpx
from typing import Dict, Any, Optional, List
from config import config

class MCPClient:
    """Универсальный MCP клиент для работы через streamable HTTP API"""
    
    def __init__(self, name: str, server_config: Dict[str, Any]):
        self.name = name
        self.config = server_config
        self.url = server_config.get("url", "http://localhost:3000")
        self.enabled = server_config.get("enabled", False)
    
    async def is_available(self) -> bool:
        """Проверяет доступность MCP сервера"""
        if not self.enabled:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Проверяем health endpoint или просто доступность порта
                response = await client.get(f"{self.url}/health")
                return response.status_code == 200
        except:
            try:
                # Альтернативная проверка - просто подключение к порту
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{self.url}/")
                    return True
            except:
                return False
    
    async def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
        """Вызывает инструмент MCP сервера через streamable HTTP API"""
        if not self.enabled:
            return None
        
        try:
            # Формируем запрос в формате MCP
            request_data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments or {}
                }
            }
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "text/event-stream"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.url}/",
                    json=request_data,
                    headers=headers
                )
                
                if response.status_code == 200:
                    # Проверяем тип контента
                    content_type = response.headers.get("content-type", "")
                    if "text/event-stream" in content_type:
                        # Обрабатываем Server-Sent Events
                        return await self._process_sse_response(response)
                    else:
                        # Обычный JSON ответ
                        result = response.json()
                        if "result" in result:
                            return result["result"]
                        elif "error" in result:
                            return {"error": result["error"]}
                        else:
                            return result
                elif response.status_code == 406:
                    # Сервер не поддерживает SSE, используем fallback
                    return await self.call_tool_fallback(tool_name, arguments)
                else:
                    return {"error": f"HTTP {response.status_code}: {response.text}"}
                    
        except Exception as e:
            return {"error": f"Ошибка подключения к {self.name}: {str(e)}"}
    
    async def _process_sse_response(self, response) -> Dict:
        """Обрабатывает Server-Sent Events ответ"""
        try:
            content = await response.aread()
            text_content = content.decode('utf-8')
            
            # Парсим SSE события
            events = []
            for line in text_content.split('\n'):
                if line.startswith('data: '):
                    data = line[6:]  # Убираем "data: "
                    if data.strip():
                        try:
                            event_data = json.loads(data)
                            events.append(event_data)
                        except json.JSONDecodeError:
                            continue
            
            # Возвращаем последнее событие с результатом
            if events:
                last_event = events[-1]
                if "result" in last_event:
                    return last_event["result"]
                elif "error" in last_event:
                    return {"error": last_event["error"]}
                else:
                    return {"events": events}
            
            return {"error": "Нет данных в SSE потоке"}
            
        except Exception as e:
            return {"error": f"Ошибка обработки SSE: {str(e)}"}
    
    async def call_tool_fallback(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
        """Fallback метод для вызова инструмента без SSE (обычный HTTP)"""
        if not self.enabled:
            return None
        
        try:
            request_data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments or {}
                }
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.url}/",
                    json=request_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "result" in result:
                        return result["result"]
                    elif "error" in result:
                        return {"error": result["error"]}
                    else:
                        return result
                else:
                    return {"error": f"HTTP {response.status_code}: {response.text}"}
                    
        except Exception as e:
            return {"error": f"Ошибка подключения к {self.name}: {str(e)}"}
    
    async def list_tools(self) -> Optional[List[Dict]]:
        """Получает список доступных инструментов MCP сервера"""
        if not self.enabled:
            return None
        
        try:
            request_data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list"
            }
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "text/event-stream"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.url}/",
                    json=request_data,
                    headers=headers
                )
                
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    if "text/event-stream" in content_type:
                        result = await self._process_sse_response(response)
                        if "tools" in result:
                            return result["tools"]
                        else:
                            return []
                    else:
                        result = response.json()
                        if "result" in result and "tools" in result["result"]:
                            return result["result"]["tools"]
                        else:
                            return []
                elif response.status_code == 406:
                    # Сервер не поддерживает SSE, используем fallback
                    return await self.list_tools_fallback()
                else:
                    return []
                    
        except Exception as e:
            return []
    
    async def list_tools_fallback(self) -> Optional[List[Dict]]:
        """Fallback метод для получения списка инструментов без SSE"""
        if not self.enabled:
            return None
        
        try:
            request_data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.url}/",
                    json=request_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "result" in result and "tools" in result["result"]:
                        return result["result"]["tools"]
                    else:
                        return []
                else:
                    return []
                    
        except Exception as e:
            return []
    
    async def get_server_info(self) -> Optional[Dict]:
        """Получает информацию о MCP сервере"""
        if not self.enabled:
            return None
        
        try:
            request_data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "ai-chat-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "text/event-stream"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.url}/",
                    json=request_data,
                    headers=headers
                )
                
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    if "text/event-stream" in content_type:
                        return await self._process_sse_response(response)
                    else:
                        result = response.json()
                        if "result" in result:
                            return result["result"]
                        else:
                            return {}
                elif response.status_code == 406:
                    # Сервер не поддерживает SSE, используем fallback
                    return await self.get_server_info_fallback()
                else:
                    return {}
                    
        except Exception as e:
            return {}
    
    async def get_server_info_fallback(self) -> Optional[Dict]:
        """Fallback метод для получения информации о сервере без SSE"""
        if not self.enabled:
            return None
        
        try:
            request_data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "ai-chat-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.url}/",
                    json=request_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "result" in result:
                        return result["result"]
                    else:
                        return {}
                else:
                    return {}
                    
        except Exception as e:
            return {}

class MCPManager:
    """Менеджер для управления всеми MCP серверами"""
    
    def __init__(self):
        self.clients = {}
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Инициализирует все MCP клиенты"""
        mcp_config = config.get_mcp_config()
        
        for server_name, server_config in mcp_config.items():
            if server_config.get("enabled", False):
                self.clients[server_name] = MCPClient(server_name, server_config)
    
    async def get_available_servers(self) -> List[str]:
        """Возвращает список доступных MCP серверов"""
        available = []
        for name, client in self.clients.items():
            if await client.is_available():
                available.append(name)
        return available
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
        """Вызывает инструмент на указанном MCP сервере"""
        if server_name not in self.clients:
            return {"error": f"MCP сервер {server_name} не найден"}
        
        client = self.clients[server_name]
        return await client.call_tool(tool_name, arguments)
    
    async def list_server_tools(self, server_name: str) -> Optional[List[Dict]]:
        """Получает список инструментов указанного сервера"""
        if server_name not in self.clients:
            return []
        
        client = self.clients[server_name]
        return await client.list_tools()
    
    async def get_server_info(self, server_name: str) -> Optional[Dict]:
        """Получает информацию о сервере"""
        if server_name not in self.clients:
            return {}
        
        client = self.clients[server_name]
        return await client.get_server_info()
    
    async def get_all_tools(self) -> Dict[str, List[Dict]]:
        """Получает список всех инструментов всех серверов"""
        all_tools = {}
        for server_name in self.clients.keys():
            tools = await self.list_server_tools(server_name)
            if tools:
                all_tools[server_name] = tools
        return all_tools

# Глобальный экземпляр менеджера MCP
mcp_manager = MCPManager()
