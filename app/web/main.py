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
from app.config import Config

app = FastAPI(title="SpotChat Admin Panel")
config = Config()

# ID супер-администратора (только он может назначать админов)
SUPER_ADMIN_ID = config.ADMIN_ID

@app.get("/", response_class=HTMLResponse)
async def login_page():
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>SpotChat Admin - Вход</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: Arial, sans-serif;
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

async def get_current_user(request: Request, session: AsyncSession):
    """Получить текущего пользователя из cookies"""
    if request.cookies.get("admin_logged_in") != "true":
        raise HTTPException(status_code=401, detail="Not authenticated")
    result = await session.execute(select(User).where(User.telegram_id == SUPER_ADMIN_ID))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            telegram_id=SUPER_ADMIN_ID,
            username="admin",
            full_name="Administrator",
            role="admin",
            profile_completed=True
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user

async def is_super_admin(request: Request, session: AsyncSession) -> bool:
    """Проверка, является ли текущий пользователь супер-админом"""
    try:
        user = await get_current_user(request, session)
        return user.telegram_id == SUPER_ADMIN_ID
    except:
        return False

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, session: AsyncSession = Depends(get_session)):
    if request.cookies.get("admin_logged_in") != "true":
        return RedirectResponse(url="/")
    
    total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
    total_events = (await session.execute(select(func.count(Event.id)))).scalar() or 0
    pending_events = (await session.execute(select(func.count(Event.id)).where(Event.status == "pending"))).scalar() or 0
    pending_profiles = (await session.execute(select(func.count(UserProfileByGoal.id)).where(UserProfileByGoal.moderation_status == "pending"))).scalar() or 0
    total_complaints = (await session.execute(select(func.count(Complaint.id)).where(Complaint.status == "pending"))).scalar() or 0
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard - SpotChat Admin</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; align-items: center; }}
            .header a.logout {{ background: #dc3545; padding: 8px 16px; border-radius: 10px; color: white; text-decoration: none; }}
            .header a.logout:hover {{ background: #c82333; }}
            .container {{ padding: 20px; max-width: 1200px; margin: 0 auto; }}
            h2 {{ margin-bottom: 20px; }}
            .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-top: 20px; }}
            .stat-card {{ background: white; border-radius: 15px; padding: 20px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .stat-card h3 {{ margin: 0 0 10px 0; color: #666; font-size: 16px; }}
            .stat-card .number {{ font-size: 48px; font-weight: bold; color: #667eea; }}
            .nav-links {{ margin-top: 30px; display: flex; gap: 15px; flex-wrap: wrap; justify-content: center; }}
            .nav-links a {{ background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 10px; }}
            .nav-links a:hover {{ background: #5a67d8; }}
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
                <div class="stat-card"><h3>⏳ События на модерации</h3><div class="number">{pending_events}</div></div>
                <div class="stat-card"><h3>📝 Анкеты на модерации</h3><div class="number">{pending_profiles}</div></div>
                <div class="stat-card"><h3>⚠️ Жалобы</h3><div class="number">{total_complaints}</div></div>
            </div>
            <div class="nav-links">
                <a href="/events/moderation">📅 Модерация событий</a>
                <a href="/profiles-moderation">📝 Модерация анкет</a>
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
        <head>
            <title>Модерация событий</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { font-family: Arial, sans-serif; margin: 0; background: #f5f5f5; }
                .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; align-items: center; }
                .header a.logout { background: #dc3545; padding: 8px 16px; border-radius: 10px; color: white; text-decoration: none; }
                .container { padding: 20px; max-width: 1200px; margin: 0 auto; text-align: center; }
                .back-link { display: inline-block; margin-top: 20px; color: #667eea; text-decoration: none; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📅 Модерация событий</h1>
                <a href="/logout" class="logout">Выйти</a>
            </div>
            <div class="container">
                <p>✅ Нет событий на модерацию</p>
                <a href="/dashboard" class="back-link">← Назад к дашборду</a>
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
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: Arial, sans-serif; margin: 0; background: #f5f5f5; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; align-items: center; }
            .header a.logout { background: #dc3545; padding: 8px 16px; border-radius: 10px; color: white; text-decoration: none; }
            .container { padding: 20px; max-width: 1200px; margin: 0 auto; }
            .table-container { background: white; border-radius: 15px; padding: 20px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); overflow-x: auto; }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background: #667eea; color: white; }
            .btn { padding: 5px 10px; border: none; border-radius: 5px; cursor: pointer; margin: 2px; }
            .btn-success { background: #28a745; color: white; }
            .btn-danger { background: #dc3545; color: white; }
            .back-link { display: inline-block; margin-top: 20px; color: #667eea; text-decoration: none; }
            .badge-pending { background: #ffc107; color: #000; padding: 3px 8px; border-radius: 5px; font-size: 12px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📅 Модерация событий</h1>
            <a href="/logout" class="logout">Выйти</a>
        </div>
        <div class="container">
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Название</th>
                            <th>Описание</th>
                            <th>Автор</th>
                            <th>Дата</th>
                            <th>Статус</th>
                            <th>Действия</th>
                        </tr>
                    </thead>
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
                            <td><span class="badge-pending">⏳ На модерации</span></td>
                            <td>
                                <button class="btn btn-success" onclick="approveEvent({event.id})">✅ Одобрить</button>
                                <button class="btn btn-danger" onclick="rejectEvent({event.id})">❌ Отклонить</button>
                            </td>
                        </tr>
        """
    
    html += """
                    </tbody>
                </table>
            </div>
            <a href="/dashboard" class="back-link">← Назад к дашборду</a>
        </div>
        <script>
            function approveEvent(id) {
                if(confirm('Одобрить событие?')) {
                    fetch('/api/events/' + id + '/approve', {method: 'POST'})
                    .then(() => location.reload())
                    .catch(err => alert('Ошибка: ' + err));
                }
            }
            function rejectEvent(id) {
                let reason = prompt('Причина отклонения:');
                if(reason) {
                    fetch('/api/events/' + id + '/reject', {
                        method: 'POST',
                        body: 'reason=' + encodeURIComponent(reason),
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
    
    return HTMLResponse(html)

@app.get("/profiles-moderation", response_class=HTMLResponse)
async def profiles_moderation(request: Request, session: AsyncSession = Depends(get_session)):
    if request.cookies.get("admin_logged_in") != "true":
        return RedirectResponse(url="/")
    
    from sqlalchemy import text
    result = await session.execute(text("SELECT id, user_id, goal_type, description, photo_id, moderation_status FROM user_profiles_by_goal WHERE moderation_status = 'pending'"))
    profiles = result.fetchall()
    
    goal_names = {"relationship": "💑 Вторую половинку", "friendship": "👥 Найти общение", "gaming": "🎮 С кем поиграть", "hobbies": "🎨 Общие интересы и хобби", "services": "💼 Предложенные услуги"}
    
    if not profiles:
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Модерация анкет</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { font-family: Arial, sans-serif; margin: 0; background: #f5f5f5; }
                .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; align-items: center; }
                .header a.logout { background: #dc3545; padding: 8px 16px; border-radius: 10px; color: white; text-decoration: none; }
                .container { padding: 20px; max-width: 1200px; margin: 0 auto; text-align: center; }
                .back-link { display: inline-block; margin-top: 20px; color: #667eea; text-decoration: none; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📝 Модерация анкет</h1>
                <a href="/logout" class="logout">Выйти</a>
            </div>
            <div class="container">
                <p>✅ Нет анкет на модерацию</p>
                <a href="/dashboard" class="back-link">← Назад к дашборду</a>
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
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: Arial, sans-serif; margin: 0; background: #f5f5f5; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; align-items: center; }
            .header a.logout { background: #dc3545; padding: 8px 16px; border-radius: 10px; color: white; text-decoration: none; }
            .container { padding: 20px; max-width: 1200px; margin: 0 auto; }
            table { width: 100%; background: white; border-radius: 10px; border-collapse: collapse; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background: #667eea; color: white; }
            .btn { padding: 5px 10px; border: none; border-radius: 5px; cursor: pointer; margin: 2px; }
            .btn-success { background: #28a745; color: white; }
            .btn-danger { background: #dc3545; color: white; }
            .back-link { display: inline-block; margin-top: 20px; color: #667eea; text-decoration: none; }
            .badge-pending { background: #ffc107; color: #000; padding: 3px 8px; border-radius: 5px; font-size: 12px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📝 Модерация анкет</h1>
            <a href="/logout" class="logout">Выйти</a>
        </div>
        <div class="container">
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Цель</th>
                        <th>Описание</th>
                        <th>Фото</th>
                        <th>Статус</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for p in profiles:
        goal = goal_names.get(p[2], p[2])
        desc = p[3][:100] if p[3] else '-'
        photo = '✅ есть' if p[4] else '❌ нет'
        html += f"""
            <tr>
                <td>{p[0]}</td>
                <td>{goal}</td>
                <td>{desc}</td>
                <td>{photo}</td>
                <td><span class="badge-pending">⏳ На модерации</span></td>
                <td>
                    <button class="btn btn-success" onclick="approveProfile({p[0]})">✅ Одобрить</button>
                    <button class="btn btn-danger" onclick="rejectProfile({p[0]})">❌ Отклонить</button>
                </td>
            </tr>
        """
    
    html += """
                </tbody>
            </table>
            <a href="/dashboard" class="back-link">← Назад к дашборду</a>
        </div>
        <script>
            function approveProfile(id) {
                if(confirm('Одобрить анкету?')) {
                    fetch('/api/profiles/' + id + '/approve', {method: 'POST'})
                    .then(() => location.reload())
                    .catch(err => alert('Ошибка: ' + err));
                }
            }
            function rejectProfile(id) {
                let reason = prompt('Причина отклонения анкеты:');
                if(reason) {
                    fetch('/api/profiles/' + id + '/reject', {
                        method: 'POST',
                        body: 'reason=' + encodeURIComponent(reason),
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
    
    return HTMLResponse(html)

@app.get("/users", response_class=HTMLResponse)
async def users_list(request: Request, session: AsyncSession = Depends(get_session)):
    if request.cookies.get("admin_logged_in") != "true":
        return RedirectResponse(url="/")
    
    is_super = await is_super_admin(request, session)
    
    result = await session.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    
    current_user = await get_current_user(request, session)
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Пользователи</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: Arial, sans-serif; margin: 0; background: #f5f5f5; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; align-items: center; }
            .header a.logout { background: #dc3545; padding: 8px 16px; border-radius: 10px; color: white; text-decoration: none; }
            .container { padding: 20px; max-width: 1200px; margin: 0 auto; }
            table { width: 100%; background: white; border-radius: 10px; border-collapse: collapse; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background: #667eea; color: white; }
            .back-link { display: inline-block; margin-top: 20px; color: #667eea; text-decoration: none; }
            .role-select { padding: 4px 8px; border-radius: 5px; border: 1px solid #ddd; }
            .badge-super { background: #9b59b6; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
            .badge-admin { background: #dc3545; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
            .badge-moderator { background: #ffc107; color: #000; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
            .badge-user { background: #6c757d; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>👥 Пользователи</h1>
            <a href="/logout" class="logout">Выйти</a>
        </div>
        <div class="container">
    """
    
    if is_super:
        html += '<p style="color: #9b59b6; margin-bottom: 10px;">👑 Вы супер-администратор — можете управлять ролями</p>'
    else:
        html += '<p style="color: #6c757d; margin-bottom: 10px;">ℹ️ Только супер-администратор может изменять роли</p>'
    
    html += """
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Telegram ID</th>
                        <th>Имя</th>
                        <th>Username</th>
                        <th>Роль</th>
                        <th>Регистрация</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for user in users:
        is_super_user = (user.telegram_id == SUPER_ADMIN_ID)
        
        if is_super_user:
            role_badge = '<span class="badge-super">👑 Супер-администратор</span>'
        elif user.role == "admin":
            role_badge = '<span class="badge-admin">👑 Администратор</span>'
        elif user.role == "moderator":
            role_badge = '<span class="badge-moderator">🛡️ Модератор</span>'
        else:
            role_badge = '<span class="badge-user">👤 Пользователь</span>'
        
        html += f"""
            <tr>
                <td>{user.id}</td>
                <td>{user.telegram_id}</td>
                <td>{user.full_name or '-'}</td>
                <td>{user.username or '-'}</td>
                <td>{role_badge}</td>
                <td>{user.created_at.strftime('%d.%m.%Y') if user.created_at else '-'}</td>
                <td>
        """
        
        if is_super and user.id != current_user.id:
            html += f"""
                <form method="post" action="/api/users/{user.id}/role" style="display:inline;">
                    <select name="role" class="role-select" onchange="this.form.submit()">
                        <option value="user" {'selected' if user.role == 'user' else ''}>👤 Пользователь</option>
                        <option value="moderator" {'selected' if user.role == 'moderator' else ''}>🛡️ Модератор</option>
                        <option value="admin" {'selected' if user.role == 'admin' else ''}>👑 Администратор</option>
                    </select>
                </form>
            """
        elif user.id == current_user.id:
            html += '<span style="color:#6c757d; font-size:12px;">Это вы</span>'
        else:
            html += '<span style="color:#6c757d; font-size:12px;">Доступ запрещён</span>'
        
        html += f"""
                </td>
            </tr>
        """
    
    html += """
                </tbody>
            </table>
            <a href="/dashboard" class="back-link">← Назад к дашборду</a>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(html)

@app.post("/api/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    role: str = Form(...),
    session: AsyncSession = Depends(get_session),
    request: Request = None
):
    if not await is_super_admin(request, session):
        raise HTTPException(status_code=403, detail="Только супер-администратор может изменять роли")
    
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    current_user = await get_current_user(request, session)
    if user.id == current_user.id:
        raise HTTPException(status_code=403, detail="Нельзя изменить свою роль")
    
    if role in ["user", "moderator", "admin"]:
        user.role = role
        await session.commit()
    
    # Возвращаем пользователя обратно на страницу пользователей
    return RedirectResponse(url="/users", status_code=303)

@app.get("/complaints", response_class=HTMLResponse)
async def complaints_list(request: Request, session: AsyncSession = Depends(get_session)):
    if request.cookies.get("admin_logged_in") != "true":
        return RedirectResponse(url="/")
    
    filter_status = request.query_params.get("status", "pending")
    
    query = select(Complaint)
    if filter_status != "all":
        query = query.where(Complaint.status == filter_status)
    query = query.order_by(Complaint.created_at.desc())
    
    result = await session.execute(query)
    complaints = result.scalars().all()
    
    pending_count = await session.execute(
        select(func.count(Complaint.id)).where(Complaint.status == "pending")
    )
    pending_count = pending_count.scalar() or 0
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Жалобы</title>
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: Arial, sans-serif; margin: 0; background: #f5f5f5; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; align-items: center; }}
            .header a.logout {{ background: #dc3545; padding: 8px 16px; border-radius: 10px; color: white; text-decoration: none; }}
            .container {{ padding: 20px; max-width: 1200px; margin: 0 auto; }}
            table {{ width: 100%; background: white; border-radius: 10px; border-collapse: collapse; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #667eea; color: white; }}
            .btn {{ padding: 5px 10px; border: none; border-radius: 5px; cursor: pointer; margin: 2px; }}
            .btn-success {{ background: #28a745; color: white; }}
            .btn-danger {{ background: #dc3545; color: white; }}
            .btn-secondary {{ background: #6c757d; color: white; }}
            .btn-sm {{ padding: 3px 8px; font-size: 12px; }}
            .back-link {{ display: inline-block; margin-top: 20px; color: #667eea; text-decoration: none; }}
            .tabs {{ display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }}
            .tabs a {{ padding: 8px 16px; background: #e9ecef; border-radius: 5px; text-decoration: none; color: #333; }}
            .tabs a.active {{ background: #667eea; color: white; }}
            .badge {{ background: #dc3545; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>⚠️ Жалобы</h1>
            <a href="/logout" class="logout">Выйти</a>
        </div>
        <div class="container">
            <div class="tabs">
                <a href="/complaints?status=pending" class="{'active' if filter_status == 'pending' else ''}">
                    ⏳ Активные <span class="badge">{pending_count}</span>
                </a>
                <a href="/complaints?status=all" class="{'active' if filter_status == 'all' else ''}">📋 Все</a>
                <a href="/complaints?status=resolved" class="{'active' if filter_status == 'resolved' else ''}">✅ Решённые</a>
                <a href="/complaints?status=rejected" class="{'active' if filter_status == 'rejected' else ''}">❌ Отклонённые</a>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Тип</th>
                        <th>ID объекта</th>
                        <th>Причина</th>
                        <th>От пользователя</th>
                        <th>Дата</th>
                        <th>Статус</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    if not complaints:
        html += '<tr><td colspan="8" style="text-align:center; padding:20px;">Нет жалоб</td></tr>'
    else:
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
                    <td>
            """
            if complaint.status == "pending":
                html += f"""
                        <button class="btn btn-success btn-sm" onclick="resolveComplaint({complaint.id})">✅ Принять</button>
                        <button class="btn btn-danger btn-sm" onclick="rejectComplaint({complaint.id})">❌ Отклонить</button>
                """
            else:
                html += '<span class="btn btn-secondary btn-sm" style="cursor:default;">✅ Обработано</span>'
            html += f"""
                    </td>
                </tr>
            """
    
    html += """
                </tbody>
            </table>
            <a href="/dashboard" class="back-link">← Назад к дашборду</a>
        </div>
        <script>
            function resolveComplaint(id) {
                if(confirm('Принять жалобу?')) {
                    fetch('/api/complaints/' + id + '/resolve', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'}
                    })
                    .then(response => response.json())
                    .then(data => {
                        if(data.status === 'success') {
                            location.reload();
                        } else {
                            alert('Ошибка: ' + data.message);
                        }
                    })
                    .catch(error => alert('Ошибка: ' + error));
                }
            }
            
            function rejectComplaint(id) {
                if(confirm('Отклонить жалобу?')) {
                    fetch('/api/complaints/' + id + '/reject', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'}
                    })
                    .then(response => response.json())
                    .then(data => {
                        if(data.status === 'success') {
                            location.reload();
                        } else {
                            alert('Ошибка: ' + data.message);
                        }
                    })
                    .catch(error => alert('Ошибка: ' + error));
                }
            }
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(html)

@app.get("/statistics", response_class=HTMLResponse)
async def statistics_page(request: Request, session: AsyncSession = Depends(get_session)):
    if request.cookies.get("admin_logged_in") != "true":
        return RedirectResponse(url="/")
    
    total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
    total_events = (await session.execute(select(func.count(Event.id)))).scalar() or 0
    pending_events = (await session.execute(select(func.count(Event.id)).where(Event.status == "pending"))).scalar() or 0
    published_events = (await session.execute(select(func.count(Event.id)).where(Event.status == "published"))).scalar() or 0
    rejected_events = (await session.execute(select(func.count(Event.id)).where(Event.status == "rejected"))).scalar() or 0
    pending_profiles = (await session.execute(select(func.count(UserProfileByGoal.id)).where(UserProfileByGoal.moderation_status == "pending"))).scalar() or 0
    published_profiles = (await session.execute(select(func.count(UserProfileByGoal.id)).where(UserProfileByGoal.moderation_status == "published"))).scalar() or 0
    total_complaints = (await session.execute(select(func.count(Complaint.id)))).scalar() or 0
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Статистика</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: Arial, sans-serif; margin: 0; background: #f5f5f5; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; align-items: center; }}
            .header a.logout {{ background: #dc3545; padding: 8px 16px; border-radius: 10px; color: white; text-decoration: none; }}
            .container {{ padding: 20px; max-width: 1200px; margin: 0 auto; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-top: 20px; }}
            .stat-card {{ background: white; border-radius: 15px; padding: 20px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .stat-card h3 {{ margin: 0 0 10px 0; color: #666; }}
            .stat-card .number {{ font-size: 36px; font-weight: bold; color: #667eea; }}
            .back-link {{ display: inline-block; margin-top: 20px; color: #667eea; text-decoration: none; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 Статистика</h1>
            <a href="/logout" class="logout">Выйти</a>
        </div>
        <div class="container">
            <div class="stats-grid">
                <div class="stat-card"><h3>👥 Пользователи</h3><div class="number">{total_users}</div></div>
                <div class="stat-card"><h3>📅 Всего событий</h3><div class="number">{total_events}</div></div>
                <div class="stat-card"><h3>⏳ События на модерации</h3><div class="number">{pending_events}</div></div>
                <div class="stat-card"><h3>✅ Опубликовано событий</h3><div class="number">{published_events}</div></div>
                <div class="stat-card"><h3>❌ Отклонено событий</h3><div class="number">{rejected_events}</div></div>
                <div class="stat-card"><h3>📝 Анкеты на модерации</h3><div class="number">{pending_profiles}</div></div>
                <div class="stat-card"><h3>✅ Опубликовано анкет</h3><div class="number">{published_profiles}</div></div>
                <div class="stat-card"><h3>⚠️ Жалобы</h3><div class="number">{total_complaints}</div></div>
            </div>
            <a href="/dashboard" class="back-link">← Назад к дашборду</a>
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
    result = await session.execute(select(UserProfileByGoal).where(UserProfileByGoal.id == profile_id))
    profile = result.scalar_one_or_none()
    if profile:
        profile.moderation_status = "published"
        profile.is_active = True
        await session.commit()
    return {"status": "success"}

@app.post("/api/profiles/{profile_id}/reject")
async def reject_profile(profile_id: int, reason: str = Form(...), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(UserProfileByGoal).where(UserProfileByGoal.id == profile_id))
    profile = result.scalar_one_or_none()
    if profile:
        profile.moderation_status = "rejected"
        profile.is_active = False
        profile.moderation_reason = reason
        await session.commit()
    return {"status": "success"}

@app.post("/api/complaints/{complaint_id}/resolve")
async def resolve_complaint(complaint_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Complaint).where(Complaint.id == complaint_id))
    complaint = result.scalar_one_or_none()
    if complaint:
        complaint.status = "resolved"
        await session.commit()
    return {"status": "success"}

@app.post("/api/complaints/{complaint_id}/reject")
async def reject_complaint(complaint_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Complaint).where(Complaint.id == complaint_id))
    complaint = result.scalar_one_or_none()
    if complaint:
        complaint.status = "rejected"
        await session.commit()
    return {"status": "success"}

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("admin_logged_in")
    return response