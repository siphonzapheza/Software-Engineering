import os
import sys
import django
from datetime import datetime, timedelta
from django.utils import timezone

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'frontend.settings')
django.setup()

from tenders.models import Tender

def seed_tenders():
    print(f"Current tender count: {Tender.objects.count()}")
    
    # Realistic tender data
    tender_data = [
        {
            'ocid': 'ZA-GP-2024-001',
            'title': 'Supply and Installation of Solar Energy Systems for Government Buildings',
            'description': 'Procurement of solar photovoltaic systems including installation, commissioning and maintenance for various government facilities in Gauteng Province.',
            'buyer_name': 'Department of Public Works - Gauteng',
            'province': 'Gauteng',
            'budget_min': 2500000.00,
            'budget_max': 5000000.00,
            'value_currency': 'ZAR',
            'tender_period_end_date': timezone.now() + timedelta(days=30),
            'summary': 'Solar energy procurement for government buildings with installation and maintenance services.'
        },
        {
            'ocid': 'ZA-WC-2024-002',
            'title': 'Construction of Primary Healthcare Clinic',
            'description': 'Design, construction and commissioning of a new primary healthcare clinic facility including medical equipment procurement.',
            'buyer_name': 'Western Cape Department of Health',
            'province': 'Western Cape',
            'budget_min': 15000000.00,
            'budget_max': 25000000.00,
            'value_currency': 'ZAR',
            'tender_period_end_date': timezone.now() + timedelta(days=45),
            'summary': 'Healthcare facility construction project including medical equipment.'
        },
        {
            'ocid': 'ZA-KZN-2024-003',
            'title': 'Road Maintenance and Rehabilitation Services',
            'description': 'Comprehensive road maintenance, pothole repairs, and rehabilitation of provincial roads in KwaZulu-Natal.',
            'buyer_name': 'KwaZulu-Natal Department of Transport',
            'province': 'KwaZulu-Natal',
            'budget_min': 8000000.00,
            'budget_max': 12000000.00,
            'value_currency': 'ZAR',
            'tender_period_end_date': timezone.now() + timedelta(days=21),
            'summary': 'Road infrastructure maintenance and rehabilitation services.'
        },
        {
            'ocid': 'ZA-EC-2024-004',
            'title': 'Water Infrastructure Development Project',
            'description': 'Installation of water treatment facilities and distribution networks for rural communities in Eastern Cape.',
            'buyer_name': 'Eastern Cape Department of Water and Sanitation',
            'province': 'Eastern Cape',
            'budget_min': 20000000.00,
            'budget_max': 35000000.00,
            'value_currency': 'ZAR',
            'tender_period_end_date': timezone.now() + timedelta(days=60),
            'summary': 'Water treatment and distribution infrastructure for rural communities.'
        },
        {
            'ocid': 'ZA-LP-2024-005',
            'title': 'School Infrastructure Upgrade Program',
            'description': 'Renovation and upgrade of existing school facilities including classrooms, laboratories, and sports facilities.',
            'buyer_name': 'Limpopo Department of Education',
            'province': 'Limpopo',
            'budget_min': 5000000.00,
            'budget_max': 8000000.00,
            'value_currency': 'ZAR',
            'tender_period_end_date': timezone.now() + timedelta(days=35),
            'summary': 'Educational facility renovation and upgrade project.'
        },
        {
            'ocid': 'ZA-MP-2024-006',
            'title': 'IT Equipment and Software Licensing',
            'description': 'Procurement of computer hardware, software licenses, and IT support services for provincial government offices.',
            'buyer_name': 'Mpumalanga Provincial Treasury',
            'province': 'Mpumalanga',
            'budget_min': 3000000.00,
            'budget_max': 6000000.00,
            'value_currency': 'ZAR',
            'tender_period_end_date': timezone.now() + timedelta(days=28),
            'summary': 'IT equipment and software procurement with support services.'
        },
        {
            'ocid': 'ZA-FS-2024-007',
            'title': 'Agricultural Development Support Services',
            'description': 'Provision of agricultural extension services, training programs, and equipment for emerging farmers.',
            'buyer_name': 'Free State Department of Agriculture',
            'province': 'Free State',
            'budget_min': 4000000.00,
            'budget_max': 7000000.00,
            'value_currency': 'ZAR',
            'tender_period_end_date': timezone.now() + timedelta(days=42),
            'summary': 'Agricultural support services and training for emerging farmers.'
        },
        {
            'ocid': 'ZA-NW-2024-008',
            'title': 'Waste Management and Recycling Services',
            'description': 'Comprehensive waste collection, treatment, and recycling services for municipal areas.',
            'buyer_name': 'North West Department of Environment',
            'province': 'North West',
            'budget_min': 6000000.00,
            'budget_max': 10000000.00,
            'value_currency': 'ZAR',
            'tender_period_end_date': timezone.now() + timedelta(days=38),
            'summary': 'Municipal waste management and recycling services.'
        },
        {
            'ocid': 'ZA-NC-2024-009',
            'title': 'Renewable Energy Feasibility Study',
            'description': 'Comprehensive feasibility study for renewable energy projects including wind and solar potential assessment.',
            'buyer_name': 'Northern Cape Department of Economic Development',
            'province': 'Northern Cape',
            'budget_min': 1500000.00,
            'budget_max': 3000000.00,
            'value_currency': 'ZAR',
            'tender_period_end_date': timezone.now() + timedelta(days=25),
            'summary': 'Renewable energy feasibility and potential assessment study.'
        },
        {
            'ocid': 'ZA-GP-2024-010',
            'title': 'Public Transport Fleet Maintenance',
            'description': 'Maintenance and repair services for public transport buses and related infrastructure.',
            'buyer_name': 'Gauteng Department of Roads and Transport',
            'province': 'Gauteng',
            'budget_min': 12000000.00,
            'budget_max': 18000000.00,
            'value_currency': 'ZAR',
            'tender_period_end_date': timezone.now() + timedelta(days=33),
            'summary': 'Public transport fleet maintenance and repair services.'
        }
    ]
    
    created_count = 0
    for data in tender_data:
        tender, created = Tender.objects.get_or_create(
            ocid=data['ocid'],
            defaults=data
        )
        if created:
            created_count += 1
            print(f"Created tender: {tender.title}")
        else:
            print(f"Tender already exists: {tender.title}")
    
    print(f"\nSeeding completed. Created {created_count} new tenders.")
    print(f"Total tenders in database: {Tender.objects.count()}")

if __name__ == '__main__':
    seed_tenders()