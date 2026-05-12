from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True)
class PaymentIntent:
    provider_order_id: str
    payment_url: str
    raw_payload: dict


class PaymentProvider:
    async def create_intent(self, channel: str, amount_cents: int, currency: str) -> PaymentIntent:
        raise NotImplementedError


class MockPaymentProvider(PaymentProvider):
    async def create_intent(self, channel: str, amount_cents: int, currency: str) -> PaymentIntent:
        provider_order_id = f'{channel}_mock_{uuid4().hex}'
        return PaymentIntent(
            provider_order_id=provider_order_id,
            payment_url=f'wenshi://mock-pay/{provider_order_id}',
            raw_payload={'mock': True, 'channel': channel, 'amount_cents': amount_cents, 'currency': currency},
        )


payment_provider: PaymentProvider = MockPaymentProvider()
