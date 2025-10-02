import json
import os
from typing import Dict, Any, Optional
from pydantic import BaseModel

class Config:
    def __init__(self, config_path: str = "config.demo.json"):
        self.config_path = config_path
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Загружает конфигурацию из JSON файла"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Файл конфигурации {self.config_path} не найден")
        except json.JSONDecodeError as e:
            raise ValueError(f"Ошибка в формате JSON файла конфигурации: {e}")
    
    def get_llm_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию LLM"""
        return self._config.get("llm", {})
    
    def get_mcp_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию MCP серверов"""
        return self._config.get("mcp_servers", {})
    
    def get_server_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию сервера"""
        return self._config.get("server", {})
    
    def get_mcp_server_config(self, server_name: str) -> Optional[Dict[str, Any]]:
        """Возвращает конфигурацию конкретного MCP сервера"""
        mcp_config = self.get_mcp_config()
        return mcp_config.get(server_name)
    
    def is_mcp_enabled(self, server_name: str) -> bool:
        """Проверяет, включен ли MCP сервер"""
        server_config = self.get_mcp_server_config(server_name)
        return server_config and server_config.get("enabled", False)

# Глобальный экземпляр конфигурации
config = Config()
