"""
FastAPI Web UI Application for EU4-Style Strategy Game
"""

import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from core.game import Game

# Create FastAPI app
app = FastAPI(title="EU4 Strategy Game Web UI")

# Get current directory
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(CURRENT_DIR, "static")), name="static")

# Setup templates
templates = Jinja2Templates(directory=os.path.join(CURRENT_DIR, "templates"))

# Global game instance (initialized on startup)
game_instance: Game = None


@app.on_event("startup")
async def startup_event():
    """Initialize game instance on startup"""
    global game_instance
    game_instance = Game()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main game page"""
    global game_instance
    
    # Get current game state
    state = game_instance.state
    provinces = game_instance.provinces
    
    # Get active events count
    active_events = game_instance.event_manager.get_active_events(state['current_month'])
    national_events = [e for e in active_events if e.event_type == 'national']
    province_events = [e for e in active_events if e.event_type == 'province']
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "month": state['current_month'],
        "treasury": state['treasury'],
        "debug_mode": state['debug_mode'],
        "national_event_count": len(national_events),
        "province_event_count": len(province_events),
        "provinces": provinces,
    })


@app.get("/api/state")
async def get_state():
    """Get current game state"""
    global game_instance
    state = game_instance.state
    
    # Get active events count
    active_events = game_instance.event_manager.get_active_events(state['current_month'])
    national_events = [e for e in active_events if e.event_type == 'national']
    province_events = [e for e in active_events if e.event_type == 'province']
    
    return {
        "month": state['current_month'],
        "treasury": state['treasury'],
        "debug_mode": state['debug_mode'],
        "national_event_count": len(national_events),
        "province_event_count": len(province_events),
    }


@app.post("/api/next-month")
async def next_month():
    """Advance to next month"""
    global game_instance
    await game_instance.next_month()
    
    state = game_instance.state
    active_events = game_instance.event_manager.get_active_events(state['current_month'])
    national_events = [e for e in active_events if e.event_type == 'national']
    province_events = [e for e in active_events if e.event_type == 'province']
    
    return {
        "month": state['current_month'],
        "treasury": state['treasury'],
        "debug_mode": state['debug_mode'],
        "national_event_count": len(national_events),
        "province_event_count": len(province_events),
    }


@app.post("/api/debug-mode")
async def toggle_debug_mode():
    """Toggle debug mode"""
    global game_instance
    game_instance.toggle_debug_mode()
    
    state = game_instance.state
    return {
        "month": state['current_month'],
        "treasury": state['treasury'],
        "debug_mode": state['debug_mode'],
    }


@app.get("/api/national-status")
async def get_national_status():
    """Get comprehensive national status"""
    global game_instance
    state = game_instance.state
    
    # Calculate totals
    total_income = sum(p.actual_income for p in game_instance.provinces)
    total_reported_income = sum(p.reported_income for p in game_instance.provinces)
    total_expenditure = sum(p.actual_expenditure for p in game_instance.provinces)
    total_reported_expenditure = sum(p.reported_expenditure for p in game_instance.provinces)
    
    # Get active events
    active_events = game_instance.event_manager.get_active_events(state['current_month'])
    
    return {
        "month": state['current_month'],
        "treasury": state['treasury'],
        "total_actual_income": total_income,
        "total_reported_income": total_reported_income,
        "total_actual_expenditure": total_expenditure,
        "total_reported_expenditure": total_reported_expenditure,
        "actual_surplus": total_income - total_expenditure,
        "reported_surplus": total_reported_income - total_reported_expenditure,
        "province_count": len(game_instance.provinces),
        "provinces": [
            {
                "province_id": p.province_id,
                "name": p.name,
                "population": p.population,
                "development_level": p.development_level,
                "loyalty": p.loyalty,
                "stability": p.stability,
                "reported_income": p.reported_income,
                "reported_surplus": p.reported_income - p.reported_expenditure,
                "last_month_corrupted": p.last_month_corrupted,
            }
            for p in game_instance.provinces
        ],
        "active_events": [
            {
                "event_id": getattr(e, 'event_id', None),
                "name": e.name,
                "event_type": e.event_type,
                "severity": e.severity,
                "province_id": getattr(e, 'province_id', None),
            }
            for e in active_events
        ],
        "debug_mode": state['debug_mode'],
    }


@app.get("/api/provinces")
async def get_provinces():
    """Get all provinces data"""
    global game_instance
    state = game_instance.state
    provinces = game_instance.provinces
    
    result = []
    for province in provinces:
        province_data = {
            "province_id": province.province_id,
            "name": province.name,
            "population": province.population,
            "development_level": province.development_level,
            "loyalty": province.loyalty,
            "stability": province.stability,
            "base_income": province.base_income,
            "reported_income": province.reported_income,
            "reported_expenditure": province.reported_expenditure,
            "reported_surplus": province.reported_surplus,
            "last_month_corrupted": province.last_month_corrupted,
        }
        
        # Include actual values only in debug mode
        if state['debug_mode']:
            province_data.update({
                "actual_income": province.actual_income,
                "actual_expenditure": province.actual_expenditure,
                "actual_surplus": province.actual_surplus,
                "adjusted_income": province.adjusted_income,
                "adjusted_expenditure": province.adjusted_expenditure,
            })
        
        result.append(province_data)
    
    return result


@app.post("/api/provinces/{province_id}/projects")
async def create_project(province_id: int, request: dict):
    """Create a new project in a province"""
    global game_instance
    
    project_type = request.get("project_type")
    if not project_type:
        return {"detail": "Project type is required"}, 400
    
    # Validate project type
    valid_types = ["agriculture", "infrastructure", "tax_relief", "security"]
    if project_type not in valid_types:
        return {"detail": f"Invalid project type. Must be one of: {valid_types}"}, 400
    
    # Find province
    province = None
    for p in game_instance.provinces:
        if p.province_id == province_id:
            province = p
            break
    
    if not province:
        return {"detail": "Province not found"}, 404
    
    # Check treasury
    from core.project import Project
    project_costs = {
        "agriculture": 50,
        "infrastructure": 80,
        "tax_relief": 30,
        "security": 60
    }
    
    if game_instance.state["treasury"] < project_costs[project_type]:
        return {"detail": "Insufficient treasury"}, 400
    
    # Create and add project
    project = Project(province_id, project_type, game_instance.state["current_month"])
    game_instance.add_project(project)
    
    return {
        "success": True,
        "project_type": project_type,
        "cost": project.cost,
        "province_name": province.name
    }


@app.get("/api/events")
async def get_events(province_id: int = None):
    """Get active events, optionally filtered by province"""
    global game_instance
    state = game_instance.state
    
    active_events = game_instance.event_manager.get_active_events(state['current_month'])
    
    result = []
    for event in active_events:
        # Filter by province if specified
        if province_id is not None:
            event_province_id = getattr(event, 'province_id', None)
            if event_province_id != province_id:
                continue
        
        event_data = {
            "event_id": getattr(event, 'event_id', None),
            "name": event.name,
            "description": event.description,
            "event_type": event.event_type,
            "severity": event.severity,
            "start_month": event.start_month,
            "duration": event.duration,
        }
        
        # Add province info for provincial events
        if event.event_type == 'province':
            event_data["province_id"] = getattr(event, 'province_id', None)
        
        # Add debug info
        if state['debug_mode']:
            event_data.update({
                "visibility": getattr(event, 'visibility', 'visible'),
                "is_hidden_by_governor": getattr(event, 'is_hidden_by_governor', False),
                "is_fabricated": getattr(event, 'is_fabricated', False),
            })
        
        result.append(event_data)
    
    return result


@app.get("/api/financial-report")
async def get_financial_report():
    """Get financial report for current month"""
    global game_instance
    
    summary = game_instance.get_financial_summary()
    state = game_instance.state
    
    # Calculate totals
    total_income = sum(p.actual_income for p in game_instance.provinces)
    total_reported_income = sum(p.reported_income for p in game_instance.provinces)
    total_expenditure = sum(p.actual_expenditure for p in game_instance.provinces)
    total_reported_expenditure = sum(p.reported_expenditure for p in game_instance.provinces)
    
    return {
        "month": state['current_month'],
        "treasury": summary['treasury'],
        "month_starting_treasury": summary['month_starting_treasury'],
        "monthly_change": summary['treasury'] - summary['month_starting_treasury'],
        "total_income": total_income,
        "total_reported_income": total_reported_income,
        "total_expenditure": total_expenditure,
        "total_reported_expenditure": total_reported_expenditure,
        "provinces": [
            {
                "province_id": p.province_id,
                "name": p.name,
                "actual_income": p.actual_income,
                "reported_income": p.reported_income,
                "actual_expenditure": p.actual_expenditure,
                "reported_expenditure": p.reported_expenditure,
                "actual_surplus": p.actual_income - p.actual_expenditure,
                "reported_surplus": p.reported_income - p.reported_expenditure,
                "last_month_corrupted": p.last_month_corrupted,
            }
            for p in game_instance.provinces
        ],
        "debug_mode": state['debug_mode'],
    }
