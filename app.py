# Основной файл приложения Flask, который инициализирует все компоненты и запускает сервер
import os

from flask import Flask
from models import db, User
from flask_login import LoginManager

from auth import auth_bp
from tasks import tasks_bp
from reports import reports_bp
from notifications import notification_bp


def _build_database_uri():
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql+psycopg://taskflow:taskflow@localhost:5432/taskflow',
    )

    if database_url.startswith('postgres://'):
        return database_url.replace('postgres://', 'postgresql+psycopg://', 1)

    if database_url.startswith('postgresql://') and '+psycopg' not in database_url:
        return database_url.replace('postgresql://', 'postgresql+psycopg://', 1)

    return database_url


app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', '8f3d5e6f7bb7d8a0f4b1431d4f0e8d2f2b6f40f7e6c2f0c0a9b3c1d2e4f5a6b7')
app.config['SQLALCHEMY_DATABASE_URI'] = _build_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация базы данных
db.init_app(app)

# Настройка Flask-Login (менеджер для управления сессиями пользователей)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login' # Редирект на страницу входа, если пользователь не вошел

# Функция помогает Flask-Login понимать, какой пользователь сейчас активен (по его ID)
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Регистрируем Blueprints для разных частей приложения
app.register_blueprint(auth_bp) # Аутентификация (регистрация, вход, выход)
app.register_blueprint(tasks_bp) # Управление задачами (создание, редактирование, удаление)
app.register_blueprint(reports_bp) # Отчеты (статистика по задачам)
app.register_blueprint(notification_bp) # Уведомления (просмотр, управление)

# При запуске создаем все таблицы в базе данных (если их еще нет)
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(
        host=os.getenv('FLASK_RUN_HOST', '0.0.0.0'),
        port=int(os.getenv('PORT', '5000')),
        debug=os.getenv('FLASK_DEBUG', '0') == '1',
    )