from accounts.models import User


def _link(label, url_name, icon):
    return {'label': label, 'url': url_name, 'icon': icon}


def sidebar_menu(request):
    sections = []
    if not request.user.is_authenticated:
        return {'sidebar_sections': sections}
    role = request.user.role
    is_admin = role in (User.Role.SUPER_ADMIN, User.Role.ADMIN)
    is_staff_or_above = role in (User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF)
    is_mechanic = role == User.Role.MECHANIC
    is_contractor_user = role == User.Role.CONTRACTOR
    is_trainee = role == User.Role.TRAINEE

    # Dashboard — always first, no collapsible section
    sections.append({'heading': None, 'items': [
        _link('Dashboard', 'accounts:dashboard', 'bi-speedometer2'),
    ]})

    # Fleet
    fleet = [_link('Trucks', 'trucks:list', 'bi-truck')]
    sections.append({'heading': 'Fleet', 'items': fleet})

    # Preventive Maintenance
    if is_staff_or_above:
        pm = [_link('PMS Schedules', 'pms:schedule_list', 'bi-calendar-check')]
        if is_admin:
            pm.append(_link('PM Categories', 'pms:category_list', 'bi-tags'))
            pm.append(_link('PM Templates', 'pms:template_list', 'bi-list-task'))
        sections.append({'heading': 'Preventive Maintenance', 'items': pm})

    # Work Orders
    if not is_trainee:
        wo = [_link('Job Orders', 'joborders:list', 'bi-clipboard-check')]
        if is_mechanic or is_contractor_user:
            wo.append(_link('My Assignments', 'joborders:my_assignments', 'bi-person-workspace'))
        sections.append({'heading': 'Work Orders', 'items': wo})

    # Service & Contractors
    if is_admin:
        sections.append({'heading': 'Service & Contractors', 'items': [
            _link('Service Ledger', 'service_log:full_ledger', 'bi-journal-text'),
            _link('Contractors', 'contractors:list', 'bi-building'),
        ]})

    # Analytics
    if is_admin:
        sections.append({'heading': 'Analytics', 'items': [
            _link('KPI Reports', 'kpi:mechanic', 'bi-graph-up'),
            _link('Trainee KPIs', 'kpi:trainee', 'bi-mortarboard'),
            _link('Predictive Analytics', 'kpi:predictive', 'bi-graph-up-arrow'),
        ]})

    # Training
    if is_staff_or_above or is_trainee:
        training = []
        if is_trainee:
            training.append(_link('My Training', 'training:dashboard', 'bi-mortarboard-fill'))
            training.append(_link('My KPIs', 'kpi:trainee', 'bi-graph-up'))
            training.append(_link('Holidays', 'training:holiday_list', 'bi-calendar-event'))
        if is_staff_or_above:
            training.append(_link('Training Dashboard', 'training:dashboard', 'bi-mortarboard-fill'))
            if is_admin:
                training.append(_link('Assign Training', 'training:assign', 'bi-person-plus'))
                training.append(_link('Manage Holidays', 'training:holiday_list', 'bi-calendar-event'))
        sections.append({'heading': 'Training', 'items': training})

    # Administration
    if role == User.Role.SUPER_ADMIN:
        sections.append({'heading': 'Administration', 'items': [
            _link('User Management', 'accounts:user_list', 'bi-people'),
        ]})

    # Resources
    sections.append({'heading': 'Resources', 'items': [
        _link('SOP Manual', 'sop:download_page', 'bi-book'),
    ]})

    # Account (logout)
    sections.append({'heading': 'Account', 'items': [
        _link('Logout', 'accounts:logout', 'bi-box-arrow-left'),
    ], 'is_logout': True})

    return {'sidebar_sections': sections}
