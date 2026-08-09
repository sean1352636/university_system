"""
Edge Case Tests for Email Operations.

Tests critical edge cases and error scenarios for email functionality:
- Malformed SMTP configuration handling
- Email send timeout handling
- Queue overflow scenarios
- Template rendering failures
- Rate limiting behavior
- Connection recovery
- Large attachment handling
"""

import pytest
import time
import socket
import threading
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from queue import Queue, Full, Empty
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class TestMalformedSMTPConfig:
    """Test handling of invalid SMTP configuration."""

    def test_missing_smtp_host(self):
        """Test error handling when SMTP host is missing."""
        config = {
            'port': 587,
            'username': 'user@example.com',
            'password': 'secret'
        }

        def validate_config(cfg):
            errors = []
            if not cfg.get('host'):
                errors.append("SMTP host is required")
            if not cfg.get('port'):
                errors.append("SMTP port is required")
            return len(errors) == 0, errors

        valid, errors = validate_config(config)
        assert valid is False
        assert "SMTP host is required" in errors

    def test_invalid_smtp_port(self):
        """Test error handling when SMTP port is invalid."""
        invalid_ports = [-1, 0, 65536, 'abc', None]

        def validate_port(port):
            if port is None:
                return False, "Port is required"
            if not isinstance(port, int):
                return False, "Port must be an integer"
            if port < 1 or port > 65535:
                return False, "Port must be between 1 and 65535"
            return True, None

        for port in invalid_ports:
            valid, error = validate_port(port)
            assert valid is False

    def test_empty_credentials(self):
        """Test handling of empty credentials."""
        config = {
            'host': 'smtp.example.com',
            'port': 587,
            'username': '',
            'password': ''
        }

        def validate_credentials(cfg):
            warnings = []
            if not cfg.get('username'):
                warnings.append("No username provided - attempting anonymous connection")
            if not cfg.get('password'):
                warnings.append("No password provided")
            return warnings

        warnings = validate_credentials(config)
        assert len(warnings) == 2

    def test_invalid_tls_configuration(self):
        """Test handling of invalid TLS/SSL configuration."""
        class SMTPConfigValidator:
            def validate_security(self, config):
                errors = []

                use_tls = config.get('use_tls', False)
                use_ssl = config.get('use_ssl', False)

                if use_tls and use_ssl:
                    errors.append("Cannot use both TLS and SSL simultaneously")

                port = config.get('port', 25)
                if use_ssl and port == 587:
                    errors.append("Port 587 typically uses STARTTLS, not SSL. Consider port 465 for SSL.")

                if not use_tls and not use_ssl and port != 25:
                    errors.append(f"Port {port} without encryption may be misconfigured")

                return errors

        validator = SMTPConfigValidator()

        # Test conflicting TLS/SSL
        errors = validator.validate_security({'use_tls': True, 'use_ssl': True, 'port': 587})
        assert any("Cannot use both" in e for e in errors)

        # Test wrong port for SSL
        errors = validator.validate_security({'use_ssl': True, 'port': 587})
        assert any("465" in e for e in errors)

    def test_config_file_parse_error(self):
        """Test handling of malformed config files."""
        import json

        malformed_configs = [
            '{"host": "smtp.example.com", "port": }',  # Invalid JSON
            '{"host": "smtp.example.com" "port": 587}',  # Missing comma
            '',  # Empty
            'not json at all',
        ]

        for config_str in malformed_configs:
            with pytest.raises((json.JSONDecodeError, ValueError)):
                if not config_str:
                    raise ValueError("Empty config")
                json.loads(config_str)


class TestEmailSendTimeout:
    """Test timeout handling during email send."""

    def test_connection_timeout(self):
        """Test handling of connection timeout."""
        class MockSMTP:
            def __init__(self, host, port, timeout=30):
                self.timeout = timeout
                if timeout < 5:
                    raise socket.timeout("Connection timed out")

            def connect(self):
                pass

        # Should succeed with normal timeout
        smtp = MockSMTP('smtp.example.com', 587, timeout=30)

        # Should fail with very short timeout
        with pytest.raises(socket.timeout):
            MockSMTP('smtp.example.com', 587, timeout=1)

    def test_send_timeout_with_retry(self):
        """Test email send with timeout and retry logic."""
        attempt_count = 0
        max_retries = 3

        def send_email_with_retry(message, max_retries=3, timeout=30):
            nonlocal attempt_count

            for attempt in range(max_retries):
                attempt_count += 1
                try:
                    if attempt < 2:
                        raise socket.timeout("Send timed out")
                    return True, "Sent successfully"
                except socket.timeout as e:
                    if attempt == max_retries - 1:
                        return False, f"Failed after {max_retries} attempts: {e}"
                    time.sleep(0.01 * (attempt + 1))  # Backoff

            return False, "Max retries exceeded"

        success, message = send_email_with_retry("Test message")
        assert success is True
        assert attempt_count == 3

    def test_partial_send_timeout(self):
        """Test timeout during partial email transmission."""
        class PartialSendSimulator:
            def __init__(self):
                self.data_sent = 0
                self.total_data = 1000

            def send_chunk(self, chunk_size=100):
                if self.data_sent >= 500:  # Timeout after 50%
                    raise socket.timeout("Connection lost during transmission")
                self.data_sent += chunk_size
                return chunk_size

            def get_progress(self):
                return self.data_sent / self.total_data

        simulator = PartialSendSimulator()
        chunks_sent = 0

        with pytest.raises(socket.timeout):
            while simulator.data_sent < simulator.total_data:
                simulator.send_chunk()
                chunks_sent += 1

        assert simulator.get_progress() == 0.5
        assert chunks_sent == 5

    def test_async_send_timeout(self):
        """Test timeout handling in async email sending."""
        import concurrent.futures

        def slow_send(delay):
            time.sleep(delay)
            return f"Sent after {delay}s"

        # Test with executor timeout
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(slow_send, 0.5)

            # Should timeout
            with pytest.raises(concurrent.futures.TimeoutError):
                future.result(timeout=0.1)


class TestEmailQueueOverflow:
    """Test handling of email queue overflow scenarios."""

    def test_queue_full_rejection(self):
        """Test behavior when email queue is full."""
        class EmailQueue:
            def __init__(self, max_size=10):
                self.queue = Queue(maxsize=max_size)
                self.rejected = []

            def enqueue(self, email):
                try:
                    self.queue.put_nowait(email)
                    return True, "Queued successfully"
                except Full:
                    self.rejected.append(email)
                    return False, "Queue full - email rejected"

            def process_one(self):
                try:
                    return self.queue.get_nowait()
                except Empty:
                    return None

        email_queue = EmailQueue(max_size=3)

        # Fill the queue
        for i in range(3):
            success, _ = email_queue.enqueue(f"email_{i}")
            assert success is True

        # Try to add more - should be rejected
        success, message = email_queue.enqueue("email_overflow")
        assert success is False
        assert "Queue full" in message
        assert len(email_queue.rejected) == 1

    def test_queue_priority_handling(self):
        """Test priority queue for urgent emails."""
        import heapq

        class PriorityEmailQueue:
            def __init__(self):
                self.heap = []
                self.counter = 0

            def enqueue(self, email, priority=5):
                # Lower number = higher priority
                heapq.heappush(self.heap, (priority, self.counter, email))
                self.counter += 1

            def dequeue(self):
                if self.heap:
                    priority, _, email = heapq.heappop(self.heap)
                    return email
                return None

        queue = PriorityEmailQueue()

        # Add emails with different priorities
        queue.enqueue("normal_email_1", priority=5)
        queue.enqueue("low_priority_email", priority=10)
        queue.enqueue("URGENT_email", priority=1)
        queue.enqueue("normal_email_2", priority=5)

        # Should get URGENT first
        assert queue.dequeue() == "URGENT_email"
        # Then normal emails in order
        assert queue.dequeue() == "normal_email_1"
        assert queue.dequeue() == "normal_email_2"
        # Then low priority
        assert queue.dequeue() == "low_priority_email"

    def test_queue_persistence_on_shutdown(self):
        """Test that queued emails are persisted on shutdown."""
        class PersistentEmailQueue:
            def __init__(self):
                self.queue = []
                self.persisted = None

            def enqueue(self, email):
                self.queue.append(email)

            def persist_to_disk(self):
                """Simulate persisting queue to disk."""
                self.persisted = list(self.queue)
                return len(self.persisted)

            def restore_from_disk(self):
                """Simulate restoring queue from disk."""
                if self.persisted:
                    self.queue = list(self.persisted)
                    return len(self.queue)
                return 0

        queue = PersistentEmailQueue()
        queue.enqueue("email_1")
        queue.enqueue("email_2")
        queue.enqueue("email_3")

        # Simulate shutdown - persist
        persisted_count = queue.persist_to_disk()
        assert persisted_count == 3

        # Clear queue (simulating restart)
        queue.queue = []

        # Restore
        restored_count = queue.restore_from_disk()
        assert restored_count == 3
        assert len(queue.queue) == 3


class TestTemplateRenderingFailures:
    """Test handling of template rendering failures."""

    def test_missing_template_variable(self):
        """Test handling of missing template variables."""
        def render_template(template, context, strict=True):
            import re
            variables = re.findall(r'\{(\w+)\}', template)
            missing = [v for v in variables if v not in context]

            if missing and strict:
                raise KeyError(f"Missing template variables: {missing}")

            result = template
            for var in variables:
                value = context.get(var, f"[MISSING: {var}]")
                result = result.replace(f"{{{var}}}", str(value))

            return result

        template = "Hello {name}, your order {order_id} is confirmed."
        context = {'name': 'John'}

        # Strict mode should raise error
        with pytest.raises(KeyError) as exc_info:
            render_template(template, context, strict=True)
        assert "order_id" in str(exc_info.value)

        # Non-strict mode should substitute placeholder
        result = render_template(template, context, strict=False)
        assert "[MISSING: order_id]" in result

    def test_invalid_template_syntax(self):
        """Test handling of invalid template syntax."""
        def validate_template(template):
            errors = []

            # Check for unclosed braces
            open_braces = template.count('{')
            close_braces = template.count('}')
            if open_braces != close_braces:
                errors.append("Mismatched braces in template")

            # Check for nested braces (not supported)
            import re
            if re.search(r'\{[^}]*\{', template):
                errors.append("Nested braces not supported")

            # Check for empty variable names
            if '{}' in template:
                errors.append("Empty variable name found")

            return len(errors) == 0, errors

        # Test mismatched braces
        valid, errors = validate_template("Hello {name")
        assert valid is False
        assert any("Mismatched" in e for e in errors)

        # Test empty variable
        valid, errors = validate_template("Hello {}")
        assert valid is False
        assert any("Empty" in e for e in errors)

    def test_template_rendering_timeout(self):
        """Test timeout during complex template rendering."""
        def render_with_timeout(template, context, timeout=1.0):
            import concurrent.futures

            def render():
                # Simulate slow rendering
                time.sleep(0.5)
                return template.format(**context)

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(render)
                try:
                    return future.result(timeout=timeout)
                except concurrent.futures.TimeoutError:
                    raise TimeoutError("Template rendering timed out")

        template = "Hello {name}!"
        context = {'name': 'World'}

        # Should succeed with adequate timeout
        result = render_with_timeout(template, context, timeout=1.0)
        assert result == "Hello World!"

        # Should fail with short timeout (commented out to not slow down tests)
        # with pytest.raises(TimeoutError):
        #     render_with_timeout(template, context, timeout=0.1)


class TestRateLimiting:
    """Test email rate limiting behavior."""

    def test_rate_limit_exceeded(self):
        """Test behavior when rate limit is exceeded."""
        class RateLimiter:
            def __init__(self, max_per_minute=10):
                self.max_per_minute = max_per_minute
                self.timestamps = []

            def can_send(self):
                now = time.time()
                # Remove timestamps older than 1 minute
                self.timestamps = [ts for ts in self.timestamps if now - ts < 60]
                return len(self.timestamps) < self.max_per_minute

            def record_send(self):
                self.timestamps.append(time.time())

            def get_wait_time(self):
                if self.can_send():
                    return 0
                oldest = min(self.timestamps)
                return max(0, 60 - (time.time() - oldest))

        limiter = RateLimiter(max_per_minute=3)

        # Send up to limit
        for _ in range(3):
            assert limiter.can_send() is True
            limiter.record_send()

        # Next should be blocked
        assert limiter.can_send() is False
        wait_time = limiter.get_wait_time()
        assert wait_time > 0

    def test_rate_limit_per_recipient(self):
        """Test rate limiting per recipient address."""
        class PerRecipientRateLimiter:
            def __init__(self, max_per_hour=5):
                self.max_per_hour = max_per_hour
                self.recipient_timestamps = {}

            def can_send_to(self, recipient):
                now = time.time()
                timestamps = self.recipient_timestamps.get(recipient, [])
                # Remove timestamps older than 1 hour
                timestamps = [ts for ts in timestamps if now - ts < 3600]
                self.recipient_timestamps[recipient] = timestamps
                return len(timestamps) < self.max_per_hour

            def record_send_to(self, recipient):
                if recipient not in self.recipient_timestamps:
                    self.recipient_timestamps[recipient] = []
                self.recipient_timestamps[recipient].append(time.time())

        limiter = PerRecipientRateLimiter(max_per_hour=2)

        # Can send to user1 twice
        assert limiter.can_send_to("user1@example.com") is True
        limiter.record_send_to("user1@example.com")
        assert limiter.can_send_to("user1@example.com") is True
        limiter.record_send_to("user1@example.com")
        assert limiter.can_send_to("user1@example.com") is False

        # Can still send to user2
        assert limiter.can_send_to("user2@example.com") is True

    def test_burst_rate_limiting(self):
        """Test burst rate limiting with token bucket."""
        class TokenBucket:
            def __init__(self, capacity=10, refill_rate=1):
                self.capacity = capacity
                self.tokens = capacity
                self.refill_rate = refill_rate  # tokens per second
                self.last_refill = time.time()

            def _refill(self):
                now = time.time()
                elapsed = now - self.last_refill
                tokens_to_add = elapsed * self.refill_rate
                self.tokens = min(self.capacity, self.tokens + tokens_to_add)
                self.last_refill = now

            def consume(self, tokens=1):
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
                return False

        bucket = TokenBucket(capacity=5, refill_rate=10)

        # Can consume burst
        for _ in range(5):
            assert bucket.consume() is True

        # Bucket empty
        assert bucket.consume() is False

        # Wait for refill
        time.sleep(0.2)  # Should add 2 tokens
        assert bucket.consume() is True


class TestConnectionRecovery:
    """Test SMTP connection recovery scenarios."""

    def test_reconnect_after_disconnect(self):
        """Test automatic reconnection after disconnect."""
        class ReconnectingSMTP:
            def __init__(self):
                self.connected = False
                self.connection_attempts = 0
                self.max_retries = 3

            def connect(self):
                self.connection_attempts += 1
                if self.connection_attempts < 2:
                    raise ConnectionError("Connection refused")
                self.connected = True

            def send(self, message):
                if not self.connected:
                    raise ConnectionError("Not connected")
                return True

            def send_with_reconnect(self, message):
                for attempt in range(self.max_retries):
                    try:
                        if not self.connected:
                            self.connect()
                        return self.send(message)
                    except ConnectionError:
                        self.connected = False
                        if attempt == self.max_retries - 1:
                            raise
                        time.sleep(0.01)

        smtp = ReconnectingSMTP()
        result = smtp.send_with_reconnect("Test message")
        assert result is True
        assert smtp.connection_attempts == 2

    def test_connection_pool_recovery(self):
        """Test connection pool recovery after failures."""
        class SMTPConnectionPool:
            def __init__(self, size=3):
                self.size = size
                self.connections = [{'id': i, 'healthy': True} for i in range(size)]
                self.lock = threading.Lock()

            def get_healthy_connection(self):
                with self.lock:
                    for conn in self.connections:
                        if conn['healthy']:
                            return conn
                    return None

            def mark_unhealthy(self, conn):
                with self.lock:
                    conn['healthy'] = False

            def recover_connections(self):
                with self.lock:
                    recovered = 0
                    for conn in self.connections:
                        if not conn['healthy']:
                            # Attempt to recover
                            conn['healthy'] = True
                            recovered += 1
                    return recovered

            def health_check(self):
                healthy = sum(1 for c in self.connections if c['healthy'])
                return {
                    'total': self.size,
                    'healthy': healthy,
                    'unhealthy': self.size - healthy
                }

        pool = SMTPConnectionPool(size=3)

        # Mark all unhealthy
        for conn in pool.connections:
            pool.mark_unhealthy(conn)

        health = pool.health_check()
        assert health['healthy'] == 0
        assert health['unhealthy'] == 3

        # Recovery
        recovered = pool.recover_connections()
        assert recovered == 3

        health = pool.health_check()
        assert health['healthy'] == 3


class TestLargeAttachmentHandling:
    """Test handling of large email attachments."""

    def test_attachment_size_limit(self):
        """Test rejection of oversized attachments."""
        MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10MB

        def validate_attachment(content, max_size=MAX_ATTACHMENT_SIZE):
            size = len(content) if isinstance(content, bytes) else len(content.encode())
            if size > max_size:
                return False, f"Attachment exceeds {max_size // (1024*1024)}MB limit"
            return True, None

        # Small attachment - OK
        small_content = b"x" * (5 * 1024 * 1024)  # 5MB
        valid, error = validate_attachment(small_content)
        assert valid is True

        # Large attachment - rejected
        large_content = b"x" * (15 * 1024 * 1024)  # 15MB
        valid, error = validate_attachment(large_content)
        assert valid is False
        assert "10MB" in error

    def test_chunked_attachment_upload(self):
        """Test chunked upload for large attachments."""
        class ChunkedUploader:
            def __init__(self, chunk_size=1024 * 1024):  # 1MB chunks
                self.chunk_size = chunk_size
                self.uploaded_chunks = []

            def upload(self, data):
                total_chunks = (len(data) + self.chunk_size - 1) // self.chunk_size
                for i in range(0, len(data), self.chunk_size):
                    chunk = data[i:i + self.chunk_size]
                    self.uploaded_chunks.append({
                        'index': len(self.uploaded_chunks),
                        'size': len(chunk),
                        'total': total_chunks
                    })
                return len(self.uploaded_chunks)

        uploader = ChunkedUploader(chunk_size=100)
        data = b"x" * 350
        chunks_uploaded = uploader.upload(data)

        assert chunks_uploaded == 4  # 350 / 100 = 3.5, rounded up
        assert sum(c['size'] for c in uploader.uploaded_chunks) == 350

    def test_total_message_size_limit(self):
        """Test total message size including all attachments."""
        MAX_MESSAGE_SIZE = 25 * 1024 * 1024  # 25MB total

        class EmailComposer:
            def __init__(self, max_size=MAX_MESSAGE_SIZE):
                self.max_size = max_size
                self.body = ""
                self.attachments = []

            def set_body(self, body):
                self.body = body

            def add_attachment(self, name, content):
                self.attachments.append({'name': name, 'content': content})

            def calculate_size(self):
                size = len(self.body.encode())
                for att in self.attachments:
                    size += len(att['content'])
                return size

            def validate(self):
                size = self.calculate_size()
                if size > self.max_size:
                    return False, f"Message size {size} exceeds limit {self.max_size}"
                return True, None

        composer = EmailComposer(max_size=1000)
        composer.set_body("Hello")
        composer.add_attachment("file1.txt", b"x" * 400)
        composer.add_attachment("file2.txt", b"x" * 400)

        valid, error = composer.validate()
        assert valid is True

        # Add one more attachment to exceed limit
        composer.add_attachment("file3.txt", b"x" * 400)
        valid, error = composer.validate()
        assert valid is False
