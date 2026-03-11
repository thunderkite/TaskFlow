// Auto-dismiss flash messages after 4 seconds
document.addEventListener('DOMContentLoaded', () => {
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach(el => {
    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transition = 'opacity .3s';
      setTimeout(() => el.remove(), 300);
    }, 4000);
  });

  // Handle status option clicks in task detail
  document.querySelectorAll('.status-option').forEach(opt => {
    opt.addEventListener('click', () => {
      document.querySelectorAll('.status-option').forEach(o => o.classList.remove('selected'));
      opt.classList.add('selected');
    });
  });

  initDashboardPopovers();
  initDashboardDnD();
});

function initDashboardPopovers() {
  const filtersBtn = document.getElementById('btn-dashboard-filters');
  const groupingBtn = document.getElementById('btn-dashboard-grouping');
  const filtersPopover = document.getElementById('dashboard-filters-popover');
  const groupingPopover = document.getElementById('dashboard-grouping-popover');

  if (!filtersBtn || !groupingBtn || !filtersPopover || !groupingPopover) {
    return;
  }

  const closeAll = () => {
    filtersPopover.classList.remove('open');
    groupingPopover.classList.remove('open');
    filtersBtn.classList.remove('active');
    groupingBtn.classList.remove('active');
  };

  filtersBtn.addEventListener('click', (event) => {
    event.stopPropagation();
    const nextOpen = !filtersPopover.classList.contains('open');
    closeAll();
    if (nextOpen) {
      filtersPopover.classList.add('open');
      filtersBtn.classList.add('active');
    }
  });

  groupingBtn.addEventListener('click', (event) => {
    event.stopPropagation();
    const nextOpen = !groupingPopover.classList.contains('open');
    closeAll();
    if (nextOpen) {
      groupingPopover.classList.add('open');
      groupingBtn.classList.add('active');
    }
  });

  [filtersPopover, groupingPopover].forEach((popover) => {
    popover.addEventListener('click', (event) => event.stopPropagation());
  });

  document.addEventListener('click', () => closeAll());
}

function initDashboardDnD() {
  const board = document.querySelector('.kanban-board[data-dashboard-group="status"]');
  if (!board) {
    return;
  }

  const cards = board.querySelectorAll('.task-card-draggable[data-task-id]');
  const zones = board.querySelectorAll('.kanban-dropzone[data-status]');
  let activeCard = null;

  cards.forEach((card) => {
    card.addEventListener('dragstart', (event) => {
      activeCard = card;
      card.classList.add('is-dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/task-id', card.dataset.taskId);
      event.dataTransfer.setData('text/from-status', card.dataset.taskStatus);
    });

    card.addEventListener('dragend', () => {
      card.classList.remove('is-dragging');
      zones.forEach((zone) => zone.classList.remove('drag-over'));
      activeCard = null;
    });
  });

  zones.forEach((zone) => {
    zone.addEventListener('dragover', (event) => {
      event.preventDefault();
      zone.classList.add('drag-over');
    });

    zone.addEventListener('dragleave', () => {
      zone.classList.remove('drag-over');
    });

    zone.addEventListener('drop', async (event) => {
      event.preventDefault();
      zone.classList.remove('drag-over');

      const taskId = event.dataTransfer.getData('text/task-id');
      const fromStatus = event.dataTransfer.getData('text/from-status');
      const toStatus = zone.dataset.status;

      if (!taskId || !toStatus || fromStatus === toStatus) {
        return;
      }

      try {
        const body = new URLSearchParams();
        body.append('status', toStatus);
        body.append('comment', 'Статус изменен перетаскиванием на доске');

        const response = await fetch(`/tasks/${taskId}/status`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
          },
          body: body.toString(),
          credentials: 'same-origin',
          redirect: 'follow',
        });

        if (!response.ok) {
          throw new Error('Не удалось изменить статус');
        }

        if (activeCard) {
          activeCard.classList.remove('is-dragging');
        }
        window.location.reload();
      } catch (error) {
        alert('Не удалось переместить задачу. Обновите страницу и попробуйте снова.');
      }
    });
  });
}
