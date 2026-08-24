from store.models import Payout, Report


class PayoutService:
    """Сервис ручных выплат."""

    @staticmethod
    def sync_with_report(report) -> Payout:
        """Создает или обновляет незавершенную выплату по отчету."""
        if report.status != Report.Status.READY:
            raise ValueError(
                'Выплата может быть создана только для готового отчета.',
            )

        payout, created = Payout.objects.get_or_create(
            report=report,
            defaults={
                'payout_recipient': report.payout_recipient,
                'amount': report.payout_amount,
            },
        )

        if created or payout.status == Payout.Status.PAID:
            return payout

        payout.payout_recipient = report.payout_recipient
        payout.amount = report.payout_amount
        payout.save(
            update_fields=[
                'payout_recipient',
                'amount',
                'updated_at',
            ],
        )

        return payout
