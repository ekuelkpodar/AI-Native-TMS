"""Vehicles (fleet) CRUD."""

from .. import deps, models, schemas
from .crud import make_crud

router = make_crud(
    model=models.Vehicle,
    create_schema=schemas.VehicleCreate,
    update_schema=schemas.VehicleUpdate,
    out_schema=schemas.VehicleOut,
    prefix="/vehicles",
    tags=["vehicles"],
    read_roles=("admin", "dispatcher", "broker", "ops_manager", "driver"),
    write_roles=("admin", "dispatcher"),
    search_fields=("unit_number", "vin", "license_plate", "make", "model"),
    soft_delete_field="is_active",
    entity_name="vehicles",
)
