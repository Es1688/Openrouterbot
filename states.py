# FILE: states.py
"""
Состояния для Finite State Machine (FSM) бота.
"""

from aiogram.fsm.state import State, StatesGroup


class Confirmation(StatesGroup):
    """Состояния для подтверждения действий."""
    awaiting_reset_confirmation = State()

