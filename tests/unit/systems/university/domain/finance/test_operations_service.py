import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import pytest
from education_system.systems.university.domains.finance.domain.operations_service import FinanceOperationsService

@pytest.fixture
def service(tmp_path):
 path=tmp_path/'finance.db'
 def connect():
  c=sqlite3.connect(path); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c
 return FinanceOperationsService(connect)

def test_supplier_po_invoice_three_way_match(service):
 supplier=service.add_supplier('Acme','ap@acme.test'); service.update_supplier_controls(supplier,bank_verified=True)
 po=service.create_po(supplier,'Lab equipment',100); service.advance_po(po,'received')
 invoice=service.add_invoice(supplier,'INV-1',100,20,po_id=po); service.approve_invoice(invoice)
 assert service.rows('finance_ap_invoices')[0]['status']=='approved'

def test_duplicate_supplier_invoice_rejected(service):
 supplier=service.add_supplier('Acme'); service.add_invoice(supplier,'DUP-1',10)
 with pytest.raises(sqlite3.IntegrityError): service.add_invoice(supplier,'DUP-1',10)

def test_cash_flow_and_vat_summaries(service):
 service.record_cash('inflow','fees',1000); service.record_cash('outflow','payroll',300)
 assert service.cash_summary()['balance']==700
 service.record_vat('invoice',1,'S20',100,20,'output'); service.record_vat('bill',2,'S20',50,10,'input')
 assert service.vat_summary()['net_payable']==10

def test_fixed_asset_book_value_and_validation(service):
 asset=service.add_asset('LAB-001','Microscope',1000,5,'2024-01-01',100)
 assert service.asset_book_value(asset,date(2025,1,1))==pytest.approx(819.63,abs=.02)
 with pytest.raises(ValueError):service.add_asset('BAD','Invalid',100,0)

def test_approval_inbox_records_decision_audit(service):
 item=service.request_approval('invoice',42,2500,'requester')
 service.decide_approval(item,'approved','finance.manager','Within budget')
 row=service.rows('finance_approval_items')[0]
 assert (row['status'],row['decision_by'],row['notes'])==('approved','finance.manager','Within budget')

def test_fraud_investigation_decision_and_risk_validation(service):
 case=service.create_fraud_case(91,.92,'Unusual payment pattern')
 service.decide_fraud_case(case,'confirmed','investigator')
 row=service.rows('finance_fraud_cases')[0]
 assert (row['status'],row['decision'],row['assigned_to'])==('closed','confirmed','investigator')
 with pytest.raises(ValueError):service.create_fraud_case(92,1.1,'Invalid score')

def test_close_checklist_requires_evidence(service):
 service.seed_close_checklist('2026-08','finance-team')
 tasks=sorted(service.rows('finance_close_tasks'), key=lambda row: row['id'])
 assert len(tasks)==6
 with pytest.raises(ValueError):service.complete_close_task(tasks[0]['id'],'')
 service.complete_close_task(tasks[0]['id'],'Reconciliation report FIN-101')
 completed=next(row for row in service.rows('finance_close_tasks') if row['id']==tasks[0]['id'])
 assert completed['status']=='complete'


def test_finance_rejects_invalid_amounts_and_foreign_keys(service):
    supplier = service.add_supplier('Acme')
    with pytest.raises(ValueError): service.add_invoice(supplier, 'NEG', -1)
    with pytest.raises(ValueError): service.record_cash('inflow', 'fees', -1)
    with pytest.raises(ValueError): service.record_vat('invoice', 1, 'S20', 100, -1, 'output')
    with pytest.raises(ValueError): service.add_invoice(9999, 'MISSING', 10)
    with pytest.raises(ValueError): service.create_po(9999, 'Invalid supplier', 10)


def test_purchase_order_numbers_are_unique_under_concurrency(tmp_path):
    path = tmp_path / 'concurrent-finance.db'

    def connect():
        connection = sqlite3.connect(path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        return connection

    service = FinanceOperationsService(connect)
    supplier = service.add_supplier('Concurrent Supplier')
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda _: service.create_po(supplier, 'Item', 10), range(16)))

    rows = service.rows('finance_purchase_orders')
    assert len(ids) == len(set(ids)) == 16
    assert len({row['po_number'] for row in rows}) == 16


def test_duplicate_approval_and_fraud_reassignment_lifecycle(service):
    item = service.request_approval('invoice', 1, 100, 'requester')
    service.decide_approval(item, 'approved', 'manager')
    with pytest.raises(ValueError): service.decide_approval(item, 'rejected', 'other-manager')

    case = service.create_fraud_case(1, 0.8, 'review')
    service.reassign_fraud_case(case, 'investigator-a')
    service.decide_fraud_case(case, 'confirmed', 'investigator-a')
    service.reopen_fraud_case(case)
    service.reassign_fraud_case(case, 'investigator-b')
    row = service.rows('finance_fraud_cases')[0]
    assert row['status'] == 'open'
    assert row['assigned_to'] == 'investigator-b'


def test_close_tasks_enforce_order_and_locking(service):
    service.seed_close_checklist('2026-08')
    tasks = sorted(service.rows('finance_close_tasks'), key=lambda row: row['id'])
    with pytest.raises(ValueError):
        service.complete_close_task(tasks[-1]['id'], 'premature')
    service.complete_close_task(tasks[0]['id'], 'bank reconciliation')
    with pytest.raises(ValueError):
        service.complete_close_task(tasks[0]['id'], 'duplicate')
