from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database import get_session
from app.models import User, Event, UserProfileByGoal, Complaint

app = FastAPI(title="SpotChat Admin Panel")

@app.get("/", response_class=HTMLResponse)
async def login_page():
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>SpotChat Admin - Вход</title>
        <style>
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: Arial, sans-serif;
                margin: 0;
            }
            .login-card {
                background: white;
                border-radius: 20px;
                padding: 40px;
                width: 100%;
                max-width: 450px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.2);
            }
            .login-card h2 {
                color: #667eea;
                text-align: center;
                margin-bottom: 30px;
            }
            .form-group {
                margin-bottom: 20px;
            }
            .form-group label {
                display: block;
                margin-bottom: 5px;
                color: #333;
            }
            .form-group input {
                width: 100%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 10px;
                font-size: 16px;
            }
            button {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border: none;
                padding: 12px;
                color: white;
                border-radius: 10px;
                width: 100%;
                font-size: 16px;
                cursor: pointer;
            }
            button:hover {
                transform: translateY(-2px);
            }
        </style>
    </head>
    <body>
        <div class="login-card">
            <h2>SpotChat Admin</h2>
            <form method="post" action="/api/login">
                <div class="form-group">
                    <label>Имя пользователя</label>
                    <input type="text" name="username" required>
                </div>
                <div class="form-group">
                    <label>Пароль</label>
                    <input type="password" name="password" required>
                </div>
                <button type="submit">Войти</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.post("/api/login")
async def login(username: str = Form(...), password: str = Form(...)):
    if username == "admin" and password == "admin123":
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="admin_logged_in", value="true")
        return response
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, session: AsyncSession = Depends(get_session)):
    if request.cookies.get("admin_logged_in") != "true":
        return RedirectResponse(url="/")
    
    total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
    total_events = (await session.execute(select(func.count(Event.id)))).scalar() or 0
    pending_events = (await session.execute(select(func.count(Event.id)).where(Event.status == "pending"))).scalar() or 0
    total_profiles = (await session.execute(select(func.count(UserProfileByGoal.id)))).scalar() or 0
    total_complaints = (await session.execute(select(func.count(Complaint.id)).where(Complaint.status == "pending"))).scalar() or 0
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard - SpotChat Admin</title>
        <style>
            body {{ font-family: Arial; margin: 0; padding: 0; background: #f5f5f5; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; align-items: center; }}
            .container {{ padding: 20px; max-width: 1200px; margin: 0 auto; }}
            .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-top: 20px; }}
            .stat-card {{ background: white; border-radius: 15px; padding: 20px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .stat-card h3 {{ margin: 0 0 10px 0; color: #666; }}
            .stat-card .number {{ font-size: 48px; font-weight: bold; color: #667eea; }}
            .nav-links {{ margin-top: 30px; display: flex; gap: 15px; flex-wrap: wrap; justify-content: center; }}
            .nav-links a {{ background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 10px; }}
            .nav-links a:hover {{ background: #5a67d8; }}
            .logout {{ background: #dc3545; padding: 8px 16px; border-radius: 10px; color: white; text-decoration: none; }}
            .logout:hover {{ background: #c82333; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>SpotChat Admin Panel</h1>
            <a href="/logout" class="logout">Выйти</a>
        </div>
        <div class="container">
            <h2>Дашборд</h2>
            <div class="stats">
                <div class="stat-card"><h3>👥 Пользователи</h3><div class="number">{total_users}</div></div>
                <div class="stat-card"><h3>📅 События</h3><div class="number">{total_events}</div></div>
                <div class="stat-card"><h3>⏳ На модерации</h3><div class="number">{pending_events}</div></div>
                <div class="stat-card"><h3>📝 Анкеты</h3><div class="number">{total_profiles}</div></div>
                <div class="stat-card"><h3>⚠️ Жалобы</h3><div class="number">{total_complaints}</div></div>
            </div>
            <div class="nav-links">
                <a href="/events/moderation">📅 Модерация событий</a>
                <a href="/profiles/moderation">📝 Модерация анкет</a>
                <a href="/users">👥 Пользователи</a>
                <a href="/complaints">⚠️ Жалобы</a>
                <a href="/statistics">📊 Статистика</a>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/events/moderation", response_class=HTMLResponse)
async def events_moderation(request: Request, session: AsyncSession = Depends(get_session)):
    if request.cookies.get("admin_logged_in") != "true":
        return RedirectResponse(url="/")
    
    result = await session.execute(
        select(Event, User)
        .join(User, Event.author_id == User.telegram_id)
        .where(Event.status == "pending")
        .order_by(Event.created_at.desc())
    )
    events = result.all()
    
    if not events:
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Модерация событий</title>
        <style>
            body { font-family: Arial; margin: 0; background: #f5f5f5; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; }
            .container { padding: 20px; }
            .back-link { display: inline-block; margin-top: 20px; color: #667eea; text-decoration: none; }
            .logout { background:#dc3545;padding:8px 16px;border-radius:10px;color:white;text-decoration:none; }
        </style>
        </head>
        <body>
            <div class="header"><h1>Модерация событий</h1><a href="/logout" class="logout">Выйти</a></div>
            <div class="container">
                <p>✅ Нет событий на модерацию</p>
                <a href="/dashboard" class="back-link">← Назад</a>
            </div>
        </body>
        </html>
        """
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Модерация событий</title>
        <style>
            body { font-family: Arial; margin: 0; background: #f5f5f5; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; }
            .container { padding: 20px; }
            table { width: 100%; background: white; border-radius: 10px; border-collapse: collapse; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background: #667eea; color: white; }
            .btn { padding: 5px 10px; border: none; border-radius: 5px; cursor: pointer; margin: 2px; }
            .btn-success { background: #28a745; color: white; }
            .btn-danger { background: #dc3545; color: white; }
            .back-link { display: inline-block; margin-top: 20px; color: #667eea; text-decoration: none; }
        </style>
    </head>
    <body>
        <div class="header"><h1>Модерация событий</h1><a href="/logout" class="logout">Выйти</a></div>
        <div class="container">
            <table>
                <thead><tr><th>ID</th><th>Название</th><th>Описание</th><th>Автор</th><th>Дата</th><th>Действия</th></tr></thead>
                <tbody>
    """
    
    for event, user in events:
        html += f"""
                    <tr>
                        <td>{event.id}</td>
                        <td><strong>{event.title}</strong></td>
                        <td>{event.description[:100] if event.description else '-'}{'...' if len(event.description or '') > 100 else ''}</td>
                        <td>{user.full_name or user.username or user.telegram_id}</td>
                        <td>{event.created_at.strftime('%d.%m.%Y %H:%M') if event.created_at else '-'}</td>
                        <td>
                            <button class="btn btn-success" onclick="approveEvent({event.id})">✅ Одобрить</button>
                            <button class="btn btn-danger" onclick="rejectEvent({event.id})">❌ Отклонить</button>
                        </td>
                    </tr>
        """
    
    html += """
                </tbody>
            </table>
            <a href="/dashboard" class="back-link">← Назад</a>
        </div>
        <script>
            function approveEvent(id) {
                if(confirm('Одобрить событие?')) {
                    fetch(`/api/events/${id}/approve`, {method: 'POST'})
                    .then(() => location.reload())
                    .catch(err => alert('Ошибка: ' + err));
                }
            }
            
            function rejectEvent(id) {
                let reason = prompt('Причина отклонения:');
                if(reason) {
                    fetch(`/api/events/${id}/reject`, {
                        method: 'POST',
                        body: `reason=${encodeURIComponent(reason)}`,
                        headers: {'Content-Type': 'application/x-www-form-urlencoded'}
                    })
                    .then(() => location.reload())
                    .catch(err => alert('Ошибка: ' + err));
                }
            }
        </script>
    </body>
    </html>
    """
    
    return html

@app.get("/profiles/moderation", response_class=HTMLResponse)
async def profiles_moderation(request: Request, session: AsyncSession = Depends(get_session)):
    if request.cookies.get("admin_logged_in") != "true":
        return RedirectResponse(url="/")
    
    result = await session.execute(
        select(UserProfileByGoal, User)
        .join(User, UserProfileByGoal.user_id == User.id)
        .order_by(UserProfileByGoal.created_at.desc())
        .limit(50)
    )
    profiles = result.all()
    
    if not profiles:
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Модерация анкет</title>
        <style>
            body { font-family: Arial; margin: 0; background: #f5f5f5; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; }
            .container { padding: 20px; }
            .back-link { display: inline-block; margin-top: 20px; color: #667eea; text-decoration: none; }
            .logout { background:#dc3545;padding:8px 16px;border-radius:10px;color:white;text-decoration:none; }
        </style>
        </head>
        <body>
            <div class="header"><h1>Модерация анкет</h1><a href="/logout" class="logout">Выйти</a></div>
            <div class="container">
                <p>✅ Нет анкет для модерации</p>
                <a href="/dashboard" class="back-link">← Назад</a>
            </div>
        </body>
        </html>
        """
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Модерация анкет</title>
        <style>
            body { font-family: Arial; margin: 0; background: #f5f5f5; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; }
            .container { padding: 20px; }
            table { width: 100%; background: white; border-radius: 10px; border-collapse: collapse; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background: #667eea; color: white; }
            .btn { padding: 5px 10px; border: none; border-radius: 5px; cursor: pointer; margin: 2px; }
            .btn-success { background: #28a745; color: white; }
            .btn-danger { background: #dc3545; color: white; }
            .back-link { display: inline-block; margin-top: 20px; color: #667eea; text-decoration: none; }
            .status-badge { padding: 3px 8px; border-radius: 5px; font-size: 12px; }
            .status-active { background: #28a745; color: white; }
            .status-inactive { background: #dc3545; color: white; }
        </style>
    </head>
    <body>
        <div class="header"><h1>Модерация анкет</h1><a href="/logout" class="logout">Выйти</a></div>
        <div class="container">
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Пользователь</th>
                        <th>Telegram ID</th>
                        <th>Цель</th>
                        <th>Описание</th>
                        <th>Фото</th>
                        <th>Статус</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    goal_names = {
        "relationship": "💑 Вторую половинку",
        "friendship": "👥 Найти общение",
        "gaming": "🎮 С кем поиграть",
        "hobbies": "🎨 Общие интересы и хобби",
        "services": "💼 Предложенные услуги"
    }
    
    for profile, user in profiles:
        goal_display = goal_names.get(profile.goal_type, profile.goal_type)
        status_class = "status-active" if profile.is_active else "status-inactive"
        status_text = "Активна" if profile.is_active else "Заблокирована"
        
        html += f"""
                    <tr>
                        <td>{profile.id}</td>
                        <td><strong>{user.full_name or user.username or user.telegram_id}</strong></td>
                        <td>{user.telegram_id}</td>
                        <td>{goal_display}</td>
                        <td>{profile.description[:100] if profile.description else '-'}{'...' if len(profile.description or '') > 100 else ''}</td>
                        <td>{'✅ есть' if profile.photo_id else '❌ нет'}</td>
                        <td><span class="status-badge {status_class}">{status_text}</span></td>
                        <td>
                            <button class="btn btn-success" onclick="approveProfile({profile.id})">✅ Одобрить</button>
                            <button class="btn btn-danger" onclick="rejectProfile({profile.id})">❌ Заблокировать</button>
                        </td>
                    </tr>
        """
    
    html += """
                </tbody>
            </table>
            <a href="/dashboard" class="back-link">← Назад</a>
        </div>
        <script>
            function approveProfile(id) {
                if(confirm('Одобрить анкету? Она будет видна другим пользователям.')) {
                    fetch(`/api/profiles/${id}/approve`, {method: 'POST'})
                    .then(() => location.reload())
                    .catch(err => alert('Ошибка: ' + err));
                }
            }
            
            function rejectProfile(id) {
                let reason = prompt('Причина блокировки анкеты:');
                if(reason) {
                    fetch(`/api/profiles/${id}/reject`, {
                        method: 'POST',
                        body: `reason=${encodeURIComponent(reason)}`,
                        headers: {'Content-Type': 'application/x-www-form-urlencoded'}
                    })
                    .then(() => location.reload())
                    .catch(err => alert('Ошибка: ' + err));
                }
            }
        </script>
    </body>
    </html>
    """
    
    return html

@app.get("/users", response_class=HTMLResponse)
async def users_list(request: Request, session: AsyncSession = Depends(get_session)):
    if request.cookies.get("admin_logged_in") != "true":
        return RedirectResponse(url="/")
    
    result = await session.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Пользователи</title>
        <style>
            body { font-family: Arial; margin: 0; background: #f5f5f5; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; }
            .container { padding: 20px; }
            table { width: 100%; background: white; border-radius: 10px; border-collapse: collapse; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background: #667eea; color: white; }
            .back-link { display: inline-block; margin-top: 20px; color: #667eea; text-decoration: none; }
            .logout { background:#dc3545;padding:8px 16px;border-radius:10px;color:white;text-decoration:none; }
        </style>
    </head>
    <body>
        <div class="header"><h1>Пользователи</h1><a href="/logout" class="logout">Выйти</a></div>
        <div class="container">
            <table>
                <thead><tr><th>ID</th><th>Telegram ID</th><th>Имя</th><th>Username</th><th>Роль</th><th>Регистрация</th></tr></thead>
                <tbody>
    """
    
    for user in users:
        html += f"""
                    <tr>
                        <td>{user.id}</td>
                        <td>{user.telegram_id}</td>
                        <td>{user.full_name or '-'}</td>
                        <td>{user.username or '-'}</td>
                        <td>{user.role or 'user'}</td>
                        <td>{user.created_at.strftime('%d.%m.%Y') if user.created_at else '-'}</td>
                    </tr>
        """
    
    html += """
                </tbody>
            </table>
            <a href="/dashboard" class="back-link">← Назад</a>
        </div>
    </body>
    </html>
    """
    
    return html

@app.get("/complaints", response_class=HTMLResponse)
async def complaints_list(request: Request, session: AsyncSession = Depends(get_session)):
    if request.cookies.get("admin_logged_in") != "true":
        return RedirectResponse(url="/")
    
    result = await session.execute(select(Complaint).order_by(Complaint.created_at.desc()))
    complaints = result.scalars().all()
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Жалобы</title>
        <style>
            body { font-family: Arial; margin: 0; background: #f5f5f5; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; }
            .container { padding: 20px; }
            table { width: 100%; background: white; border-radius: 10px; border-collapse: collapse; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background: #667eea; color: white; }
            .back-link { display: inline-block; margin-top: 20px; color: #667eea; text-decoration: none; }
            .logout { background:#dc3545;padding:8px 16px;border-radius:10px;color:white;text-decoration:none; }
        </style>
    </head>
    <body>
        <div class="header"><h1>Жалобы</h1><a href="/logout" class="logout">Выйти</a></div>
        <div class="container">
            <table>
                <thead><tr><th>ID</th><th>Тип</th><th>ID объекта</th><th>Причина</th><th>От пользователя</th><th>Дата</th><th>Статус</th></tr></thead>
                <tbody>
    """
    
    for complaint in complaints:
        status_text = {"pending": "⏳ На рассмотрении", "resolved": "✅ Решена", "rejected": "❌ Отклонена"}.get(complaint.status, complaint.status)
        html += f"""
                    <tr>
                        <td>{complaint.id}</td>
                        <td>{complaint.target_type}</td>
                        <td>{complaint.target_id}</td>
                        <td>{complaint.reason[:100] if complaint.reason else '-'}</td>
                        <td>{complaint.user_id}</td>
                        <td>{complaint.created_at.strftime('%d.%m.%Y %H:%M') if complaint.created_at else '-'}</td>
                        <td>{status_text}</td>
                    </tr>
        """
    
    html += """
                </tbody>
            </table>
            <a href="/dashboard" class="back-link">← Назад</a>
        </div>
    </body>
    </html>
    """
    
    return html

@app.get("/statistics", response_class=HTMLResponse)
async def statistics_page(request: Request, session: AsyncSession = Depends(get_session)):
    if request.cookies.get("admin_logged_in") != "true":
        return RedirectResponse(url="/")
    
    total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
    total_events = (await session.execute(select(func.count(Event.id)))).scalar() or 0
    pending_events = (await session.execute(select(func.count(Event.id)).where(Event.status == "pending"))).scalar() or 0
    published_events = (await session.execute(select(func.count(Event.id)).where(Event.status == "published"))).scalar() or 0
    rejected_events = (await session.execute(select(func.count(Event.id)).where(Event.status == "rejected"))).scalar() or 0
    total_profiles = (await session.execute(select(func.count(UserProfileByGoal.id)))).scalar() or 0
    total_complaints = (await session.execute(select(func.count(Complaint.id)))).scalar() or 0
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Статистика</title>
        <style>
            body {{ font-family: Arial; margin: 0; background: #f5f5f5; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; }}
            .container {{ padding: 20px; max-width: 1200px; margin: 0 auto; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-top: 20px; }}
            .stat-card {{ background: white; border-radius: 15px; padding: 20px; text-align: center; }}
            .stat-card h3 {{ margin: 0 0 10px 0; color: #666; }}
            .stat-card .number {{ font-size: 36px; font-weight: bold; color: #667eea; }}
            .back-link {{ display: inline-block; margin-top: 20px; color: #667eea; text-decoration: none; }}
            .logout {{ background:#dc3545;padding:8px 16px;border-radius:10px;color:white;text-decoration:none; }}
        </style>
    </head>
    <body>
        <div class="header"><h1>Статистика</h1><a href="/logout" class="logout">Выйти</a></div>
        <div class="container">
            <div class="stats-grid">
                <div class="stat-card"><h3>👥 Пользователи</h3><div class="number">{total_users}</div></div>
                <div class="stat-card"><h3>📅 Всего событий</h3><div class="number">{total_events}</div></div>
                <div class="stat-card"><h3>⏳ На модерации</h3><div class="number">{pending_events}</div></div>
                <div class="stat-card"><h3>✅ Опубликовано</h3><div class="number">{published_events}</div></div>
                <div class="stat-card"><h3>❌ Отклонено</h3><div class="number">{rejected_events}</div></div>
                <div class="stat-card"><h3>📝 Анкеты</h3><div class="number">{total_profiles}</div></div>
                <div class="stat-card"><h3>⚠️ Жалобы</h3><div class="number">{total_complaints}</div></div>
            </div>
            <a href="/dashboard" class="back-link">← Назад</a>
        </div>
    </body>
    </html>
    """

@app.post("/api/events/{event_id}/approve")
async def approve_event(event_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if event:
        event.status = "published"
        await session.commit()
    return {"status": "success"}

@app.post("/api/events/{event_id}/reject")
async def reject_event(event_id: int, reason: str = Form(...), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if event:
        event.status = "rejected"
        event.rejection_reason = reason
        await session.commit()
    return {"status": "success"}

@app.post("/api/profiles/{profile_id}/approve")
async def approve_profile(profile_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(UserProfileByGoal).where(UserProfileByGoal.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if profile:
        profile.is_active = True
        await session.commit()
    return {"status": "success"}

@app.post("/api/profiles/{profile_id}/reject")
async def reject_profile(profile_id: int, reason: str = Form(...), session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(UserProfileByGoal).where(UserProfileByGoal.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if profile:
        profile.is_active = False
        await session.commit()
    return {"status": "success"}

@app.get("/api/events")
async def get_all_events(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Event).order_by(Event.created_at.desc()).limit(50)
    )
    events = result.scalars().all()
    return [
        {
            "id": e.id, 
            "title": e.title, 
            "status": e.status,
            "created_at": e.created_at.isoformat() if e.created_at else None
        } 
        for e in events
    ]

@app.get("/api/events/pending")
async def get_pending_events(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Event).where(Event.status == "pending").order_by(Event.created_at.desc())
    )
    events = result.scalars().all()
    return [
        {
            "id": e.id, 
            "title": e.title, 
            "description": e.description[:200] if e.description else "",
            "author_id": e.author_id,
            "rejection_reason": e.rejection_reason
        } 
        for e in events
    ]

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("admin_logged_in")
    return response