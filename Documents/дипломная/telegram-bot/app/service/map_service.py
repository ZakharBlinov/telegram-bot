import aiohttp
import requests
from urllib.parse import urlencode
import logging
from typing import List, Tuple, Optional
from app.models import Event
from app.service.event_service import EventService

class MapService:
    
    @staticmethod
    def generate_static_map_url(events: List[Event], center_lat: float, center_lon: float, width: int = 650, height: int = 450) -> Optional[str]:
        """
        Генерирует URL для статической карты Yandex с событиями
        """
        try:
            # Базовый URL Yandex Static Maps API
            base_url = "https://static-maps.yandex.ru/1.x/"
            
            # Параметры карты
            params = {
                'll': f'{center_lon},{center_lat}',
                'size': f'{width},{height}',
                'z': '13',
                'l': 'map',
                'pt': ''
            }
            
            # Добавляем точку пользователя (синий круг)
            user_point = f"{center_lon},{center_lat},pm2blm"
            points = [user_point]
            
            # Добавляем точки событий на карту
            event_count = 0
            for i, event in enumerate(events[:25]):
                try:
                    lat = float(event.latitude)
                    lon = float(event.longitude)
                    
                    # pm2rdl - красный флажок с номером
                    point = f"{lon},{lat},pm2rdl{i+1}"
                    points.append(point)
                    event_count += 1
                    
                except (ValueError, TypeError) as e:
                    logging.warning(f"Ошибка координат события {event.id}: {e}")
                    continue
            
            if points:
                params['pt'] = '~'.join(points)
            
            # Формируем полный URL
            url = f"{base_url}?{urlencode(params)}"
            
            logging.info(f"Сгенерирован URL карты: {event_count} событий, центр: {center_lat},{center_lon}")
            logging.debug(f"URL карты: {url}")
            
            return url
            
        except Exception as e:
            logging.error(f"Ошибка генерации URL карты: {e}")
            return None
    
    @staticmethod
    async def download_map_image_async(map_url: str) -> Optional[bytes]:
        """
        Скачивает изображение карты асинхронно
        """
        try:
            logging.info(f"Асинхронная загрузка карты по URL: {map_url[:100]}...")
            
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(map_url) as response:
                    logging.info(f"Статус ответа: {response.status}")
                    logging.info(f"Content-Type: {response.headers.get('content-type')}")
                    
                    if response.status != 200:
                        logging.error(f"Ошибка HTTP: {response.status}")
                        return None
                    
                    # Проверяем, что это изображение
                    content_type = response.headers.get('content-type', '')
                    if 'image' not in content_type:
                        logging.error(f"Получен не image контент: {content_type}")
                        return None
                    
                    image_data = await response.read()
                    logging.info(f"Успешно загружено: {len(image_data)} байт")
                    return image_data
                    
        except aiohttp.ClientError as e:
            logging.error(f"Ошибка клиента при загрузке карты: {e}")
            return None
        except asyncio.TimeoutError:
            logging.error("Таймаут при загрузке карты")
            return None
        except Exception as e:
            logging.error(f"Неожиданная ошибка при асинхронной загрузке карты: {e}")
            return None
    
    @staticmethod
    def download_map_image_sync(map_url: str) -> Optional[bytes]:
        """
        Скачивает изображение карты синхронно (резервный метод)
        """
        try:
            logging.info(f"Синхронная загрузка карты по URL: {map_url[:100]}...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
            }
            response = requests.get(map_url, timeout=15, headers=headers)
            
            logging.info(f"Статус ответа: {response.status_code}")
            logging.info(f"Content-Type: {response.headers.get('content-type')}")
            
            response.raise_for_status()
            
            # Проверяем, что это изображение
            content_type = response.headers.get('content-type', '')
            if 'image' not in content_type:
                logging.error(f"Получен не image контент: {content_type}")
                logging.error(f"Тело ответа: {response.text[:200]}...")
                return None
                
            image_data = response.content
            logging.info(f"Успешно загружено: {len(image_data)} байт")
            return image_data
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка запроса карты: {e}")
            return None
        except Exception as e:
            logging.error(f"Неожиданная ошибка при синхронной загрузке карты: {e}")
            return None
    
    @staticmethod
    async def create_map_with_events(events: List[Event], user_lat: float, user_lon: float) -> Tuple[Optional[bytes], str]:
        """
        Создает карту с событиями и возвращает изображение
        """
        try:
            logging.info(f"Создание карты: {len(events)} событий, пользователь: {user_lat},{user_lon}")
            
            if not events:
                description = "🗺️ <b>Карта событий</b>\n\n🤷 <b>Событий не найдено поблизости</b>\n\nСоздайте первое событие в вашем районе!"
                return None, description
            
            # Генерируем URL карты
            map_url = MapService.generate_static_map_url(events, user_lat, user_lon)
            
            if not map_url:
                error_msg = "❌ <b>Не удалось создать карту</b>\n\nПопробуйте позже."
                logging.error(error_msg)
                return None, error_msg
            
            # Скачиваем изображение асинхронно
            image_data = await MapService.download_map_image_async(map_url)
            
            # Если асинхронная загрузка не удалась, пробуем синхронно
            if not image_data:
                logging.info("Пробуем синхронную загрузку...")
                image_data = MapService.download_map_image_sync(map_url)
            
            if not image_data:
                error_msg = "❌ <b>Не удалось загрузить карту</b>\n\nПроверьте подключение к интернету."
                logging.error(error_msg)
                return None, error_msg
            
            # Формируем описание карты
            description = f"🗺️ <b>Карта событий</b>\n\n"
            
            if events:
                description += f"📍 <b>Ваше местоположение</b> - синий круг\n"
                description += f"🔴 <b>События</b> - красные флажки с номерами\n\n"
                description += f"📅 <b>Найдено событий:</b> {len(events)}\n"
                
                # Показываем ближайшие события
                nearest_events = events[:3]
                for i, event in enumerate(nearest_events, 1):
                    distance = getattr(event, 'distance', None)
                    distance_text = f" ({EventService.format_distance(distance)})" if distance else ""
                    description += f"{i}. {event.title}{distance_text}\n"
                
                if len(events) > 3:
                    description += f"... и еще {len(events) - 3} событий\n"
                
            else:
                description += "🤷 <b>Событий не найдено поблизости</b>\n\n"
                description += "Создайте первое событие в вашем районе!"
            
            description += "\n👇 <b>Используйте кнопки для управления:</b>"
            
            logging.info(f"Карта успешно создана: {len(image_data)} байт")
            return image_data, description
            
        except Exception as e:
            logging.error(f"Ошибка создания карты с событиями: {e}", exc_info=True)
            error_msg = f"❌ <b>Ошибка при создании карты</b>\n\n{str(e)}"
            return None, error_msg
    
    @staticmethod
    def get_map_legend() -> str:
        """
        Возвращает легенду для карты
        """
        return (
            "📋 <b>Легенда карты:</b>\n\n"
            "🔵 <b>Синий круг</b> - ваше текущее местоположение\n"
            "🔴 <b>Красный флажок</b> - событие поблизости\n"
            "📝 <b>Цифры на флажках</b> - порядковый номер события\n\n"
            "<i>Карта обновляется при каждом запросе</i>"
        )