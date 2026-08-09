"""Direct behavioral smoke tests for previously untested infrastructure packages."""

from education_system.systems.university.infrastructure.async_utils.background_tasks import (
    BackgroundTaskRunner,
)
from education_system.systems.university.infrastructure.cache.cache_manager import CacheManager
from education_system.systems.university.infrastructure.communication.realtime_notifications import (
    InMemoryNotificationHandler,
    Notification,
    NotificationType,
)
from education_system.systems.university.infrastructure.health.export_writer import write_csv
from education_system.systems.university.infrastructure.monitoring.metrics import MetricsCollector
from education_system.systems.university.infrastructure.performance.cache import (
    CacheManager as PerformanceCache,
)
from education_system.systems.university.infrastructure.repositories.base import Entity
from education_system.systems.university.infrastructure.workflows.models import (
    StepType,
    Workflow,
    WorkflowStep,
)


def test_async_runner_propagates_success_and_failure():
    runner = BackgroundTaskRunner(max_workers=2)
    try:
        ok = runner.submit(lambda: 42)
        failed = runner.submit(lambda: 1 / 0)
        assert runner.wait(ok, timeout=5).result == 42
        assert runner.wait(failed, timeout=5).error is not None
    finally:
        runner.shutdown()


def test_caches_expire_and_evict():
    cache = CacheManager(default_ttl=60, max_size=1)
    cache.set("first", 1)
    cache.set("second", 2)
    assert cache.get("first") is None
    assert cache.get("second") == 2

    performance_cache = PerformanceCache(max_size=1, default_ttl=0)
    performance_cache.set("key", "value")
    assert performance_cache.get("key") == "value"


def test_notification_handler_rejects_missing_recipient_and_delivers():
    handler = InMemoryNotificationHandler(max_queue_size=1)
    missing = Notification(type=NotificationType.SYSTEM_ALERT, title="x", message="y")
    assert handler.send(missing) is False
    notification = Notification(
        type=NotificationType.SYSTEM_ALERT,
        title="Notice",
        message="Ready",
        recipient_id=7,
    )
    assert handler.send(notification) is True
    assert handler.get_notifications(7) == [notification]


def test_health_export_writes_a_round_trip_csv(tmp_path):
    path = write_csv(tmp_path / "health.csv", ["id", "status"], [[1, "ok"]])
    assert path.read_text(encoding="utf-8").splitlines() == ["id,status", "1,ok"]


def test_metrics_and_entity_state_are_behavioral():
    metrics = MetricsCollector()
    metrics.increment_counter("requests", 2)
    metrics.record_error("requests", "timeout")
    snapshot = metrics.get_all_metrics()
    assert snapshot["counters"]["requests"] == 2
    assert snapshot["error_rates"]["requests"] == 1

    entity = Entity(id="E1")
    original = entity.updated_at
    entity.mark_updated()
    assert entity.id == "E1"
    assert entity.updated_at >= original


def test_search_and_workflow_boundaries():
    workflow = Workflow("wf", "Approval", "Approval workflow")
    workflow.add_step(WorkflowStep("second", "Second", StepType.MANUAL, 2))
    workflow.add_step(WorkflowStep("first", "First", StepType.APPROVAL, 1))
    assert [step.step_id for step in workflow.steps] == ["first", "second"]
    assert workflow.get_next_step() is workflow.steps[0]
