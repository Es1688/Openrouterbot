"""
Модуль API для OpenRouter (OpenAI-совместимый).
Функции: validate_api_key (проверка ключа), get_balance (/credits), pick_models_in_order, chat_completion.
Использует requests. Логирование INFO для debug. Sanitization headers (фикс UnicodeEncodeError).
Изменено: УБРАНА загрузка списка моделей и цен. Используются ТОЛЬКО модели из .env.
Добавлено: try/except вокруг requests, логирование вызовов/ошибок с traceback.
Изменено: УБРАН расчет стоимости. В chat_completion возвращается только количество токенов.
"""

import logging
import re
import json  # Для обработки JSONDecodeError
import requests
from typing import Dict, Any, List, Optional, Union

from config import config

logger = logging.getLogger(__name__)

BASE_URL: str = "https://openrouter.ai/api/v1"
SITE_URL: str = "https://openrouter.ai"


def _get_headers(api_key: str, app_url: str = "", app_name: str = "") -> Dict[str, str]:
    """Возвращает headers для OpenRouter. Sanitize non-ASCII в app_url/app_name (фикс UnicodeEncodeError)."""
    headers: Dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    if app_url:
        sanitized_url: str = re.sub(r'[^\x00-\x7F]', '', app_url)
        if sanitized_url != app_url:
            logger.warning(f"Sanitized app_url: '{app_url}' → '{sanitized_url}' (non-ASCII removed)")
        headers["HTTP-Referer"] = sanitized_url
    if app_name:
        sanitized_name: str = re.sub(r'[^\x00-\x7F]', '', app_name)
        if sanitized_name != app_name:
            logger.warning(f"Sanitized app_name: '{app_name}' → '{sanitized_name}' (non-ASCII removed)")
        headers["X-Title"] = sanitized_name
    return headers


def pick_models_in_order(paid_model_1: str, paid_model_2: str, free_model: str, mode: str) -> List[str]:
    """
    Возвращает список моделей по mode: paid1=[paid1, paid2, free], paid2=[paid2, paid1, free], free=[free], default=paid1.
    Использует config для реальных ID.
    """
    if mode == "free":
        return [config.free_model]
    elif mode == "paid2":
        return [config.paid_model_2, config.paid_model_1, config.free_model]
    elif mode == "paid1":
        return [config.paid_model_1, config.paid_model_2, config.free_model]
    else:
        logger.warning(f"Invalid mode '{mode}', default to paid1")
        return [config.paid_model_1, config.paid_model_2, config.free_model]


def validate_api_key(api_key: str, app_url: str = "", app_name: str = "") -> Dict[str, Union[bool, float]]:
    """
    Валидирует API key: GET /models (200=valid, 401=invalid, 402=valid but no credits).
    Затем GET /credits для balance. Возвращает {'valid': bool, 'balance': float}.
    """
    if not api_key or not api_key.startswith("sk-or-v1-"):
        logger.warning("Invalid API key format")
        return {"valid": False, "balance": 0.0}
    
    url: str = f"{BASE_URL}/models"
    headers: Dict[str, str] = _get_headers(api_key, app_url, app_name)
    
    try:
        logger.info(f"Validating API key via GET {url}")
        response = requests.get(url, headers=headers, timeout=10)
        logger.info(f"Validate key via /models: status={response.status_code}")
        if response.status_code == 200:
            logger.info("Key valid via /models")
        elif response.status_code == 401:
            logger.error("API key invalid (401)")
            return {"valid": False, "balance": 0.0}
        elif response.status_code == 402:
            logger.warning("Key valid but insufficient credits (402) — free models may work")
        else:
            logger.error(f"Validate error: {response.status_code}, {response.text[:200]}")
            return {"valid": False, "balance": 0.0}
    except requests.RequestException as e:
        logger.exception(f"Validate request error: {e}")
        return {"valid": False, "balance": 0.0}
    except Exception as e:
        logger.exception(f"Unexpected error in validate_api_key: {e}")
        return {"valid": False, "balance": 0.0}
    
    # Balance via /credits
    balance_info: Optional[Dict[str, float]] = get_balance(api_key, app_url, app_name)
    balance: float = balance_info.get("balance", 0.0) if balance_info else 0.0
    return {"valid": True, "balance": balance}


def get_balance(api_key: str, app_url: str = "", app_name: str = "") -> Optional[Dict[str, float]]:
    """
    Получает баланс: GET /credits (total_credits, total_usage, balance=credits-usage).
    OpenRouter возвращает данные внутри поля 'data'.
    """
    url: str = f"{BASE_URL}/credits"
    headers: Dict[str, str] = _get_headers(api_key, app_url, app_name)
    try:
        logger.info(f"Fetching balance via GET {url}")
        response = requests.get(url, headers=headers, timeout=10)
        logger.info(f"Balance request: status={response.status_code}")
        if response.status_code == 200:
            data: Dict[str, Any] = response.json()
            # <<< ИСПРАВЛЕНИЕ: данные внутри 'data' >>>
            balance_data = data.get("data", {})
            creds: float = float(balance_data.get("total_credits", 0.0))
            usage: float = float(balance_data.get("total_usage", 0.0))
            result = {"total_credits": creds, "total_usage": usage, "balance": creds - usage}
            logger.info(f"Balance fetched: ${result['balance']:.2f}")
            return result
        else:
            logger.warning(f"Balance error: {response.status_code}, {response.text[:200]}")
            return None
    except requests.RequestException as e:
        logger.exception(f"Balance request error: {e}")
        return None
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.exception(f"Balance parse error: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error in get_balance: {e}")
        return None


def chat_completion(
    messages: List[Dict[str, str]],
    mode: str,
    api_key: str,
    app_url: str = "",
    app_name: str = "",
    max_tokens: int = 1024,
    temperature: float = 0.7
) -> Dict[str, Any]:
    """
    Выполняет chat completion: POST /chat/completions с fallback (mode → list моделей, "route": "fallback").
    Использует ТОЛЬКО модели из .env. Стоимость НЕ рассчитывается — возвращаются только токены.
    """
    if not messages:
        raise ValueError("No messages provided")
    
    model_list: List[str] = pick_models_in_order(config.paid_model_1, config.paid_model_2, config.free_model, mode)
    
    url: str = f"{BASE_URL}/chat/completions"
    headers: Dict[str, str] = _get_headers(api_key, app_url, app_name)
    
    body: Dict[str, Any] = {
        "models": model_list,
        "route": "fallback",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False
    }
    
    try:
        logger.info(f"Chat completion call: mode={mode}, models={model_list}, messages_count={len(messages)}")
        response = requests.post(url, headers=headers, json=body, timeout=30)
        logger.info(f"Chat completion response: status={response.status_code}, models={model_list}")
        
        if response.status_code == 200:
            try:
                data: Dict[str, Any] = response.json()
                choice: Dict[str, Any] = data["choices"][0]
                content: str = choice["message"]["content"]
                # Используем первую модель как used_model (без fallback-логики)
                used_model: str = model_list[0]
                usage: Dict[str, int] = data.get("usage", {})
                total_tokens: int = usage.get("total_tokens", 0)
                
                # Стоимость НЕ рассчитывается и НЕ возвращается
                logger.info(f"Chat success: used_model={used_model}, tokens={total_tokens}")
                return {
                    "content": content,
                    "tokens": total_tokens,
                    "used_model": used_model
                }
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                logger.exception(f"Response parse error in chat_completion: {e}, raw_response={response.text[:200]}")
                raise ValueError("Invalid API response format")
        elif response.status_code == 401:
            logger.error(f"Chat error 401: Invalid API key")
            raise ValueError("Invalid API key")
        elif response.status_code == 402:
            logger.warning(f"Chat error 402: Insufficient credits — fallback to free model (/setmodel free)")
            raise ValueError("Insufficient credits — fallback to free model (/setmodel free)")
        elif response.status_code == 404:
            try:
                error_data: Dict[str, Any] = response.json()
                error_msg: str = error_data.get("error", {}).get("message", "Model not found")
            except json.JSONDecodeError:
                error_msg: str = response.text[:200]
            logger.error(f"Chat error: 404, {error_msg}")
            raise ValueError(f"Invalid model ID (404): {error_msg}. Проверьте .env (e.g., PAID_MODEL_1=google/gemini-2.5-pro).")
        elif response.status_code == 429:
            logger.warning(f"Chat error 429: Rate limit — try later")
            raise ValueError("Rate limit — try later")
        elif response.status_code == 400:
            try:
                error_data: Dict[str, Any] = response.json()
                error_msg: str = error_data.get("error", {}).get("message", "Unknown")
            except json.JSONDecodeError:
                error_msg: str = response.text[:200]
            logger.error(f"Chat error: 400, {error_msg}")
            raise ValueError(f"Bad request: {error_msg}")
        else:
            logger.error(f"Chat error: {response.status_code}, {response.text[:200]}")
            raise ValueError(f"API error: {response.status_code}")
    except requests.RequestException as e:
        logger.exception(f"Chat request error (network/timeout): {e}")
        raise ValueError(f"Network error: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error in chat_completion: {e}")
        raise ValueError("Internal API error")

