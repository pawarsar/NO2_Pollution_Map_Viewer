# NO2 Pollution Map Viewer - PRD

## Original Problem Statement
Build a NO2 Pollution Map Viewer that visualizes near-real-time tropospheric NO2 concentration over user-defined polygons using satellite data from Google Earth Engine (GEE) and Sentinel-5P TROPOMI. Features include LangGraph multi-agent pipeline, real-time status updates, report generation, and light/dark themes.

## Architecture
- **Frontend**: React 19 + Tailwind CSS + Shadcn/UI + react-leaflet + recharts + socket.io-client
- **Backend**: FastAPI + python-socketio + LangGraph + Motor (MongoDB) + JWT auth
- **Database**: MongoDB
- **Real-time**: Socket.IO for agent pipeline status updates

## User Personas
- Environmental researchers analyzing air quality
- Policy makers reviewing pollution data
- POC demo users (single admin: sarvesh_pc)

## Core Requirements
1. JWT authentication (single user POC)
2. Interactive Leaflet map with polygon drawing
3. LangGraph sequential 4-agent pipeline with real-time updates
4. Report generation with statistics, 7-day trend chart, recommendations
5. Light/dark theme toggle
6. GEE and Azure OpenAI integration (currently MOCKED)

## What's Been Implemented (2026-03-29)
- [x] JWT auth with login/logout/me endpoints
- [x] Admin seeding (sarvesh_pc / sarvesh_pc@06)
- [x] Interactive Leaflet map with CartoDB Positron/DarkMatter tiles
- [x] Polygon drawing via leaflet-draw
- [x] LangGraph pipeline with 4 sequential agents (Data Fetcher, Stats Analyzer, Trend Analyzer, Recommendation Generator)
- [x] Socket.IO real-time agent status updates
- [x] **NEW: Dedicated Analysis Page** (/analysis/:id) with two-column layout
  - Left: Agent pipeline stepper with vertical connectors, progress indicators, and badges
  - Right: Live results panel with slide-in animations per agent
  - Top: Animated progress bar + percentage counter
- [x] Report page with human-readable values (percentages of safe threshold)
- [x] Color-coded pollution bars (green/amber/red) instead of scientific notation
- [x] Chart with color zones (green/yellow/red) + safe threshold reference line
- [x] Recommendation cards with category icons and impact priority bars
- [x] Light/dark theme with Swiss High-Contrast design
- [x] Cabinet Grotesk + IBM Plex Sans typography
- [x] Glassmorphism map overlays
- [x] Polygon validation
- [x] Staggered entrance animations, indeterminate progress, result card animations

## MOCKED Integrations
- Google Earth Engine (GEE) - returns realistic mock NO2 data
- Azure OpenAI - returns predefined recommendations

## Prioritized Backlog
### P0 (Critical for Production)
- [ ] GEE service account key integration (user will provide)
- [ ] Azure OpenAI integration (user will provide key)

### P1 (Important)
- [ ] GeoJSON file upload for polygon
- [ ] Map NO2 tile overlay from GEE (getMapId)
- [ ] Historical analysis persistence / comparison

### P2 (Nice to Have)
- [ ] Export report as PDF
- [ ] Multiple polygon analysis
- [ ] AQI correlation display
- [ ] User management (multi-user)

## Next Tasks
1. User provides GEE credentials → replace mock with real satellite data
2. User provides Azure OpenAI credentials → replace mock recommendations with AI-generated ones
3. Add GeoJSON upload support
4. Add NO2 tile overlay on map during analysis
