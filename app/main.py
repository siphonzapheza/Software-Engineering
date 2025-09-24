from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.routers import ocds, company_profiles, document_processing, readiness, workspace, search, auth, analytics
from app.database import init_postgres, close_connections

app = FastAPI(
    title="Tender Insight Hub",
    description="A cloud-native SaaS platform designed to assist South African SMEs in navigating public procurement opportunities.",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ocds.router)
app.include_router(company_profiles.router)
app.include_router(document_processing.router)
app.include_router(readiness.router)
app.include_router(workspace.router)
app.include_router(search.router)
app.include_router(auth.router)
app.include_router(analytics.router)

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    await init_postgres()

@app.on_event("shutdown")
def shutdown_event():
    close_connections()
