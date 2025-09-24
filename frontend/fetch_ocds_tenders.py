#!/usr/bin/env python
import requests
import json
import os
import sys
import django
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'frontend.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

from tenders.models import Tender

def fetch_ocds_releases():
    """Fetch OCDS releases from the primary API endpoint with pagination"""
    # Use only the primary OCDS API endpoint
    base_url = "https://ocds-api.etenders.gov.za/api/OCDSReleases"
    
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'TenderInsightHub/1.0'
    }
    
    all_releases = []
    page_number = 1
    page_size = 1000  # Increased page size to get more tenders
    
    while True:
        try:
            # Build URL with pagination parameters
            url = f"{base_url}?PageNumber={page_number}&PageSize={page_size}&dateFrom=2023-01-01&dateTo=2025-12-31"
            print(f"Fetching page {page_number} from: {url}")
            
            response = requests.get(url, headers=headers, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                
                # Handle different response structures
                if isinstance(data, dict):
                    releases = data.get('releases', data.get('data', []))
                    total_pages = data.get('totalPages', 1)
                    total_records = data.get('totalRecords', len(releases))
                else:
                    releases = data if isinstance(data, list) else []
                    total_pages = 1
                    total_records = len(releases)
                
                print(f"✓ Page {page_number}: Fetched {len(releases)} releases")
                all_releases.extend(releases)
                
                # Check if we have more pages or if this page is empty
                if len(releases) == 0 or page_number >= total_pages:
                    break
                    
                page_number += 1
                
                # Safety limit to prevent infinite loops
                if page_number > 10:  # Limit to 10 pages (up to 10,000 records)
                    print("Reached maximum page limit (10 pages)")
                    break
                    
            else:
                print(f"✗ API returned status {response.status_code}: {response.text[:200]}")
                break
                
        except requests.exceptions.RequestException as e:
            print(f"✗ Request failed: {e}")
            break
    
    print(f"Total releases fetched: {len(all_releases)}")
    return all_releases

# Sample data function removed - now using only real API data

def map_ocds_to_tender(release):
    """Map OCDS release data to Tender model fields"""
    try:
        # Extract basic tender information
        ocid = release.get('ocid', '')
        tender_data = release.get('tender', {})
        
        # Map OCDS fields to our Tender model
        tender_info = {
            'ocid': ocid,
            'tender_id': release.get('id', ocid),
            'title': tender_data.get('title', 'No title provided'),
            'description': tender_data.get('description', 'No description provided'),
        }
        
        # Extract buyer information
        buyer = release.get('buyer', {})
        tender_info['buyer_name'] = buyer.get('name', 'Unknown Buyer')
        
        # Extract budget/value information
        value = tender_data.get('value', {})
        if value:
            amount = value.get('amount', 0)
            tender_info['budget_min'] = amount
            tender_info['budget_max'] = amount
        else:
            tender_info['budget_min'] = 0
            tender_info['budget_max'] = 0
        
        # Extract tender period
        tender_period = tender_data.get('tenderPeriod', {})
        end_date_str = tender_period.get('endDate')
        if end_date_str:
            try:
                # Parse ISO format date
                tender_info['tender_period_end_date'] = datetime.fromisoformat(end_date_str.replace('Z', '+00:00')).date()
            except ValueError:
                tender_info['tender_period_end_date'] = None
        else:
            tender_info['tender_period_end_date'] = None
        
        # Set default values for other fields
        tender_info['province'] = 'Not specified'
        # Note: Removed status, procurement_method, submission_method as they don't exist in Tender model
        
        return tender_info
        
    except Exception as e:
        print(f"Error mapping OCDS data: {e}")
        return None

def save_tenders_to_db(releases):
    """Save OCDS releases to the local database"""
    created_count = 0
    updated_count = 0
    error_count = 0
    
    for release in releases:
        try:
            tender_data = map_ocds_to_tender(release)
            if not tender_data:
                error_count += 1
                continue
            
            # Use get_or_create to avoid duplicates
            tender, created = Tender.objects.get_or_create(
                ocid=tender_data['ocid'],
                defaults=tender_data
            )
            
            if created:
                created_count += 1
                print(f"Created tender: {tender.title[:50]}...")
            else:
                # Update existing tender with new data
                for key, value in tender_data.items():
                    setattr(tender, key, value)
                tender.save()
                updated_count += 1
                print(f"Updated tender: {tender.title[:50]}...")
                
        except Exception as e:
            print(f"Error saving tender: {e}")
            error_count += 1
    
    return created_count, updated_count, error_count

def main():
    """Main function to fetch and save OCDS tenders"""
    print("Starting OCDS tender fetch process...")
    
    # Check current tender count
    initial_count = Tender.objects.count()
    print(f"Current tenders in database: {initial_count}")
    
    # Fetch OCDS releases
    releases = fetch_ocds_releases()
    
    if not releases:
        print("No releases fetched. Exiting.")
        return
    
    # Save to database
    created, updated, errors = save_tenders_to_db(releases)
    
    # Final statistics
    final_count = Tender.objects.count()
    print(f"\n=== OCDS Import Summary ===")
    print(f"Releases processed: {len(releases)}")
    print(f"Tenders created: {created}")
    print(f"Tenders updated: {updated}")
    print(f"Errors: {errors}")
    print(f"Total tenders in database: {final_count}")
    print(f"Net change: +{final_count - initial_count}")

if __name__ == '__main__':
    main()