from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any
import httpx
import io
import json
from openpyxl import Workbook

router = APIRouter(prefix="/api", tags=["OCDS API"])

# eTenders OCDS base URL
OCDS_SOURCE_URL = "https://ocds-api.etenders.gov.za/api/OCDSReleases"


@router.get("/OCDSReleases", response_model=Dict[str, Any])
async def get_ocds_releases(
    PageNumber: int = Query(1, ge=1, description="Page number"),
    PageSize: int = Query(
    50,
    ge=1,
    le=1000,  # max 1000 per request
    description="Page size (max 1000 in browser)"
),
    dateFrom: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    dateTo: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)")
):
    params = {
        "PageNumber": PageNumber,
        "PageSize": PageSize
    }
    if dateFrom:
        params["dateFrom"] = dateFrom
    if dateTo:
        params["dateTo"] = dateTo

    async with httpx.AsyncClient() as client:
        response = await client.get(OCDS_SOURCE_URL, params=params)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch OCDS releases")

    try:
        data = response.json()
    except Exception:
        raise HTTPException(status_code=500, detail="Invalid JSON response from OCDS API")

    releases = data.get("releases", [])
    total = data.get("total", len(releases))

    has_next = PageNumber * PageSize < total

    return {
        "releases": releases,
        "meta": {
            "total": total,
            "page": PageNumber,
            "pageSize": PageSize,
            "hasNext": has_next,
            "totalPages": (total + PageSize - 1) // PageSize
        },
        "links": {
            "self": f"/api/OCDSReleases?PageNumber={PageNumber}&PageSize={PageSize}",
            "next": f"/api/OCDSReleases?PageNumber={PageNumber + 1}&PageSize={PageSize}" if has_next else None,
            "prev": f"/api/OCDSReleases?PageNumber={PageNumber - 1}&PageSize={PageSize}" if PageNumber > 1 else None
        }
    }


@router.get("/OCDSReleases/{ocid}", response_model=Dict[str, Any])
async def get_ocds_release_by_ocid(ocid: str):
    url = f"{OCDS_SOURCE_URL}/{ocid}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Tender with OCID {ocid} not found")

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch tender by OCID")

    return response.json()


@router.get("/OCDSReleases/export/excel")
async def export_ocds_releases_to_excel(
    PageNumber: int = Query(1, ge=1),
    PageSize: int = Query(50, ge=1, le=20000),
    dateFrom: Optional[str] = Query(None),
    dateTo: Optional[str] = Query(None)
):
    # Fetch tenders
    params = {"PageNumber": PageNumber, "PageSize": PageSize}
    if dateFrom:
        params["dateFrom"] = dateFrom
    if dateTo:
        params["dateTo"] = dateTo

    async with httpx.AsyncClient() as client:
        response = await client.get(OCDS_SOURCE_URL, params=params)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch OCDS releases")

    try:
        data = response.json()
    except Exception:
        raise HTTPException(status_code=500, detail="Invalid JSON response from OCDS API")

    releases = data.get("releases", [])

    # Create Excel file in memory
    wb = Workbook()
    ws = wb.active
    ws.title = "Tenders"

    if releases:
        headers = list(releases[0].keys())
        ws.append(headers)

        for release in releases:
            row = []
            for h in headers:
                value = release.get(h, "")
                # Convert dicts/lists to JSON string
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                row.append(value)
            ws.append(row)
    else:
        ws.append(["No data found"])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=tenders.xlsx"}
    )
