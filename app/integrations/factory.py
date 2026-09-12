# app/integrations/factory.py
from app.integrations.mock_crm_client import MockCRMClient

class IntegrationFactory:
    @staticmethod
    def get_adapter(integration_type: str):
        # Future implementations: SALESFORCE, HUBSPOT
        if integration_type in ("MOCK_CRM", "SALESFORCE", "HUBSPOT"):
            return MockCRMClient()
        raise ValueError(f"Unsupported integration type: {integration_type}")