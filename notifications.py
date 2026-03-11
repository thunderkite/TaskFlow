from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from models import db, Notification

# Создаем Blueprint для уведомлений (просмотр, управление)
notification_bp = Blueprint('notifications', __name__)


# Показываем уведомления пользователя в обратном хронологическом порядке,
# чтобы наверху всегда были самые свежие события.
@notification_bp.route('/notifications')
@login_required
def notifications():
    # Получаем все уведомления для текущего пользователя, сортируем по дате создания
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifications)


# Маршрут помечает конкретное уведомление прочитанным, но только для его владельца.
@notification_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_read(notif_id):
    # Получаем уведомление по ID и проверяем, что оно принадлежит текущему пользователю
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        return redirect(url_for('notifications.notifications')) # Редирект, если уведомление не принадлежит пользователю

    notif.is_read = True # Отмечаем уведомление как прочитанное
    db.session.commit() # Сохраняем изменения в базе данных
    return redirect(url_for('notifications.notifications')) # Редирект обратно на страницу уведомлений


# Массовое действие для страницы уведомлений: одним запросом закрываем все непрочитанные записи.
@notification_bp.route('/notifications/read_all', methods=['POST'])
@login_required
def mark_all_as_read():
    # Получаем все непрочитанные уведомления для текущего пользователя и отмечаем их как прочитанные
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit() # Сохраняем изменения в базе данных
    return redirect(url_for('notifications.notifications')) # Редирект обратно на страницу уведомлений

