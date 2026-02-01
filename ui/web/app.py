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
