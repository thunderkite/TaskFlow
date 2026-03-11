from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import User, Task
from datetime import datetime

# Создаем Blueprint для отчетов (статистика по задачам)
reports_bp = Blueprint('reports', __name__)


# Все отчеты доступны только руководителю, поэтому вынесли общую проверку в helper.
def _manager_only_redirect():
    if current_user.is_manager:
        return None

    flash('Раздел отчетов доступен только руководителю', 'danger')
    return redirect(url_for('tasks.dashboard'))

@reports_bp.route('/reports')
@login_required # Только для авторизованных пользователей
def reports():
    redirect_response = _manager_only_redirect()
    if redirect_response:
        return redirect_response

    return render_template('reports.html')


# Отчет по загрузке собирает количество задач по каждому статусу для каждого исполнителя.
@reports_bp.route('/reports/workload')
@login_required
def report_workload():
    redirect_response = _manager_only_redirect()
    if redirect_response:
        return redirect_response

    # Получаем всех сотрудников
    employees = User.query.filter_by(role='employee').all()

    # Формируем данные для отчета о загрузке сотрудников
    workload_data = []

    for emp in employees:
        # Начинаем счетчики с нуля для каждого статуса
        counts = {
            'new': 0,
            'in_progress': 0,
            'done': 0,
            'overdue': 0,
        }
        employee_tasks = Task.query.filter_by(assignee_id=emp.id).all()

        for task in employee_tasks:
            # effective_status учитывает просрочку по дедлайну, даже если статус в базе ещё не обновлён
            status = task.effective_status
            if status in counts:
                counts[status] += 1

        counts['total'] = len(employee_tasks)
        workload_data.append({'user': emp, 'counts': counts})

    return render_template('report_workload.html', data=workload_data)
    

# Этот отчет показывает завершенные задачи и поддерживает фильтрацию по диапазону дат.
@reports_bp.route('/reports/done')
@login_required
def report_done():
    redirect_response = _manager_only_redirect()
    if redirect_response:
        return redirect_response

    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    # Получаем все задачи со статусом "сделано"
    query = Task.query.filter_by(status='done')

    # Ограничиваем выборку по дате завершения через поле `updated_at`.
    if date_from:
        from_dt = datetime.strptime(date_from, '%Y-%m-%d')
        query = query.filter(Task.updated_at >= from_dt)

    if date_to:
        # Берём конец дня, чтобы включить задачи, выполненные в этот же день
        to_dt = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query = query.filter(Task.updated_at < to_dt)

    done_tasks = query.order_by(Task.updated_at.desc()).all()
    return render_template('report_done.html', tasks=done_tasks, date_from=date_from, date_to=date_to)


# Отчет по просроченным задачам показывает только актуально просроченные записи.
@reports_bp.route('/reports/overdue')
@login_required
def report_overdue():
    redirect_response = _manager_only_redirect()
    if redirect_response:
        return redirect_response

    # Берём все незавершённые задачи и оставляем только те, у которых вышел дедлайн.
    # Логика определения «просрочено» уже описана в модели Task (свойство is_overdue).
    active_tasks = Task.query.filter(Task.status != 'done').all()
    overdue_tasks = [task for task in active_tasks if task.is_overdue]

    # Сортируем по дедлайну: кто просрочен раньше всех — тот вверху
    overdue_tasks.sort(key=lambda task: task.deadline or datetime.max)

    return render_template('report_overdue.html', tasks=overdue_tasks)