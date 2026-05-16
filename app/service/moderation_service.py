import logging
import re

class ModerationService:
    
    TOXIC_PATTERNS = [
        # Базовые матерные слова
        r'(?i)(хуй|хуя|хую|хуём|хуе|хуи|хуёв)',
        r'(?i)(пизд|пиздец|пиздюк|пиздабол|спиздить|пиздануться|допиздеться)',
        r'(?i)(блядь|бляд|блядина|ёбля|блядство)',
        r'(?i)(ебал|ебать|ебаный|ёблан|долбоёб|ебанат|объебаться|ебашить|ебанутый)',
        r'(?i)(сука|сукин|сучий)',
        r'(?i)(мудак|мудило|мудозвон)',
        r'(?i)(гандон|гондон)',
        r'(?i)(шлюха|шлюш|проститутка)',
        r'(?i)(ссанина|ссать)',
        r'(?i)(дебил|идиот|тупой|урод)',
        
        # Производные от Хуй
        r'(?i)(хуйня|охуеть|хуесос|охуительный|дохуя|похуй|нахуй|охуенно)',
        
        # Производные от Пизда
        r'(?i)(пиздец|пиздюк|пиздабол|спиздить|пиздануться|допиздеться|пиздюлина)',
        
        # Производные от Блядь
        r'(?i)(блядство|блядина|ёбля|блядовать)',
        
        # Производные от Ебать
        r'(?i)(ебаный|ёблан|долбоёб|ебанат|объебаться|ебашить|ебак|ебало)',
        
        # Вариации с заменой букв
        r'(?i)(xуй|xуя|xую|xуёв)',
        r'(?i)(пuзд|пuздец)',
        r'(?i)(бля\*ь|бл\*ть|б\*\*\*ь)',
        r'(?i)(cук[а-я]|с\[email protected])',
        r'(?i)(п\[email protected]|п\[email protected])',
        r'(?i)(\[email protected]|\[email protected])',
        
        # Английские аналоги
        r'(?i)(fuck|shit|bitch|cunt|dick|asshole|cock|pussy|whore)',
        
        # Комбинации с точками и символами
        r'(?i)(х\.у\.й|б\.л\.я|п\.и\.з\.д)',
        r'(?i)([хx][уy][йи])',
        r'(?i)([б6][лl][яа])',
    ]
    
    @staticmethod
    async def check_event_content(title: str, description: str) -> dict:
        """Проверка содержимого события"""
        full_text = f"{title} {description}"
        
        found_words = []
        for pattern in ModerationService.TOXIC_PATTERNS:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            if matches:
                found_words.extend(matches)
        
        unique_words = list(set(found_words)) if found_words else []
        
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
        
        logging.info(f"Событие опубликовано автоматически: title={title[:30]}")
        return {
            "action": "published",
            "reason": None,
            "found_words": []
        }
    
    @staticmethod
    async def check_profile_content(description: str) -> dict:
        """Проверка содержимого анкеты - ВСЕ анкеты идут на модерацию, кроме мата"""
        
        found_words = []
        for pattern in ModerationService.TOXIC_PATTERNS:
            matches = re.findall(pattern, description, re.IGNORECASE)
            if matches:
                found_words.extend(matches)
        
        unique_words = list(set(found_words)) if found_words else []
        
        if unique_words:
            logging.warning(f"Обнаружен мат в анкете: {unique_words}")
            return {
                "action": "rejected",
                "reason": f"Обнаружены запрещённые слова: {', '.join(unique_words[:5])}",
                "found_words": unique_words
            }
        
        logging.info(f"Анкета отправлена на модерацию: description={description[:30]}")
        return {
            "action": "pending",
            "reason": "Требуется проверка администратором",
            "found_words": []
        }
    
    @staticmethod
    async def check_user_message(message_text: str) -> dict:
        """Проверка сообщения пользователя на мат"""
        
        found_words = []
        for pattern in ModerationService.TOXIC_PATTERNS:
            matches = re.findall(pattern, message_text, re.IGNORECASE)
            if matches:
                found_words.extend(matches)
        
        unique_words = list(set(found_words)) if found_words else []
        
        if unique_words:
            return {
                "is_toxic": True,
                "toxicity_score": min(0.3 + len(unique_words) * 0.1, 1.0),
                "is_safe": False,
                "found_words": unique_words
            }
        
        return {
            "is_toxic": False,
            "toxicity_score": 0.0,
            "is_safe": True,
            "found_words": []
        }