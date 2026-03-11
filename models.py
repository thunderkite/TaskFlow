from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


# Создаем объект базы данных
db = SQLAlchemy() # Он дает Api для работы с базой данных, позволяет создавать модели и выполнять запросы

# Таблица пользователей (наследуем UserMixin для работы авторизации Flask-Login)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)  # Уникальный идентификатор
    full_name = db.Column(db.String(255), nullable=False)  # Полное имя пользователя
    username = db.Column(db.String(150), unique=True, nullable=False)  # Имя пользователя
    email = db.Column(db.String(150), unique=True, nullable=False)  # Электронная почта
    password_hash = db.Column(db.String(255), nullable=False)  # Хэш пароля
    role = db.Column(db.String(50)) # Роль пользователя ('manager' или 'работник')

    # Связь: у одного пользователя может быть много уведомлений
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')

    # Удобное свойство для разграничения прав в маршрутах и шаблонах.
    @property
    def is_manager(self):
        return self.role == 'manager'

    # Функция для шифрования пароля
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # Функция для проверки пароля при входе
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Таблица задач
class Task(db.Model):
    STATUS_LABELS = {
        'new': 'Новая',
        'in_progress': 'В работе',
        'done': 'Готово',
        'overdue': 'Просрочено',
    }

    PRIORITY_LABELS = {
        'low': 'Низкий',
        'medium': 'Средний',
        'high': 'Высокий',
        'critical': 'Критический',
    }

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), unique=True, nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='new') # новая, в процессе, сделана, просрочена
    priority = db.Column(db.String(50), default='medium') # низкий, средний, высокий, критический
    deadline = db.Column(db.DateTime)

    # Даты для отчетов и сортировки
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # ID того, кто создал, и того, кто должен выполнить
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    assignee_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    # Настройка связи, чтобы можно было обращаться task.author и task.assignee
    author = db.relationship('User', foreign_keys=[author_id])
    assignee = db.relationship('User', foreign_keys=[assignee_id])

    # Если задача уже просрочена по дате, в интерфейсе показываем именно этот статус,
    # даже если в базе формально хранится другое текущее значение.
    @property
    def effective_status(self):
        if self.status == 'overdue':
            return 'overdue'

        if self.deadline and self.status != 'done' and self.deadline < datetime.now():
            return 'overdue'

        return self.status


    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.effective_status, self.effective_status)
    

    @property
    def priority_label(self):
        return self.PRIORITY_LABELS.get(self.priority, self.priority)


    # Это свойство нужно для отчетов, таблиц и канбан-доски, чтобы в одном месте
    # определить, считается ли задача просроченной на текущий момент.
    @property
    def is_overdue(self):
        return self.effective_status == 'overdue'

# История изменений задач
class TaskHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'))  # К какой задаче относится запись
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Кто сделал изменение
    old_status = db.Column(db.String(50))  # Старый статус
    new_status = db.Column(db.String(50))  # Новый статус
    comment = db.Column(db.String(255))  # Комментарий к изменению
    changed_at = db.Column(db.DateTime, default=datetime.now)  # Время изменения

    # История загружается как запрос, чтобы можно было гибко сортировать записи в карточке задачи.
    task = db.relationship('Task', backref=db.backref('history', lazy='dynamic', cascade='all, delete-orphan'))
    user = db.relationship('User')  # Связь с пользователем, который изменил

# Таблица уведомлений
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Кому отправлено уведомление
    text = db.Column(db.String(255), nullable=False)  # Текст уведомления
    is_read = db.Column(db.Boolean, default=False)  # Прочитано ли уведомление
    icon_type = db.Column(db.String(50), default='info')  # Иконка для уведомления (например, "info", "success", "warning", "danger")
    link = db.Column(db.String(255))  # Ссылка, куда перейти при клике на уведомление
    created_at = db.Column(db.DateTime, default=datetime.now)  # Дата создания уведомления