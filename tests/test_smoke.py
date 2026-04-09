"""Smoke tests — verify packages import correctly."""


def test_shared_models_import():
    from simu_shared.models import TapeEvent, Session, AgentRegistration
    assert TapeEvent is not None


def test_shared_constants_import():
    from simu_shared.constants import EventType
    assert EventType.CHAT == "chat"


def test_sdk_agent_import():
    from simu_sdk.agent import BaseAgent
    assert BaseAgent is not None


def test_sdk_react_import():
    from simu_sdk.react import ReActLoop
    assert ReActLoop is not None


def test_server_app_import():
    from simu_server.app import create_app
    assert create_app is not None
