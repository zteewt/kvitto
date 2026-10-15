"""``POST /webhooks/bank`` — уведомление банка о смене статуса."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from kvitto.api.deps import ContainerDep, require_webhook_signature
from kvitto.api.schemas import BankWebhookRequest, WebhookResponse
from kvitto.application.dto import ChangePaymentStatusCommand

router = APIRouter(tags=["webhooks"])


@router.post(
    "/webhooks/bank",
    response_model=WebhookResponse,
    dependencies=[Depends(require_webhook_signature)],
    summary="Смена статуса платежа",
    description=(
        "404 — платежа нет; 409 — запрещённый переход, статус не меняется; "
        "200 — статус обновлён. "
        "Если задан `WEBHOOK_SECRET`, заголовок `X-Signature` обязателен: "
        "HMAC-SHA256 от тела запроса, иначе 401."
    ),
)
def handle_bank_webhook(payload: BankWebhookRequest, container: ContainerDep) -> WebhookResponse:
    container.change_payment_status.execute(
        ChangePaymentStatusCommand(payment_id=payload.payment_id, target=payload.status)
    )
    return WebhookResponse()
