import logging
import re

class ModerationService:
    
    TOXIC_WORDS = [
        'сука', 'бля', 'блять', 'хуй', 'хую', 'хуя', 'пизда', 'пиздец',
        'нахуй', 'ебать', 'ёбать', 'ебаный', 'ебанный', 'ебанутый',
        'мудак', 'дебил', 'идиот', 'тупой', 'урод', 'гандон', 'шлюха',
        'проститутка', 'cock', 'fuck', 'shit', 'bitch', 'dick', 'asshole',
        'damn', 'хрен', 'фиг', 'черт', 'блин', 'залупа', 'манда', 'пидор',
        'гомик', 'лох', 'редиска', 'козел', 'осел', 'сволочь', 'стерва'
    ]
    
    @staticmethod
    async def check_event_content(title: str, description: str) -> dict:
        """
        Проверка содержимого события
        Возвращает:
            "published" - можно публиковать сразу
            "pending" - требует ручной модерации  
            "rejected" - автоматически отклонить
        """
        full_text = f"{title} {description}".lower()
        
        found_words = []
        for word in ModerationService.TOXIC_WORDS:
            if word.lower() in full_text:
                found_words.append(word)
        
        unique_words = list(set(found_words))
        
        if unique_words:
            logging.warning(f"Обнаружен мат в событии: {unique_words}")
            return {
                "action": "rejected",
                "reason": f"Обнаружены запрещённые слова: {', '.join(unique_words[:5])}",
                "found_words": unique_words
            }
        
        if len(title) < 3:
            return {
                "action": "pending",
                "reason": "Слишком короткое название (нужно минимум 3 символа)",
                "found_words": []
            }
        
        if len(description) < 10:
            return {
                "action": "pending",
                "reason": "Слишком короткое описание (нужно минимум 10 символов)",
                "found_words": []
            }
        
        if re.search(r'[<>{}[\]()]', full_text):
            return {
                "action": "pending",
                "reason": "Обнаружены подозрительные символы",
                "found_words": []
            }
        
        logging.info(f"Событие прошло проверку: title={title[:30]}")
        return {
            "action": "published",
            "reason": None,
            "found_words": []
        }
    
    @staticmethod
    async def check_profile_content(description: str) -> dict:
        """
        Проверка содержимого анкеты
        Возвращает:
            "published" - можно публиковать сразу
            "pending" - требует ручной модерации  
            "rejected" - автоматически отклонить
        """
        text_lower = description.lower()
        
        found_words = []
        for word in ModerationService.TOXIC_WORDS:
            if word.lower() in text_lower:
                found_words.append(word)
        
        unique_words = list(set(found_words))
        
        if unique_words:
            logging.warning(f"Обнаружен мат в анкете: {unique_words}")
            return {
                "action": "rejected",
                "reason": f"Обнаружены запрещённые слова: {', '.join(unique_words[:5])}",
                "found_words": unique_words
            }
        
        if len(description) < 20:
            return {
                "action": "pending",
                "reason": "Слишком короткое описание (нужно минимум 20 символов)",
                "found_words": []
            }
        
        if len(description) > 1000:
            return {
                "action": "pending",
                "reason": "Слишком длинное описание (максимум 1000 символов)",
                "found_words": []
            }
        
        if re.search(r'[<>{}[\]()]', text_lower):
            return {
                "action": "pending",
                "reason": "Обнаружены подозрительные символы",
                "found_words": []
            }
        
        logging.info(f"Анкета прошла проверку: description={description[:30]}")
        return {
            "action": "published",
            "reason": None,
            "found_words": []
        }
    
    @staticmethod
    async def check_user_message(message_text: str) -> dict:
        """Проверка сообщения пользователя на мат"""
        message_lower = message_text.lower()
        
        found_words = []
        for word in ModerationService.TOXIC_WORDS:
            if word.lower() in message_lower:
                found_words.append(word)
        
        if found_words:
            return {
                "is_toxic": True,
                "toxicity_score": min(0.3 + len(found_words) * 0.1, 1.0),
                "is_safe": False,
                "found_words": list(set(found_words))
            }
        
        return {
            "is_toxic": False,
            "toxicity_score": 0.0,
            "is_safe": True,
            "found_words": []
        }