"""Pydantic schemas for finance endpoints.

This module provides request/response models for financial operations,
including payments, income reports, and dashboard metrics.

Key components:
    - PaymentCreate: Schema for creating payments
    - PaymentResponse: Schema for payment API responses
    - DashboardMetricsResponse: Schema for dashboard metrics
    - IncomeReportResponse: Schema for income reports
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field, field_validator

from api.schemas.base import BaseRequest, BaseResponse, TimestampMixin, TenantMixin


class PaymentCreate(BaseRequest):
    """Request schema for creating a payment.
    
    Attributes:
        learner_id: ID of the learner making payment
        package_id: Associated package ID (optional)
        lesson_id: Associated lesson ID for standalone lessons (optional)
        amount: Payment amount (must be positive)
        paid_at: Date/time of payment
        notes: Optional payment notes
    """
    learner_id: int = Field(..., gt=0, description="Learner ID")
    package_id: Optional[int] = Field(None, gt=0, description="Package ID (optional)")
    lesson_id: Optional[int] = Field(None, gt=0, description="Lesson ID for standalone lessons")
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="Payment amount")
    paid_at: datetime = Field(..., description="Payment date/time")
    notes: Optional[str] = Field(None, max_length=1000, description="Payment notes")

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class PaymentResponse(BaseResponse, TimestampMixin, TenantMixin):
    """Response schema for payment.
    
    Attributes:
        id: Payment ID
        learner_id: Learner ID
        learner_name: Learner display name
        package_id: Package ID (if package payment)
        package_title: Package title (if package payment)
        lesson_id: Lesson ID (if standalone lesson payment)
        amount: Payment amount
        currency: Currency code
        paid_at: Payment date/time
        notes: Payment notes
    """
    id: int = Field(..., description="Payment ID")
    learner_id: int = Field(..., description="Learner ID")
    learner_name: Optional[str] = Field(None, description="Learner display name")
    package_id: Optional[int] = Field(None, description="Package ID")
    package_title: Optional[str] = Field(None, description="Package title")
    lesson_id: Optional[int] = Field(None, description="Lesson ID")
    amount: Decimal = Field(..., description="Payment amount")
    currency: str = Field(default="RUB", description="Currency code")
    paid_at: datetime = Field(..., description="Payment date/time")
    notes: Optional[str] = Field(None, description="Payment notes")


class MonthlyIncomeResponse(BaseResponse):
    """Monthly income data point for charts."""
    month: str = Field(..., description="Month in YYYY-MM format")
    amount: Decimal = Field(..., description="Income amount")


class DashboardMetricsResponse(BaseResponse):
    """Response schema for financial dashboard metrics.
    
    Attributes:
        current_month_income: Total income for current month
        previous_month_income: Total income for previous month
        total_outstanding: Total outstanding balance across all learners
        unpaid_learners_count: Count of learners with unpaid packages
        income_chart: 6-month income chart data
    """
    current_month_income: Decimal = Field(..., description="Current month income")
    previous_month_income: Decimal = Field(..., description="Previous month income")
    total_outstanding: Decimal = Field(..., description="Total outstanding balance")
    unpaid_learners_count: int = Field(..., description="Count of learners with unpaid packages")
    income_chart: list[MonthlyIncomeResponse] = Field(..., description="6-month income chart")


class LearnerIncomeResponse(BaseResponse):
    """Income breakdown by learner."""
    learner_id: int = Field(..., description="Learner ID")
    learner_name: str = Field(..., description="Learner name")
    amount: Decimal = Field(..., description="Total amount")


class PackageIncomeResponse(BaseResponse):
    """Income breakdown by package."""
    package_id: int = Field(..., description="Package ID")
    package_title: str = Field(..., description="Package title")
    amount: Decimal = Field(..., description="Total amount")


class IncomeReportResponse(BaseResponse):
    """Response schema for income report.
    
    Attributes:
        period_start: Start of report period
        period_end: End of report period
        total: Total income for period
        by_learner: Breakdown by learner
        by_package: Breakdown by package
        previous_period_total: Previous period total for comparison
        change_percent: Percentage change from previous period
    """
    period_start: datetime = Field(..., description="Period start date")
    period_end: datetime = Field(..., description="Period end date")
    total: Decimal = Field(..., description="Total income")
    by_learner: list[LearnerIncomeResponse] = Field(..., description="Breakdown by learner")
    by_package: list[PackageIncomeResponse] = Field(..., description="Breakdown by package")
    previous_period_total: Decimal = Field(..., description="Previous period total")
    change_percent: float = Field(..., description="Change percentage")


class LearnerFinanceResponse(BaseResponse):
    """Response schema for learner finance profile.
    
    Attributes:
        learner_id: Learner ID
        lesson_rate: Individual lesson rate
        outstanding_balance: Total outstanding balance
        total_paid: Total amount paid
        payment_history: List of payments
    """
    learner_id: int = Field(..., description="Learner ID")
    lesson_rate: Optional[Decimal] = Field(None, description="Lesson rate")
    outstanding_balance: Decimal = Field(..., description="Outstanding balance")
    total_paid: Decimal = Field(..., description="Total paid")
    payment_history: list[PaymentResponse] = Field(..., description="Payment history")


class DebtorResponse(BaseResponse):
    """Response schema for a debtor (learner with outstanding balance)."""

    learner_id: int = Field(..., description="Learner ID")
    learner_name: str = Field(..., description="Learner name")
    outstanding_balance: Decimal = Field(..., description="Outstanding balance for learner")


__all__ = [
    'PaymentCreate',
    'PaymentResponse',
    'MonthlyIncomeResponse',
    'DashboardMetricsResponse',
    'LearnerIncomeResponse',
    'PackageIncomeResponse',
    'IncomeReportResponse',
    'LearnerFinanceResponse',
    'DebtorResponse',
]
