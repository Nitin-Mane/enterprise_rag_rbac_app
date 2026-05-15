def can_access(user, source):
    department_ok = "all" in source.departments or user.department in source.departments
    role_ok = "all" in source.allowed_roles or user.role in source.allowed_roles
    clearance_ok = user.clearance >= source.min_clearance
    return department_ok and role_ok and clearance_ok


def visible_sources_for(user, sources):
    visible = []
    blocked = []
    for source in sources:
        if can_access(user, source):
            visible.append(source)
        else:
            blocked.append(
                {
                    "source_id": source.source_id,
                    "title": source.title,
                    "reason": "RBAC policy denied department, role, or clearance access.",
                }
            )
    return visible, blocked
