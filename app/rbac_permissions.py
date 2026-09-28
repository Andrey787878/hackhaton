"""Константы slug-разрешений RBAC."""


class PermissionSlugs:
    """Набор permission-slug для обязательных операций ЛР3."""

    GET_LIST_USER = "get-list-user"
    READ_USER = "read-user"
    UPDATE_USER = "update-user"
    DELETE_USER = "delete-user"
    RESTORE_USER = "restore-user"

    GET_LIST_ROLE = "get-list-role"
    READ_ROLE = "read-role"
    CREATE_ROLE = "create-role"
    UPDATE_ROLE = "update-role"
    DELETE_ROLE = "delete-role"
    RESTORE_ROLE = "restore-role"

    GET_LIST_PERMISSION = "get-list-permission"
    READ_PERMISSION = "read-permission"
    CREATE_PERMISSION = "create-permission"
    UPDATE_PERMISSION = "update-permission"
    DELETE_PERMISSION = "delete-permission"
    RESTORE_PERMISSION = "restore-permission"

    CREATE_HACKATHON = "create-hackathon"
    MANAGE_HACKATHON = "manage-hackathon"
    ASSIGN_EXPERT = "assign-expert"
    CREATE_TEAM = "create-team"
    JOIN_TEAM = "join-team"
    SUBMIT_SOLUTION = "submit-solution"
    READ_ASSIGNED_SUBMISSION = "read-assigned-submission"
    SCORE_SUBMISSION = "score-submission"
