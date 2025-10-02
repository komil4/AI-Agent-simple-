import asyncio
import json
import httpx
from typing import Dict, Any, Optional, List
from config import config

class MCPServer:
    """Базовый класс для работы с MCP серверами"""
    
    def __init__(self, name: str, server_config: Dict[str, Any]):
        self.name = name
        self.config = server_config
        self.host = server_config.get("host", "localhost")
        self.port = server_config.get("port", 3000)
        self.base_url = f"http://{self.host}:{self.port}"
        self.enabled = server_config.get("enabled", False)
    
    async def is_available(self) -> bool:
        """Проверяет доступность MCP сервера"""
        if not self.enabled:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except:
            return False
    
    async def send_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """Отправляет запрос к MCP серверу"""
        if not self.enabled:
            return None
        
        try:
            # Подготавливаем заголовки для аутентификации
            headers = await self._prepare_auth_headers()
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{self.base_url}{endpoint}"
                
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers)
                elif method.upper() == "POST":
                    response = await client.post(url, json=data, headers=headers)
                elif method.upper() == "PUT":
                    response = await client.put(url, json=data, headers=headers)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    return None
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"error": f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            return {"error": f"Ошибка подключения к {self.name}: {str(e)}"}
    
    async def _prepare_auth_headers(self) -> Dict[str, str]:
        """Подготавливает заголовки аутентификации для конкретного сервера"""
        headers = {"Content-Type": "application/json"}
        
        if self.name == "gitlab" and hasattr(self, 'token') and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.name == "jira" and hasattr(self, 'api_token') and hasattr(self, 'email'):
            if self.api_token and self.email:
                import base64
                credentials = f"{self.email}:{self.api_token}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()
                headers["Authorization"] = f"Basic {encoded_credentials}"
        elif self.name == "confluence" and hasattr(self, 'api_token') and hasattr(self, 'email'):
            if self.api_token and self.email:
                import base64
                credentials = f"{self.email}:{self.api_token}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()
                headers["Authorization"] = f"Basic {encoded_credentials}"
        elif self.name == "activedirectory" and hasattr(self, 'username') and hasattr(self, 'password'):
            if self.username and self.password:
                headers["Authorization"] = f"Bearer {self.password}"  # Упрощенная аутентификация для AD
        
        return headers

class GitLabMCP(MCPServer):
    """MCP сервер для GitLab"""
    
    def __init__(self, server_config: Dict[str, Any]):
        super().__init__("gitlab", server_config)
        self.token = server_config.get("token")
        self.url = server_config.get("url")
    
    async def get_projects(self) -> Optional[Dict]:
        """Получает список проектов"""
        return await self.send_request("GET", "/api/v4/projects")
    
    async def get_issues(self, project_id: str) -> Optional[Dict]:
        """Получает список задач проекта"""
        return await self.send_request("GET", f"/api/v4/projects/{project_id}/issues")

class JiraMCP(MCPServer):
    """MCP сервер для Jira"""
    
    def __init__(self, server_config: Dict[str, Any]):
        super().__init__("jira", server_config)
        self.api_token = server_config.get("api_token")
        self.email = server_config.get("email")
        self.url = server_config.get("url")
    
    async def get_issues(self, jql: str = "") -> Optional[Dict]:
        """Получает список задач по JQL запросу"""
        data = {"jql": jql} if jql else {}
        return await self.send_request("POST", "/rest/api/2/search", data)
    
    async def get_projects(self) -> Optional[Dict]:
        """Получает список проектов"""
        return await self.send_request("GET", "/rest/api/2/project")

class ConfluenceMCP(MCPServer):
    """MCP сервер для Confluence"""
    
    def __init__(self, server_config: Dict[str, Any]):
        super().__init__("confluence", server_config)
        self.api_token = server_config.get("api_token")
        self.email = server_config.get("email")
        self.url = server_config.get("url")
    
    async def get_spaces(self) -> Optional[Dict]:
        """Получает список пространств"""
        return await self.send_request("GET", "/rest/api/space")
    
    async def get_pages(self, space_key: str) -> Optional[Dict]:
        """Получает список страниц в пространстве"""
        return await self.send_request("GET", f"/rest/api/content?spaceKey={space_key}")

class ActiveDirectoryMCP(MCPServer):
    """MCP сервер для Active Directory"""
    
    def __init__(self, server_config: Dict[str, Any]):
        super().__init__("activedirectory", server_config)
        self.domain = server_config.get("domain")
        self.username = server_config.get("username")
        self.password = server_config.get("password")
    
    async def get_users(self) -> Optional[Dict]:
        """Получает список пользователей"""
        return await self.send_request("GET", "/api/users")
    
    async def get_groups(self) -> Optional[Dict]:
        """Получает список групп"""
        return await self.send_request("GET", "/api/groups")

class MCPManager:
    """Менеджер для управления всеми MCP серверами"""
    
    def __init__(self):
        self.servers = {}
        self._initialize_servers()
    
    def _initialize_servers(self):
        """Инициализирует все MCP серверы"""
        mcp_config = config.get_mcp_config()
        
        if config.is_mcp_enabled("gitlab"):
            self.servers["gitlab"] = GitLabMCP(mcp_config["gitlab"])
        
        if config.is_mcp_enabled("jira"):
            self.servers["jira"] = JiraMCP(mcp_config["jira"])
        
        if config.is_mcp_enabled("confluence"):
            self.servers["confluence"] = ConfluenceMCP(mcp_config["confluence"])
        
        if config.is_mcp_enabled("activedirectory"):
            self.servers["activedirectory"] = ActiveDirectoryMCP(mcp_config["activedirectory"])
    
    async def get_available_servers(self) -> List[str]:
        """Возвращает список доступных MCP серверов"""
        available = []
        for name, server in self.servers.items():
            if await server.is_available():
                available.append(name)
        return available
    
    async def execute_mcp_command(self, server_name: str, command: str, params: Dict[str, Any]) -> Optional[Dict]:
        """Выполняет команду на указанном MCP сервере"""
        if server_name not in self.servers:
            return {"error": f"MCP сервер {server_name} не найден"}
        
        server = self.servers[server_name]
        
        if command == "get_projects":
            if isinstance(server, (GitLabMCP, JiraMCP)):
                return await server.get_projects()
        elif command == "get_issues":
            if isinstance(server, GitLabMCP):
                project_id = params.get("project_id")
                return await server.get_issues(project_id)
            elif isinstance(server, JiraMCP):
                jql = params.get("jql", "")
                return await server.get_issues(jql)
        elif command == "get_spaces":
            if isinstance(server, ConfluenceMCP):
                return await server.get_spaces()
        elif command == "get_pages":
            if isinstance(server, ConfluenceMCP):
                space_key = params.get("space_key")
                return await server.get_pages(space_key)
        elif command == "get_users":
            if isinstance(server, ActiveDirectoryMCP):
                return await server.get_users()
        elif command == "get_groups":
            if isinstance(server, ActiveDirectoryMCP):
                return await server.get_groups()
        
        return {"error": f"Команда {command} не поддерживается сервером {server_name}"}

# Глобальный экземпляр менеджера MCP
mcp_manager = MCPManager()
