import asyncio
import json
from typing import Dict, Any, Optional, List
from config import config
import aiohttp
from fastmcp import Client

class MCPClient:
    """MCP клиент с архитектурой FastMCP"""
    
    def __init__(self, name: str, server_config: Dict[str, Any]):
        self.name = name
        self.config = server_config
        self.url = server_config.get("url", "http://localhost:3000")
        self.enabled = server_config.get("enabled", False)
        self._initialized = False
        self.mcp_client = None
    
    async def ensure_initialized(self):
        """Убеждается, что клиент инициализирован"""
        if not self._initialized:
            await self.mcp_client.is_connected()
    
    async def list_tools(self):
        """Получение списка доступных инструментов"""
        try:
            return await self.mcp_client.list_tools()
        except Exception as e:
            return {"error": f"Ошибка получения инструментов {self.name}: {str(e)}"}
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]):
        """Вызов инструмента"""
        try:
            return await self.mcp_client.tools.call(tool_name, arguments)
        except Exception as e:
            return {"error": f"Ошибка вызова инструмента {tool_name} на {self.name}: {str(e)}"}
    
    async def list_resources(self):
        """Получение списка ресурсов"""
        try:
            return await self.mcp_client.list_resources()
        except Exception as e:
            return {"error": f"Ошибка получения ресурсов {self.name}: {str(e)}"}
    
    async def read_resource(self, uri: str):
        """Чтение ресурса"""
        try:
            return await self.mcp_client.read_resource(uri)
        except Exception as e:
            return {"error": f"Ошибка чтения ресурса {uri} на {self.name}: {str(e)}"}
    
    async def initialize(self):
        """Инициализация MCP клиента"""
        if not self._initialized:
            self.mcp_client = Client(self.name)
            await self.mcp_client.is_connected()
            self._initialized = True
    
    async def is_available(self) -> bool:
        """Проверяет доступность MCP сервера"""
        if not self.enabled:
            return False
        
        try:
            if not self._initialized:
                await self.initialize()
            return await self.mcp_client.is_connected()
        except:
            return False
    
    async def close(self):
        """Закрытие соединения"""
        if self.mcp_client:
            await self.mcp_client.close()
            self.mcp_client = None
            self._initialized = False


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
        result = await client.call_tool(tool_name, arguments or {})
        
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
        result = await client.list_tools()
        
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
    
    async def close_all(self):
        """Закрывает все соединения"""
        for client in self.clients.values():
            await client.close()
        self.clients.clear()
        self._initialized = False

# Глобальный экземпляр менеджера MCP
mcp_manager = MCPManager()