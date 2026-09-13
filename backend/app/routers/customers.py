"""Customers CRUD. Shippers see only their own customer record."""

from .. import deps, models, schemas
from .crud import make_crud

router = make_crud(
    model=models.Customer,
    create_schema=schemas.CustomerCreate,
    update_schema=schemas.CustomerUpdate,
    out_schema=schemas.CustomerOut,
    prefix="/customers",
    tags=["customers"],
    read_roles=("admin", "broker", "dispatcher", "finance", "ops_manager", "shipper"),
    write_roles=("admin", "broker", "dispatcher"),
    search_fields=("name", "contact_name", "email", "city", "state"),
    scope_fn=deps.scope_customers,
    soft_delete_field="is_active",
    entity_name="customers",
)
