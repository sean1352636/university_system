"""
Portfolio Module - Achievement & Portfolio System

Comprehensive digital portfolio management system for students.
"""

from education_system.post_18.university_system.modules.domain.student_affairs.portfolio.services.portfolio_service import PortfolioService
from education_system.post_18.university_system.modules.domain.student_affairs.portfolio.cli.portfolio_cli import PortfolioCLI
from education_system.post_18.university_system.modules.domain.student_affairs.portfolio.gui.portfolio_gui import PortfolioGUI

__all__ = ['PortfolioService', 'PortfolioCLI', 'PortfolioGUI']
