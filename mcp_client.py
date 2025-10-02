import asyncio
import json
import aiohttp
from typing import Dict, Any, Optional, List
from config import config

class MCPClient:
    """Универсальный MCP клиент для работы через streamable HTTP API"""
    
    def __init__(self, name: str, server_config: Dict[str, Any]):
        self.name = name
        self.config = server_config
        self.url = server_config.get("url", "http://localhost:3000")
        self.enabled = server_config.get("enabled", False)
        self.session_id = None
        self.server_info = None
        self._initialized = False
    
    async def is_available(self) -> bool:
        """Проверяет доступность MCP сервера"""
        if not self.enabled:
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.url}/health", timeout=5.0) as response:
                    return response.status == 200
        except:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.url}/", timeout=5.0) as response:
                        return True
            except:
                return False
    
    async def send_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Отправка запроса к MCP серверу"""
        if not self.enabled:
            return {"error": f"MCP сервер {self.name} отключен"}
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": method,
                    "params": params or {}
                }
                
                async with session.post(
                    f"{self.url}/",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    return await response.json()
        except Exception as e:
            return {"error": f"Ошибка подключения к {self.name}: {str(e)}"}

    async def initialize(self, client_name: str = "python-client"):
        """Инициализация сессии (кэшируется)"""
        if self._initialized and self.server_info:
            return {"result": self.server_info}
        
        result = await self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": client_name, "version": "1.0.0"}
        })
        
        if "result" in result:
            self.session_id = result.get("result", {}).get("sessionId")
            self.server_info = result["result"]
            self._initialized = True
        
    async def ensure_initialized(self):
        """Убеждается, что клиент инициализирован"""
        if not self._initialized:
            await self.initialize()

    async def tools_list(self):
        """Получение списка доступных инструментов"""
        return await self.send_request("tools/list")

    async def tools_call(self, tool_name: str, arguments: Dict[str, Any]):
        """Вызов инструмента"""
        return await self.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })

    async def resources_list(self):
        """Получение списка ресурсов"""
        return await self.send_request("resources/list")

    async def resources_read(self, uri: str):
        """Чтение ресурса"""
        return await self.send_request("resources/read", {"uri": uri})



class MCPManager:
    """Менеджер для управления всеми MCP серверами"""
    
    def __init__(self):
        self.clients = {}
        self._initialized = False
    
    async def initialize(self):
        """Инициализирует все MCP клиенты асинхронно"""
        if self._initialized:
            return
        
        mcp_config = config.get_mcp_config()
        
        for server_name, server_config in mcp_config.items():
            if server_config.get("enabled", False):
                client = MCPClient(server_name, server_config)
                self.clients[server_name] = client
                # Инициализируем клиент сразу
                await client.initialize()
        
        self._initialized = True
    
    async def get_available_servers(self) -> List[str]:
        """Возвращает список доступных MCP серверов"""
        await self.initialize()
        available = []
        for name, client in self.clients.items():
            if await client.is_available():
                available.append(name)
        return available
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
        """Вызывает инструмент на указанном MCP сервере"""
        await self.initialize()
        
        if server_name not in self.clients:
            return {"error": f"MCP сервер {server_name} не найден"}
        
        client = self.clients[server_name]
        result = await client.tools_call(tool_name, arguments or {})
        
        # Извлекаем результат из JSON-RPC ответа
        if "result" in result:
            return result["result"]
        elif "error" in result:
            return {"error": result["error"]}
        else:
            return result
    
    async def list_server_tools(self, server_name: str) -> Optional[List[Dict]]:
        """Получает список инструментов указанного сервера"""
        await self.initialize()
        
        if server_name not in self.clients:
            return []
        
        client = self.clients[server_name]
        result = await client.tools_list()
        
        # Извлекаем список инструментов из JSON-RPC ответа
        if "result" in result and "tools" in result["result"]:
            return result["result"]["tools"]
        else:
            return []
    
    async def get_server_info(self, server_name: str) -> Optional[Dict]:
        """Получает информацию о сервере (использует кэш)"""
        await self.initialize()
        
        if server_name not in self.clients:
            return {}
        
        client = self.clients[server_name]
        # Возвращаем кэшированную информацию
        return client.server_info or {}
    
    async def get_all_tools(self) -> Dict[str, List[Dict]]:
        """Получает список всех инструментов всех серверов"""
        await self.initialize()
        
        all_tools = {}
        for server_name in self.clients.keys():
            tools = await self.list_server_tools(server_name)
            if tools:
                all_tools[server_name] = tools
        return all_tools

# Глобальный экземпляр менеджера MCP
mcp_manager = MCPManager()
