"""AI agent registry: table CRUD only (admin).

The AI control plane (policy engine, tool execution, heuristic agents) is
owned by a separate track under backend/app/ai/ — this router never executes
agent logic.
"""

from .. import models, schemas
from .crud import make_crud

router = make_crud(
    model=models.AIAgent,
    create_schema=schemas.AIAgentCreate,
    update_schema=schemas.AIAgentUpdate,
    out_schema=schemas.AIAgentOut,
    prefix="/agents",
    tags=["agents"],
    read_roles=("admin",),
    write_roles=("admin",),
    search_fields=("name", "model", "owner"),
    entity_name="ai_agents",
    include=("list", "update"),  # contract: GET /agents, PUT /agents/{id}
)
