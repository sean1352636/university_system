#!/usr/bin/env python3
"""
Key Management Service (KMS) Integration Module.

Provides secure master key storage through external Key Management Services.
Supports AWS KMS, Azure Key Vault, and HashiCorp Vault.

This module addresses the critical security risk of storing master encryption
keys in plain files on the filesystem.
"""

import os
import logging
from typing import Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class KMSError(Exception):
    """Base exception for KMS-related errors."""
    pass


class KMSProviderNotConfigured(KMSError):
    """Raised when KMS provider is not properly configured."""
    pass


class KMSKeyRetrievalError(KMSError):
    """Raised when key retrieval from KMS fails."""
    pass


class BaseKMSProvider(ABC):
    """Abstract base class for KMS providers."""

    @abstractmethod
    def get_master_key(self, key_id: str = None) -> bytes:
        """
        Retrieve master encryption key from KMS.

        Args:
            key_id: KMS key identifier

        Returns:
            Master key as bytes

        Raises:
            KMSKeyRetrievalError: If key retrieval fails
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the provider is properly configured."""
        pass


class AWSKMSProvider(BaseKMSProvider):
    """AWS Key Management Service provider."""

    def __init__(self):
        """Initialize AWS KMS client."""
        self._client = None
        self._region = os.getenv('AWS_REGION', 'us-east-1')
        self._key_id = os.getenv('AWS_KMS_KEY_ID')

    def _get_client(self):
        """Lazily initialize AWS KMS client."""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client('kms', region_name=self._region)
            except ImportError:
                raise KMSProviderNotConfigured(
                    "boto3 package not installed. Install with: pip install boto3"
                )
            except Exception as e:
                raise KMSProviderNotConfigured(f"Failed to initialize AWS KMS client: {e}")
        return self._client

    def is_configured(self) -> bool:
        """Check if AWS KMS is properly configured."""
        return bool(self._key_id)

    def get_master_key(self, key_id: str = None) -> bytes:
        """
        Get master key from AWS KMS.

        Uses AWS KMS GenerateDataKey to get a data key encrypted by the CMK.
        The plaintext key is returned for use in the application.

        Args:
            key_id: KMS key ARN or alias (defaults to AWS_KMS_KEY_ID env var)

        Returns:
            Master key as bytes

        Raises:
            KMSKeyRetrievalError: If key retrieval fails
        """
        key_id = key_id or self._key_id
        if not key_id:
            raise KMSProviderNotConfigured("AWS_KMS_KEY_ID environment variable not set")

        try:
            client = self._get_client()
            response = client.generate_data_key(
                KeyId=key_id,
                KeySpec='AES_256'
            )
            logger.info("Successfully retrieved master key from AWS KMS")
            return response['Plaintext']
        except Exception as e:
            logger.error("Failed to retrieve key from AWS KMS")
            raise KMSKeyRetrievalError(f"AWS KMS key retrieval failed: {e}")


class AzureKeyVaultProvider(BaseKMSProvider):
    """Azure Key Vault provider."""

    def __init__(self):
        """Initialize Azure Key Vault client."""
        self._client = None
        self._vault_url = os.getenv('AZURE_VAULT_URL')
        self._key_name = os.getenv('AZURE_KEY_NAME')

    def _get_client(self):
        """Lazily initialize Azure Key Vault client."""
        if self._client is None:
            if not self._vault_url:
                raise KMSProviderNotConfigured("AZURE_VAULT_URL environment variable not set")
            try:
                from azure.keyvault.secrets import SecretClient
                from azure.identity import DefaultAzureCredential

                credential = DefaultAzureCredential()
                self._client = SecretClient(vault_url=self._vault_url, credential=credential)
            except ImportError:
                raise KMSProviderNotConfigured(
                    "Azure SDK packages not installed. Install with: "
                    "pip install azure-keyvault-secrets azure-identity"
                )
            except Exception as e:
                raise KMSProviderNotConfigured(f"Failed to initialize Azure Key Vault client: {e}")
        return self._client

    def is_configured(self) -> bool:
        """Check if Azure Key Vault is properly configured."""
        return bool(self._vault_url and self._key_name)

    def get_master_key(self, key_id: str = None) -> bytes:
        """
        Get master key from Azure Key Vault.

        Args:
            key_id: Secret name in Key Vault (defaults to AZURE_KEY_NAME env var)

        Returns:
            Master key as bytes

        Raises:
            KMSKeyRetrievalError: If key retrieval fails
        """
        key_name = key_id or self._key_name
        if not key_name:
            raise KMSProviderNotConfigured("AZURE_KEY_NAME environment variable not set")

        try:
            client = self._get_client()
            secret = client.get_secret(key_name)
            logger.info("Successfully retrieved master key from Azure Key Vault")
            return secret.value.encode()
        except Exception as e:
            logger.error("Failed to retrieve key from Azure Key Vault")
            raise KMSKeyRetrievalError(f"Azure Key Vault key retrieval failed: {e}")


class HashiCorpVaultProvider(BaseKMSProvider):
    """HashiCorp Vault provider."""

    def __init__(self):
        """Initialize HashiCorp Vault client."""
        self._client = None
        self._vault_addr = os.getenv('VAULT_ADDR')
        self._vault_token = os.getenv('VAULT_TOKEN')
        self._key_path = os.getenv('VAULT_KEY_PATH')

    def _get_client(self):
        """Lazily initialize HashiCorp Vault client."""
        if self._client is None:
            if not self._vault_addr:
                raise KMSProviderNotConfigured("VAULT_ADDR environment variable not set")
            if not self._vault_token:
                raise KMSProviderNotConfigured("VAULT_TOKEN environment variable not set")
            try:
                import hvac
                self._client = hvac.Client(
                    url=self._vault_addr,
                    token=self._vault_token
                )
                if not self._client.is_authenticated():
                    raise KMSProviderNotConfigured("HashiCorp Vault authentication failed")
            except ImportError:
                raise KMSProviderNotConfigured(
                    "hvac package not installed. Install with: pip install hvac"
                )
            except Exception as e:
                raise KMSProviderNotConfigured(f"Failed to initialize HashiCorp Vault client: {e}")
        return self._client

    def is_configured(self) -> bool:
        """Check if HashiCorp Vault is properly configured."""
        return bool(self._vault_addr and self._vault_token and self._key_path)

    def get_master_key(self, key_id: str = None) -> bytes:
        """
        Get master key from HashiCorp Vault.

        Args:
            key_id: Secret path in Vault (defaults to VAULT_KEY_PATH env var)

        Returns:
            Master key as bytes

        Raises:
            KMSKeyRetrievalError: If key retrieval fails
        """
        key_path = key_id or self._key_path
        if not key_path:
            raise KMSProviderNotConfigured("VAULT_KEY_PATH environment variable not set")

        try:
            client = self._get_client()
            secret = client.secrets.kv.v2.read_secret_version(path=key_path)
            key_value = secret['data']['data'].get('key')
            if not key_value:
                raise KMSKeyRetrievalError(f"No 'key' field found at path: {key_path}")
            logger.info("Successfully retrieved master key from HashiCorp Vault")
            return key_value.encode()
        except KMSKeyRetrievalError:
            raise
        except Exception as e:
            logger.error("Failed to retrieve key from HashiCorp Vault")
            raise KMSKeyRetrievalError(f"HashiCorp Vault key retrieval failed: {e}")


class KMSIntegration:
    """
    Integration with cloud Key Management Services.

    Supports AWS KMS, Azure Key Vault, and HashiCorp Vault.
    Provides a unified interface for master key retrieval.
    """

    PROVIDERS = {
        'aws': AWSKMSProvider,
        'azure': AzureKeyVaultProvider,
        'vault': HashiCorpVaultProvider,
    }

    def __init__(self, provider: str = None):
        """
        Initialize KMS integration.

        Args:
            provider: 'aws', 'azure', or 'vault'. If not specified,
                     uses KMS_PROVIDER environment variable.
        """
        self.provider_name = provider or os.getenv('KMS_PROVIDER', 'aws')
        self._provider: Optional[BaseKMSProvider] = None
        self._initialize_provider()

    def _initialize_provider(self):
        """Initialize the appropriate KMS provider."""
        provider_class = self.PROVIDERS.get(self.provider_name.lower())
        if not provider_class:
            raise KMSProviderNotConfigured(
                f"Unknown KMS provider: {self.provider_name}. "
                f"Supported providers: {', '.join(self.PROVIDERS.keys())}"
            )
        self._provider = provider_class()

    def is_configured(self) -> bool:
        """Check if KMS is properly configured."""
        return self._provider is not None and self._provider.is_configured()

    def get_master_key(self, key_id: str = None) -> bytes:
        """
        Retrieve master encryption key from KMS.

        Args:
            key_id: KMS key identifier (provider-specific)

        Returns:
            Master key as bytes

        Raises:
            KMSKeyRetrievalError: If key retrieval fails
        """
        if not self._provider:
            raise KMSProviderNotConfigured("KMS provider not initialized")
        return self._provider.get_master_key(key_id)

    def rotate_key(self, old_key_id: str, new_key_id: str) -> bool:
        """
        Rotate encryption key.

        Note: Actual key rotation requires re-encrypting all data with the new key.
        This method facilitates the key transition process.

        Args:
            old_key_id: Current key ID
            new_key_id: New key ID

        Returns:
            Success status
        """
        try:
            # Verify new key is accessible
            self.get_master_key(new_key_id)
            logger.info(f"Key rotation prepared: {old_key_id} -> {new_key_id}")
            return True
        except Exception:
            logger.error("Key rotation preparation failed")
            return False


def is_kms_enabled() -> bool:
    """
    Check if KMS integration is enabled.

    Returns:
        True if USE_KMS environment variable is set to 'true'
    """
    return os.getenv('USE_KMS', 'false').lower() == 'true'


def get_kms_provider() -> Optional[str]:
    """
    Get the configured KMS provider name.

    Returns:
        Provider name or None if not configured
    """
    if is_kms_enabled():
        return os.getenv('KMS_PROVIDER', 'aws')
    return None


def get_kms_integration() -> Optional[KMSIntegration]:
    """
    Get KMS integration instance if enabled and configured.

    Returns:
        KMSIntegration instance or None
    """
    if not is_kms_enabled():
        return None

    try:
        kms = KMSIntegration()
        if kms.is_configured():
            return kms
        logger.warning("KMS is enabled but not properly configured")
        return None
    except KMSProviderNotConfigured as e:
        logger.warning(f"KMS configuration error: {e}")
        return None


if __name__ == '__main__':
    # Test KMS configuration
    print("KMS Integration Test")
    print("=" * 50)
    print(f"KMS Enabled: {is_kms_enabled()}")
    print(f"KMS Provider: {get_kms_provider()}")

    if is_kms_enabled():
        try:
            kms = KMSIntegration()
            print(f"KMS Configured: {kms.is_configured()}")
            if kms.is_configured():
                key = kms.get_master_key()
                print(f"Master Key Retrieved: {len(key)} bytes")
        except Exception as e:
            print(f"KMS Error: {e}")
    else:
        print("\nTo enable KMS, set the following environment variables:")
        print("  USE_KMS=true")
        print("  KMS_PROVIDER=aws|azure|vault")
        print("\nFor AWS KMS:")
        print("  AWS_REGION=us-east-1")
        print("  AWS_KMS_KEY_ID=arn:aws:kms:...")
        print("\nFor Azure Key Vault:")
        print("  AZURE_VAULT_URL=https://myvault.vault.azure.net/")
        print("  AZURE_KEY_NAME=encryption-master-key")
        print("\nFor HashiCorp Vault:")
        print("  VAULT_ADDR=https://vault.example.com:8200")
        print("  VAULT_TOKEN=s.abcdefg")
        print("  VAULT_KEY_PATH=secret/data/university/encryption-key")
