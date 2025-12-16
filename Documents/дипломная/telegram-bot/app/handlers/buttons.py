from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InputFile
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import io

from app.service.user_service import UserService
from app.service.event_service import EventService
from app.service.map_service import MapService
from app.keyboards.main_menu import get_main_keyboard

router = Router()

class MapStates(StatesGroup):
    viewing_map = State()

def get_map_keyboard():
    """Клавиатура для работы с картой"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🗺️ Показать на карте"), KeyboardButton(text="📋 Список событий")],
            [KeyboardButton(text="❓ Легенда карты"), KeyboardButton(text="🔄 Обновить")],
            [KeyboardButton(text="🏠 В главное меню")]
        ],
        resize_keyboard=True
    )

@router.message(F.text == "🔍 Найти события")
async def handle_find_events(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка кнопки 'Найти события' с опцией карты"""
    # Проверяем есть ли сохраненная локация
    user_location = await UserService.get_user_location(
        session=session,
        telegram_id=message.from_user.id
    )
    
    if not user_location:
        await message.answer(
            "🔍 <b>Поиск событий</b>\n\n"
            "📍 Сначала поделитесь своей геолокацией, чтобы найти события поблизости.\n\n"
            "Используйте кнопку «📍 Поделиться локацией» в главном меню.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return
    
    try:
        user_lat = float(user_location.latitude)
        user_lon = float(user_location.longitude)
        
        # Получаем события рядом
        events = await EventService.get_events_nearby(
            session=session,
            user_latitude=user_lat,
            user_longitude=user_lon,
            radius_km=10.0,
            max_results=20
        )
        
        # Сохраняем данные в состоянии
        await state.set_state(MapStates.viewing_map)
        await state.update_data(
            user_lat=user_lat,
            user_lon=user_lon,
            events=events
        )
        
        logging.info(f"Поиск событий: пользователь {message.from_user.id}, найдено {len(events)} событий")
        
        if not events:
            await message.answer(
                f"🔍 <b>Поиск событий рядом</b>\n\n"
                f"📍 <b>Ваша локация:</b> установлена\n"
                f"📏 <b>Радиус поиска:</b> 10 км\n\n"
                f"🤷 <b>Событий не найдено</b>\n"
                f"Поблизости пока нет событий. Создайте первое!",
                reply_markup=get_map_keyboard(),
                parse_mode="HTML"
            )
        else:
            response = (
                f"🔍 <b>Найдено событий: {len(events)}</b>\n\n"
                f"📍 <b>Ваша локация:</b> установлена\n"
                f"📏 <b>Радиус поиска:</b> 10 км\n\n"
                "👇 <b>Выберите способ просмотра:</b>\n"
                "• 🗺️ <b>Показать на карте</b> - визуальное отображение\n"
                "• 📋 <b>Список событий</b> - текстовый формат\n"
                "• ❓ <b>Легенда карты</b> - пояснения к карте"
            )
            
            await message.answer(
                response,
                reply_markup=get_map_keyboard(),
                parse_mode="HTML"
            )
            
    except Exception as e:
        logging.error(f"Ошибка поиска событий: {e}", exc_info=True)
        await message.answer(
            "❌ <b>Ошибка поиска</b>\n\n"
            "Произошла ошибка при поиске событий. Попробуйте позже.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )

@router.message(MapStates.viewing_map, F.text == "🗺️ Показать на карте")
async def show_events_on_map(message: Message, state: FSMContext, session: AsyncSession):
    """Показать события на карте Yandex"""
    try:
        data = await state.get_data()
        user_lat = data.get('user_lat')
        user_lon = data.get('user_lon')
        events = data.get('events', [])
        
        logging.info(f"Попытка показать карту: user_lat={user_lat}, user_lon={user_lon}, events_count={len(events)}")
        
        if not events:
            await message.answer(
                "🤷 <b>Нет событий для отображения на карте</b>\n\n"
                "Создайте первое событие в вашем районе!",
                reply_markup=get_map_keyboard()
            )
            return
        
        if not user_lat or not user_lon:
            await message.answer(
                "❌ <b>Не удалось определить ваше местоположение</b>\n\n"
                "Поделитесь локацией еще раз.",
                reply_markup=get_map_keyboard()
            )
            return
        
        image_data, description = await MapService.create_map_with_events(events, user_lat, user_lon)
        
        logging.info(f"Результат создания карты: image_data={'есть' if image_data else 'нет'}, description={description[:100]}...")
        
        if image_data:
            from aiogram.types import BufferedInputFile
            
            photo = BufferedInputFile(image_data, filename="map.png")
            
            await message.answer_photo(
                photo=photo,
                caption=description,
                reply_markup=get_map_keyboard(),
                parse_mode="HTML"
            )
            logging.info("Карта успешно отправлена")
        else:
            logging.warning(f"Не удалось загрузить карту: {description}")
            await message.answer(
                f"❌ <b>Не удалось загрузить карту</b>\n\n{description}\n\n"
                f"Показываем список событий:",
                reply_markup=get_map_keyboard(),
                parse_mode="HTML"
            )
            await show_events_list(message, state)
            
    except Exception as e:
        logging.error(f"Ошибка отображения карты: {e}", exc_info=True)
        await message.answer(
            f"❌ <b>Ошибка отображения карты</b>\n\nПопробуйте посмотреть список событий.",
            reply_markup=get_map_keyboard()
        )

@router.message(MapStates.viewing_map, F.text == "📋 Список событий")
async def show_events_list(message: Message, state: FSMContext):
    """Показать список событий"""
    try:
        data = await state.get_data()
        events = data.get('events', [])
        user_lat = data.get('user_lat')
        user_lon = data.get('user_lon')
        
        logging.info(f"Показ списка событий: {len(events)} событий")
        
        if not events:
            await message.answer(
                "🤷 <b>Событий не найдено</b>",
                reply_markup=get_map_keyboard()
            )
            return
        
        response = EventService.format_events_list(events, user_lat, user_lon)
        await message.answer(
            response,
            reply_markup=get_map_keyboard(),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logging.error(f"Ошибка показа списка событий: {e}", exc_info=True)
        await message.answer(
            "❌ <b>Ошибка отображения списка</b>",
            reply_markup=get_map_keyboard()
        )

@router.message(MapStates.viewing_map, F.text == "❓ Легенда карты")
async def show_map_legend(message: Message):
    """Показать легенду карты"""
    try:
        legend = MapService.get_map_legend()
        await message.answer(
            legend,
            reply_markup=get_map_keyboard(),
            parse_mode="HTML"
        )
        logging.info("Показана легенда карты")
    except Exception as e:
        logging.error(f"Ошибка показа легенды карты: {e}")
        await message.answer(
            "❌ <b>Ошибка загрузки легенды</b>",
            reply_markup=get_map_keyboard()
        )

@router.message(MapStates.viewing_map, F.text == "🔄 Обновить")
async def refresh_map(message: Message, session: AsyncSession, state: FSMContext):
    """Обновить карту и список событий"""
    try:
        data = await state.get_data()
        user_lat = data.get('user_lat')
        user_lon = data.get('user_lon')
        
        logging.info(f"Обновление карты: user_lat={user_lat}, user_lon={user_lon}")
        
        if not user_lat or not user_lon:
            await message.answer(
                "❌ <b>Не удалось обновить</b>\nЛокация не найдена.",
                reply_markup=get_map_keyboard()
            )
            return
        
        # Получаем актуальные события
        events = await EventService.get_events_nearby(
            session=session,
            user_latitude=user_lat,
            user_longitude=user_lon,
            radius_km=10.0,
            max_results=20
        )
        
        # Обновляем состояние
        await state.update_data(events=events)
        
        logging.info(f"Обновление завершено: найдено {len(events)} событий")
        
        await message.answer(
            f"✅ <b>Данные обновлены!</b>\n\n"
            f"📅 Найдено событий: {len(events)}",
            reply_markup=get_map_keyboard(),
            parse_mode="HTML"
        )
            
    except Exception as e:
        logging.error(f"Ошибка обновления карты: {e}", exc_info=True)
        await message.answer(
            "❌ <b>Ошибка обновления</b>",
            reply_markup=get_map_keyboard()
        )

@router.message(MapStates.viewing_map, F.text == "🏠 В главное меню")
async def back_to_main_from_map(message: Message, state: FSMContext):
    """Вернуться в главное меню из режима карты"""
    try:
        await state.clear()
        logging.info(f"Пользователь {message.from_user.id} вернулся в главное меню из режима карты")
        await message.answer(
            "Возвращаемся в главное меню...",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logging.error(f"Ошибка возврата в главное меню: {e}")
        await message.answer(
            "Возвращаемся в главное меню...",
            reply_markup=get_main_keyboard()
        )

# Общий обработчик для кнопки "🔍 Найти рядом" (старая функциональность)
@router.message(F.text == "🔍 Найти рядом")
async def handle_find_nearby(message: Message, session: AsyncSession):
    """Обработка кнопки 'Найти рядом' с улучшенным выводом"""
    # Проверяем есть ли сохраненная локация
    user_location = await UserService.get_user_location(
        session=session,
        telegram_id=message.from_user.id
    )
    
    if not user_location:
        await message.answer(
            "🔍 <b>Поиск событий рядом</b>\n\n"
            "📍 Сначала поделитесь своей геолокацией, чтобы найти события поблизости.\n\n"
            "Используйте кнопку «📍 Поделиться локацией» в главном меню.",
            parse_mode="HTML"
        )
        return
    
    try:
        user_lat = float(user_location.latitude)
        user_lon = float(user_location.longitude)
        
        # Получаем события рядом с расчетом расстояния
        events = await EventService.get_events_nearby(
            session=session,
            user_latitude=user_lat,
            user_longitude=user_lon,
            radius_km=10.0,  # Радиус 10 км
            max_results=15   # Максимум 15 событий
        )
        
        logging.info(f"Поиск рядом: пользователь {message.from_user.id}, найдено {len(events)} событий")
        
        if not events:
            await message.answer(
                f"🔍 <b>Поиск рядом с вами</b>\n\n"
                f"📍 <b>Ваша локация:</b> установлена\n"
                f"📏 <b>Радиус поиска:</b> 10 км\n\n"
                f"🤷 <b>Событий не найдено</b>\n"
                f"Поблизости пока нет событий. Создайте первое!",
                parse_mode="HTML"
            )
        else:
            events_count = len(events)
            nearest_distance = EventService.format_distance(events[0].distance) if events else "N/A"
            
            response = (
                f"🔍 <b>События рядом с вами</b>\n\n"
                f"📍 <b>Ваша локация:</b> установлена\n"
                f"📏 <b>Радиус поиска:</b> 10 км\n"
                f"📅 <b>Найдено событий:</b> {events_count}\n"
                f"📍 <b>Ближайшее:</b> {nearest_distance}\n\n"
            )
            
            # Добавляем список событий (первые 5)
            for i, event in enumerate(events[:5], 1):
                distance_text = EventService.format_distance(event.distance)
                response += (
                    f"{i}. <b>{event.title}</b> ({distance_text})\n"
                    f"   {event.description[:80]}{'...' if len(event.description) > 80 else ''}\n\n"
                )
            
            if events_count > 5:
                response += f"<i>... и еще {events_count - 5} событий</i>"
            
            await message.answer(response, parse_mode="HTML")
            
    except Exception as e:
        logging.error(f"Ошибка поиска событий рядом: {e}", exc_info=True)
        await message.answer(
            "❌ <b>Ошибка поиска</b>\n\n"
            "Произошла ошибка при поиске событий. Попробуйте позже.",
            parse_mode="HTML"
        )

# Общий обработчик для кнопки "🏠 В главное меню"
@router.message(F.text == "🏠 В главное меню")
async def back_to_main_general(message: Message):
    """Общий обработчик для кнопки 'В главное меню'"""
    try:
        logging.info(f"Пользователь {message.from_user.id} вернулся в главное меню")
        await message.answer(
            "Возвращаемся в главное меню...",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logging.error(f"Ошибка возврата в главное меню: {e}")
        # Все равно пытаемся показать главное меню
        await message.answer(
            "Возвращаемся в главное меню...",
            reply_markup=get_main_keyboard()
        )