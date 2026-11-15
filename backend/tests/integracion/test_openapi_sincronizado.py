"""El contrato que usa el frontend (frontend/openapi.json) coincide con la API (§11.7)."""

import json

from app.cli import exportar_openapi
from tests.ayudas import RAIZ_REPO


def test_openapi_sincronizado() -> None:
    archivo = RAIZ_REPO / "frontend" / "openapi.json"
    assert json.loads(archivo.read_text(encoding="utf-8")) == json.loads(exportar_openapi()), (
        "frontend/openapi.json está desactualizado. Desde backend/: "
        "uv run python -m app.cli exportar-openapi > ../frontend/openapi.json "
        "y después, en frontend/, npm run tipos"
    )
