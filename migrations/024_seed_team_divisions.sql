-- Migration: 024_seed_team_divisions.sql
-- Description: Assign teams to their divisions and conferences
-- Author: Claude Code
-- Date: 2025-12-22
-- Issue: #223 - Teams page blank due to missing division assignments

-- Eastern Conference (conference_id = 6)
-- Atlantic Division (division_id = 15)
UPDATE teams SET division_id = 15, conference_id = 6 WHERE abbreviation IN (
    'BOS',  -- Boston Bruins
    'BUF',  -- Buffalo Sabres
    'DET',  -- Detroit Red Wings
    'FLA',  -- Florida Panthers
    'MTL',  -- Montreal Canadiens
    'OTT',  -- Ottawa Senators
    'TBL',  -- Tampa Bay Lightning
    'TOR'   -- Toronto Maple Leafs
);

-- Metropolitan Division (division_id = 17)
UPDATE teams SET division_id = 17, conference_id = 6 WHERE abbreviation IN (
    'CAR',  -- Carolina Hurricanes
    'CBJ',  -- Columbus Blue Jackets
    'NJD',  -- New Jersey Devils
    'NYI',  -- New York Islanders
    'NYR',  -- New York Rangers
    'PHI',  -- Philadelphia Flyers
    'PIT',  -- Pittsburgh Penguins
    'WSH'   -- Washington Capitals
);

-- Western Conference (conference_id = 5)
-- Central Division (division_id = 16)
UPDATE teams SET division_id = 16, conference_id = 5 WHERE abbreviation IN (
    'ARI',  -- Arizona Coyotes (historical, inactive)
    'UTA',  -- Utah Hockey Club (relocated from Arizona)
    'CHI',  -- Chicago Blackhawks
    'COL',  -- Colorado Avalanche
    'DAL',  -- Dallas Stars
    'MIN',  -- Minnesota Wild
    'NSH',  -- Nashville Predators
    'STL',  -- St. Louis Blues
    'WPG'   -- Winnipeg Jets
);

-- Pacific Division (division_id = 18)
UPDATE teams SET division_id = 18, conference_id = 5 WHERE abbreviation IN (
    'ANA',  -- Anaheim Ducks
    'CGY',  -- Calgary Flames
    'EDM',  -- Edmonton Oilers
    'LAK',  -- Los Angeles Kings
    'SEA',  -- Seattle Kraken
    'SJS',  -- San Jose Sharks
    'VAN',  -- Vancouver Canucks
    'VGK'   -- Vegas Golden Knights
);
