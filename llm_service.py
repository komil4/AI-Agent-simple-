import asyncio
import json
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from config import config
from mcp_client import mcp_manager

class LLMService:
    """Сервис для работы с LLM"""
    
    def __init__(self):
        self.llm_config = config.get_llm_config()
        self.client = AsyncOpenAI(
            api_key=self.llm_config.get("api_key"),
            base_url=self.llm_config.get("base_url")
        )
        self.model = self.llm_config.get("model", "gpt-3.5-turbo")
        self.temperature = self.llm_config.get("temperature", 0.7)
        self.max_tokens = self.llm_config.get("max_tokens", 1000)
    
    async def generate_response(self, messages: List[Dict[str, str]], mcp_context: Optional[Dict] = None) -> str:
        """Генерирует ответ от LLM с учетом контекста MCP"""
        
        # Добавляем системное сообщение с информацией о доступных MCP серверах
        system_message = self._create_system_message(mcp_context)
        
        # Формируем сообщения для LLM
        llm_messages = [{"role": "system", "content": system_message}] + messages
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=llm_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            return response.choices[0].message.content
        except Exception as e:
            return f"Ошибка при обращении к LLM: {str(e)}"
    
    def _create_system_message(self, mcp_context: Optional[Dict] = None) -> str:
        """Создает системное сообщение с информацией о доступных MCP серверах"""
        system_prompt = """Вы - полезный AI ассистент, который может работать с различными системами через MCP (Model Context Protocol) серверы.

Доступные MCP серверы:
- GitLab: для работы с проектами и задачами GitLab
- Atlassian: объединенный сервер для работы с Jira и Confluence
- Active Directory: для работы с пользователями и группами AD

Если пользователь просит информацию из этих систем, используйте соответствующие MCP команды:
- Для GitLab: get_projects, get_issues
- Для Jira: get_jira_projects, get_jira_issues
- Для Confluence: get_confluence_spaces, get_confluence_pages
- Для Active Directory: get_users, get_groups

Отвечайте на русском языке, если пользователь пишет на русском."""
        
        if mcp_context:
            system_prompt += f"\n\nКонтекст MCP серверов: {json.dumps(mcp_context, ensure_ascii=False)}"
        
        return system_prompt
    
    async def process_message_with_mcp(self, user_message: str) -> Dict[str, Any]:
        """Обрабатывает сообщение пользователя с использованием MCP серверов"""
        
        # Проверяем доступные MCP серверы
        available_servers = await mcp_manager.get_available_servers()
        
        # Анализируем сообщение на предмет запросов к MCP серверам
        mcp_requests = self._analyze_message_for_mcp_requests(user_message)
        
        mcp_results = {}
        
        # Выполняем запросы к MCP серверам
        for server_name, command, params in mcp_requests:
            if server_name in available_servers:
                result = await mcp_manager.execute_mcp_command(server_name, command, params)
                mcp_results[f"{server_name}_{command}"] = result
        
        # Формируем контекст для LLM
        mcp_context = {
            "available_servers": available_servers,
            "mcp_results": mcp_results
        }
        
        # Генерируем ответ от LLM
        messages = [{"role": "user", "content": user_message}]
        llm_response = await self.generate_response(messages, mcp_context)
        
        return {
            "response": llm_response,
            "mcp_context": mcp_context,
            "available_servers": available_servers
        }
    
    def _analyze_message_for_mcp_requests(self, message: str) -> List[tuple]:
        """Анализирует сообщение и определяет необходимые запросы к MCP серверам"""
        requests = []
        message_lower = message.lower()
        
        # Простой анализ ключевых слов для определения нужных MCP запросов
        if any(word in message_lower for word in ["gitlab", "git", "проект", "репозиторий"]):
            requests.append(("gitlab", "get_projects", {}))
        
        if any(word in message_lower for word in ["jira", "задача", "тикет", "баг"]):
            requests.append(("atlassian", "get_jira_issues", {"jql": ""}))
        
        if any(word in message_lower for word in ["confluence", "документ", "страница", "wiki"]):
            requests.append(("atlassian", "get_confluence_spaces", {}))
        
        if any(word in message_lower for word in ["пользователь", "группа", "ad", "active directory"]):
            requests.append(("activedirectory", "get_users", {}))
        
        return requests

# Глобальный экземпляр сервиса LLM
llm_service = LLMService()
