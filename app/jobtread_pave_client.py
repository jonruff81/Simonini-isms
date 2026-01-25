"""
JobTread Pave API Client
Uses JobTread's Pave query language (GraphQL-like)

API Documentation: https://app.jobtread.com/docs
API Endpoint: https://api.jobtread.com/pave
"""

import requests
import logging
import sys
import os
from typing import Dict, List, Optional, Any

# Import config from app
from app.config import JOBTREAD_CONFIG

logger = logging.getLogger(__name__)


class JobTreadAPIError(Exception):
    """Custom exception for JobTread API errors"""
    pass


class JobTreadPaveClient:
    """Client for interacting with JobTread Pave API"""

    def __init__(self, api_key: str = None, base_url: str = None, organization_id: str = None):
        """
        Initialize JobTread Pave API client

        Args:
            api_key: JobTread API grant key (defaults to config)
            base_url: Base URL for API (defaults to https://api.jobtread.com/pave)
            organization_id: JobTread organization ID (defaults to config)
        """
        self.api_key = api_key or JOBTREAD_CONFIG.api_key
        self.base_url = (base_url or JOBTREAD_CONFIG.base_url).rstrip('/')
        self.organization_id = organization_id or JOBTREAD_CONFIG.organization_id

        if not self.api_key:
            raise JobTreadAPIError("JobTread API key is required. Set JOBTREAD_API_KEY in .env")

        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def query(self, pave_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a Pave query

        Args:
            pave_query: Pave query object (YAML structure as dict)

        Returns:
            JSON response as dictionary

        Raises:
            JobTreadAPIError: If request fails
        """
        # Add grantKey to query if not present
        if '$' not in pave_query:
            pave_query['$'] = {}
        if 'grantKey' not in pave_query.get('$', {}):
            pave_query['$']['grantKey'] = self.api_key

        payload = {'query': pave_query}

        try:
            response = self.session.post(self.base_url, json=payload)
            response.raise_for_status()

            result = response.json()

            # Check for Pave errors in response
            if isinstance(result, dict) and 'errors' in result:
                error_msg = f"Pave query error: {result['errors']}"
                logger.error(error_msg)
                raise JobTreadAPIError(error_msg)

            return result

        except requests.exceptions.HTTPError as e:
            error_msg = f"JobTread API error ({response.status_code}): {response.text}"
            logger.error(error_msg)
            raise JobTreadAPIError(error_msg) from e
        except requests.exceptions.RequestException as e:
            error_msg = f"JobTread API request failed: {str(e)}"
            logger.error(error_msg)
            raise JobTreadAPIError(error_msg) from e

    # =====================================================================
    # ORGANIZATION QUERIES
    # =====================================================================

    def get_organization_info(self) -> Dict:
        """
        Get basic organization information

        Returns:
            Organization data dictionary
        """
        query = {
            'organization': {
                '$': {'id': self.organization_id},
                'id': {},
                'name': {},
                'currencyCode': {},
                'timeZone': {}
            }
        }
        result = self.query(query)
        return result.get('organization', {})

    # =====================================================================
    # JOB QUERIES
    # =====================================================================

    def list_jobs(self, limit: int = 50, page: str = None) -> Dict:
        """
        List jobs in the organization

        Args:
            limit: Number of jobs to return (default 50)
            page: Page token for pagination

        Returns:
            Jobs connection with nodes and pagination info
        """
        query = {
            'organization': {
                '$': {'id': self.organization_id},
                'jobs': {
                    '$': {'size': limit},
                    'nodes': {
                        'id': {},
                        'name': {},
                        'number': {},
                        'description': {},
                        'priceType': {},
                        'closedOn': {},
                        'createdAt': {},
                        'customFieldValues': {  # Include custom field values like Job Type
                            'nodes': {
                                'id': {},
                                'customField': {
                                    'id': {},
                                    'name': {}
                                },
                                'value': {}
                            }
                        },
                        'location': {
                            'id': {},
                            'name': {},
                            'address': {},
                            'account': {
                                'id': {},
                                'name': {},
                                'type': {}
                            }
                        }
                    },
                    'nextPage': {},
                    'previousPage': {}
                }
            }
        }

        if page:
            query['organization']['jobs']['$']['page'] = page

        result = self.query(query)
        return result.get('organization', {}).get('jobs', {})

    def get_job(self, job_id: str) -> Dict:
        """
        Get a specific job by ID

        Args:
            job_id: JobTread job ID

        Returns:
            Job dictionary
        """
        query = {
            'job': {
                '$': {'id': job_id},
                'id': {},
                'name': {},
                'number': {},
                'description': {},
                'priceType': {},
                'closedOn': {},
                'createdAt': {},
                'customFieldValues': {
                    '$': {'size': 25},
                    'nodes': {
                        'id': {},
                        'value': {},
                        'customField': {
                            'id': {},
                            'name': {}
                        }
                    }
                },
                'location': {
                    'id': {},
                    'name': {},
                    'address': {},
                    'account': {
                        'id': {},
                        'name': {},
                        'type': {}
                    }
                }
            }
        }
        result = self.query(query)
        return result.get('job', {})

    def create_job(self, name: str, location_id: str = None, number: str = None,
                   description: str = None, custom_fields: Dict = None) -> Dict:
        """
        Create a new job

        Args:
            name: Job name
            location_id: Location ID (optional)
            number: Job number (optional)
            description: Job description (optional)
            custom_fields: Custom field values dict (optional)

        Returns:
            Created job dictionary
        """
        job_data = {
            'name': name
        }

        if location_id:
            job_data['locationId'] = location_id
        if number:
            job_data['number'] = number
        if description:
            job_data['description'] = description
        if custom_fields:
            job_data['customFieldValues'] = custom_fields

        query = {
            'createJob': {
                '$': job_data,
                'createdJob': {
                    'id': {},
                    'name': {},
                    'number': {},
                    'description': {},
                    'createdAt': {}
                }
            }
        }

        result = self.query(query)
        return result.get('createJob', {}).get('createdJob', {})

    # =====================================================================
    # ACCOUNT (CUSTOMER/VENDOR) QUERIES
    # =====================================================================

    def list_accounts(self, account_type: str = None, limit: int = 50) -> Dict:
        """
        List accounts (customers and/or vendors)

        Args:
            account_type: 'customer', 'vendor', or None for both
            limit: Number of accounts to return (fetches more if filtering by type)

        Returns:
            Accounts connection with nodes
        """
        # Fetch more records if filtering, since we filter client-side
        # API max is 100, so cap it there
        fetch_limit = min(100, limit * 2 if account_type else limit)

        query_args = {'size': fetch_limit}

        query = {
            'organization': {
                '$': {'id': self.organization_id},
                'accounts': {
                    '$': query_args,
                    'nodes': {
                        'id': {},
                        'name': {},
                        'type': {},
                        'isTaxable': {},
                        'createdAt': {}
                    },
                    'nextPage': {}
                }
            }
        }

        result = self.query(query)
        accounts = result.get('organization', {}).get('accounts', {})

        # Filter client-side if account_type specified
        if account_type and accounts.get('nodes'):
            filtered_nodes = [node for node in accounts['nodes'] if node.get('type') == account_type]
            accounts['nodes'] = filtered_nodes[:limit]  # Limit to requested size

        return accounts

    def create_account(self, name: str, account_type: str, is_taxable: bool = True,
                      custom_fields: Dict = None) -> Dict:
        """
        Create an account (customer or vendor)

        Args:
            name: Account name
            account_type: 'customer' or 'vendor'
            is_taxable: Whether account is taxable
            custom_fields: Custom field values dict

        Returns:
            Created account dictionary
        """
        account_data = {
            'organizationId': self.organization_id,
            'name': name,
            'type': account_type,
            'isTaxable': is_taxable
        }

        if custom_fields:
            account_data['customFieldValues'] = custom_fields

        query = {
            'createAccount': {
                '$': account_data,
                'createdAccount': {
                    'id': {},
                    'name': {},
                    'type': {},
                    'isTaxable': {},
                    'createdAt': {}
                }
            }
        }

        result = self.query(query)
        return result.get('createAccount', {}).get('createdAccount', {})

    # =====================================================================
    # LOCATION QUERIES
    # =====================================================================

    def create_location(self, account_id: str, name: str, address: str) -> Dict:
        """
        Create a location for an account

        Args:
            account_id: Account ID
            name: Location name
            address: Location address

        Returns:
            Created location dictionary
        """
        query = {
            'createLocation': {
                '$': {
                    'accountId': account_id,
                    'name': name,
                    'address': address
                },
                'createdLocation': {
                    'id': {},
                    'name': {},
                    'address': {},
                    'account': {
                        'id': {},
                        'name': {}
                    }
                }
            }
        }

        result = self.query(query)
        return result.get('createLocation', {}).get('createdLocation', {})

    # =====================================================================
    # COST CODE/ITEM QUERIES
    # =====================================================================

    def list_cost_codes(self, limit: int = 100) -> Dict:
        """
        List cost codes

        Args:
            limit: Number to return

        Returns:
            Cost codes connection
        """
        query = {
            'organization': {
                '$': {'id': self.organization_id},
                'costCodes': {
                    '$': {'size': limit},
                    'nodes': {
                        'id': {},
                        'name': {},
                        'number': {},
                        'isActive': {}
                    },
                    'nextPage': {}
                }
            }
        }

        result = self.query(query)
        return result.get('organization', {}).get('costCodes', {})

    # =====================================================================
    # FILE QUERIES
    # =====================================================================

    def get_job_files(self, job_id: str, limit: int = 100) -> List[Dict]:
        """
        Get files attached to a specific job

        Args:
            job_id: JobTread job ID
            limit: Max number of files to return (max 100 per page)

        Returns:
            List of file dictionaries with id, name, url, size, type, createdAt
        """
        query = {
            'job': {
                '$': {'id': job_id},
                'id': {},
                'name': {},
                'number': {},
                'files': {
                    '$': {'size': min(limit, 100)},
                    'nodes': {
                        'id': {},
                        'name': {},
                        'url': {},
                        'size': {},
                        'type': {},
                        'createdAt': {}
                    },
                    'nextPage': {}
                }
            }
        }

        result = self.query(query)
        job_data = result.get('job', {})
        files = job_data.get('files', {}).get('nodes', [])
        return files

    def get_phase_spec_files(self, job_id: str) -> List[Dict]:
        """
        Get Phase Spec PDF files from a job, sorted by phase number

        Args:
            job_id: JobTread job ID (typically the Phase Specs job)

        Returns:
            List of PDF files sorted by phase number
        """
        files = self.get_job_files(job_id, limit=100)

        # Filter to only PDF files
        pdf_files = [f for f in files if f.get('type') == 'application/pdf' or
                     f.get('name', '').lower().endswith('.pdf')]

        # Sort by phase number (extract from filename like "Phase 30-500 ALARM SYSTEM.pdf")
        def get_phase_sort_key(file):
            name = file.get('name', '')
            # Try to extract phase number like "30-500" or "40-100"
            import re
            match = re.search(r'Phase\s+(\d+)-(\d+)', name)
            if match:
                return (int(match.group(1)), int(match.group(2)))
            return (999, 999)  # Put non-matching files at the end

        pdf_files.sort(key=get_phase_sort_key)
        return pdf_files

    # =====================================================================
    # UTILITY METHODS
    # =====================================================================

    def test_connection(self) -> bool:
        """
        Test the API connection by fetching organization info

        Returns:
            True if connection successful, False otherwise
        """
        try:
            org = self.get_organization_info()
            if org and 'id' in org:
                logger.info(f"JobTread API connection successful. Organization: {org.get('name')}")
                return True
            return False
        except JobTreadAPIError as e:
            logger.error(f"JobTread API connection failed: {e}")
            return False


if __name__ == '__main__':
    # Test the connection when run directly
    logging.basicConfig(level=logging.INFO)

    try:
        client = JobTreadPaveClient()
        print("Testing JobTread Pave API connection...")
        print(f"Organization ID: {client.organization_id}")
        print()

        if client.test_connection():
            print("[OK] Connection successful!")

            # Get organization info
            org = client.get_organization_info()
            print(f"\nOrganization: {org.get('name')}")
            print(f"Currency: {org.get('currencyCode')}")
            print(f"Time Zone: {org.get('timeZone')}")

            # List a few jobs
            print("\nFetching jobs...")
            jobs = client.list_jobs(limit=5)
            nodes = jobs.get('nodes', [])
            print(f"Found {len(nodes)} jobs:")
            for job in nodes[:5]:
                print(f"  - {job.get('name')} (#{job.get('number')})")

        else:
            print("[FAIL] Connection failed. Check your API key and organization ID.")

    except JobTreadAPIError as e:
        print(f"[ERROR] {e}")
