"""
Portfolio Module - Achievement & Portfolio System

Comprehensive digital portfolio management system for students.
"""

from education_system.university_system.modules.domain.portfolio.services.portfolio_service import PortfolioService
from education_system.university_system.modules.domain.portfolio.cli.portfolio_cli import PortfolioCLI
from education_system.university_system.modules.domain.portfolio.gui.portfolio_gui import PortfolioGUI

__all__ = ['PortfolioService', 'PortfolioCLI', 'PortfolioGUI']
