"""``GET /tariffs`` — каталог тарифов."""

from __future__ import annotations

from fastapi import APIRouter

from kvitto.api.deps import ContainerDep
from kvitto.api.schemas import TariffResponse, tariff_to_response

router = APIRouter(tags=["tariffs"])


@router.get("/tariffs", response_model=list[TariffResponse], summary="Список тарифов")
def list_tariffs(container: ContainerDep) -> list[TariffResponse]:
    return [tariff_to_response(tariff) for tariff in container.list_tariffs.execute()]
