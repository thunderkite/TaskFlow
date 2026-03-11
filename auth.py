from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import User, db

# Создаем Blueprint для аутентификации (регистрация, вход, выход)
auth_bp = Blueprint('auth', __name__)

# Страница логина
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Если пользователь уже вошел, повторно показывать форму входа не нужно.
    if current_user.is_authenticated:
        return redirect(url_for('tasks.dashboard'))

    if request.method == 'POST':
        # Получаем данные из формы
        username = request.form['username'].strip()
        password = request.form['password']

        # Ищем пользователя в базе данных по имени
        user = User.query.filter_by(username=username).first() # query позволяет получать данные из бд

        # Проверяем пароль и авторизуем пользователя
        if user and user.check_password(password):
            login_user(user) # Логиним пользователя (создаем сессию)
            flash('Вы успешно вошли в систему', 'success')
            return redirect(url_for('tasks.dashboard')) # Редирект на главную страницу после входа
        else:
            # (flash - для одноразовых сообщений)
            flash('Неверное имя пользователя или пароль', 'danger') # Показываем сообщение об ошибке

    return render_template('login.html') # Показываем страницу логина

# Страница регистрации
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Повторная регистрация не нужна, если сессия уже активна.
    if current_user.is_authenticated:
        return redirect(url_for('tasks.dashboard'))

    if request.method == 'POST':
        # Получаем данные из формы
        full_name = request.form['full_name'].strip()
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        role = request.form['role']

        # Проверяем, нет ли такого пользователя уже в базе данных
        if User.query.filter_by(username=username).first(): # first() возвращает первый результат или None, если ничего не найдено
            flash('Пользователь с таким именем уже существует', 'danger')
            return redirect(url_for('auth.register'))

        if User.query.filter_by(email=email).first():
            flash('Пользователь с такой почтой уже существует', 'danger')
            return redirect(url_for('auth.register'))
        
        # После базовых проверок создаем пользователя и сохраняем его в БД.
        new_user = User(full_name=full_name, username=username, email=email, role=role) # Создаем объект пользователя
        new_user.set_password(password)  # Устанавливаем пароль
        db.session.add(new_user) # Добавляем нового пользователя в сессию базы данных
        db.session.commit() # Сохраняем изменения в базе данных

        flash('Пользователь успешно зарегистрирован', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html')

# Страница выхода
@auth_bp.route('/logout')
@login_required # Только для авторизованных пользователей
def logout():
    logout_user() # Выходим (удаляем сессию)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('auth.login')) # Редирект на страницу логина после выхода