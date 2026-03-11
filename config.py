# FILE: config.py
"""
Модуль конфигурации для OpenRouter Bot.
Загружает .env и определяет класс Config с валидацией.
Все модели задаются только в .env (дефолты пустые; валидация обязательна).
Соответствует README: модели из .env, бюджет в токенах, параметры чата.
"""

import os
import re
from dataclasses import dataclass, field
from typing import List
import json
import logging
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MAX_TOKENS_PER_DAY = 10000
DEFAULT_MAX_TOKENS = 8192
DEFAULT_CONTEXT_TURNS = 5
DEFAULT_TEMPERATURE = 0.2

logger = logging.getLogger(__name__)

@dataclass
class Config:
    """
    Конфигурация бота: API-ключи, модели, лимиты, авторизация.
    Автоматически загружает из .env (дефолты пустые для моделей — заполните .env!).
    """
    # OpenRouter (теперь опциональный)
    api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", "").strip())
    app_url: str = field(default_factory=lambda: os.getenv("APP_URL", "").strip())
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "OpenRouter Telegram Bot").strip())
    
    # Модели: только из .env (дефолты пустые; валидация в __post_init__)
    paid_model_1: str = field(default_factory=lambda: os.getenv("PAID_MODEL_1", ""))
    paid_model_2: str = field(default_factory=lambda: os.getenv("PAID_MODEL_2", ""))
    free_model: str = field(default_factory=lambda: os.getenv("FREE_MODEL", ""))
    
    # Лимиты
    max_tokens_per_day: int = field(
        default_factory=lambda: int(os.getenv("MAX_TOKENS_PER_DAY", str(DEFAULT_MAX_TOKENS_PER_DAY)))
    )
    max_tokens: int = field(default_factory=lambda: int(os.getenv("MAX_TOKENS", str(DEFAULT_MAX_TOKENS))))
    context_turns: int = field(default_factory=lambda: int(os.getenv("CONTEXT_TURNS", str(DEFAULT_CONTEXT_TURNS))))
    temperature: float = field(default_factory=lambda: float(os.getenv("TEMPERATURE", str(DEFAULT_TEMPERATURE))))
    
    # Telegram Bot
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", "").strip())
    
    # Авторизация
    admin_users: List[int] = field(
        default_factory=lambda: json.loads(os.getenv("ADMIN_USERS", "[]"))
    )
    authorized_users: List[int] = field(
        default_factory=lambda: json.loads(os.getenv("AUTHORIZED_USERS", "[]"))
    )

    def __post_init__(self):
        """Валидация после инициализации. Обязательны: bot_token + модели. api_key опционален (валидация в runtime)."""
        # Обязательный bot_token
        if not self.bot_token:
            raise ValueError("BOT_TOKEN обязателен для Telegram-бота! Получите у @BotFather и укажите в .env.")
        
        # Обязательные модели из .env
        if not self.paid_model_1:
            raise ValueError("PAID_MODEL_1 обязателен в .env! Пример: google/gemini-2.5-pro")
        if not self.paid_model_2:
            raise ValueError("PAID_MODEL_2 обязателен в .env! Пример: x-ai/grok-4-fast")
        if not self.free_model:
            raise ValueError("FREE_MODEL обязателен в .env! Пример: mistralai/devstral-2512:free (с :free для бесплатного tier)")

        # Логируем отсутствие API-ключа
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY не задан в .env! Бот запущен, но функции чата будут недоступны.")
        elif not self.api_key.startswith("sk-or-v1-"):
            logger.warning("OPENROUTER_API_KEY имеет неверный формат! Должен начинаться с 'sk-or-v1-'.")

        # Авторизация
        if not isinstance(self.admin_users, list) or not all(isinstance(uid, int) for uid in self.admin_users):
            raise ValueError("ADMIN_USERS должен быть JSON-списком целых чисел (Telegram user_id). Пример: [123456789]")
        if not isinstance(self.authorized_users, list) or not all(isinstance(uid, int) for uid in self.authorized_users):
            raise ValueError("AUTHORIZED_USERS должен быть JSON-списком целых чисел. Пример: [123456789, 987654321] (optional, default []).")
        
        # Sanitize non-ASCII
        if self.app_url:
            original_url = self.app_url
            self.app_url = re.sub(r'[^\x00-\x7F]', '', self.app_url)
            if self.app_url != original_url:
                logger.warning(f"Sanitized app_url: '{original_url}' → '{self.app_url}' (non-ASCII removed).")
        if self.app_name:
            original_name = self.app_name
            self.app_name = re.sub(r'[^\x00-\x7F]', '', self.app_name)
            if self.app_name != original_name:
                logger.warning(f"Sanitized app_name: '{original_name}' → '{self.app_name}' (non-ASCII removed).")
        
        # Проверки limits
        self.max_tokens = max(8, self.max_tokens)
        self.context_turns = max(0, self.context_turns)
        self.max_tokens_per_day = max(0, self.max_tokens_per_day)
        self.temperature = max(0.0, min(2.0, self.temperature))

    @classmethod
    def load(cls):
        return cls()

config = Config.load()
