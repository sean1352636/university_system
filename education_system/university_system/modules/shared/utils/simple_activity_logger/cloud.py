import asyncio
from datetime import datetime
from typing import Dict, Any

import requests

from .models import LogEntry


class CloudIntegration:
    """Handle cloud service integrations"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled_services = config.get('enabled_services', [])
        self.session = requests.Session()
        self.session.timeout = config.get('timeout', 10)

    async def send_to_cloud(self, log_entry: LogEntry):
        """Send log entry to configured cloud services"""
        tasks = []

        if 'aws_cloudwatch' in self.enabled_services:
            tasks.append(self._send_to_cloudwatch(log_entry))

        if 'elasticsearch' in self.enabled_services:
            tasks.append(self._send_to_elasticsearch(log_entry))

        if 'webhook' in self.enabled_services:
            tasks.append(self._send_webhook(log_entry))

        if 'splunk' in self.enabled_services:
            tasks.append(self._send_to_splunk(log_entry))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_to_cloudwatch(self, log_entry: LogEntry):
        """Send to AWS CloudWatch"""
        try:
            # This would require boto3 in a real implementation
            cloudwatch_config = self.config.get('aws_cloudwatch', {})
            log_group = cloudwatch_config.get('log_group', 'application-logs')
            log_stream = cloudwatch_config.get('log_stream', 'default-stream')

            # Placeholder for CloudWatch implementation
            print(f"Would send to CloudWatch: {log_group}/{log_stream}")

        except Exception as e:
            print(f"CloudWatch send failed: {e}")

    async def _send_to_elasticsearch(self, log_entry: LogEntry):
        """Send to Elasticsearch"""
        try:
            es_config = self.config.get('elasticsearch', {})
            es_url = es_config.get('url', 'http://localhost:9200')
            index_name = es_config.get('index', 'activity-logs')

            # Prepare document
            doc = log_entry.to_dict()
            doc['@timestamp'] = log_entry.timestamp

            # Send to Elasticsearch
            url = f"{es_url}/{index_name}/_doc"
            headers = {'Content-Type': 'application/json'}

            if es_config.get('username') and es_config.get('password'):
                auth = (es_config['username'], es_config['password'])
            else:
                auth = None

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.session.post(url, json=doc, headers=headers, auth=auth)
            )
            response.raise_for_status()

        except Exception as e:
            print(f"Elasticsearch send failed: {e}")

    async def _send_webhook(self, log_entry: LogEntry):
        """Send to webhook endpoint"""
        webhook_url = self.config.get('webhook_url')
        if not webhook_url:
            return

        try:
            payload = {
                'timestamp': log_entry.timestamp,
                'event_type': 'activity_log',
                'data': log_entry.to_dict()
            }

            headers = {'Content-Type': 'application/json'}
            webhook_config = self.config.get('webhook', {})

            # Add custom headers if configured
            if 'headers' in webhook_config:
                headers.update(webhook_config['headers'])

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.session.post(webhook_url, json=payload, headers=headers)
            )
            response.raise_for_status()

        except Exception as e:
            print(f"Webhook send failed: {e}")

    async def _send_to_splunk(self, log_entry: LogEntry):
        """Send to Splunk HEC (HTTP Event Collector)"""
        try:
            splunk_config = self.config.get('splunk', {})
            hec_url = splunk_config.get('hec_url')
            hec_token = splunk_config.get('hec_token')

            if not hec_url or not hec_token:
                return

            # Prepare Splunk event
            event = {
                'time': int(datetime.strptime(log_entry.timestamp, "%Y-%m-%d %H:%M:%S.%f").timestamp()),
                'source': 'activity_logger',
                'sourcetype': 'json',
                'index': splunk_config.get('index', 'main'),
                'event': log_entry.to_dict()
            }

            headers = {
                'Authorization': f'Splunk {hec_token}',
                'Content-Type': 'application/json'
            }

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.session.post(hec_url, json=event, headers=headers)
            )
            response.raise_for_status()

        except Exception as e:
            print(f"Splunk send failed: {e}")

    def test_connectivity(self) -> Dict[str, bool]:
        """Test connectivity to all configured services"""
        results = {}

        for service in self.enabled_services:
            try:
                if service == 'webhook':
                    webhook_url = self.config.get('webhook_url')
                    if webhook_url:
                        response = self.session.head(webhook_url, timeout=5)
                        results[service] = response.status_code < 400
                    else:
                        results[service] = False

                elif service == 'elasticsearch':
                    es_config = self.config.get('elasticsearch', {})
                    es_url = es_config.get('url', 'http://localhost:9200')
                    response = self.session.get(f"{es_url}/_cluster/health", timeout=5)
                    results[service] = response.status_code == 200

                elif service == 'splunk':
                    splunk_config = self.config.get('splunk', {})
                    hec_url = splunk_config.get('hec_url')
                    if hec_url:
                        # Test with a simple health check
                        response = self.session.get(hec_url.replace('/event', '/health'), timeout=5)
                        results[service] = response.status_code < 500
                    else:
                        results[service] = False

                else:
                    results[service] = True  # Assume other services are OK

            except Exception as e:
                results[service] = False
                print(f"Connectivity test failed for {service}: {e}")

        return results
