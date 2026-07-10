from accounts.models import User


def sidebar_menu(request):
    menu = []
    if not request.user.is_authenticated:
        return {'sidebar_menu': menu}
    role = request.user.role
    is_admin = role in (User.Role.SUPER_ADMIN, User.Role.ADMIN)
    is_staff_or_above = role in (User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF)
    is_mechanic = role == User.Role.MECHANIC
    is_contractor_user = role == User.Role.CONTRACTOR
    is_trainee = role == User.Role.TRAINEE

    menu = [
        {'label': 'Dashboard', 'url': 'accounts:dashboard', 'icon': 'bi-speedometer2'},
    ]
    menu.append({'label': 'Trucks', 'url': 'trucks:list', 'icon': 'bi-truck'})

    if is_staff_or_above:
        menu.append({'label': 'PMS Schedules', 'url': 'pms:schedule_list', 'icon': 'bi-calendar-check'})

    if is_admin:
        menu.append({'label': 'PM Categories', 'url': 'pms:category_list', 'icon': 'bi-tags'})
        menu.append({'label': 'PM Templates', 'url': 'pms:template_list', 'icon': 'bi-list-task'})

    menu.append({'label': 'Job Orders', 'url': 'joborders:list', 'icon': 'bi-clipboard-check'})

    if is_mechanic or is_contractor_user:
        menu.append({'label': 'My Assignments', 'url': 'joborders:my_assignments', 'icon': 'bi-person-workspace'})

    if is_admin:
        menu.append({'label': 'Service Ledger', 'url': 'service_log:full_ledger', 'icon': 'bi-journal-text'})
        menu.append({'label': 'Contractors', 'url': 'contractors:list', 'icon': 'bi-building'})
        menu.append({'label': 'KPI Reports', 'url': 'kpi:mechanic', 'icon': 'bi-graph-up'})
        menu.append({'label': 'Trainee KPIs', 'url': 'kpi:trainee', 'icon': 'bi-mortarboard'})
        menu.append({'label': 'Predictive Analytics', 'url': 'kpi:predictive', 'icon': 'bi-graph-up-arrow'})

    if role == User.Role.SUPER_ADMIN:
        menu.append({'label': 'User Management', 'url': 'accounts:user_list', 'icon': 'bi-people'})

    if is_trainee:
        menu.append({'label': 'Training', 'url': 'training:dashboard', 'icon': 'bi-mortarboard-fill'})
        menu.append({'label': 'My KPIs', 'url': 'kpi:trainee', 'icon': 'bi-graph-up'})
        menu.append({'label': 'Holidays', 'url': 'training:holiday_list', 'icon': 'bi-calendar-event'})

    if is_staff_or_above:
        menu.append({'label': 'Training', 'url': 'training:dashboard', 'icon': 'bi-mortarboard-fill'})

    if is_admin:
        menu.append({'label': 'Assign Training', 'url': 'training:assign', 'icon': 'bi-person-plus'})
        menu.append({'label': 'Manage Holidays', 'url': 'training:holiday_list', 'icon': 'bi-calendar-event'})

    if is_trainee:
        menu = [m for m in menu if m['label'] != 'Job Orders']

    # SOP Manual — visible to all authenticated roles
    menu.append({'label': 'SOP Manual', 'url': 'sop:download_page', 'icon': 'bi-book'})

    return {'sidebar_menu': menu}
