"""Policies CRUD (admin). The policy *engine* lives in the AI track;
this router only manages the policy table rows."""

from .. import models, schemas
from .crud import make_crud

router = make_crud(
    model=models.Policy,
    create_schema=schemas.PolicyCreate,
    update_schema=schemas.PolicyUpdate,
    out_schema=schemas.PolicyOut,
    prefix="/policies",
    tags=["policies"],
    read_roles=("admin",),
    write_roles=("admin",),
    search_fields=("name", "description"),
    entity_name="policies",
)
