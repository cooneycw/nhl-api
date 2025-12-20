-- Migration: 011_seed_teams.sql
-- Description: Seed NHL teams data
-- Author: Claude Code
-- Date: 2025-12-20

-- Current 32 NHL teams with their official team IDs from NHL API
-- Note: Arizona Coyotes relocated to Utah Hockey Club for 2024-25 season

INSERT INTO teams (team_id, name, abbreviation, team_name, location_name, active)
VALUES
    (1, 'New Jersey Devils', 'NJD', 'Devils', 'New Jersey', TRUE),
    (2, 'New York Islanders', 'NYI', 'Islanders', 'New York', TRUE),
    (3, 'New York Rangers', 'NYR', 'Rangers', 'New York', TRUE),
    (4, 'Philadelphia Flyers', 'PHI', 'Flyers', 'Philadelphia', TRUE),
    (5, 'Pittsburgh Penguins', 'PIT', 'Penguins', 'Pittsburgh', TRUE),
    (6, 'Boston Bruins', 'BOS', 'Bruins', 'Boston', TRUE),
    (7, 'Buffalo Sabres', 'BUF', 'Sabres', 'Buffalo', TRUE),
    (8, 'Montreal Canadiens', 'MTL', 'Canadiens', 'Montréal', TRUE),
    (9, 'Ottawa Senators', 'OTT', 'Senators', 'Ottawa', TRUE),
    (10, 'Toronto Maple Leafs', 'TOR', 'Maple Leafs', 'Toronto', TRUE),
    (12, 'Carolina Hurricanes', 'CAR', 'Hurricanes', 'Carolina', TRUE),
    (13, 'Florida Panthers', 'FLA', 'Panthers', 'Florida', TRUE),
    (14, 'Tampa Bay Lightning', 'TBL', 'Lightning', 'Tampa Bay', TRUE),
    (15, 'Washington Capitals', 'WSH', 'Capitals', 'Washington', TRUE),
    (16, 'Chicago Blackhawks', 'CHI', 'Blackhawks', 'Chicago', TRUE),
    (17, 'Detroit Red Wings', 'DET', 'Red Wings', 'Detroit', TRUE),
    (18, 'Nashville Predators', 'NSH', 'Predators', 'Nashville', TRUE),
    (19, 'St. Louis Blues', 'STL', 'Blues', 'St. Louis', TRUE),
    (20, 'Calgary Flames', 'CGY', 'Flames', 'Calgary', TRUE),
    (21, 'Colorado Avalanche', 'COL', 'Avalanche', 'Colorado', TRUE),
    (22, 'Edmonton Oilers', 'EDM', 'Oilers', 'Edmonton', TRUE),
    (23, 'Vancouver Canucks', 'VAN', 'Canucks', 'Vancouver', TRUE),
    (24, 'Anaheim Ducks', 'ANA', 'Ducks', 'Anaheim', TRUE),
    (25, 'Dallas Stars', 'DAL', 'Stars', 'Dallas', TRUE),
    (26, 'Los Angeles Kings', 'LAK', 'Kings', 'Los Angeles', TRUE),
    (28, 'San Jose Sharks', 'SJS', 'Sharks', 'San Jose', TRUE),
    (29, 'Columbus Blue Jackets', 'CBJ', 'Blue Jackets', 'Columbus', TRUE),
    (30, 'Minnesota Wild', 'MIN', 'Wild', 'Minnesota', TRUE),
    (52, 'Winnipeg Jets', 'WPG', 'Jets', 'Winnipeg', TRUE),
    (53, 'Arizona Coyotes', 'ARI', 'Coyotes', 'Arizona', FALSE),  -- Relocated to Utah
    (54, 'Vegas Golden Knights', 'VGK', 'Golden Knights', 'Vegas', TRUE),
    (55, 'Seattle Kraken', 'SEA', 'Kraken', 'Seattle', TRUE),
    (59, 'Utah Hockey Club', 'UTA', 'Hockey Club', 'Utah', TRUE)
ON CONFLICT (team_id) DO UPDATE SET
    name = EXCLUDED.name,
    abbreviation = EXCLUDED.abbreviation,
    team_name = EXCLUDED.team_name,
    location_name = EXCLUDED.location_name,
    active = EXCLUDED.active,
    updated_at = CURRENT_TIMESTAMP;

-- Also seed seasons if not present
INSERT INTO seasons (season_id, start_year, end_year, is_current)
VALUES
    (20232024, 2023, 2024, FALSE),
    (20242025, 2024, 2025, TRUE)
ON CONFLICT (season_id) DO NOTHING;
