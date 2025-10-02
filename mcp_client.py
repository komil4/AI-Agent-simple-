import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from config import config
import aiohttp
from fastmcp import Client

class MCPClient:
    """MCP клиент с использованием FastMCP Client"""
    
    def __init__(self, name: str, server_config: Dict[str, Any]):
        self.name = name
        self.config = server_config
        self.url = server_config.get("url", "http://localhost:3000")
        self.enabled = server_config.get("enabled", False)
        self._initialized = False
        self._tools_cache = None
        self._cache_time = 0
        self._resources_cache = None
        self._resources_cache_time = 0
        self._cache_ttl = 300
        self.client = Client(self.url)
    
    async def ensure_initialized(self):
        """Убеждается, что клиент инициализирован"""
        if not self._initialized:
            await self.initialize()
    
    async def list_tools(self):
        """Получение списка доступных инструментов с кэшированием"""
        try:
            # Проверяем кэш
            if self._tools_cache and time.time() - self._cache_time < self._cache_ttl:
                return self._tools_cache
            
            # Получаем данные
            async with self.client:
                result = await self.client.list_tools()
                self._tools_cache = result
                self._cache_time = time.time()
                return result
        except Exception as e:
            return {"error": f"Ошибка получения инструментов {self.name}: {str(e)}"}
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]):
        """Вызов инструмента"""
        try:
            async with self.client:
                return await self.client.call_tool(tool_name, arguments)
        except Exception as e:
            return {"error": f"Ошибка вызова инструмента {tool_name} на {self.name}: {str(e)}"}
    
    async def list_resources(self):
        """Получение списка ресурсов с кэшированием"""
        try:
            # Проверяем кэш ресурсов
            if hasattr(self, '_resources_cache') and self._resources_cache and time.time() - self._resources_cache_time < self._cache_ttl:
                return self._resources_cache
            
            # Получаем данные
            async with self.client:
                result = await self.client.list_resources()
                self._resources_cache = result
                self._resources_cache_time = time.time()
                return result
        except Exception as e:
            return {"error": f"Ошибка получения ресурсов {self.name}: {str(e)}"}
    
    async def initialize(self):
        """Инициализация MCP клиента - проверяет возможность подключения"""
        if not self.enabled:
            self._initialized = False
            return False
        
        try:
            # Проверяем подключение
            async with self.client:
                self._initialized = self.client.is_connected()
                return self._initialized
        except Exception as e:
            self._initialized = False
            return False
    
    async def is_available(self) -> bool:
        """Проверяет доступность MCP сервера"""
        if not self.enabled:
            return False
        
        try:
            async with self.client:
                return self.client.is_connected()
        except:
            return False 
    
    async def get_cache_stats(self):
        """Получение статистики кэша"""
        current_time = time.time()
        stats = {
            "tools_cache": {
                "cached": self._tools_cache is not None,
                "age": current_time - self._cache_time if self._cache_time > 0 else 0,
                "ttl": self._cache_ttl
            },
            "resources_cache": {
                "cached": self._resources_cache is not None,
                "age": current_time - self._resources_cache_time if self._resources_cache_time > 0 else 0,
                "ttl": self._cache_ttl
            }
        }
        return stats
    
    async def clear_cache(self):
        """Очистка всех кэшей"""
        self._tools_cache = None
        self._cache_time = 0
        self._resources_cache = None
        self._resources_cache_time = 0
        return {"status": "cache_cleared"}


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
        """Получает информацию о сервере"""
        await self.initialize()
        
        if server_name not in self.clients:
            return {}
        
        client = self.clients[server_name]
        try:
            # Получаем информацию от сервера
            server_info = await client.get_server_info()
            if "error" not in server_info:
                return server_info
            
            # Fallback к базовой информации
            return {
                "name": client.name,
                "url": client.url,
                "enabled": client.enabled,
                "initialized": client._initialized
            }
        except Exception as e:
            return {"error": f"Ошибка получения информации о сервере {server_name}: {str(e)}"}
    
    
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