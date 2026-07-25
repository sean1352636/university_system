"""
Portfolio Module - Achievement & Portfolio System

Comprehensive digital portfolio management system for students.
"""

from education_system.systems.university.domain.progression.portfolio.services.portfolio_service import PortfolioService
from education_system.systems.university.interfaces.cli.progression.portfolio.portfolio_cli import PortfolioCLI
from education_system.systems.university.interfaces.gui.progression.portfolio.portfolio_gui import PortfolioGUI

__all__ = ['PortfolioService', 'PortfolioCLI', 'PortfolioGUI']
