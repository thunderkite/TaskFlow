from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy import and_, or_

from models import Task, TaskHistory, User, db, Notification

# Создаем Blueprint для управления задачами (создание, редактирование, удаление)
tasks_bp = Blueprint('tasks', __name__)


# Отдельный helper для списка исполнителей, чтобы не дублировать сортировку по ФИО в каждом маршруте.
def _employee_query():
    return User.query.filter_by(role='employee').order_by(User.full_name.asc())


# Базовый запрос зависит от роли: менеджер видит все задачи, исполнитель — только связанные с ним.
def _task_query_for_current_user():
    if current_user.is_manager:
        return Task.query

    return Task.query.filter(
        or_(Task.assignee_id == current_user.id, Task.author_id == current_user.id)
    )


def _can_access_task(task):
    return current_user.is_manager or task.assignee_id == current_user.id or task.author_id == current_user.id


# Эта функция возвращает подписи и CSS-класс колонки для дашборда,
# чтобы шаблон оставался максимально простым.
def _column_meta(group, key):
    if group == 'priority':
        return {
            'low': ('Низкий', 'col-slate'),
            'medium': ('Средний', 'col-indigo'),
            'high': ('Высокий', 'col-rose'),
            'critical': ('Критический', 'col-rose'),
        }.get(key, (key, 'col-slate'))

    return {
        'new': ('К выполнению', 'col-slate'),
        'in_progress': ('В работе', 'col-indigo'),
        'done': ('Готово', 'col-emerald'),
        'overdue': ('Просрочено', 'col-rose'),
    }.get(key, (key, 'col-slate'))


def _create_notification(user_id, text, link=None, icon_type='info'):
    if not user_id:
        return

    db.session.add(Notification(user_id=user_id, text=text, link=link, icon_type=icon_type))


def _overdue_filter():
    return or_(
        Task.status == 'overdue',
        and_(Task.deadline.is_not(None), Task.deadline < datetime.now(), Task.status != 'done'),
    )


# Главная kanban-страница: собирает задачи, применяет фильтры и группирует карточки по выбранному признаку.
@tasks_bp.route('/')
@tasks_bp.route('/dashboard')
@login_required # Только для авторизованных пользователей
def dashboard():
    # Получаем параметры фильтрации из адресной строки (GET-параметры)
    group = request.args.get('group', 'status') # По умолчанию группируем по статусу
    status_filter = request.args.get('status', '').strip()
    priority_filter = request.args.get('priority', '').strip()
    assignee_filter = request.args.get('assignee_id', '').strip()

    tasks_query = _task_query_for_current_user()

    # Сначала применяем фильтры, чтобы дальше группировать уже готовый набор задач.
    if status_filter == 'overdue':
        tasks_query = tasks_query.filter(_overdue_filter())
    elif status_filter:
        tasks_query = tasks_query.filter(Task.status == status_filter)

    if priority_filter:
        tasks_query = tasks_query.filter(Task.priority == priority_filter)

    if assignee_filter and current_user.is_manager:
        tasks_query = tasks_query.filter(Task.assignee_id == int(assignee_filter))


    # Выполняем запрос к бд и получаем список всех задач
    tasks = tasks_query.order_by(Task.deadline.asc().nullslast(), Task.created_at.desc()).all()

    # Формируем колонки для Kanban-доски в зависимости от группировки
    board_columns = []

    # В зависимости от выбранной группировки строим колонки канбан-доски.
    # Каждая колонка — это словарь с ключом, заголовком, CSS-классом и списком задач.
    if group == 'status':
        # Порядок колонок фиксирован: сначала новые, потом в работе, потом готовые, потом просроченные
        statuses = ['new', 'in_progress', 'done', 'overdue']
        for status in statuses:
            # Отбираем только те задачи, чей эффективный статус совпадает с текущей колонкой.
            # effective_status — это вычисляемое свойство модели: если у задачи вышел дедлайн,
            # оно возвращает 'overdue', даже если в базе записан другой статус.
            column_tasks = [task for task in tasks if task.effective_status == status]
            # _column_meta возвращает русский заголовок колонки и CSS-класс для её цвета
            label, col_class = _column_meta(group, status)
            board_columns.append({'key': status, 'label': label, 'col_class': col_class, 'tasks': column_tasks})

    elif group == 'priority':
        # Колонки идут от низкого приоритета к критическому
        priorities = ['low', 'medium', 'high', 'critical']
        for priority in priorities:
            # Здесь фильтруем по полю priority — оно хранится в базе как есть, без вычислений
            column_tasks = [task for task in tasks if task.priority == priority]
            label, col_class = _column_meta(group, priority)
            board_columns.append({'key': priority, 'label': label, 'col_class': col_class, 'tasks': column_tasks})

    elif group == 'assignee' and current_user.is_manager:
        # Группировка по исполнителям доступна только менеджеру
        employees = list(_employee_query().all())
        for employee in employees:
            # Каждый сотрудник получает свою колонку; фильтруем задачи по его ID
            column_tasks = [task for task in tasks if task.assignee_id == employee.id]
            board_columns.append({'key': str(employee.id), 'label': employee.full_name, 'col_class': 'col-slate', 'tasks': column_tasks})

        # В конце добавляем колонку для задач без исполнителя
        unassigned_tasks = [task for task in tasks if task.assignee_id is None]
        board_columns.append({'key': 'unassigned', 'label': 'Не назначено', 'col_class': 'col-slate', 'tasks': unassigned_tasks})

    else:
        # Если передан неизвестный режим группировки — сбрасываем на группировку по статусу
        return redirect(url_for('tasks.dashboard', group='status', status=status_filter, priority=priority_filter, assignee_id=assignee_filter))

    # Список сотрудников для фильтрации по исполнителю (только для менеджера)
    employees = _employee_query().all() if current_user.is_manager else []

    return render_template(
        'dashboard.html',
        board_columns=board_columns,
        group=group,
        employees=employees,
        status_filter=status_filter,
        priority_filter=priority_filter,
        assignee_filter=assignee_filter,
    )


# Табличное представление всех задач с поиском и фильтрами.
@tasks_bp.route('/tasks')
@login_required
def task_list():
    q = request.args.get('q', '').strip()
    status = request.args.get('status', '').strip()
    priority = request.args.get('priority', '').strip()
    assignee_id = request.args.get('assignee_id', '').strip()

    query = _task_query_for_current_user()

    # Ищет задачи, где название или описание содержит поисковую строку, без учета регистра.
    if q:
        pattern = f'%{q}%'
        query = query.filter(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))
    # Если выбран статус (status), фильтрует задачи по статусу. Если статус 'overdue', применяет специальный фильтр для просроченных задач.
    if status == 'overdue':
        query = query.filter(_overdue_filter())
    elif status:
        query = query.filter(Task.status == status)
    # Если выбран приоритет (priority), фильтрует задачи по приоритету.
    if priority:
        query = query.filter(Task.priority == priority)
    # Если выбран исполнитель (assignee_id) и текущий пользователь — менеджер, фильтрует задачи по исполнителю.
    if assignee_id and current_user.is_manager:
        query = query.filter(Task.assignee_id == int(assignee_id))
    # Выполняет запрос к базе данных, сортирует задачи по дедлайну (сначала те, у которых он есть и он ближе) и по дате создания (сначала новые), и передает их в шаблон для отображения.
    tasks = query.order_by(Task.deadline.asc().nullslast(), Task.created_at.desc()).all()
    employees = _employee_query().all() if current_user.is_manager else []

    return render_template(
        'tasks.html',
        tasks=tasks,
        employees=employees,
        q=q,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
    )


# Форма создания задачи доступна только менеджеру и сразу пишет запись в историю изменений.
@tasks_bp.route('/tasks/new', methods=['GET', 'POST'])
@login_required
def task_new():
    if not current_user.is_manager:
        flash('Создавать задачи может только руководитель', 'danger')
        return redirect(url_for('tasks.task_list'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        deadline_value = request.form.get('deadline', '').strip()
        assignee_value = request.form.get('assignee_id', '').strip()

        if Task.query.filter_by(title=title).first():
            flash('Задача с таким названием уже существует', 'danger')
            return render_template('task_form.html', task=None, employees=_employee_query().all())

        # Преобразуем данные формы в модель и сохраняем автора вместе с исполнителем.
        task = Task(
            title=title,
            description=request.form.get('description', '').strip() or None,
            priority=request.form.get('priority', 'medium'),
            deadline=datetime.strptime(deadline_value, '%Y-%m-%dT%H:%M') if deadline_value else None,
            author_id=current_user.id,
            assignee_id=int(assignee_value) if assignee_value else None,
        )

        db.session.add(task)
        db.session.flush()

        # После flush у задачи уже есть `id`, поэтому можно безопасно писать историю и уведомления.
        db.session.add(TaskHistory(task_id=task.id, user_id=current_user.id, comment='Задача создана'))

        if task.assignee_id:
            _create_notification(
                task.assignee_id,
                f'Вам назначена новая задача "{task.title}"',
                link=url_for('tasks.task_detail', task_id=task.id),
                icon_type='info',
            )

        db.session.commit()
        flash('Задача создана', 'success')
        return redirect(url_for('tasks.task_detail', task_id=task.id))

    return render_template('task_form.html', task=None, employees=_employee_query().all())

# --- Редактирование задачи ---
@tasks_bp.route('/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def task_edit(task_id):
    task = Task.query.get_or_404(task_id)
    
    if not current_user.is_manager:
        flash('У вас нет прав на редактирование', 'danger')
        return redirect(url_for('tasks.task_list'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        duplicate_task = Task.query.filter(Task.title == title, Task.id != task.id).first()
        if duplicate_task:
            flash('Задача с таким названием уже существует', 'danger')
            return render_template('task_form.html', task=task, employees=_employee_query().all())

        # Запоминаем старого исполнителя, чтобы понять, нужно ли отправлять новое уведомление.
        previous_assignee_id = task.assignee_id
        task.title = title
        task.description = request.form.get('description', '').strip() or None
        assignee_value = request.form.get('assignee_id', '').strip()
        task.assignee_id = int(assignee_value) if assignee_value else None
        task.priority = request.form.get('priority', 'medium')
        
        deadline_str = request.form.get('deadline', '').strip()
        if deadline_str:
            task.deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
        else:
            task.deadline = None

        db.session.add(TaskHistory(task_id=task.id, user_id=current_user.id, comment='Параметры задачи обновлены'))

        if task.assignee_id and task.assignee_id != previous_assignee_id:
            _create_notification(
                task.assignee_id,
                f'Вам назначена задача "{task.title}"',
                link=url_for('tasks.task_detail', task_id=task.id),
                icon_type='info',
            )

        db.session.commit()
        flash('Задача сохранена', 'success')
        return redirect(url_for('tasks.task_detail', task_id=task.id))

    employees = _employee_query().all()
    return render_template('task_form.html', task=task, employees=employees)

# --- Карточка задачи ---
@tasks_bp.route('/tasks/<int:task_id>')
@login_required
def task_detail(task_id):
    task = Task.query.get_or_404(task_id)
    if not _can_access_task(task):
        abort(403)

    # Историю сортируем от новых записей к старым, чтобы последние изменения были видны сразу.
    history = task.history.order_by(TaskHistory.changed_at.desc()).all() # Получаем историю
    return render_template('task_detail.html', task=task, history=history)

# --- Изменение статуса ---
@tasks_bp.route('/tasks/<int:task_id>/status', methods=['POST'])
@login_required
def task_update_status(task_id):
    task = Task.query.get_or_404(task_id)
    if not _can_access_task(task):
        abort(403)

    # Один и тот же маршрут поддерживает и обычную HTML-форму, и AJAX-запрос с дашборда.
    payload = request.get_json(silent=True) if request.is_json else request.form
    new_status = (payload.get('status') or '').strip()
    comment = (payload.get('comment') or '').strip()

    if new_status and new_status != task.status:
        old_status = task.status
        task.status = new_status
        
        # Записываем в историю
        history = TaskHistory(
            task_id=task.id,
            user_id=current_user.id,
            old_status=old_status,
            new_status=new_status,
            comment=comment or None,
        )
        db.session.add(history)
        
        # Уведомления отправляем второй стороне процесса, чтобы участники видели смену статуса.
        target_user_id = task.author_id if current_user.id == task.assignee_id else task.assignee_id
        if target_user_id:
            _create_notification(
                target_user_id,
                f'Статус задачи "{task.title}" изменен на {task.status_label}',
                link=url_for('tasks.task_detail', task_id=task.id),
                icon_type='info',
            )

        db.session.commit()
        flash('Статус задачи обновлен', 'success')
        
    # Если запрос пришел из браузера с обычным переходом
    if not request.is_json:
        return redirect(url_for('tasks.task_detail', task_id=task.id))
    
    # Если запрос пришел из JS
    return 'OK', 200

# --- Удаление ---
@tasks_bp.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def task_delete(task_id):
    if current_user.is_manager:
        task = Task.query.get_or_404(task_id)
        # Сначала удаляем историю задачи
        TaskHistory.query.filter_by(task_id=task.id).delete()
        db.session.delete(task)
        db.session.commit()
        flash('Задача удалена', 'success')
    return redirect(url_for('tasks.task_list'))