"""Drivers CRUD. Drivers see only themselves; carriers see their own drivers."""

from .. import deps, models, schemas
from .crud import make_crud

router = make_crud(
    model=models.Driver,
    create_schema=schemas.DriverCreate,
    update_schema=schemas.DriverUpdate,
    out_schema=schemas.DriverOut,
    prefix="/drivers",
    tags=["drivers"],
    read_roles=("admin", "dispatcher", "broker", "ops_manager", "driver", "carrier"),
    write_roles=("admin", "dispatcher"),
    search_fields=("full_name", "phone", "email", "license_number"),
    scope_fn=deps.scope_drivers,
    soft_delete_field="is_active",
    entity_name="drivers",
)
