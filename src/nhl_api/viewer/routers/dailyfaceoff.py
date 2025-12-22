"""DailyFaceoff data endpoints.

Provides access to DailyFaceoff lineup data including:
- Line combinations (forward lines, defense pairs, goalies)
- Power play units (PP1, PP2)
- Penalty kill units (PK1, PK2)
- Injuries (team and league-wide)
- Starting goalies for today's games
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from nhl_api.services.db import DatabaseService
from nhl_api.viewer.dependencies import get_db

# Type alias for dependency injection
DbDep = Annotated[DatabaseService, Depends(get_db)]

router = APIRouter(prefix="/dailyfaceoff", tags=["dailyfaceoff"])


# =============================================================================
# Schemas
# =============================================================================


class PlayerLineupEntry(BaseModel):
    """A player in a line combination."""

    player_name: str
    player_id: int | None
    jersey_number: int | None
    position_code: str
    injury_status: str | None = None


class ForwardLineResponse(BaseModel):
    """A forward line (3 players)."""

    line_number: int
    lw: PlayerLineupEntry | None
    c: PlayerLineupEntry | None
    rw: PlayerLineupEntry | None


class DefensePairResponse(BaseModel):
    """A defensive pair (2 players)."""

    pair_number: int
    ld: PlayerLineupEntry | None
    rd: PlayerLineupEntry | None


class GoalieDepthResponse(BaseModel):
    """Goalie depth chart."""

    starter: PlayerLineupEntry | None
    backup: PlayerLineupEntry | None


class TeamLineCombinationsResponse(BaseModel):
    """Complete line combinations for a team."""

    team_abbrev: str
    snapshot_date: date
    forward_lines: list[ForwardLineResponse]
    defense_pairs: list[DefensePairResponse]
    goalies: GoalieDepthResponse


class PowerPlayPlayerEntry(BaseModel):
    """A player in a power play unit."""

    player_name: str
    player_id: int | None
    jersey_number: int | None
    position_code: str
    df_rating: float | None
    season_goals: int | None
    season_assists: int | None
    season_points: int | None


class PowerPlayUnitResponse(BaseModel):
    """A power play unit (5 players)."""

    unit_number: int
    players: list[PowerPlayPlayerEntry]


class TeamPowerPlayResponse(BaseModel):
    """Power play units for a team."""

    team_abbrev: str
    snapshot_date: date
    pp1: PowerPlayUnitResponse | None
    pp2: PowerPlayUnitResponse | None


class PenaltyKillPlayerEntry(BaseModel):
    """A player in a penalty kill unit."""

    player_name: str
    player_id: int | None
    jersey_number: int | None
    position_type: str  # 'forward' or 'defense'


class PenaltyKillUnitResponse(BaseModel):
    """A penalty kill unit (4 players)."""

    unit_number: int
    forwards: list[PenaltyKillPlayerEntry]
    defensemen: list[PenaltyKillPlayerEntry]


class TeamPenaltyKillResponse(BaseModel):
    """Penalty kill units for a team."""

    team_abbrev: str
    snapshot_date: date
    pk1: PenaltyKillUnitResponse | None
    pk2: PenaltyKillUnitResponse | None


class InjuryEntry(BaseModel):
    """An injury record."""

    player_name: str
    player_id: int | None
    team_abbrev: str
    injury_type: str | None
    injury_status: str
    expected_return: str | None
    injury_details: str | None


class TeamInjuriesResponse(BaseModel):
    """Injuries for a specific team."""

    team_abbrev: str
    snapshot_date: date
    injuries: list[InjuryEntry]
    injury_count: int


class LeagueInjuriesResponse(BaseModel):
    """League-wide injuries grouped by team."""

    snapshot_date: date
    teams: dict[str, list[InjuryEntry]]
    total_injuries: int


class StartingGoalieEntry(BaseModel):
    """A starting goalie for today's game."""

    goalie_name: str
    goalie_id: int | None
    team_abbrev: str
    opponent_abbrev: str
    is_home: bool
    confirmation_status: str  # 'confirmed', 'likely', 'unconfirmed'
    wins: int | None
    losses: int | None
    otl: int | None
    save_pct: float | None
    gaa: float | None
    shutouts: int | None


class TodaysStartersResponse(BaseModel):
    """Starting goalies for today's games."""

    game_date: date
    starters: list[StartingGoalieEntry]
    game_count: int


# =============================================================================
# Line Combinations
# =============================================================================


@router.get(
    "/lines/{team_abbrev}",
    response_model=TeamLineCombinationsResponse,
    summary="Get Team Line Combinations",
    description="Get current line combinations for a team",
)
async def get_team_lines(
    team_abbrev: str,
    db: DbDep,
    snapshot_date: Annotated[
        date | None, Query(description="Date of snapshot (defaults to latest)")
    ] = None,
) -> TeamLineCombinationsResponse:
    """Get line combinations for a specific team."""
    team_abbrev = team_abbrev.upper()

    # Get the snapshot date to use
    if snapshot_date is None:
        snapshot_row = await db.fetchrow(
            """
            SELECT MAX(snapshot_date) as latest_date
            FROM df_line_combinations
            WHERE team_abbrev = $1
            """,
            team_abbrev,
        )
        if not snapshot_row or not snapshot_row["latest_date"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No line combinations found for team {team_abbrev}",
            )
        snapshot_date = snapshot_row["latest_date"]

    # Fetch all line entries for this team and date
    rows = await db.fetch(
        """
        SELECT player_name, player_id, jersey_number, line_type,
               unit_number, position_code, injury_status
        FROM df_line_combinations
        WHERE team_abbrev = $1 AND snapshot_date = $2
        ORDER BY line_type, unit_number, position_code
        """,
        team_abbrev,
        snapshot_date,
    )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No line combinations found for team {team_abbrev} on {snapshot_date}",
        )

    # Organize into forward lines, defense pairs, goalies
    forward_lines: dict[int, dict[str, PlayerLineupEntry]] = {}
    defense_pairs: dict[int, dict[str, PlayerLineupEntry]] = {}
    goalies: dict[int, PlayerLineupEntry] = {}

    for row in rows:
        entry = PlayerLineupEntry(
            player_name=row["player_name"],
            player_id=row["player_id"],
            jersey_number=row["jersey_number"],
            position_code=row["position_code"],
            injury_status=row["injury_status"],
        )

        if row["line_type"] == "forward":
            if row["unit_number"] not in forward_lines:
                forward_lines[row["unit_number"]] = {}
            forward_lines[row["unit_number"]][row["position_code"]] = entry
        elif row["line_type"] == "defense":
            if row["unit_number"] not in defense_pairs:
                defense_pairs[row["unit_number"]] = {}
            defense_pairs[row["unit_number"]][row["position_code"]] = entry
        elif row["line_type"] == "goalie":
            goalies[row["unit_number"]] = entry

    # Build response
    forward_lines_resp = [
        ForwardLineResponse(
            line_number=num,
            lw=players.get("lw"),
            c=players.get("c"),
            rw=players.get("rw"),
        )
        for num, players in sorted(forward_lines.items())
    ]

    defense_pairs_resp = [
        DefensePairResponse(
            pair_number=num,
            ld=players.get("ld"),
            rd=players.get("rd"),
        )
        for num, players in sorted(defense_pairs.items())
    ]

    goalie_resp = GoalieDepthResponse(
        starter=goalies.get(1),
        backup=goalies.get(2),
    )

    return TeamLineCombinationsResponse(
        team_abbrev=team_abbrev,
        snapshot_date=snapshot_date,
        forward_lines=forward_lines_resp,
        defense_pairs=defense_pairs_resp,
        goalies=goalie_resp,
    )


@router.get(
    "/lines/{team_abbrev}/history",
    response_model=list[date],
    summary="Get Line History Dates",
    description="Get available snapshot dates for a team's line combinations",
)
async def get_team_lines_history(
    team_abbrev: str,
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=90, description="Max dates to return")] = 30,
) -> list[date]:
    """Get available snapshot dates for a team's line combinations."""
    team_abbrev = team_abbrev.upper()

    rows = await db.fetch(
        """
        SELECT DISTINCT snapshot_date
        FROM df_line_combinations
        WHERE team_abbrev = $1
        ORDER BY snapshot_date DESC
        LIMIT $2
        """,
        team_abbrev,
        limit,
    )

    return [row["snapshot_date"] for row in rows]


# =============================================================================
# Power Play Units
# =============================================================================


@router.get(
    "/power-play/{team_abbrev}",
    response_model=TeamPowerPlayResponse,
    summary="Get Team Power Play Units",
    description="Get current power play units (PP1, PP2) for a team",
)
async def get_team_power_play(
    team_abbrev: str,
    db: DbDep,
    snapshot_date: Annotated[
        date | None, Query(description="Date of snapshot (defaults to latest)")
    ] = None,
) -> TeamPowerPlayResponse:
    """Get power play units for a specific team."""
    team_abbrev = team_abbrev.upper()

    # Get the snapshot date to use
    if snapshot_date is None:
        snapshot_row = await db.fetchrow(
            """
            SELECT MAX(snapshot_date) as latest_date
            FROM df_power_play_units
            WHERE team_abbrev = $1
            """,
            team_abbrev,
        )
        if not snapshot_row or not snapshot_row["latest_date"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No power play data found for team {team_abbrev}",
            )
        snapshot_date = snapshot_row["latest_date"]

    # Fetch all PP entries
    rows = await db.fetch(
        """
        SELECT unit_number, player_name, player_id, jersey_number,
               position_code, df_rating, season_goals, season_assists, season_points
        FROM df_power_play_units
        WHERE team_abbrev = $1 AND snapshot_date = $2
        ORDER BY unit_number, position_code
        """,
        team_abbrev,
        snapshot_date,
    )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No power play data found for team {team_abbrev} on {snapshot_date}",
        )

    # Group by unit
    units: dict[int, list[PowerPlayPlayerEntry]] = {1: [], 2: []}
    for row in rows:
        entry = PowerPlayPlayerEntry(
            player_name=row["player_name"],
            player_id=row["player_id"],
            jersey_number=row["jersey_number"],
            position_code=row["position_code"],
            df_rating=float(row["df_rating"]) if row["df_rating"] else None,
            season_goals=row["season_goals"],
            season_assists=row["season_assists"],
            season_points=row["season_points"],
        )
        if row["unit_number"] in units:
            units[row["unit_number"]].append(entry)

    return TeamPowerPlayResponse(
        team_abbrev=team_abbrev,
        snapshot_date=snapshot_date,
        pp1=PowerPlayUnitResponse(unit_number=1, players=units[1])
        if units[1]
        else None,
        pp2=PowerPlayUnitResponse(unit_number=2, players=units[2])
        if units[2]
        else None,
    )


# =============================================================================
# Penalty Kill Units
# =============================================================================


@router.get(
    "/penalty-kill/{team_abbrev}",
    response_model=TeamPenaltyKillResponse,
    summary="Get Team Penalty Kill Units",
    description="Get current penalty kill units (PK1, PK2) for a team",
)
async def get_team_penalty_kill(
    team_abbrev: str,
    db: DbDep,
    snapshot_date: Annotated[
        date | None, Query(description="Date of snapshot (defaults to latest)")
    ] = None,
) -> TeamPenaltyKillResponse:
    """Get penalty kill units for a specific team."""
    team_abbrev = team_abbrev.upper()

    # Get the snapshot date to use
    if snapshot_date is None:
        snapshot_row = await db.fetchrow(
            """
            SELECT MAX(snapshot_date) as latest_date
            FROM df_penalty_kill_units
            WHERE team_abbrev = $1
            """,
            team_abbrev,
        )
        if not snapshot_row or not snapshot_row["latest_date"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No penalty kill data found for team {team_abbrev}",
            )
        snapshot_date = snapshot_row["latest_date"]

    # Fetch all PK entries
    rows = await db.fetch(
        """
        SELECT unit_number, player_name, player_id, jersey_number, position_type
        FROM df_penalty_kill_units
        WHERE team_abbrev = $1 AND snapshot_date = $2
        ORDER BY unit_number, position_type
        """,
        team_abbrev,
        snapshot_date,
    )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No penalty kill data found for team {team_abbrev} on {snapshot_date}",
        )

    # Group by unit and position type
    units: dict[int, dict[str, list[PenaltyKillPlayerEntry]]] = {
        1: {"forward": [], "defense": []},
        2: {"forward": [], "defense": []},
    }
    for row in rows:
        entry = PenaltyKillPlayerEntry(
            player_name=row["player_name"],
            player_id=row["player_id"],
            jersey_number=row["jersey_number"],
            position_type=row["position_type"],
        )
        if row["unit_number"] in units:
            units[row["unit_number"]][row["position_type"]].append(entry)

    return TeamPenaltyKillResponse(
        team_abbrev=team_abbrev,
        snapshot_date=snapshot_date,
        pk1=PenaltyKillUnitResponse(
            unit_number=1,
            forwards=units[1]["forward"],
            defensemen=units[1]["defense"],
        )
        if units[1]["forward"] or units[1]["defense"]
        else None,
        pk2=PenaltyKillUnitResponse(
            unit_number=2,
            forwards=units[2]["forward"],
            defensemen=units[2]["defense"],
        )
        if units[2]["forward"] or units[2]["defense"]
        else None,
    )


# =============================================================================
# Injuries
# =============================================================================


@router.get(
    "/injuries/{team_abbrev}",
    response_model=TeamInjuriesResponse,
    summary="Get Team Injuries",
    description="Get current injuries for a specific team",
)
async def get_team_injuries(
    team_abbrev: str,
    db: DbDep,
    snapshot_date: Annotated[
        date | None, Query(description="Date of snapshot (defaults to latest)")
    ] = None,
) -> TeamInjuriesResponse:
    """Get injuries for a specific team."""
    team_abbrev = team_abbrev.upper()

    # Get the snapshot date to use
    if snapshot_date is None:
        snapshot_row = await db.fetchrow(
            """
            SELECT MAX(snapshot_date) as latest_date
            FROM df_injuries
            WHERE team_abbrev = $1
            """,
            team_abbrev,
        )
        if not snapshot_row or not snapshot_row["latest_date"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No injury data found for team {team_abbrev}",
            )
        snapshot_date = snapshot_row["latest_date"]

    rows = await db.fetch(
        """
        SELECT player_name, player_id, injury_type, injury_status,
               expected_return, injury_details
        FROM df_injuries
        WHERE team_abbrev = $1 AND snapshot_date = $2
        ORDER BY injury_status, player_name
        """,
        team_abbrev,
        snapshot_date,
    )

    injuries = [
        InjuryEntry(
            player_name=row["player_name"],
            player_id=row["player_id"],
            team_abbrev=team_abbrev,
            injury_type=row["injury_type"],
            injury_status=row["injury_status"],
            expected_return=row["expected_return"],
            injury_details=row["injury_details"],
        )
        for row in rows
    ]

    return TeamInjuriesResponse(
        team_abbrev=team_abbrev,
        snapshot_date=snapshot_date,
        injuries=injuries,
        injury_count=len(injuries),
    )


@router.get(
    "/injuries",
    response_model=LeagueInjuriesResponse,
    summary="Get League Injuries",
    description="Get current injuries for all teams",
)
async def get_league_injuries(
    db: DbDep,
    snapshot_date: Annotated[
        date | None, Query(description="Date of snapshot (defaults to latest)")
    ] = None,
    status_filter: Annotated[
        str | None,
        Query(description="Filter by status (ir, day-to-day, out, questionable)"),
    ] = None,
) -> LeagueInjuriesResponse:
    """Get injuries for all teams in the league."""
    # Get the snapshot date to use
    if snapshot_date is None:
        snapshot_row = await db.fetchrow(
            """
            SELECT MAX(snapshot_date) as latest_date
            FROM df_injuries
            """
        )
        if not snapshot_row or not snapshot_row["latest_date"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No injury data found",
            )
        snapshot_date = snapshot_row["latest_date"]

    # Build query
    query = """
        SELECT team_abbrev, player_name, player_id, injury_type, injury_status,
               expected_return, injury_details
        FROM df_injuries
        WHERE snapshot_date = $1
    """
    params: list[Any] = [snapshot_date]

    if status_filter:
        query += " AND injury_status = $2"
        params.append(status_filter.lower())

    query += " ORDER BY team_abbrev, player_name"

    rows = await db.fetch(query, *params)

    # Group by team
    teams: dict[str, list[InjuryEntry]] = {}
    for row in rows:
        team = row["team_abbrev"]
        if team not in teams:
            teams[team] = []
        teams[team].append(
            InjuryEntry(
                player_name=row["player_name"],
                player_id=row["player_id"],
                team_abbrev=team,
                injury_type=row["injury_type"],
                injury_status=row["injury_status"],
                expected_return=row["expected_return"],
                injury_details=row["injury_details"],
            )
        )

    total_injuries = sum(len(injuries) for injuries in teams.values())

    return LeagueInjuriesResponse(
        snapshot_date=snapshot_date,
        teams=teams,
        total_injuries=total_injuries,
    )


# =============================================================================
# Starting Goalies
# =============================================================================


@router.get(
    "/starting-goalies",
    response_model=TodaysStartersResponse,
    summary="Get Today's Starting Goalies",
    description="Get confirmed and expected starting goalies for today's games",
)
async def get_todays_starters(
    db: DbDep,
    game_date: Annotated[
        date | None, Query(description="Game date (defaults to today)")
    ] = None,
) -> TodaysStartersResponse:
    """Get starting goalies for today's (or specified date's) games."""
    if game_date is None:
        game_date = date.today()

    rows = await db.fetch(
        """
        SELECT goalie_name, goalie_id, team_abbrev, opponent_abbrev, is_home,
               confirmation_status, wins, losses, otl, save_pct, gaa, shutouts
        FROM df_starting_goalies
        WHERE game_date = $1
        ORDER BY game_time, team_abbrev
        """,
        game_date,
    )

    starters = [
        StartingGoalieEntry(
            goalie_name=row["goalie_name"],
            goalie_id=row["goalie_id"],
            team_abbrev=row["team_abbrev"],
            opponent_abbrev=row["opponent_abbrev"],
            is_home=row["is_home"],
            confirmation_status=row["confirmation_status"],
            wins=row["wins"],
            losses=row["losses"],
            otl=row["otl"],
            save_pct=float(row["save_pct"]) if row["save_pct"] else None,
            gaa=float(row["gaa"]) if row["gaa"] else None,
            shutouts=row["shutouts"],
        )
        for row in rows
    ]

    # Count unique games (2 goalies per game)
    game_count = len(starters) // 2

    return TodaysStartersResponse(
        game_date=game_date,
        starters=starters,
        game_count=game_count,
    )
