import pygame

# Screen
SCREEN_W = 1280
SCREEN_H = 800
MAP_W = 1280
MAP_H = 640
MAP_OFFSET_Y = 40  # below top bar
FPS = 60

# Map projection bounds (equirectangular)
MAP_LON_MIN = -180
MAP_LON_MAX = 180
MAP_LAT_MIN = -60
MAP_LAT_MAX = 85

# UI regions
TOP_BAR_RECT    = pygame.Rect(0, 0, SCREEN_W, MAP_OFFSET_Y)
MAP_RECT        = pygame.Rect(0, MAP_OFFSET_Y, MAP_W, MAP_H)
BOTTOM_BAR_RECT = pygame.Rect(0, MAP_OFFSET_Y + MAP_H, SCREEN_W, SCREEN_H - MAP_OFFSET_Y - MAP_H)

# Colors
C_BG          = (15, 20, 35)
C_OCEAN       = (30, 60, 100)
C_OCEAN_DEEP  = (20, 45, 80)
C_TERRITORY_NEUTRAL = (90, 90, 80)
C_TERRITORY_HOVER   = (200, 200, 180)
C_BORDER      = (0, 0, 0)
C_SELECTED    = (255, 220, 50)
C_TEXT        = (220, 220, 200)
C_TEXT_DARK   = (30, 30, 30)
C_PANEL       = (25, 30, 45)
C_PANEL_LIGHT = (40, 48, 65)
C_BUTTON      = (60, 80, 110)
C_BUTTON_HOV  = (80, 110, 150)
C_BUTTON_DIS  = (40, 45, 55)
C_RED         = (200, 60, 60)
C_GREEN       = (60, 180, 80)
C_GOLD        = (220, 180, 50)
C_WHITE       = (255, 255, 255)

# Player faction colors (index matches Faction enum value)
FACTION_COLORS = [
    (60,  120, 200),   # 0 USA       — blue
    (200,  50,  50),   # 1 USSR      — red
    (220, 180,  40),   # 2 China     — gold
    (50,  160,  80),   # 3 Britain   — green
    (160,  80, 200),   # 4 Germany   — purple
    (220, 120,  30),   # 5 Japan     — orange
    (120, 120, 120),   # 6 Neutral   — grey
]

FACTION_NAMES = ["USA", "USSR", "China", "Britain", "Germany", "Japan", "Neutral"]

# Game balance
STARTING_ARMIES   = 16   # armies placed in home territories at start
ARMY_COST         = 1    # income spent per new army
MIN_ATTACK_ARMIES = 2    # min armies in a territory to launch an attack (1 stays behind)
NEUTRAL_ARMIES    = 2    # base garrison in neutral territories (+income each)
VICTORY_THRESHOLD = 0.65 # fraction of territories to win

# Combat (dice-based)
ATTACKER_DICE = 3
DEFENDER_DICE = 2

# Phases
PHASE_INCOME   = "income"
PHASE_PURCHASE = "purchase"
PHASE_MOVE     = "move"
PHASE_ATTACK   = "attack"
PHASE_END      = "end"

PHASES = [PHASE_INCOME, PHASE_PURCHASE, PHASE_MOVE, PHASE_ATTACK, PHASE_END]
