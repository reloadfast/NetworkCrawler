"""Telegram message sender for Nightwatch digest and error alerts.

Handles sending messages to Telegram via the Bot API.
Includes auto-splitting for >4096 char messages.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot"
_MAX_MSG_LENGTH = 4096


def send_digest(
    bot_token: str,
    chat_id: str,
    message: str,
) -> bool:
    """Send a digest message to Telegram.
    
    Splits long messages (>4096 char) into connected messages.
    
    Args:
        bot_token: Telegram bot token.
        chat_id: Destination chat/group ID.
        message: Message text (may be >4096 chars, will be split).
        
    Returns:
        True if message(s) sent successfully, False otherwise.
    """
    chunks = _split_message_for_telegram(message)
    
    payload = {
        "chat_id": chat_id,
        "text": chunks[0],
        "parse_mode": "MarkdownV2",
    }
    
    url = f"{_TELEGRAM_API}{bot_token}/sendMessage"
    headers = {"Content-Type": "application/json"}
    
    for idx, chunk in enumerate(chunks):
        if idx > 0:
            payload["text"] = chunk
        
        try:
            r = httpx.post(url, json=payload, headers=headers, timeout=10)
            r.raise_for_status()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to send Telegram message: %s", exc)
            return False
    
    return False


def send_error(
    bot_token: str,
    chat_id: str,
    error_message: str,
) -> bool:
    """Send an error alert to Telegram.
    
    Args:
        bot_token: Telegram bot token.
        chat_id: Destination chat/group ID.
        error_message: Error message text.
        
    Returns:
        True if sent successfully, False otherwise.
    """
    payload = {
        "chat_id": chat_id,
        "text": f"*Nightwatch Error*\n\n{error_message}",
        "parse_mode": "MarkdownV2",
    }
    
    url = f"{_TELEGRAM_API}{bot_token}/sendMessage"
    headers = {"Content-Type": "application/json"}
    
    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=10)
        r.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to send Telegram error message: %s", exc)
        return False


def _split_message_for_telegram(text: str, chunk_size: int = _MAX_MSG_LENGTH) -> list[str]:
    """Split a message into Telegram-compatible chunks.
    
    Splits at newline boundaries to preserve formatting.
    
    Args:
        text: Input text to split.
        chunk_size: Maximum chunk size (default 4096).
        
    Returns:
        List of text chunks.
    """
    if len(text) <= chunk_size:
        return [text]

    # Split first at double newlines (paragraph breaks)
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 > chunk_size:
            if current:
                chunks.append(current)
            if len(para) <= chunk_size:
                chunks.append(para)
            else:
                # Split at character boundary
                sub_chunk = ""
                for char in para:
                    if len(sub_chunk) + len(char) > chunk_size:
                        if sub_chunk:
                            chunks.append(sub_chunk)
                        sub_chunk = ""
                    sub_chunk += char
                if sub_chunk:
                    chunks.append(sub_chunk)
            current = ""
        else:
            current = f"{current}\n\n{para}" if current else para

    if current:
        chunks.append(current)

    return chunks if chunks else [text]
