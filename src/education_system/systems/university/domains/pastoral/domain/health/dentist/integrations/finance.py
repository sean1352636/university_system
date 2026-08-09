def notify_refund(transaction_id, processed_by):
    from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
    return notify_ledger("refund", transaction_id, posted_by=processed_by)
