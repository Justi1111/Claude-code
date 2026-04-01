// ─── Canvas ───────────────────────────────────────────────────────────────────
const canvas = document.getElementById('gameCanvas');
const ctx    = canvas.getContext('2d');
function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
resize();
window.addEventListener('resize', resize);

// ─── Debug panel ──────────────────────────────────────────────────────────────
const dbg = { zoom: 0.6, fireRateOverride: null, godMode: false };
let paused = false;

const debugPanel = document.getElementById('debug-panel');
document.getElementById('debug-toggle').addEventListener('click', () => {
    const opening = debugPanel.style.display === 'none';
    debugPanel.style.display = opening ? 'block' : 'none';
    if (state === STATES.PLAYING) paused = opening;
});
document.getElementById('zoom-slider').addEventListener('input', e => {
    dbg.zoom = parseFloat(e.target.value);
    document.getElementById('zoom-val').textContent = dbg.zoom.toFixed(2);
});
document.getElementById('fr-slider').addEventListener('input', e => {
    const v = parseInt(e.target.value);
    dbg.fireRateOverride = v >= 49 ? null : v;
    document.getElementById('fr-val').textContent = v >= 49 ? 'off' : v;
});
document.getElementById('godmode').addEventListener('change', e => { dbg.godMode = e.target.checked; });
document.getElementById('btn-levelup').addEventListener('click', () => {
    if (state !== STATES.PLAYING) return;
    upgradeChoices = pickUpgrades(2);
    state = STATES.LEVELUP;
});
document.getElementById('btn-wave').addEventListener('click', () => {
    if (state !== STATES.PLAYING) return;
    const count = 3 + Math.floor(score / 10);
    for (let i = 0; i < count; i++) spawnEnemy();
});
document.getElementById('btn-killall').addEventListener('click', () => {
    if (state !== STATES.PLAYING) return;
    for (const e of enemies) { score++; xp += e.xpVal; }
    enemies = [];
    if (xp >= xpToNext) { upgradeChoices = pickUpgrades(2); state = STATES.LEVELUP; }
});

// ─── Constants ────────────────────────────────────────────────────────────────
const TILE_SIZE = 64;
const STATES    = { START: 'start', PLAYING: 'playing', LEVELUP: 'levelup', DEAD: 'dead', SETTINGS: 'settings' };

const SHIELD_ORBIT_R      = 50;
const SHIELD_R            = 8;
const SHIELD_SPEED        = Math.PI / 70;
const SHIELD_DAMAGE       = 1;
const SHIELD_HIT_COOLDOWN = 30;

// ─── Advanced Settings ────────────────────────────────────────────────────────
const ADV_DEFAULTS = {
    waveInterval: 200, minInterval: 50, intervalDecay: 1, waveBaseSize: 2,
    fastFromLevel: 5, tankFromLevel: 10, fastMaxChance: 0.35, tankMaxChance: 0.15,
    normalHp: 3, normalSpdMin: 0.9, normalSpdMax: 2.25, normalXp: 10,
    fastHp: 1, fastSpdMin: 2.8, fastSpdMax: 4.0, fastXp: 15,
    tankHp: 18, tankSpdMin: 0.45, tankSpdMax: 0.75, tankXp: 40,
    playerSpeed: 4, playerRadius: 18, baseFireRate: 48, baseDamage: 1,
    invincibility: 90, startHearts: 3,
    bulletSpeed: 10, bulletLifetime: 120, bulletRadius: 5,
    xpStart: 60, xpMultiplier: 1.22,
    maxShields: 8, maxDarkHearts: 3, maxDirections: 4, maxSpread: 5, maxFocusLevels: 3,
    shieldDamage: 1, shieldCooldown: 30, shieldOrbitR: 50,
};
const ADV_ROWS = [
    { section: 'SPAWN' },
    { key: 'waveInterval',   label: 'Wave Interval',    min: 50,   max: 300,  step: 10   },
    { key: 'minInterval',    label: 'Min Interval',     min: 20,   max: 100,  step: 5    },
    { key: 'intervalDecay',  label: 'Interval Decay',   min: 1,    max: 5,    step: 1    },
    { key: 'waveBaseSize',   label: 'Wave Base Size',   min: 1,    max: 8,    step: 1    },
    { key: 'fastFromLevel',  label: 'Fast From Level',  min: 1,    max: 20,   step: 1    },
    { key: 'tankFromLevel',  label: 'Tank From Level',  min: 1,    max: 20,   step: 1    },
    { key: 'fastMaxChance',  label: 'Fast Max Chance',  min: 0.05, max: 0.6,  step: 0.05 },
    { key: 'tankMaxChance',  label: 'Tank Max Chance',  min: 0.05, max: 0.3,  step: 0.05 },
    { section: 'ENEMIES' },
    { key: 'normalHp',       label: 'Normal HP',        min: 1,    max: 20,   step: 1    },
    { key: 'normalSpdMin',   label: 'Normal Spd Min',   min: 0.3,  max: 3.0,  step: 0.1  },
    { key: 'normalSpdMax',   label: 'Normal Spd Max',   min: 0.5,  max: 5.0,  step: 0.1  },
    { key: 'normalXp',       label: 'Normal XP',        min: 1,    max: 50,   step: 1    },
    { key: 'fastHp',         label: 'Fast HP',          min: 1,    max: 10,   step: 1    },
    { key: 'fastSpdMin',     label: 'Fast Spd Min',     min: 1.0,  max: 5.0,  step: 0.1  },
    { key: 'fastSpdMax',     label: 'Fast Spd Max',     min: 1.5,  max: 8.0,  step: 0.1  },
    { key: 'fastXp',         label: 'Fast XP',          min: 1,    max: 50,   step: 1    },
    { key: 'tankHp',         label: 'Tank HP',          min: 5,    max: 50,   step: 1    },
    { key: 'tankSpdMin',     label: 'Tank Spd Min',     min: 0.1,  max: 2.0,  step: 0.05 },
    { key: 'tankSpdMax',     label: 'Tank Spd Max',     min: 0.2,  max: 3.0,  step: 0.05 },
    { key: 'tankXp',         label: 'Tank XP',          min: 5,    max: 100,  step: 5    },
    { section: 'PLAYER' },
    { key: 'playerSpeed',    label: 'Player Speed',     min: 1,    max: 10,   step: 0.5  },
    { key: 'playerRadius',   label: 'Player Radius',    min: 8,    max: 30,   step: 1    },
    { key: 'baseFireRate',   label: 'Base Fire Rate',   min: 2,    max: 60,   step: 2    },
    { key: 'baseDamage',     label: 'Base Damage',      min: 1,    max: 10,   step: 1    },
    { key: 'invincibility',  label: 'Invincibility',    min: 20,   max: 180,  step: 10   },
    { key: 'startHearts',    label: 'Start Hearts',     min: 1,    max: 5,    step: 1    },
    { section: 'BULLETS' },
    { key: 'bulletSpeed',    label: 'Bullet Speed',     min: 4,    max: 20,   step: 1    },
    { key: 'bulletLifetime', label: 'Bullet Lifetime',  min: 30,   max: 240,  step: 10   },
    { key: 'bulletRadius',   label: 'Bullet Radius',    min: 2,    max: 12,   step: 1    },
    { section: 'XP & LEVELS' },
    { key: 'xpStart',        label: 'XP Start',         min: 10,   max: 200,  step: 10   },
    { key: 'xpMultiplier',   label: 'XP Multiplier',    min: 1.05, max: 2.0,  step: 0.05 },
    { section: 'UPGRADES' },
    { key: 'maxShields',     label: 'Max Shields',      min: 1,    max: 12,   step: 1    },
    { key: 'maxDarkHearts',  label: 'Max Dark Hearts',  min: 1,    max: 5,    step: 1    },
    { key: 'maxDirections',  label: 'Max Directions',   min: 1,    max: 4,    step: 1    },
    { key: 'maxSpread',      label: 'Max Spread',       min: 1,    max: 5,    step: 2    },
    { key: 'maxFocusLevels', label: 'Max Focus Levels', min: 1,    max: 5,    step: 1    },
    { section: 'SHIELDS' },
    { key: 'shieldDamage',   label: 'Shield Damage',    min: 0.1,  max: 5,    step: 0.1  },
    { key: 'shieldCooldown', label: 'Shield Cooldown',  min: 5,    max: 60,   step: 5    },
    { key: 'shieldOrbitR',   label: 'Shield Orbit R',   min: 30,   max: 100,  step: 5    },
];
let advancedSettings = { ...ADV_DEFAULTS };
function loadAdvancedSettings() {
    try { const s = JSON.parse(localStorage.getItem('zeroAdvancedSettings')); if (s) Object.assign(advancedSettings, s); } catch(e) {}
}
function saveAdvancedSettings() { localStorage.setItem('zeroAdvancedSettings', JSON.stringify(advancedSettings)); }

// ─── Upgrades ─────────────────────────────────────────────────────────────────
const UPGRADE_POOL = [
    { id: 'firerate',    name: '+20% Fire Rate', desc: 'Shoot 20% faster' },
    { id: 'damage',      name: '+50% Damage',    desc: 'Multiply bullet damage\nby 1.5×' },
    { id: 'directions',  name: '+1 Direction',   desc: 'Add a new shoot\ndirection' },
    { id: 'spread',      name: 'Spread Shot',    desc: 'Fire extra bullets\nper direction' },
    { id: 'focus',       name: 'Focus',          desc: 'Tighten bullet spread\nfor better accuracy' },
    { id: 'heal',        name: 'Heal 1 Heart',   desc: 'Restore one lost heart' },
    { id: 'darkheart',   name: 'Dark Heart',     desc: 'Gain an extra life.\nCannot be healed.' },
    { id: 'shield',      name: 'Shield',         desc: 'Orbiting shield that\ndamages and pushes enemies' },
    { id: 'penetration', name: 'Penetration',    desc: 'Bullets pierce through\none extra enemy' },
];

function pickUpgrades(n) {
    const a = advancedSettings;
    const pool = UPGRADE_POOL.filter(u => {
        if (u.id === 'heal'       && lives >= player.maxHearts)              return false;
        if (u.id === 'darkheart'  && player.darkHearts >= a.maxDarkHearts)   return false;
        if (u.id === 'shield'     && player.shields >= a.maxShields)         return false;
        if (u.id === 'directions' && player.directions >= a.maxDirections)   return false;
        if (u.id === 'spread'     && player.spreadCount >= a.maxSpread)      return false;
        if (u.id === 'focus'      && player.focusCount >= a.maxFocusLevels)  return false;
        return true;
    });
    return [...pool].sort(() => Math.random() - 0.5).slice(0, n);
}

function applyUpgrade(upg) {
    switch (upg.id) {
        case 'firerate':    player.fireRate = Math.max(2, Math.floor(player.fireRate * 0.8)); break;
        case 'damage':      player.damage = Math.round(player.damage * 1.5 * 10) / 10; break;
        case 'directions':  if (player.directions < 4) player.directions++; break;
        case 'spread':      player.spreadCount = player.spreadCount === 1 ? 3 : 5; break;
        case 'focus':       player.spreadAngle = Math.max(4, player.spreadAngle * 0.6); player.focusCount++; break;
        case 'heal':        lives = Math.min(lives + 1, player.maxHearts); break;
        case 'darkheart':   player.darkHearts++; break;
        case 'shield':      player.shields += player.shields === 0 ? 2 : 1; break;
        case 'penetration': player.pierceCount++; break;
    }
}

// ─── Utility ──────────────────────────────────────────────────────────────────
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

function cardRects() {
    const cw = Math.min(300, canvas.width - 48);
    const ch = 120, gap = 14;
    const x  = (canvas.width - cw) / 2;
    const y0 = canvas.height / 2 - ch - gap / 2;
    return [
        { x, y: y0,            w: cw, h: ch },
        { x, y: y0 + ch + gap, w: cw, h: ch },
    ];
}

// ─── Settings ─────────────────────────────────────────────────────────────────
const settings = { aimMode: 'auto', autoFireEnabled: false };
function loadSettings() {
    try { const s = JSON.parse(localStorage.getItem('zeroSettings')); if (s) Object.assign(settings, s); } catch(e) {}
}
function saveSettings() { localStorage.setItem('zeroSettings', JSON.stringify(settings)); }
loadSettings();
loadAdvancedSettings();

// ─── Game state ───────────────────────────────────────────────────────────────
let state = STATES.START;
let frameCount = 0;
let menuEnemies = [];
let player, bullets, enemies, score, lives, spawnTimer, spawnInterval;
let camera = { x: 0, y: 0 };
let xp, level, xpToNext, upgradeChoices;
let pupilAngle = 0;
let runHistory = [];
let settingsScrollY = 0;
let settingsTouchId = null, settingsTouchStartY = 0, settingsTouchScrollStart = 0;

function initGame() {
    const a = advancedSettings;
    player = {
        x: 0, y: 0,
        radius: a.playerRadius, speed: a.playerSpeed, angle: 0,
        shootCooldown: 0, invincible: 0,
        fireRate:     a.baseFireRate,
        directions:   1,
        spreadCount:  1,
        spreadAngle:  18,
        focusCount:   0,
        damage:       a.baseDamage,
        pierceCount:  0,
        maxHearts:    a.startHearts,
        darkHearts:   0,
        shields:      0,
        shieldAngle:  0,
    };
    bullets = []; enemies = [];
    score = 0; lives = a.startHearts;
    spawnTimer = 0; spawnInterval = a.waveInterval;
    xp = 0; level = 1; xpToNext = a.xpStart;
    upgradeChoices = [];
    autoFire = settings.autoFireEnabled;
    paused = false;
    state = STATES.PLAYING;
    updateCamera();
}

function updateCamera() {
    const vw = canvas.width / dbg.zoom;
    const vh = canvas.height / dbg.zoom;
    camera.x = player.x - vw / 2;
    camera.y = player.y - vh / 2;
}

// ─── Input ────────────────────────────────────────────────────────────────────
const JOY_R  = 60;
const FIRE_R = 45;
const FIRE_BTN = () => ({ x: canvas.width - 90, y: canvas.height - 90 });

let joy     = { active: false, id: null, sx: 0, sy: 0, dx: 0, dy: 0 };
let aimJoy  = { active: false, id: null, sx: 0, sy: 0, dx: 0, dy: 0 };
let autoFire = false;

canvas.addEventListener('touchstart', e => {
    e.preventDefault();
    const t0 = e.changedTouches[0];
    if (state === STATES.START)   { handleStartTap(t0.clientX, t0.clientY); return; }
    if (state === STATES.DEAD)    { handleDeadTap(t0.clientX, t0.clientY); return; }
    if (state === STATES.LEVELUP) { handleUpgradeTap(t0.clientX, t0.clientY); return; }
    if (state === STATES.SETTINGS) {
        const { panelX, panelY, panelW, panelH, scrollTop, scrollBottom } = settingsLayout();
        const scrAbsTop = panelY + scrollTop, scrAbsBottom = panelY + scrollBottom;
        if (t0.clientY >= scrAbsTop && t0.clientY <= scrAbsBottom &&
            t0.clientX >= panelX    && t0.clientX <= panelX + panelW) {
            settingsTouchId = t0.identifier;
            settingsTouchStartY = t0.clientY;
            settingsTouchScrollStart = settingsScrollY;
        } else {
            handleSettingsTap(t0.clientX, t0.clientY);
        }
        return;
    }
    if (paused) return;
    for (const t of e.changedTouches) {
        if (t.clientX > canvas.width / 2) {
            if (!aimJoy.active) Object.assign(aimJoy, { active: true, id: t.identifier, sx: t.clientX, sy: t.clientY, dx: 0, dy: 0 });
        } else if (!joy.active) {
            Object.assign(joy, { active: true, id: t.identifier, sx: t.clientX, sy: t.clientY, dx: 0, dy: 0 });
        }
    }
}, { passive: false });

canvas.addEventListener('touchmove', e => {
    e.preventDefault();
    for (const t of e.changedTouches) {
        if (state === STATES.SETTINGS && t.identifier === settingsTouchId) {
            const { scrollTop, scrollBottom } = settingsLayout();
            const totalAdvH = ADV_ROWS.reduce((s, r) => s + (r.section ? 30 : 38), 0);
            const maxScroll = Math.max(0, totalAdvH - (scrollBottom - scrollTop));
            settingsScrollY = clamp(settingsTouchScrollStart + (settingsTouchStartY - t.clientY), 0, maxScroll);
        }
        if (t.identifier === joy.id) {
            joy.dx = t.clientX - joy.sx;
            joy.dy = t.clientY - joy.sy;
            const len = Math.hypot(joy.dx, joy.dy);
            if (len > JOY_R) { joy.dx = joy.dx / len * JOY_R; joy.dy = joy.dy / len * JOY_R; }
        }
        if (t.identifier === aimJoy.id) {
            aimJoy.dx = t.clientX - aimJoy.sx;
            aimJoy.dy = t.clientY - aimJoy.sy;
            const len = Math.hypot(aimJoy.dx, aimJoy.dy);
            if (len > JOY_R) { aimJoy.dx = aimJoy.dx / len * JOY_R; aimJoy.dy = aimJoy.dy / len * JOY_R; }
        }
    }
}, { passive: false });

canvas.addEventListener('touchend', e => {
    e.preventDefault();
    for (const t of e.changedTouches) {
        if (state === STATES.SETTINGS && t.identifier === settingsTouchId) {
            if (Math.abs(settingsTouchStartY - t.clientY) < 8) handleSettingsTap(t.clientX, t.clientY);
            settingsTouchId = null;
        }
        if (t.identifier === joy.id)    { joy.active = false; joy.dx = 0; joy.dy = 0; }
        if (t.identifier === aimJoy.id) { aimJoy.active = false; aimJoy.dx = 0; aimJoy.dy = 0; }
    }
}, { passive: false });

canvas.addEventListener('click', e => {
    if (state === STATES.START)    { handleStartTap(e.clientX, e.clientY); return; }
    if (state === STATES.DEAD)     { handleDeadTap(e.clientX, e.clientY); return; }
    if (state === STATES.SETTINGS) { handleSettingsTap(e.clientX, e.clientY); return; }
    if (state === STATES.LEVELUP)  { handleUpgradeTap(e.clientX, e.clientY); return; }
});

const keys = {};
window.addEventListener('keydown', e => {
    keys[e.key] = true;
    if (e.key === 'Enter' && state !== STATES.PLAYING) initGame();
});
window.addEventListener('keyup', e => { keys[e.key] = false; });

// ─── Tap handlers ─────────────────────────────────────────────────────────────
function handleUpgradeTap(cx, cy) {
    const cards = cardRects();
    for (let i = 0; i < cards.length; i++) {
        const c = cards[i];
        if (cx >= c.x && cx <= c.x + c.w && cy >= c.y && cy <= c.y + c.h) {
            applyUpgrade(upgradeChoices[i]);
            xp = Math.max(0, xp - xpToNext);
            level++;
            xpToNext = Math.floor(xpToNext * advancedSettings.xpMultiplier);
            state = STATES.PLAYING;
            return;
        }
    }
}

function handleStartTap(cx, cy) {
    const gx = canvas.width - 42, gy = canvas.height - 42;
    if (Math.hypot(cx - gx, cy - gy) < 26) { state = STATES.SETTINGS; return; }
    initGame();
}

function deathBtnRects() {
    const bw = 150, bh = 48, gap = 16;
    const by = canvas.height / 2 + 100;
    return [
        { x: canvas.width / 2 - bw - gap / 2, y: by, w: bw, h: bh, action: 'play' },
        { x: canvas.width / 2 + gap / 2,       y: by, w: bw, h: bh, action: 'menu' },
    ];
}

function handleDeadTap(cx, cy) {
    for (const b of deathBtnRects()) {
        if (cx >= b.x && cx <= b.x + b.w && cy >= b.y && cy <= b.y + b.h) {
            if (b.action === 'play') initGame();
            else { state = STATES.START; initMenuEnemies(); }
            return;
        }
    }
}

function settingsLayout() {
    const panelW = Math.min(340, canvas.width - 32);
    const panelH = Math.min(canvas.height - 60, 520);
    const scrollTop = 195, scrollBottom = panelH - 80;
    return { panelX: (canvas.width - panelW) / 2, panelY: (canvas.height - panelH) / 2, panelW, panelH, scrollTop, scrollBottom };
}
function saveRunHistory() {
    try { runHistory = JSON.parse(localStorage.getItem('zeroRunHistory') || '[]'); } catch(e) { runHistory = []; }
    runHistory.push(score);
    if (runHistory.length > 10) runHistory = runHistory.slice(-10);
    try { localStorage.setItem('zeroRunHistory', JSON.stringify(runHistory)); } catch(e) {}
}

function handleSettingsTap(cx, cy) {
    const { panelX, panelY, panelW, panelH, scrollTop, scrollBottom } = settingsLayout();
    const bw = 90, bh = 34, tx = panelX + panelW - bw - 16;
    if (cx >= tx && cx <= tx + bw && cy >= panelY + 80 && cy <= panelY + 80 + bh) {
        settings.aimMode = settings.aimMode === 'auto' ? 'manual' : 'auto';
        saveSettings(); return;
    }
    if (cx >= tx && cx <= tx + bw && cy >= panelY + 140 && cy <= panelY + 140 + bh) {
        settings.autoFireEnabled = !settings.autoFireEnabled;
        saveSettings(); return;
    }
    const resetW = 140, resetH = 28, resetX = panelX + (panelW - resetW) / 2, resetY = panelY + panelH - 82;
    if (cx >= resetX && cx <= resetX + resetW && cy >= resetY && cy <= resetY + resetH) {
        advancedSettings = { ...ADV_DEFAULTS }; saveAdvancedSettings(); return;
    }
    const backW = 120, backH = 34, backX = panelX + (panelW - backW) / 2, backY = panelY + panelH - 46;
    if (cx >= backX && cx <= backX + backW && cy >= backY && cy <= backY + backH) {
        state = STATES.START; settingsScrollY = 0; return;
    }
    // Advanced rows (scrollable area)
    const scrAbsTop = panelY + scrollTop, scrAbsBottom = panelY + scrollBottom;
    if (cy < scrAbsTop || cy > scrAbsBottom || cx < panelX + 4 || cx > panelX + panelW - 4) return;
    const virtualY = cy - scrAbsTop + settingsScrollY;
    let accumY = 0;
    for (const row of ADV_ROWS) {
        const rh = row.section ? 30 : 38;
        if (!row.section && virtualY >= accumY && virtualY < accumY + rh) {
            const btnW = 28, plusX = panelX + panelW - 8 - btnW, minusX = plusX - 4 - btnW;
            const btnScreenY = scrAbsTop + accumY - settingsScrollY + 6;
            if (cx >= plusX && cx <= plusX + btnW && cy >= btnScreenY && cy <= btnScreenY + 26) {
                advancedSettings[row.key] = Math.min(row.max, +((advancedSettings[row.key] + row.step).toFixed(4)));
                saveAdvancedSettings(); return;
            }
            if (cx >= minusX && cx <= minusX + btnW && cy >= btnScreenY && cy <= btnScreenY + 26) {
                advancedSettings[row.key] = Math.max(row.min, +((advancedSettings[row.key] - row.step).toFixed(4)));
                saveAdvancedSettings(); return;
            }
            break;
        }
        accumY += rh;
    }
}

// ─── Enemy types ──────────────────────────────────────────────────────────────
const ENEMY_TYPES = {
    normal: { radius: 14, speed: () => 0.9 + Math.random() * 1.35, hp: 3,  xpVal: 10, color: '#ff3333', glow: '#f00' },
    fast:   { radius: 9,  speed: () => 2.8 + Math.random() * 1.2,  hp: 1,  xpVal: 15, color: '#ff8800', glow: '#f80' },
    tank:   { radius: 22, speed: () => 0.45 + Math.random() * 0.3, hp: 18, xpVal: 40, color: '#9933cc', glow: '#a0f' },
};

function initMenuEnemies() {
    menuEnemies = ['normal','normal','fast','fast','tank','tank'].map(type => ({
        x: 60 + Math.random() * (canvas.width - 120),
        y: 60 + Math.random() * (canvas.height - 120),
        type, radius: ENEMY_TYPES[type].radius,
        vx: (Math.random() - 0.5) * 1.4,
        vy: (Math.random() - 0.5) * 1.4,
    }));
}

function spawnEnemy(type) {
    const a = advancedSettings;
    if (!type) {
        const r = Math.random();
        const fl = a.fastFromLevel, tl = a.tankFromLevel;
        const fastChance = level >= fl ? Math.min(a.fastMaxChance, (level - fl) * 0.04) : 0;
        const tankChance = level >= tl ? Math.min(a.tankMaxChance, (level - tl) * 0.03) : 0;
        if (r < tankChance) type = 'tank';
        else if (r < tankChance + fastChance) type = 'fast';
        else type = 'normal';
    }
    const t      = ENEMY_TYPES[type];
    const ang    = Math.random() * Math.PI * 2;
    const dist   = Math.max(canvas.width, canvas.height) / dbg.zoom * 0.6;
    const hp     = type === 'normal' ? a.normalHp     : type === 'fast' ? a.fastHp     : a.tankHp;
    const xpVal  = type === 'normal' ? a.normalXp     : type === 'fast' ? a.fastXp     : a.tankXp;
    const spdMin = type === 'normal' ? a.normalSpdMin : type === 'fast' ? a.fastSpdMin : a.tankSpdMin;
    const spdMax = type === 'normal' ? a.normalSpdMax : type === 'fast' ? a.fastSpdMax : a.tankSpdMax;
    enemies.push({
        x: player.x + Math.cos(ang) * dist,
        y: player.y + Math.sin(ang) * dist,
        type, radius: t.radius, speed: spdMin + Math.random() * (spdMax - spdMin),
        hp, xpVal, hitFlash: 0, shieldHitCooldown: 0,
    });
}

function shoot() {
    if (player.shootCooldown > 0) return;
    player.shootCooldown = dbg.fireRateOverride ?? player.fireRate;
    const baseAngles = [0, Math.PI, Math.PI / 2, -Math.PI / 2].slice(0, player.directions);
    for (const baseAngle of baseAngles) {
        for (let i = 0; i < player.spreadCount; i++) {
            const offset = (i - (player.spreadCount - 1) / 2) * player.spreadAngle * Math.PI / 180;
            const ang = player.angle + baseAngle + offset;
            bullets.push({
                x: player.x + Math.cos(player.angle) * player.radius,
                y: player.y + Math.sin(player.angle) * player.radius,
                dx: Math.cos(ang) * advancedSettings.bulletSpeed,
                dy: Math.sin(ang) * advancedSettings.bulletSpeed,
                radius: advancedSettings.bulletRadius, life: advancedSettings.bulletLifetime,
                pierceLeft: player.pierceCount,
                damageMult: 1.0,
                hitEnemies: new Set(),
            });
        }
    }
}

// ─── Update ───────────────────────────────────────────────────────────────────
function update() {
    if (state !== STATES.PLAYING || paused) return;

    // Player movement
    let mx = 0, my = 0;
    if (keys['ArrowUp']    || keys['w']) my -= 1;
    if (keys['ArrowDown']  || keys['s']) my += 1;
    if (keys['ArrowLeft']  || keys['a']) mx -= 1;
    if (keys['ArrowRight'] || keys['d']) mx += 1;
    if (joy.active) { mx = joy.dx / JOY_R; my = joy.dy / JOY_R; }
    const mlen = Math.hypot(mx, my);
    if (mlen > 0) {
        const effectiveSpeed = player.speed * (1 + player.darkHearts * 0.05 + (player.darkHearts === 3 ? 0.05 : 0));
        player.x += mx / mlen * effectiveSpeed;
        player.y += my / mlen * effectiveSpeed;
    }
    updateCamera();

    // Auto-aim at nearest visible enemy
    const vw = canvas.width / dbg.zoom, vh = canvas.height / dbg.zoom;
    let best = null, bestDist = Infinity;
    for (const e of enemies) {
        if (e.x < camera.x - 30 || e.x > camera.x + vw + 30) continue;
        if (e.y < camera.y - 30 || e.y > camera.y + vh + 30) continue;
        const d = Math.hypot(e.x - player.x, e.y - player.y);
        if (d < bestDist) { bestDist = d; best = e; }
    }

    // Smooth pupil tracking toward nearest enemy
    if (best) {
        const targetAngle = Math.atan2(best.y - player.y, best.x - player.x);
        let diff = targetAngle - pupilAngle;
        while (diff >  Math.PI) diff -= Math.PI * 2;
        while (diff < -Math.PI) diff += Math.PI * 2;
        pupilAngle += diff * 0.08;
    }

    // Aim & shoot
    const aimLen = Math.hypot(aimJoy.dx, aimJoy.dy);
    if (settings.aimMode === 'manual') {
        if (mlen > 0) player.angle = Math.atan2(my, mx);
    } else {
        if (aimJoy.active && aimLen > 15) player.angle = Math.atan2(aimJoy.dy, aimJoy.dx);
        else if (best) player.angle = Math.atan2(best.y - player.y, best.x - player.x);
    }
    const manualFire = settings.aimMode === 'manual' && mlen > 0;
    const autoFiring = settings.aimMode !== 'manual' && (autoFire || (aimJoy.active && aimLen > 15));
    if (keys[' '] || keys['z'] || manualFire || autoFiring) shoot();
    if (player.shootCooldown > 0) player.shootCooldown--;
    if (player.invincible > 0)    player.invincible--;
    player.shieldAngle += SHIELD_SPEED;

    // Move bullets
    bullets = bullets.filter(b => b.life > 0);
    for (const b of bullets) { b.x += b.dx; b.y += b.dy; b.life--; }

    // Spawn wave
    spawnTimer++;
    if (spawnTimer >= spawnInterval) {
        spawnTimer = 0;
        const count = advancedSettings.waveBaseSize + Math.floor(level / 4);
        for (let i = 0; i < count; i++) spawnEnemy();
        const minI = advancedSettings.minInterval;
        if (spawnInterval > minI) spawnInterval = Math.max(minI, spawnInterval - advancedSettings.intervalDecay);
    }

    // ── Screen culling ────────────────────────────────────────────────────────
    const CULL_MARGIN = 250;
    const onScreen = [], offScreen = [];
    for (const e of enemies) {
        if (e.x >= camera.x - CULL_MARGIN && e.x <= camera.x + vw + CULL_MARGIN &&
            e.y >= camera.y - CULL_MARGIN && e.y <= camera.y + vh + CULL_MARGIN) {
            onScreen.push(e);
        } else {
            offScreen.push(e);
        }
    }

    // Move all enemies toward player
    for (const e of enemies) {
        const dx = player.x - e.x, dy = player.y - e.y;
        const len = Math.hypot(dx, dy);
        e.x += dx / len * e.speed;
        e.y += dy / len * e.speed;
    }
    // Cooldown timers — onScreen only
    for (const e of onScreen) {
        if (e.hitFlash > 0)          e.hitFlash--;
        if (e.shieldHitCooldown > 0) e.shieldHitCooldown--;
    }

    // Enemy separation — spatial grid, onScreen only
    const SEP_CELL = 64;
    const sepGrid = new Map();
    for (let i = 0; i < onScreen.length; i++) {
        const e = onScreen[i];
        e._idx = i;
        const key = Math.floor(e.x / SEP_CELL) + ',' + Math.floor(e.y / SEP_CELL);
        if (!sepGrid.has(key)) sepGrid.set(key, []);
        sepGrid.get(key).push(e);
    }
    for (const e of onScreen) {
        const cx = Math.floor(e.x / SEP_CELL), cy = Math.floor(e.y / SEP_CELL);
        for (let ncx = cx - 1; ncx <= cx + 1; ncx++) {
            for (let ncy = cy - 1; ncy <= cy + 1; ncy++) {
                const cell = sepGrid.get(ncx + ',' + ncy);
                if (!cell) continue;
                for (const other of cell) {
                    if (other._idx <= e._idx) continue;
                    const dx = other.x - e.x, dy = other.y - e.y;
                    const dist = Math.hypot(dx, dy);
                    const minDist = e.radius + other.radius;
                    if (dist < minDist && dist > 0) {
                        const push = (minDist - dist) / 2;
                        const nx = dx / dist * push, ny = dy / dist * push;
                        e.x -= nx; e.y -= ny;
                        other.x += nx; other.y += ny;
                    }
                }
            }
        }
    }

    // Collision phase
    const dead = new Set();

    // Bullet ↔ enemy (onScreen only)
    for (const b of bullets) {
        if (b.life <= 0) continue;
        for (const e of onScreen) {
            if (dead.has(e) || b.hitEnemies.has(e)) continue;
            if (Math.hypot(b.x - e.x, b.y - e.y) >= b.radius + e.radius) continue;
            b.hitEnemies.add(e);
            e.hp -= Math.max(0.1, player.damage * b.damageMult);
            e.hitFlash = 8;
            if (e.hp <= 0) dead.add(e);
            if (b.pierceLeft <= 0) { b.life = 0; break; }
            else { b.pierceLeft--; b.damageMult *= 0.75; }
        }
    }

    // Shield ↔ enemy (onScreen only)
    const shieldOrbitR = advancedSettings.shieldOrbitR;
    for (let i = 0; i < player.shields; i++) {
        const ang = player.shieldAngle + (i / player.shields) * Math.PI * 2;
        const sx  = player.x + Math.cos(ang) * shieldOrbitR;
        const sy  = player.y + Math.sin(ang) * shieldOrbitR;
        for (const e of onScreen) {
            if (dead.has(e)) continue;
            const dist = Math.hypot(e.x - sx, e.y - sy);
            if (dist >= SHIELD_R + e.radius) continue;
            const pdx = e.x - player.x, pdy = e.y - player.y;
            const pdist = Math.hypot(pdx, pdy);
            if (pdist > 0) {
                const targetDist = shieldOrbitR + e.radius + SHIELD_R;
                e.x = player.x + pdx / pdist * targetDist;
                e.y = player.y + pdy / pdist * targetDist;
            }
            if (e.shieldHitCooldown <= 0) {
                e.hp -= advancedSettings.shieldDamage;
                e.hitFlash = 8;
                e.shieldHitCooldown = advancedSettings.shieldCooldown;
                if (e.hp <= 0) dead.add(e);
            }
        }
    }

    // Process kills
    let newXP = 0;
    for (const e of dead) { score++; newXP += e.xpVal; }
    enemies = enemies.filter(e => !dead.has(e));
    if (newXP > 0) {
        xp += newXP;
        if (xp >= xpToNext) { upgradeChoices = pickUpgrades(2); state = STATES.LEVELUP; }
    }

    // Player ↔ enemy (all enemies)
    if (!dbg.godMode && player.invincible === 0) {
        for (const e of enemies) {
            if (Math.hypot(player.x - e.x, player.y - e.y) >= player.radius + e.radius - 4) continue;
            if (player.darkHearts > 0) player.darkHearts--;
            else lives--;
            player.invincible = advancedSettings.invincibility;
            enemies = enemies.filter(en => en !== e);
            if (lives <= 0 && player.darkHearts <= 0) { saveRunHistory(); state = STATES.DEAD; }
            break;
        }
    }
}
