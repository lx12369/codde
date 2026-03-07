BUILTIN_ADMIN_ACCOUNT = 'admin'
BUILTIN_SUPER_ADMIN_ACCOUNT = 'superadmin'
SUPER_ADMIN_ROLE = 'super_admin'
ADMIN_ROLE = 'admin'
STAFF_ROLE = 'staff'
MANAGEMENT_ROLES = {ADMIN_ROLE, SUPER_ADMIN_ROLE}


def normalize_role(value, fallback='staff'):
    if value is None:
        return fallback

    role = str(value).strip().lower()
    if not role:
        return fallback
    return role


def is_super_admin(user_or_role):
    role = user_or_role
    if hasattr(user_or_role, 'role'):
        role = getattr(user_or_role, 'role', None)
    return normalize_role(role, fallback='') == SUPER_ADMIN_ROLE


def is_admin(user_or_role):
    role = user_or_role
    if hasattr(user_or_role, 'role'):
        role = getattr(user_or_role, 'role', None)
    return normalize_role(role, fallback='') in MANAGEMENT_ROLES


def is_builtin_admin(user):
    return str(getattr(user, 'account', '') or '').strip().lower() == BUILTIN_ADMIN_ACCOUNT


def is_builtin_super_admin(user):
    account = str(getattr(user, 'account', '') or '').strip().lower()
    return account == BUILTIN_SUPER_ADMIN_ACCOUNT and is_super_admin(user)
