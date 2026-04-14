"""
Portfolio Module - Achievement & Portfolio System

Comprehensive digital portfolio management system for students.
"""

from education_system.university_system.modules.domain.events.portfolio.services.portfolio_service import PortfolioService
from education_system.university_system.modules.domain.events.portfolio.cli.portfolio_cli import PortfolioCLI
from education_system.university_system.modules.domain.events.portfolio.gui.portfolio_gui import PortfolioGUI

__all__ = ['PortfolioService', 'PortfolioCLI', 'PortfolioGUI']
