import curses

GREEN      = 1
RED        = 2
YELLOW     = 3
CYAN       = 4
WHITE      = 5
DIM        = 6
BOLD_GREEN = 7
BTN_BG     = 8
BTN_RED    = 9

# Active theme: 'green' | 'amber' | 'cyan' | 'mono'
_THEME = ['green']

THEMES = {
    'green': {
        'primary': curses.COLOR_GREEN,
        'accent':  curses.COLOR_CYAN,
        'warn':    curses.COLOR_YELLOW,
        'danger':  curses.COLOR_RED,
        'dim_n':   8,
    },
    'amber': {
        'primary': curses.COLOR_YELLOW,
        'accent':  curses.COLOR_RED,
        'warn':    curses.COLOR_YELLOW,
        'danger':  curses.COLOR_RED,
        'dim_n':   8,
    },
    'cyan': {
        'primary': curses.COLOR_CYAN,
        'accent':  curses.COLOR_MAGENTA,
        'warn':    curses.COLOR_YELLOW,
        'danger':  curses.COLOR_RED,
        'dim_n':   8,
    },
    'mono': {
        'primary': curses.COLOR_WHITE,
        'accent':  curses.COLOR_WHITE,
        'warn':    curses.COLOR_WHITE,
        'danger':  curses.COLOR_RED,
        'dim_n':   8,
    },
}

def set_theme(name):
    _THEME[0] = name if name in THEMES else 'green'
    _reinit()

def get_theme():
    return _THEME[0]

def _reinit():
    try:
        t = THEMES[_THEME[0]]
        curses.init_pair(GREEN,      t['primary'],  -1)
        curses.init_pair(RED,        t['danger'],   -1)
        curses.init_pair(YELLOW,     t['warn'],     -1)
        curses.init_pair(CYAN,       t['accent'],   -1)
        curses.init_pair(WHITE,      curses.COLOR_WHITE, -1)
        curses.init_pair(DIM,        t['dim_n'],    -1)
        curses.init_pair(BOLD_GREEN, t['primary'],  -1)
        curses.init_pair(BTN_BG,     curses.COLOR_BLACK, t['primary'])
        curses.init_pair(BTN_RED,    curses.COLOR_BLACK, t['danger'])
    except Exception:
        pass

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    _reinit()

def cg(n):
    return curses.color_pair(n)
