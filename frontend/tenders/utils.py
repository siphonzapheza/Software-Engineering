from .models import Tender
from .db import tenders_collection
from datetime import datetime, timedelta
import re
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseForbidden
from django.utils import timezone

def save_tenders_locally(tenders_list):
    for t in tenders_list:
        # Save to MongoDB
        tenders_collection.update_one(
            {"ocid": t.get("ocid")},
            {"$set": t},
            upsert=True
        )

        # Save to PostgreSQL
        Tender.objects.update_or_create(
            ocid=t.get("ocid"),
            defaults={
                "title": t.get("title"),
                "description": t.get("description"),
                "buyer_name": t.get("buyer_name"),
                "province": t.get("province"),
                "value_amount": t.get("value_amount"),
                "value_currency": t.get("value_currency"),
                "tender_period_end_date": t.get("tender_period_end_date") and datetime.fromisoformat(t.get("tender_period_end_date"))
            }
        )

def extract_province_from_buyer(buyer_name):
    """
    Extract province name from buyer name when province is 'Not specified'
    
    Examples:
    - "Western Cape - Health" -> "Western Cape"
    - "Gauteng Department of Education" -> "Gauteng"
    - "KwaZulu-Natal Provincial Treasury" -> "KwaZulu-Natal"
    """
    if not buyer_name:
        return None
    
    # South African provinces
    provinces = [
        'Western Cape',
        'Eastern Cape', 
        'Northern Cape',
        'Free State',
        'KwaZulu-Natal',
        'North West',
        'Gauteng',
        'Mpumalanga',
        'Limpopo'
    ]
    
    # Check for exact province matches at the beginning of buyer name
    for province in provinces:
        # Pattern: "Province - Department" or "Province Department"
        if buyer_name.startswith(province):
            return province
        
        # Pattern: "Department of Province" or "Province Provincial"
        if province.lower() in buyer_name.lower():
            return province
    
    # Check for common patterns
    patterns = [
        r'^(Western Cape|Eastern Cape|Northern Cape|Free State|KwaZulu-Natal|North West|Gauteng|Mpumalanga|Limpopo)\s*[-\s]',
        r'(Western Cape|Eastern Cape|Northern Cape|Free State|KwaZulu-Natal|North West|Gauteng|Mpumalanga|Limpopo)\s+(?:Department|Provincial|Government)',
        r'Department.*?(Western Cape|Eastern Cape|Northern Cape|Free State|KwaZulu-Natal|North West|Gauteng|Mpumalanga|Limpopo)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, buyer_name, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def normalize_province_data():
    """
    Update tenders with extracted provinces from buyer names where province is 'Not specified'
    """
    # Get tenders with 'Not specified' province
    tenders_to_update = Tender.objects.filter(
        province__in=['Not specified', '', None]
    )
    
    updated_count = 0
    for tender in tenders_to_update:
        extracted_province = extract_province_from_buyer(tender.buyer_name)
        if extracted_province:
            tender.province = extracted_province
            tender.save()
            updated_count += 1
    
    return updated_count
