

## Tender Insight Hub

AI-powered platform helping South African SMEs discover, analyze, and win public procurement opportunities.

### Features
- **Smart Search & Filtering**: Find relevant tenders with AI-powered keyword matching
- **AI Document Analysis**: Get plain-language summaries of complex tender documents
- **Readiness Scoring**: Know your chances with automated suitability assessments
- **Team Collaboration**: Work together with notes, tasks, and status tracking
- **Real-time Updates**: Never miss deadlines with automated notifications
- **OCDS Integration**: Direct access to official government tender data



### Backend API

The FastAPI backend runs on `http://localhost:8000` and provides:
- Authentication endpoints (`/api/auth/login`, `/api/auth/register`)
- Tender search and filtering (`/api/tenders`)
- AI analysis capabilities (`/api/tenders/{id}/analyze`)
- Dashboard statistics (`/api/dashboard/stats`)

API documentation is available at `http://localhost:8000/docs` when the backend is running.

**Edit a file directly in GitHub**

- Navigate to the desired file(s).
- Click the "Edit" button (pencil icon) at the top right of the file view.
- Make your changes and commit the changes.

**Use GitHub Codespaces**

- Navigate to the main page of your repository.
- Click on the "Code" button (green button) near the top right.
- Select the "Codespaces" tab.
- Click on "New codespace" to launch a new Codespace environment.
- Edit files directly within the Codespace and commit and push your changes once you're done.

## What technologies are used for this project?

This project is built with:

### Frontend
- Vite
- TypeScript
- React
- shadcn-ui
- Tailwind CSS
- Axios for API calls

### Backend
- FastAPI
- Python
- Pydantic for data validation
- Uvicorn ASGI server

