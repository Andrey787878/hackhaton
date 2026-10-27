from __future__ import annotations

from collections.abc import Callable
from typing import NoReturn, TypeVar

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.dependencies import (
    CurrentUserContext,
    get_current_user_context,
    get_rbac_service,
    require_permission,
)
from app.dto import (
    MessageResponseDTO,
    PermissionCollectionDTO,
    PermissionDTO,
    RoleCollectionDTO,
    RoleDTO,
    UserDTO,
)
from app.rbac_permissions import PermissionSlugs
from app.rbac_service import (
    RbacConflictError,
    RbacNotFoundError,
    RbacPersistenceError,
    RbacService,
    RbacServiceError,
)
from app.schemas import (
    AttachRolePermissionRequest,
    AttachUserRoleRequest,
    StorePermissionRequest,
    StoreRoleRequest,
    UpdatePermissionRequest,
    UpdateRoleRequest,
)


router = APIRouter(prefix="/admin", tags=["rbac"])
_ResultT = TypeVar("_ResultT")


def _raise_http_for_rbac_error(
    error: RbacServiceError | SQLAlchemyError | ValueError,
) -> NoReturn:
    """Преобразует доменные RBAC-ошибки в HTTPException."""
    if isinstance(error, RbacNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, RbacConflictError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))
    if isinstance(error, RbacPersistenceError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Временная ошибка сохранения данных. Повторите попытку позже.",
        )
    if isinstance(error, SQLAlchemyError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Временная ошибка доступа к данным. Повторите попытку позже.",
        )
    if isinstance(error, ValueError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))
    if isinstance(error, RbacServiceError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Внутренняя ошибка RBAC.",
    ) from error


def _call_rbac(fn: Callable[[], _ResultT]) -> _ResultT:
    """Выполняет RBAC-операцию и маппит доменные ошибки в HTTPException."""
    try:
        return fn()
    except (RbacServiceError, SQLAlchemyError, ValueError) as exc:
        _raise_http_for_rbac_error(exc)


@router.get(
    "/user",
    summary="Список пользователей",
    response_model=list[UserDTO],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.GET_LIST_USER))],
)
def list_users(
    rbac_service: RbacService = Depends(get_rbac_service),
) -> list[UserDTO]:
    """Возвращает список пользователей."""
    return _call_rbac(rbac_service.list_users)


@router.get(
    "/user/{user_id}/role",
    summary="Список активных ролей пользователя",
    response_model=RoleCollectionDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.READ_USER))],
)
def list_user_roles(
    user_id: int,
    rbac_service: RbacService = Depends(get_rbac_service),
) -> RoleCollectionDTO:
    """Возвращает активные роли пользователя."""
    return _call_rbac(lambda: rbac_service.list_user_active_roles(user_id=user_id))


@router.post(
    "/user/{user_id}/role",
    summary="Назначить роль пользователю",
    response_model=RoleDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.UPDATE_USER))],
)
def attach_user_role(
    user_id: int,
    payload: AttachUserRoleRequest,
    context: CurrentUserContext = Depends(get_current_user_context),
    rbac_service: RbacService = Depends(get_rbac_service),
) -> RoleDTO:
    """Назначает роль пользователю."""
    data = payload.to_dto()
    return _call_rbac(
        lambda: rbac_service.attach_user_role(
            user_id=user_id,
            role_id=data.role_id,
            actor_user_id=context.user_id,
        )
    )


@router.delete(
    "/user/{user_id}/role/{role_id}",
    summary="Удалить связь пользователь-роль (hard)",
    response_model=MessageResponseDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.DELETE_USER))],
)
def hard_delete_user_role(
    user_id: int,
    role_id: int,
    rbac_service: RbacService = Depends(get_rbac_service),
) -> MessageResponseDTO:
    """Физически удаляет связь пользователь-роль."""
    _call_rbac(lambda: rbac_service.hard_delete_user_role(user_id=user_id, role_id=role_id))
    return MessageResponseDTO(message="Связь пользователь-роль удалена.")


@router.delete(
    "/user/{user_id}/role/{role_id}/soft",
    summary="Мягко удалить связь пользователь-роль",
    response_model=MessageResponseDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.DELETE_USER))],
)
def soft_delete_user_role(
    user_id: int,
    role_id: int,
    context: CurrentUserContext = Depends(get_current_user_context),
    rbac_service: RbacService = Depends(get_rbac_service),
) -> MessageResponseDTO:
    """Мягко удаляет связь пользователь-роль."""
    _call_rbac(
        lambda: rbac_service.soft_delete_user_role(
            user_id=user_id,
            role_id=role_id,
            actor_user_id=context.user_id,
        )
    )
    return MessageResponseDTO(message="Связь пользователь-роль мягко удалена.")


@router.post(
    "/user/{user_id}/role/{role_id}/restore",
    summary="Восстановить связь пользователь-роль",
    response_model=MessageResponseDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.RESTORE_USER))],
)
def restore_user_role(
    user_id: int,
    role_id: int,
    rbac_service: RbacService = Depends(get_rbac_service),
) -> MessageResponseDTO:
    """Восстанавливает мягко удалённую связь пользователь-роль."""
    _call_rbac(lambda: rbac_service.restore_user_role(user_id=user_id, role_id=role_id))
    return MessageResponseDTO(message="Связь пользователь-роль восстановлена.")


@router.get(
    "/policy/role",
    summary="Список ролей",
    response_model=RoleCollectionDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.GET_LIST_ROLE))],
)
def list_roles(
    rbac_service: RbacService = Depends(get_rbac_service),
) -> RoleCollectionDTO:
    """Возвращает список ролей."""
    return _call_rbac(rbac_service.list_roles)


@router.get(
    "/policy/role/{role_id}",
    summary="Получить роль по ID",
    response_model=RoleDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.READ_ROLE))],
)
def get_role(
    role_id: int,
    rbac_service: RbacService = Depends(get_rbac_service),
) -> RoleDTO:
    """Возвращает роль по id."""
    return _call_rbac(lambda: rbac_service.get_role(role_id=role_id))


@router.post(
    "/policy/role",
    summary="Создать роль",
    response_model=RoleDTO,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(PermissionSlugs.CREATE_ROLE))],
)
def create_role(
    payload: StoreRoleRequest,
    context: CurrentUserContext = Depends(get_current_user_context),
    rbac_service: RbacService = Depends(get_rbac_service),
) -> RoleDTO:
    """Создаёт роль."""
    return _call_rbac(
        lambda: rbac_service.create_role(
            data=payload.to_dto(),
            actor_user_id=context.user_id,
        )
    )


@router.put(
    "/policy/role/{role_id}",
    summary="Полностью обновить роль (PUT)",
    response_model=RoleDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.UPDATE_ROLE))],
)
def update_role_put(
    role_id: int,
    payload: StoreRoleRequest,
    context: CurrentUserContext = Depends(get_current_user_context),
    rbac_service: RbacService = Depends(get_rbac_service),
) -> RoleDTO:
    """Полностью обновляет роль (PUT)."""
    return _call_rbac(
        lambda: rbac_service.update_role_put(
            role_id=role_id,
            data=payload.to_dto(),
            actor_user_id=context.user_id,
        )
    )


@router.patch(
    "/policy/role/{role_id}",
    summary="Частично обновить роль (PATCH)",
    response_model=RoleDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.UPDATE_ROLE))],
)
def update_role_patch(
    role_id: int,
    payload: UpdateRoleRequest,
    context: CurrentUserContext = Depends(get_current_user_context),
    rbac_service: RbacService = Depends(get_rbac_service),
) -> RoleDTO:
    """Частично обновляет роль (PATCH)."""
    return _call_rbac(
        lambda: rbac_service.update_role_patch(
            role_id=role_id,
            data=payload.to_dto(),
            actor_user_id=context.user_id,
        )
    )


@router.delete(
    "/policy/role/{role_id}",
    summary="Удалить роль (hard)",
    response_model=MessageResponseDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.DELETE_ROLE))],
)
def hard_delete_role(
    role_id: int,
    rbac_service: RbacService = Depends(get_rbac_service),
) -> MessageResponseDTO:
    """Физически удаляет роль."""
    _call_rbac(lambda: rbac_service.hard_delete_role(role_id=role_id))
    return MessageResponseDTO(message="Роль удалена.")


@router.delete(
    "/policy/role/{role_id}/soft",
    summary="Мягко удалить роль",
    response_model=MessageResponseDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.DELETE_ROLE))],
)
def soft_delete_role(
    role_id: int,
    context: CurrentUserContext = Depends(get_current_user_context),
    rbac_service: RbacService = Depends(get_rbac_service),
) -> MessageResponseDTO:
    """Мягко удаляет роль."""
    _call_rbac(lambda: rbac_service.soft_delete_role(role_id=role_id, actor_user_id=context.user_id))
    return MessageResponseDTO(message="Роль мягко удалена.")


@router.post(
    "/policy/role/{role_id}/restore",
    summary="Восстановить роль",
    response_model=MessageResponseDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.RESTORE_ROLE))],
)
def restore_role(
    role_id: int,
    rbac_service: RbacService = Depends(get_rbac_service),
) -> MessageResponseDTO:
    """Восстанавливает мягко удалённую роль."""
    _call_rbac(lambda: rbac_service.restore_role(role_id=role_id))
    return MessageResponseDTO(message="Роль восстановлена.")


@router.get(
    "/policy/permission",
    summary="Список разрешений",
    response_model=PermissionCollectionDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.GET_LIST_PERMISSION))],
)
def list_permissions(
    rbac_service: RbacService = Depends(get_rbac_service),
) -> PermissionCollectionDTO:
    """Возвращает список разрешений."""
    return _call_rbac(rbac_service.list_permissions)


@router.get(
    "/policy/permission/{permission_id}",
    summary="Получить разрешение по ID",
    response_model=PermissionDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.READ_PERMISSION))],
)
def get_permission(
    permission_id: int,
    rbac_service: RbacService = Depends(get_rbac_service),
) -> PermissionDTO:
    """Возвращает разрешение по id."""
    return _call_rbac(lambda: rbac_service.get_permission(permission_id=permission_id))


@router.post(
    "/policy/permission",
    summary="Создать разрешение",
    response_model=PermissionDTO,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(PermissionSlugs.CREATE_PERMISSION))],
)
def create_permission(
    payload: StorePermissionRequest,
    context: CurrentUserContext = Depends(get_current_user_context),
    rbac_service: RbacService = Depends(get_rbac_service),
) -> PermissionDTO:
    """Создаёт разрешение."""
    return _call_rbac(
        lambda: rbac_service.create_permission(
            data=payload.to_dto(),
            actor_user_id=context.user_id,
        )
    )


@router.put(
    "/policy/permission/{permission_id}",
    summary="Полностью обновить разрешение (PUT)",
    response_model=PermissionDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.UPDATE_PERMISSION))],
)
def update_permission_put(
    permission_id: int,
    payload: StorePermissionRequest,
    context: CurrentUserContext = Depends(get_current_user_context),
    rbac_service: RbacService = Depends(get_rbac_service),
) -> PermissionDTO:
    """Полностью обновляет разрешение (PUT)."""
    return _call_rbac(
        lambda: rbac_service.update_permission_put(
            permission_id=permission_id,
            data=payload.to_dto(),
            actor_user_id=context.user_id,
        )
    )


@router.patch(
    "/policy/permission/{permission_id}",
    summary="Частично обновить разрешение (PATCH)",
    response_model=PermissionDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.UPDATE_PERMISSION))],
)
def update_permission_patch(
    permission_id: int,
    payload: UpdatePermissionRequest,
    context: CurrentUserContext = Depends(get_current_user_context),
    rbac_service: RbacService = Depends(get_rbac_service),
) -> PermissionDTO:
    """Частично обновляет разрешение (PATCH)."""
    return _call_rbac(
        lambda: rbac_service.update_permission_patch(
            permission_id=permission_id,
            data=payload.to_dto(),
            actor_user_id=context.user_id,
        )
    )


@router.delete(
    "/policy/permission/{permission_id}",
    summary="Удалить разрешение (hard)",
    response_model=MessageResponseDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.DELETE_PERMISSION))],
)
def hard_delete_permission(
    permission_id: int,
    rbac_service: RbacService = Depends(get_rbac_service),
) -> MessageResponseDTO:
    """Физически удаляет разрешение."""
    _call_rbac(lambda: rbac_service.hard_delete_permission(permission_id=permission_id))
    return MessageResponseDTO(message="Разрешение удалено.")


@router.delete(
    "/policy/permission/{permission_id}/soft",
    summary="Мягко удалить разрешение",
    response_model=MessageResponseDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.DELETE_PERMISSION))],
)
def soft_delete_permission(
    permission_id: int,
    context: CurrentUserContext = Depends(get_current_user_context),
    rbac_service: RbacService = Depends(get_rbac_service),
) -> MessageResponseDTO:
    """Мягко удаляет разрешение."""
    _call_rbac(
        lambda: rbac_service.soft_delete_permission(
            permission_id=permission_id,
            actor_user_id=context.user_id,
        )
    )
    return MessageResponseDTO(message="Разрешение мягко удалено.")


@router.post(
    "/policy/permission/{permission_id}/restore",
    summary="Восстановить разрешение",
    response_model=MessageResponseDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.RESTORE_PERMISSION))],
)
def restore_permission(
    permission_id: int,
    rbac_service: RbacService = Depends(get_rbac_service),
) -> MessageResponseDTO:
    """Восстанавливает мягко удалённое разрешение."""
    _call_rbac(lambda: rbac_service.restore_permission(permission_id=permission_id))
    return MessageResponseDTO(message="Разрешение восстановлено.")


@router.get(
    "/policy/role/{role_id}/permission",
    summary="Список активных разрешений роли",
    response_model=PermissionCollectionDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.READ_ROLE))],
)
def list_role_permissions(
    role_id: int,
    rbac_service: RbacService = Depends(get_rbac_service),
) -> PermissionCollectionDTO:
    """Возвращает активные разрешения роли."""
    return _call_rbac(lambda: rbac_service.list_role_active_permissions(role_id=role_id))


@router.post(
    "/policy/role/{role_id}/permission",
    summary="Назначить разрешение роли",
    response_model=PermissionDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.UPDATE_ROLE))],
)
def attach_role_permission(
    role_id: int,
    payload: AttachRolePermissionRequest,
    context: CurrentUserContext = Depends(get_current_user_context),
    rbac_service: RbacService = Depends(get_rbac_service),
) -> PermissionDTO:
    """Назначает разрешение роли."""
    data = payload.to_dto()
    return _call_rbac(
        lambda: rbac_service.attach_role_permission(
            role_id=role_id,
            permission_id=data.permission_id,
            actor_user_id=context.user_id,
        )
    )


@router.delete(
    "/policy/role/{role_id}/permission/{permission_id}",
    summary="Удалить связь роль-разрешение (hard)",
    response_model=MessageResponseDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.DELETE_ROLE))],
)
def hard_delete_role_permission(
    role_id: int,
    permission_id: int,
    rbac_service: RbacService = Depends(get_rbac_service),
) -> MessageResponseDTO:
    """Физически удаляет связь роль-разрешение."""
    _call_rbac(
        lambda: rbac_service.hard_delete_role_permission(
            role_id=role_id,
            permission_id=permission_id,
        )
    )
    return MessageResponseDTO(message="Связь роль-разрешение удалена.")


@router.delete(
    "/policy/role/{role_id}/permission/{permission_id}/soft",
    summary="Мягко удалить связь роль-разрешение",
    response_model=MessageResponseDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.DELETE_ROLE))],
)
def soft_delete_role_permission(
    role_id: int,
    permission_id: int,
    context: CurrentUserContext = Depends(get_current_user_context),
    rbac_service: RbacService = Depends(get_rbac_service),
) -> MessageResponseDTO:
    """Мягко удаляет связь роль-разрешение."""
    _call_rbac(
        lambda: rbac_service.soft_delete_role_permission(
            role_id=role_id,
            permission_id=permission_id,
            actor_user_id=context.user_id,
        )
    )
    return MessageResponseDTO(message="Связь роль-разрешение мягко удалена.")


@router.post(
    "/policy/role/{role_id}/permission/{permission_id}/restore",
    summary="Восстановить связь роль-разрешение",
    response_model=MessageResponseDTO,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionSlugs.RESTORE_ROLE))],
)
def restore_role_permission(
    role_id: int,
    permission_id: int,
    rbac_service: RbacService = Depends(get_rbac_service),
) -> MessageResponseDTO:
    """Восстанавливает мягко удалённую связь роль-разрешение."""
    _call_rbac(
        lambda: rbac_service.restore_role_permission(
            role_id=role_id,
            permission_id=permission_id,
        )
    )
    return MessageResponseDTO(message="Связь роль-разрешение восстановлена.")
