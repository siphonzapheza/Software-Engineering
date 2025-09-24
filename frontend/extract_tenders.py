"""
Script to extract tenders from API endpoints and store them in both PostgreSQL and MongoDB databases.
"""
import os
import sys
import json
import requests
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'frontend.settings')
django.setup()

from tenders.models import Tender
from tenders.mongodb_utils import get_database, save_to_mongodb
from django.db.models import Q

def extract_and_store_tenders():
    """
    Extract tenders from eTenders API and store them in both PostgreSQL and MongoDB.
    Fetches multiple pages to get more tender data.
    """
    print("Starting tender extraction process...")
    
    # API endpoint with pagination support
    base_url = "https://ocds-api.etenders.gov.za/api/OCDSReleases"
    
    all_tenders = []
    page_number = 1
    page_size = 500
    max_pages = 10  # Limit to prevent excessive API calls
    
    # Extended date range to capture more historical data
    date_from = "2020-01-01"
    date_to = "2025-12-31"
    
    while page_number <= max_pages:
        # Construct URL with pagination parameters
        endpoint = f"{base_url}?PageNumber={page_number}&PageSize={page_size}&dateFrom={date_from}&dateTo={date_to}"
        print(f"Fetching page {page_number} from: {endpoint}")
        
        try:
            response = requests.get(endpoint, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                print(f"Successfully fetched data from eTenders API (Page {page_number})")
                
                # Extract tenders from OCDS releases structure
                if 'releases' in data:
                    releases = data['releases']
                    if not releases:
                        print(f"No more releases found on page {page_number}. Stopping pagination.")
                        break
                        
                    print(f"Found {len(releases)} releases on page {page_number}")
                    
                    page_tenders = []
                    for release in releases:
                        if 'tender' in release:
                            tender_data = release['tender']
                            
                            # Extract relevant tender information
                            tender = {
                                'tender_id': tender_data.get('id', ''),
                                'ocid': release.get('ocid', ''),
                                'title': tender_data.get('title', ''),
                                'description': tender_data.get('description', ''),
                                'status': tender_data.get('status', ''),
                                'procurement_category': tender_data.get('mainProcurementCategory', ''),
                                'procurement_method': tender_data.get('procurementMethod', ''),
                                'procurement_method_details': tender_data.get('procurementMethodDetails', ''),
                                'buyer_name': release.get('buyer', {}).get('name', ''),
                                'buyer_id': release.get('buyer', {}).get('id', ''),
                                'province': release.get('buyer', {}).get('address', {}).get('region', ''),
                                'procuring_entity': tender_data.get('procuringEntity', {}).get('name', ''),
                                'estimated_value': tender_data.get('value', {}).get('amount', 0),
                                'currency': tender_data.get('value', {}).get('currency', 'ZAR'),
                                'tender_period_start': tender_data.get('tenderPeriod', {}).get('startDate', ''),
                                'tender_period_end': tender_data.get('tenderPeriod', {}).get('endDate', ''),
                                'publication_date': release.get('date', ''),
                                'language': release.get('language', ''),
                                'documents': tender_data.get('documents', []),
                                'url': f"https://www.etenders.gov.za/content/tender-detail/{tender_data.get('id', '')}"
                            }
                            
                            page_tenders.append(tender)
                    
                    all_tenders.extend(page_tenders)
                    print(f"Processed {len(page_tenders)} tenders from page {page_number}")
                    
                    # Check if we should continue to next page
                    if len(releases) < page_size:
                        print(f"Page {page_number} returned fewer results than page size. This might be the last page.")
                        break
                        
                else:
                    print(f"Unexpected data structure on page {page_number}: {list(data.keys())}")
                    break
                    
            else:
                print(f"Failed to fetch data from page {page_number}. Status code: {response.status_code}")
                print(f"Response: {response.text[:500]}...")
                break
                
            page_number += 1
            
        except Exception as e:
            print(f"Error fetching data from page {page_number}: {str(e)}")
            import traceback
            traceback.print_exc()
            break
    
    print(f"Total tenders extracted from {page_number} pages: {len(all_tenders)}")
    
    if all_tenders:
        # Store in PostgreSQL
        store_in_postgresql(all_tenders)
        
        # Store in MongoDB
        store_in_mongodb(all_tenders)
    else:
        print("No tenders were extracted from the API")
    
    print("Tender extraction and storage process completed.")

def store_in_postgresql(tenders):
    """
    Store tenders in PostgreSQL database using Django ORM.
    """
    print("Storing tenders in PostgreSQL...")
    
    count = 0
    for tender_data in tenders:
        try:
            # Extract required fields
            tender_id = tender_data.get('tender_id') or tender_data.get('ocid')
            ocid = tender_data.get('ocid', '')
            
            # Skip if tender already exists
            if Tender.objects.filter(Q(tender_id=tender_id) | Q(ocid=ocid)).exists():
                continue
                
            # Parse dates
            tender_period_end_date = None
            
            try:
                from datetime import datetime
                if tender_data.get('tender_period_end'):
                    tender_period_end_date = datetime.fromisoformat(tender_data['tender_period_end'].replace('Z', '+00:00'))
            except Exception as date_error:
                print(f"Date parsing error for tender {tender_id}: {date_error}")
                
            # Create new tender object with correct field names
            tender = Tender(
                tender_id=tender_id,
                ocid=ocid,
                title=tender_data.get('title', ''),
                description=tender_data.get('description', ''),
                buyer_name=tender_data.get('buyer_name', ''),
                province=tender_data.get('province', ''),
                budget_min=float(tender_data.get('estimated_value', 0)) if tender_data.get('estimated_value') else None,
                budget_max=float(tender_data.get('estimated_value', 0)) if tender_data.get('estimated_value') else None,
                value_currency=tender_data.get('currency', 'ZAR'),
                tender_period_end_date=tender_period_end_date,
                summary=f"Status: {tender_data.get('status', '')} | Category: {tender_data.get('procurement_category', '')} | Method: {tender_data.get('procurement_method', '')}"
            )
            tender.save()
            count += 1
            
        except Exception as e:
            print(f"Error storing tender {tender_data.get('tender_id', 'unknown')} in PostgreSQL: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print(f"Successfully stored {count} new tenders in PostgreSQL")

def store_in_mongodb(tenders):
    """
    Store tenders in MongoDB database.
    """
    print("Storing tenders in MongoDB...")
    
    try:
        # Get MongoDB database
        db = get_database()
        collection = db['tenders']
        
        count = 0
        # Insert tenders
        for tender in tenders:
            try:
                # Handle Django model instances (from .values())
                if isinstance(tender, dict):
                    tender_data = tender.copy()  # Make a copy to avoid modifying original
                else:
                    # Convert model instance to dict
                    tender_data = tender.__dict__.copy()
                
                # Add a unique identifier if not present
                tender_id = tender_data.get('tender_id') or tender_data.get('ocid')
                if not tender_id:
                    print(f"Skipping tender without ID: {tender_data}")
                    continue
                    
                # Use tender_id as _id for MongoDB
                tender_data['_id'] = str(tender_id)
                
                # Remove Django-specific fields that might cause issues
                tender_data.pop('_state', None)
                
                # Convert any datetime objects to strings for MongoDB compatibility
                for key, value in tender_data.items():
                    if hasattr(value, 'isoformat'):  # datetime object
                        tender_data[key] = value.isoformat()
                
                # Insert or update tender
                result = collection.update_one(
                    {'_id': str(tender_id)},
                    {'$set': tender_data},
                    upsert=True
                )
                
                if result.upserted_id or result.modified_count > 0:
                    count += 1
                    
            except Exception as tender_error:
                print(f"Error processing individual tender for MongoDB: {tender_error}")
                continue
        
        print(f"Successfully stored {count} tenders in MongoDB")
        
    except Exception as e:
        print(f"Error storing tenders in MongoDB: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    extract_and_store_tenders()