"""Validation service for data quality and discrepancy management.

Provides business logic for:
- Listing and managing validation rules
- Tracking validation run history
- Computing and retrieving quality scores
- Managing discrepancies
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from nhl_api.services.db import DatabaseService
from nhl_api.viewer.schemas.validation import (
    DiscrepanciesResponse,
    DiscrepancyDetail,
    DiscrepancySummary,
    QualityScore,
    QualityScoresResponse,
    ValidationResult,
    ValidationRule,
    ValidationRulesResponse,
    ValidationRunDetail,
    ValidationRunsResponse,
    ValidationRunSummary,
)


@dataclass
class ValidationService:
    """Service for validation data access and business logic."""

    # =========================================================================
    # Validation Rules
    # =========================================================================

    async def get_validation_rules(
        self,
        db: DatabaseService,
        category: str | None = None,
        is_active: bool | None = None,
    ) -> ValidationRulesResponse:
        """Get all validation rules with optional filters."""
        conditions: list[str] = []
        params: list[Any] = []
        param_idx = 1

        if category is not None:
            conditions.append(f"category = ${param_idx}")
            params.append(category)
            param_idx += 1

        if is_active is not None:
            conditions.append(f"is_active = ${param_idx}")
            params.append(is_active)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT
                rule_id, name, description, category, severity,
                is_active, config
            FROM validation_rules
            WHERE {where_clause}
            ORDER BY category, name
        """

        rows = await db.fetch(query, *params)

        rules = [
            ValidationRule(
                rule_id=row["rule_id"],
                name=row["name"],
                description=row["description"],
                category=row["category"],
                severity=row["severity"],
                is_active=row["is_active"],
                config=row["config"],
            )
            for row in rows
        ]

        return ValidationRulesResponse(rules=rules, total=len(rules))

    # =========================================================================
    # Validation Runs
    # =========================================================================

    async def get_validation_runs(
        self,
        db: DatabaseService,
        season_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ValidationRunsResponse:
        """Get paginated list of validation runs."""
        conditions: list[str] = []
        params: list[Any] = []
        param_idx = 1

        if season_id is not None:
            conditions.append(f"season_id = ${param_idx}")
            params.append(season_id)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Count total
        count_query = f"SELECT COUNT(*) FROM validation_runs WHERE {where_clause}"
        total = await db.fetchval(count_query, *params) or 0

        # Calculate pagination
        offset = (page - 1) * page_size
        pages = math.ceil(total / page_size) if total > 0 else 1

        # Fetch paginated data
        query = f"""
            SELECT
                run_id, season_id, started_at, completed_at, status,
                rules_checked, total_passed, total_failed, total_warnings
            FROM validation_runs
            WHERE {where_clause}
            ORDER BY started_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([page_size, offset])

        rows = await db.fetch(query, *params)

        runs = [
            ValidationRunSummary(
                run_id=row["run_id"],
                season_id=row["season_id"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                status=row["status"],
                rules_checked=row["rules_checked"] or 0,
                total_passed=row["total_passed"] or 0,
                total_failed=row["total_failed"] or 0,
                total_warnings=row["total_warnings"] or 0,
            )
            for row in rows
        ]

        return ValidationRunsResponse(
            runs=runs,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    async def get_validation_run(
        self,
        db: DatabaseService,
        run_id: int,
    ) -> ValidationRunDetail:
        """Get detailed validation run with results."""
        # Get run info
        run_query = """
            SELECT
                run_id, season_id, started_at, completed_at, status,
                rules_checked, total_passed, total_failed, total_warnings,
                metadata
            FROM validation_runs
            WHERE run_id = $1
        """
        run_row = await db.fetchrow(run_query, run_id)

        if not run_row:
            raise ValueError(f"Validation run {run_id} not found")

        # Get results for this run
        results_query = """
            SELECT
                vr.result_id, vr.rule_id, r.name as rule_name, vr.game_id,
                vr.passed, vr.severity, vr.message, vr.details, vr.source_values,
                vr.created_at
            FROM validation_results vr
            JOIN validation_rules r ON r.rule_id = vr.rule_id
            WHERE vr.run_id = $1
            ORDER BY vr.passed ASC, vr.created_at DESC
            LIMIT 1000
        """
        result_rows = await db.fetch(results_query, run_id)

        results = [
            ValidationResult(
                result_id=row["result_id"],
                rule_id=row["rule_id"],
                rule_name=row["rule_name"],
                game_id=row["game_id"],
                passed=row["passed"],
                severity=row["severity"],
                message=row["message"],
                details=row["details"],
                source_values=row["source_values"],
                created_at=row["created_at"],
            )
            for row in result_rows
        ]

        return ValidationRunDetail(
            run_id=run_row["run_id"],
            season_id=run_row["season_id"],
            started_at=run_row["started_at"],
            completed_at=run_row["completed_at"],
            status=run_row["status"],
            rules_checked=run_row["rules_checked"] or 0,
            total_passed=run_row["total_passed"] or 0,
            total_failed=run_row["total_failed"] or 0,
            total_warnings=run_row["total_warnings"] or 0,
            results=results,
            metadata=run_row["metadata"],
        )

    # =========================================================================
    # Quality Scores
    # =========================================================================

    async def get_quality_scores(
        self,
        db: DatabaseService,
        season_id: int | None = None,
        entity_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> QualityScoresResponse:
        """Get paginated list of quality scores."""
        conditions: list[str] = []
        params: list[Any] = []
        param_idx = 1

        if season_id is not None:
            conditions.append(f"season_id = ${param_idx}")
            params.append(season_id)
            param_idx += 1

        if entity_type is not None:
            if entity_type == "game":
                conditions.append("game_id IS NOT NULL")
            elif entity_type == "season":
                conditions.append("game_id IS NULL")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Count total
        count_query = f"SELECT COUNT(*) FROM data_quality_scores WHERE {where_clause}"
        total = await db.fetchval(count_query, *params) or 0

        # Calculate pagination
        offset = (page - 1) * page_size
        pages = math.ceil(total / page_size) if total > 0 else 1

        # Fetch paginated data
        query = f"""
            SELECT
                score_id, season_id, game_id,
                completeness_score, accuracy_score, consistency_score,
                timeliness_score, overall_score,
                total_checks, passed_checks, failed_checks, warning_checks,
                calculated_at
            FROM data_quality_scores
            WHERE {where_clause}
            ORDER BY overall_score ASC NULLS LAST, calculated_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([page_size, offset])

        rows = await db.fetch(query, *params)

        scores = [
            QualityScore(
                score_id=row["score_id"],
                season_id=row["season_id"],
                game_id=row["game_id"],
                entity_type="game" if row["game_id"] else "season",
                entity_id=str(row["game_id"])
                if row["game_id"]
                else str(row["season_id"]),
                completeness_score=float(row["completeness_score"])
                if row["completeness_score"]
                else None,
                accuracy_score=float(row["accuracy_score"])
                if row["accuracy_score"]
                else None,
                consistency_score=float(row["consistency_score"])
                if row["consistency_score"]
                else None,
                timeliness_score=float(row["timeliness_score"])
                if row["timeliness_score"]
                else None,
                overall_score=float(row["overall_score"])
                if row["overall_score"]
                else None,
                total_checks=row["total_checks"] or 0,
                passed_checks=row["passed_checks"] or 0,
                failed_checks=row["failed_checks"] or 0,
                warning_checks=row["warning_checks"] or 0,
                calculated_at=row["calculated_at"],
            )
            for row in rows
        ]

        return QualityScoresResponse(
            scores=scores,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    async def get_entity_score(
        self,
        db: DatabaseService,
        entity_type: Literal["season", "game"],
        entity_id: str,
    ) -> QualityScore:
        """Get quality score for a specific entity."""
        if entity_type == "game":
            query = """
                SELECT
                    score_id, season_id, game_id,
                    completeness_score, accuracy_score, consistency_score,
                    timeliness_score, overall_score,
                    total_checks, passed_checks, failed_checks, warning_checks,
                    calculated_at
                FROM data_quality_scores
                WHERE game_id = $1
                ORDER BY calculated_at DESC
                LIMIT 1
            """
            row = await db.fetchrow(query, int(entity_id))
        elif entity_type == "season":
            query = """
                SELECT
                    score_id, season_id, game_id,
                    completeness_score, accuracy_score, consistency_score,
                    timeliness_score, overall_score,
                    total_checks, passed_checks, failed_checks, warning_checks,
                    calculated_at
                FROM data_quality_scores
                WHERE season_id = $1 AND game_id IS NULL
                ORDER BY calculated_at DESC
                LIMIT 1
            """
            row = await db.fetchrow(query, int(entity_id))
        else:
            raise ValueError(f"Invalid entity type: {entity_type}")

        if not row:
            raise ValueError(f"No quality score found for {entity_type} {entity_id}")

        return QualityScore(
            score_id=row["score_id"],
            season_id=row["season_id"],
            game_id=row["game_id"],
            entity_type=entity_type,
            entity_id=entity_id,
            completeness_score=float(row["completeness_score"])
            if row["completeness_score"]
            else None,
            accuracy_score=float(row["accuracy_score"])
            if row["accuracy_score"]
            else None,
            consistency_score=float(row["consistency_score"])
            if row["consistency_score"]
            else None,
            timeliness_score=float(row["timeliness_score"])
            if row["timeliness_score"]
            else None,
            overall_score=float(row["overall_score"]) if row["overall_score"] else None,
            total_checks=row["total_checks"] or 0,
            passed_checks=row["passed_checks"] or 0,
            failed_checks=row["failed_checks"] or 0,
            warning_checks=row["warning_checks"] or 0,
            calculated_at=row["calculated_at"],
        )

    # =========================================================================
    # Discrepancies
    # =========================================================================

    async def get_discrepancies(
        self,
        db: DatabaseService,
        season_id: int | None = None,
        status: str | None = None,
        entity_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> DiscrepanciesResponse:
        """Get paginated list of discrepancies."""
        conditions: list[str] = []
        params: list[Any] = []
        param_idx = 1

        if season_id is not None:
            conditions.append(f"d.season_id = ${param_idx}")
            params.append(season_id)
            param_idx += 1

        if status is not None:
            conditions.append(f"d.resolution_status = ${param_idx}")
            params.append(status)
            param_idx += 1

        if entity_type is not None:
            conditions.append(f"d.entity_type = ${param_idx}")
            params.append(entity_type)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Count total
        count_query = f"""
            SELECT COUNT(*) FROM discrepancies d WHERE {where_clause}
        """
        total = await db.fetchval(count_query, *params) or 0

        # Calculate pagination
        offset = (page - 1) * page_size
        pages = math.ceil(total / page_size) if total > 0 else 1

        # Fetch paginated data
        query = f"""
            SELECT
                d.discrepancy_id, d.rule_id, r.name as rule_name,
                d.game_id, d.season_id, d.entity_type, d.entity_id,
                d.field_name, d.source_a, d.source_b,
                d.resolution_status, d.created_at
            FROM discrepancies d
            JOIN validation_rules r ON r.rule_id = d.rule_id
            WHERE {where_clause}
            ORDER BY d.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([page_size, offset])

        rows = await db.fetch(query, *params)

        discrepancies = [
            DiscrepancySummary(
                discrepancy_id=row["discrepancy_id"],
                rule_id=row["rule_id"],
                rule_name=row["rule_name"],
                game_id=row["game_id"],
                season_id=row["season_id"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                field_name=row["field_name"],
                source_a=row["source_a"],
                source_b=row["source_b"],
                resolution_status=row["resolution_status"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

        return DiscrepanciesResponse(
            discrepancies=discrepancies,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    async def get_discrepancy(
        self,
        db: DatabaseService,
        discrepancy_id: int,
    ) -> DiscrepancyDetail:
        """Get detailed discrepancy with source values."""
        query = """
            SELECT
                d.discrepancy_id, d.rule_id, r.name as rule_name,
                d.game_id, d.season_id, d.entity_type, d.entity_id,
                d.field_name, d.source_a, d.source_a_value,
                d.source_b, d.source_b_value,
                d.resolution_status, d.resolution_notes,
                d.created_at, d.resolved_at, d.result_id
            FROM discrepancies d
            JOIN validation_rules r ON r.rule_id = d.rule_id
            WHERE d.discrepancy_id = $1
        """
        row = await db.fetchrow(query, discrepancy_id)

        if not row:
            raise ValueError(f"Discrepancy {discrepancy_id} not found")

        return DiscrepancyDetail(
            discrepancy_id=row["discrepancy_id"],
            rule_id=row["rule_id"],
            rule_name=row["rule_name"],
            game_id=row["game_id"],
            season_id=row["season_id"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            field_name=row["field_name"],
            source_a=row["source_a"],
            source_a_value=row["source_a_value"],
            source_b=row["source_b"],
            source_b_value=row["source_b_value"],
            resolution_status=row["resolution_status"],
            resolution_notes=row["resolution_notes"],
            created_at=row["created_at"],
            resolved_at=row["resolved_at"],
            result_id=row["result_id"],
        )
