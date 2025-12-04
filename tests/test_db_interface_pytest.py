"""
Database Interface Tests - pytest version
"""

import pytest
import os
from db.database import Database


@pytest.fixture
def temp_db():
    """Create temporary database"""
    db_path = "test_temp.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    db = Database(db_path)
    yield db
    # Cleanup after test
    if os.path.exists(db_path):
        os.remove(db_path)


def test_database_initialization():
    """Test database initialization"""
    db = Database(":memory:")
    assert db is not None


def test_game_state_save_and_load(temp_db):
    """Test game state save and load"""
    test_state = {
        'current_month': 5,
        'treasury': 1500.50,
        'month_starting_treasury': 1000.0,
        'debug_mode': True
    }

    temp_db.save_game_state(test_state)
    loaded_state = temp_db.load_game_state()

    assert loaded_state['current_month'] == 5
    assert loaded_state['treasury'] == 1500.50
    assert loaded_state['debug_mode'] is True


def test_provinces_save_and_load(temp_db):
    """Test province data save and load"""
    # Modify first province
    provinces = temp_db.load_provinces()
    original_name = provinces[0]['name']
    provinces[0]['name'] = 'Test Province'
    provinces[0]['population'] = 9999

    temp_db.save_provinces(provinces)
    loaded_provinces = temp_db.load_provinces()

    assert loaded_provinces[0]['name'] == 'Test Province'
    assert loaded_provinces[0]['population'] == 9999


def test_monthly_report_interface(temp_db):
    """Test monthly report save and load"""
    provinces = temp_db.load_provinces()
    test_province_id = provinces[0]['province_id']

    temp_db.add_monthly_report(
        month=3,
        province_id=test_province_id,
        reported_income=500.0,
        reported_expenditure=200.0,
        actual_income=600.0,
        actual_expenditure=180.0,
        treasury_change=300.0
    )

    # Verify data was written
    conn = temp_db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM monthly_reports WHERE month=3")
    result_row = cursor.fetchone()

    assert result_row is not None
    assert result_row[3] == 500.0


def test_project_lifecycle_interface(temp_db):
    """Test project lifecycle"""
    provinces = temp_db.load_provinces()
    test_province_id = provinces[0]['province_id']

    test_project = {
        'province_id': test_province_id,
        'project_type': 'agriculture',
        'cost': 50.0,
        'effect_type': 'income_bonus',
        'effect_value': 0.08,
        'month_created': 2
    }

    temp_db.add_project(test_project)
    active_projects = temp_db.get_active_projects()
    assert len(active_projects) == 1
    assert active_projects[0]['project_type'] == 'agriculture'

    # Complete project
    project_id = active_projects[0]['project_id']
    temp_db.complete_project(project_id)

    # Verify project is no longer active
    active_projects_after = temp_db.get_active_projects()
    assert len(active_projects_after) == 0
