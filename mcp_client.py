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
        self._cache_ttl = 300  # 5 минут
    
    async def _with_client(self, operation):
        """Выполняет операцию с MCP клиентом"""
        try:
            async with Client(self.name) as mcp:
                await mcp.connect(self.url)
                return await operation(mcp)
        except Exception as e:
            return {"error": f"Ошибка подключения к {self.name}: {str(e)}"}
    
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
            result = await self._with_client(lambda mcp: mcp.list_tools())
            
            # Кэшируем результат
            if "error" not in result:
                self._tools_cache = result
                self._cache_time = time.time()
            
            return result
        except Exception as e:
            return {"error": f"Ошибка получения инструментов {self.name}: {str(e)}"}
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]):
        """Вызов инструмента"""
        try:
            return await self._with_client(lambda mcp: mcp.tools.call(tool_name, arguments))
        except Exception as e:
            return {"error": f"Ошибка вызова инструмента {tool_name} на {self.name}: {str(e)}"}
    
    async def list_resources(self):
        """Получение списка ресурсов с кэшированием"""
        try:
            # Проверяем кэш ресурсов
            if hasattr(self, '_resources_cache') and self._resources_cache and time.time() - self._resources_cache_time < self._cache_ttl:
                return self._resources_cache
            
            # Получаем данные
            result = await self._with_client(lambda mcp: mcp.list_resources())
            
            # Кэшируем результат
            if "error" not in result:
                self._resources_cache = result
                self._resources_cache_time = time.time()
            
            return result
        except Exception as e:
            return {"error": f"Ошибка получения ресурсов {self.name}: {str(e)}"}
    
    async def read_resource(self, uri: str):
        """Чтение ресурса"""
        try:
            return await self._with_client(lambda mcp: mcp.read_resource(uri))
        except Exception as e:
            return {"error": f"Ошибка чтения ресурса {uri} на {self.name}: {str(e)}"}
    
    async def initialize(self):
        """Инициализация MCP клиента - проверяет возможность подключения"""
        if not self.enabled:
            self._initialized = False
            return False
        
        try:
            # Проверяем подключение
            result = await self._with_client(lambda mcp: {"status": "connected"})
            self._initialized = "error" not in result
            return self._initialized
        except Exception as e:
            self._initialized = False
            return False
    
    async def is_available(self) -> bool:
        """Проверяет доступность MCP сервера"""
        if not self.enabled:
            return False
        
        try:
            result = await self._with_client(lambda mcp: {"status": "available"})
            return "error" not in result
        except:
            return False
    
    async def get_server_info(self):
        """Получение информации о сервере"""
        try:
            return await self._with_client(lambda mcp: mcp.get_server_info())
        except Exception as e:
            return {"error": f"Ошибка получения информации о сервере {self.name}: {str(e)}"}
    
    async def get_capabilities(self):
        """Получение возможностей сервера"""
        try:
            return await self._with_client(lambda mcp: mcp.get_capabilities())
        except Exception as e:
            return {"error": f"Ошибка получения возможностей сервера {self.name}: {str(e)}"}
    
    async def ping(self):
        """Проверка связи с сервером"""
        try:
            result = await self._with_client(lambda mcp: {"status": "pong", "timestamp": time.time()})
            return result
        except Exception as e:
            return {"error": f"Ошибка ping сервера {self.name}: {str(e)}"}
    
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
    
    async def ping_server(self, server_name: str) -> Dict[str, Any]:
        """Проверка связи с сервером"""
        await self.initialize()
        
        if server_name not in self.clients:
            return {"error": f"MCP сервер {server_name} не найден"}
        
        client = self.clients[server_name]
        return await client.ping()
    
    async def get_server_capabilities(self, server_name: str) -> Dict[str, Any]:
        """Получение возможностей сервера"""
        await self.initialize()
        
        if server_name not in self.clients:
            return {"error": f"MCP сервер {server_name} не найден"}
        
        client = self.clients[server_name]
        return await client.get_capabilities()
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Получение статистики кэша всех серверов"""
        await self.initialize()
        
        stats = {}
        for server_name, client in self.clients.items():
            stats[server_name] = await client.get_cache_stats()
        
        return stats
    
    async def clear_all_caches(self) -> Dict[str, Any]:
        """Очистка кэшей всех серверов"""
        await self.initialize()
        
        results = {}
        for server_name, client in self.clients.items():
            results[server_name] = await client.clear_cache()
        
        return results
    
    async def get_all_tools(self) -> Dict[str, List[Dict]]:
        """Получает список всех инструментов всех серверов"""
        await self.initialize()
        
        all_tools = {}
        for server_name in self.clients.keys():
            tools = await self.list_server_tools(server_name)
            if tools:
                all_tools[server_name] = tools
        return all_tools
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """Получение общей статистики системы"""
        await self.initialize()
        
        stats = {
            "total_servers": len(self.clients),
            "enabled_servers": sum(1 for client in self.clients.values() if client.enabled),
            "available_servers": 0,
            "servers": {}
        }
        
        for server_name, client in self.clients.items():
            is_available = await client.is_available()
            if is_available:
                stats["available_servers"] += 1
            
            stats["servers"][server_name] = {
                "enabled": client.enabled,
                "available": is_available,
                "initialized": client._initialized,
                "url": client.url
            }
        
        return stats
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья всех серверов"""
        await self.initialize()
        
        health_status = {
            "overall": "healthy",
            "servers": {},
            "issues": []
        }
        
        for server_name, client in self.clients.items():
            if not client.enabled:
                health_status["servers"][server_name] = "disabled"
                continue
            
            try:
                is_available = await client.is_available()
                if is_available:
                    health_status["servers"][server_name] = "healthy"
                else:
                    health_status["servers"][server_name] = "unavailable"
                    health_status["issues"].append(f"Сервер {server_name} недоступен")
            except Exception as e:
                health_status["servers"][server_name] = "error"
                health_status["issues"].append(f"Ошибка проверки сервера {server_name}: {str(e)}")
        
        # Определяем общий статус
        if health_status["issues"]:
            health_status["overall"] = "unhealthy"
        elif not any(status == "healthy" for status in health_status["servers"].values()):
            health_status["overall"] = "no_servers"
        
        return health_status
    
    async def close_all(self):
        """Закрывает все соединения"""
        for client in self.clients.values():
            await client.close()
        self.clients.clear()
        self._initialized = False

# Глобальный экземпляр менеджера MCP
mcp_manager = MCPManager()