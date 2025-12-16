from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from math import radians, sin, cos, sqrt, atan2
from app.models import Event
import logging

class EventService:
    
    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Рассчитать расстояние между двумя точками в км по формуле гаверсинуса
        
        Args:
            lat1: Широта первой точки
            lon1: Долгота первой точки
            lat2: Широта второй точки
            lon2: Долгота второй точки
            
        Returns:
            Расстояние в километрах
        """
        try:
            # Земной радиус в километрах
            R = 6371.0
            
            # Переводим градусы в радианы
            lat1_rad = radians(lat1)
            lon1_rad = radians(lon1)
            lat2_rad = radians(lat2)
            lon2_rad = radians(lon2)
            
            # Разница между координатами
            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad
            
            # Формула гаверсинуса
            a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            
            distance = R * c
            return round(distance, 2)  # Округляем до 2 знаков после запятой
            
        except (ValueError, TypeError, Exception) as e:
            logging.error(f"Ошибка расчета расстояния: {e}")
            return float('inf')
    
    @staticmethod
    async def create_event(
        session: AsyncSession, 
        title: str, 
        description: str, 
        latitude: float, 
        longitude: float, 
        author_id: int, 
        address: str = None,
        category: str = 'other'
    ) -> Event:
        """Создать новое событие"""
        try:
            event = Event(
                title=title,
                description=description,
                latitude=str(latitude),
                longitude=str(longitude),
                author_id=author_id,
                address=address,
                category=category
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)
            logging.info(f"Создано событие: {title} пользователем {author_id}")
            return event
        except Exception as e:
            await session.rollback()
            logging.error(f"Ошибка создания события: {e}")
            raise
    
    @staticmethod
    async def get_events_nearby(
        session: AsyncSession, 
        user_latitude: float, 
        user_longitude: float, 
        radius_km: float = 5.0,
        max_results: int = 20
    ) -> list:
        """
        Получить события в радиусе с расчетом расстояния
        
        Args:
            session: Сессия БД
            user_latitude: Широта пользователя
            user_longitude: Долгота пользователя
            radius_km: Радиус поиска в км
            max_results: Максимальное количество результатов
            
        Returns:
            Список событий с добавленным полем distance
        """
        try:
            # Получаем все активные события
            result = await session.execute(
                select(Event).where(
                    and_(
                        Event.is_active == True,
                        Event.latitude.isnot(None),
                        Event.longitude.isnot(None)
                    )
                ).order_by(Event.created_at.desc())
            )
            events = result.scalars().all()
            
            nearby_events = []
            for event in events:
                try:
                    # Преобразуем строковые координаты в float
                    event_lat = float(event.latitude)
                    event_lon = float(event.longitude)
                    
                    # Рассчитываем расстояние
                    distance = EventService.calculate_distance(
                        user_latitude, user_longitude,
                        event_lat, event_lon
                    )
                    
                    # Если событие в пределах радиуса
                    if distance <= radius_km:
                        # Добавляем расстояние к объекту события
                        event.distance = distance
                        nearby_events.append(event)
                        
                        # Ограничиваем количество результатов
                        if len(nearby_events) >= max_results:
                            break
                            
                except (ValueError, TypeError) as e:
                    logging.warning(f"Неверные координаты события {event.id}: {e}")
                    continue
                except Exception as e:
                    logging.error(f"Ошибка обработки события {event.id}: {e}")
                    continue
            
            # Сортируем по расстоянию (ближайшие сначала)
            nearby_events.sort(key=lambda x: getattr(x, 'distance', float('inf')))
            
            logging.info(f"Найдено {len(nearby_events)} событий в радиусе {radius_km}км")
            return nearby_events
            
        except Exception as e:
            logging.error(f"Ошибка поиска событий рядом: {e}")
            return []
    
    @staticmethod
    async def get_user_events(session: AsyncSession, author_id: int) -> list:
        """Получить события пользователя"""
        try:
            result = await session.execute(
                select(Event).where(
                    and_(
                        Event.author_id == author_id,
                        Event.is_active == True
                    )
                ).order_by(Event.created_at.desc())
            )
            events = result.scalars().all()
            logging.info(f"Найдено {len(events)} событий пользователя {author_id}")
            return events
        except Exception as e:
            logging.error(f"Ошибка получения событий пользователя {author_id}: {e}")
            return []
    
    @staticmethod
    async def get_event_by_id(session: AsyncSession, event_id: int) -> Event:
        """Получить событие по ID"""
        try:
            result = await session.execute(
                select(Event).where(Event.id == event_id)
            )
            event = result.scalar_one_or_none()
            return event
        except Exception as e:
            logging.error(f"Ошибка получения события {event_id}: {e}")
            return None
    
    @staticmethod
    async def update_event(
        session: AsyncSession, 
        event_id: int, 
        title: str = None, 
        description: str = None,
        latitude: float = None,
        longitude: float = None,
        address: str = None
    ) -> Event:
        """Обновить событие"""
        try:
            event = await EventService.get_event_by_id(session, event_id)
            if not event:
                logging.warning(f"Событие {event_id} не найдено для обновления")
                return None
            
            if title is not None:
                event.title = title
            if description is not None:
                event.description = description
            if latitude is not None:
                event.latitude = str(latitude)
            if longitude is not None:
                event.longitude = str(longitude)
            if address is not None:
                event.address = address
            
            await session.commit()
            await session.refresh(event)
            logging.info(f"Событие {event_id} обновлено")
            return event
            
        except Exception as e:
            await session.rollback()
            logging.error(f"Ошибка обновления события {event_id}: {e}")
            return None
    
    @staticmethod
    async def delete_event(session: AsyncSession, event_id: int) -> bool:
        """Удалить событие (мягкое удаление - деактивация)"""
        try:
            event = await EventService.get_event_by_id(session, event_id)
            if event:
                event.is_active = False
                await session.commit()
                logging.info(f"Событие {event_id} деактивировано")
                return True
            return False
        except Exception as e:
            await session.rollback()
            logging.error(f"Ошибка удаления события {event_id}: {e}")
            return False
    
    @staticmethod
    async def hard_delete_event(session: AsyncSession, event_id: int) -> bool:
        """Полное удаление события из БД"""
        try:
            event = await EventService.get_event_by_id(session, event_id)
            if event:
                await session.delete(event)
                await session.commit()
                logging.info(f"Событие {event_id} полностью удалено")
                return True
            return False
        except Exception as e:
            await session.rollback()
            logging.error(f"Ошибка полного удаления события {event_id}: {e}")
            return False
    
    @staticmethod
    async def get_events_by_category(session: AsyncSession, category: str, limit: int = 50) -> list:
        """Получить события по категории"""
        try:
            result = await session.execute(
                select(Event).where(
                    and_(
                        Event.category == category,
                        Event.is_active == True
                    )
                ).order_by(Event.created_at.desc()).limit(limit)
            )
            events = result.scalars().all()
            logging.info(f"Найдено {len(events)} событий в категории {category}")
            return events
        except Exception as e:
            logging.error(f"Ошибка получения событий категории {category}: {e}")
            return []
    
    @staticmethod
    async def search_events(session: AsyncSession, search_query: str, limit: int = 20) -> list:
        """Поиск событий по названию и описанию"""
        try:
            result = await session.execute(
                select(Event).where(
                    and_(
                        Event.is_active == True,
                        Event.title.ilike(f"%{search_query}%") | Event.description.ilike(f"%{search_query}%")
                    )
                ).order_by(Event.created_at.desc()).limit(limit)
            )
            events = result.scalars().all()
            logging.info(f"Найдено {len(events)} событий по запросу '{search_query}'")
            return events
        except Exception as e:
            logging.error(f"Ошибка поиска событий по запросу '{search_query}': {e}")
            return []
    
    @staticmethod
    async def get_recent_events(session: AsyncSession, hours: int = 24, limit: int = 50) -> list:
        """Получить недавние события"""
        from datetime import datetime, timedelta
        
        try:
            time_threshold = datetime.utcnow() - timedelta(hours=hours)
            result = await session.execute(
                select(Event).where(
                    and_(
                        Event.is_active == True,
                        Event.created_at >= time_threshold
                    )
                ).order_by(Event.created_at.desc()).limit(limit)
            )
            events = result.scalars().all()
            logging.info(f"Найдено {len(events)} событий за последние {hours} часов")
            return events
        except Exception as e:
            logging.error(f"Ошибка получения недавних событий: {e}")
            return []
    
    @staticmethod
    def format_distance(distance: float) -> str:
        """Форматировать расстояние для отображения"""
        if distance < 1:
            return f"{int(distance * 1000)}м"
        else:
            return f"{distance:.1f}км"
    
    @staticmethod
    def format_events_list(events: list, user_lat: float = None, user_lon: float = None) -> str:
        """Форматировать список событий для отображения"""
        if not events:
            return "🤷 <b>Событий не найдено</b>"
        
        events_text = []
        for i, event in enumerate(events, 1):
            distance_text = ""
            if hasattr(event, 'distance'):
                distance_text = f" ({EventService.format_distance(event.distance)})"
            elif user_lat and user_lon:
                try:
                    distance = EventService.calculate_distance(
                        user_lat, user_lon,
                        float(event.latitude), float(event.longitude)
                    )
                    distance_text = f" ({EventService.format_distance(distance)})"
                except:
                    pass
            
            events_text.append(
                f"{i}. <b>{event.title}</b>{distance_text}\n"
                f"   📄 {event.description[:100]}{'...' if len(event.description) > 100 else ''}\n"
                f"   🕐 {event.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            )
        
        return "\n".join(events_text)