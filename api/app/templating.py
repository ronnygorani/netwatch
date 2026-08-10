"""Config templating: variable inheritance plus sandboxed Jinja2 rendering.

Mirrors the group_vars/host_vars model network teams already use with Ansible:
define a value once at the broadest scope that is true, override it only where
a device or site genuinely differs.
"""

from jinja2 import StrictUndefined, TemplateError
from jinja2.sandbox import SandboxedEnvironment
from sqlalchemy.orm import Session

from app.models.config_template import ConfigTemplate, ConfigVariable
from app.models.device import Device

# Sandboxed: templates are operator-authored but render inside our process, so
# an unsandboxed environment would let a template reach Python internals
# (server-side template injection). StrictUndefined turns a typo'd variable
# into an error instead of silently rendering an empty string into a switch.
_env = SandboxedEnvironment(undefined=StrictUndefined, keep_trailing_newline=True)

SCOPES = ("global", "site", "device")


def deep_merge(base: dict, overlay: dict) -> dict:
    """Overlay wins. Nested dicts merge key by key; lists replace wholesale.

    List-replace matches Ansible's default and keeps overrides predictable:
    a site that declares vlans gets exactly those, not the union with global.
    """
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def resolve_variables(db: Session, device: Device) -> dict:
    """Merge global -> site -> device variables for one device."""
    rows = (
        db.query(ConfigVariable)
        .filter(
            (ConfigVariable.scope == "global")
            | ((ConfigVariable.scope == "site") & (ConfigVariable.scope_ref == device.site))
            | ((ConfigVariable.scope == "device") & (ConfigVariable.scope_ref == str(device.id)))
        )
        .all()
    )
    by_scope = {row.scope: row.data for row in rows}
    merged: dict = {}
    for scope in SCOPES:
        merged = deep_merge(merged, by_scope.get(scope) or {})
    return merged


def device_context(db: Session, device: Device) -> dict:
    """Variables plus the device's own facts, available to every template."""
    return {
        **resolve_variables(db, device),
        "device": {
            "id": device.id,
            "hostname": device.hostname,
            "ip_address": device.ip_address,
            "site": device.site,
            "device_type": device.device_type,
        },
    }


def render_for_device(db: Session, template: ConfigTemplate, device: Device) -> str:
    """Render one template for one device. Raises ValueError on template errors."""
    try:
        return _env.from_string(template.body).render(**device_context(db, device))
    except TemplateError as exc:
        raise ValueError(
            f"Template '{template.name}' failed for {device.hostname}: {exc}"
        ) from None
