"""Audit logging service."""

from sqlalchemy.ext.asyncio import AsyncSession

from obsidian_sync.models.audit import AuditLog


async def log_action(
    db: AsyncSession,
    actor_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str,
    details: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Record an audit log entry."""
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    return entry
