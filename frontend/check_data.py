#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'frontend.settings')
django.setup()

from tenders.models import Tender, WorkspaceItem, Team

print(f"Total tenders: {Tender.objects.count()}")
print(f"Workspace items: {WorkspaceItem.objects.count()}")
print(f"Teams: {Team.objects.count()}")

print("\nSample tender data:")
for t in Tender.objects.all()[:5]:
    title = t.title[:50] + "..." if t.title and len(t.title) > 50 else (t.title or "No title")
    print(f"- {title}")
    print(f"  Buyer: {t.buyer_name or 'Unknown'}")
    print(f"  Province: {t.province or 'Unknown'}")
    print(f"  Budget: {t.budget_max or 'Unknown'}")
    print(f"  Created: {t.created_at}")
    print()

print("\nWorkspace items by status:")
from django.db.models import Count
workspace_stats = WorkspaceItem.objects.values('status').annotate(count=Count('id'))
for stat in workspace_stats:
    print(f"- {stat['status']}: {stat['count']}")