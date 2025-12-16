import os
from dataclasses import dataclass
from dotenv import load_dotenv
import logging

load_dotenv()

@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", 0))
    
    def __post_init__(self):
        """Валидация конфигурации"""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не найден в .env файле")
        
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL не найден в .env файле")
        
        logging.info("Конфигурация загружена успешно")