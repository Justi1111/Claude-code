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
const WORLD_W   = 4000;
const WORLD_H   = 4000;
const TILE_SIZE = 64;
const STATES    = { START: 'start', PLAYING: 'playing', LEVELUP: 'levelup', DEAD: 'dead', SETTINGS: 'settings' };

const SHIELD_ORBIT_R      = 50;
const SHIELD_R            = 8;
const SHIELD_SPEED        = Math.PI / 70;
const SHIELD_DAMAGE       = 0.25;
const SHIELD_HIT_COOLDOWN = 30;

// ─── Upgrades ─────────────────────────────────────────────────────────────────
const UPGRADE_POOL = [
    { id: 'firerate',     name: '+20% Fire Rate',  desc: 'Shoot 20% faster' },
    { id: 'damage',       name: '+0.5 Damage',     desc: 'Bullets deal 0.5 extra\ndamage per hit' },
    { id: 'multishot',    name: '+1 Projectile',   desc: 'Fire an extra bullet\nwith each shot' },
    { id: 'heal',         name: 'Heal 1 Heart',    desc: 'Restore one lost heart' },
    { id: 'darkheart',    name: 'Dark Heart',      desc: 'Gain an extra life.\nCannot be healed.' },
    { id: 'shield',       name: 'Shield',          desc: 'Orbiting shield that\ndamages and pushes enemies' },
    { id: 'penetration',  name: 'Penetration',     desc: 'Bullets pierce through\none extra enemy' },
];

function pickUpgrades(n) {
    const pool = UPGRADE_POOL.filter(u => {
        if (u.id === 'heal'      && lives >= player.maxHearts) return false;
        if (u.id === 'darkheart' && player.darkHearts >= 3)    return false;
        if (u.id === 'shield'    && player.shields >= 8)       return false;
        if (u.id === 'multishot' && player.projectiles >= 5)   return false;
        return true;
    });
    // Weight multishot down when player already has many projectiles
    const weighted = [];
    for (const u of pool) {
        const copies = (u.id === 'multishot' && player.projectiles === 4) ? 1
                     : (u.id === 'multishot' && player.projectiles === 3) ? 2
                     : 4;
        for (let i = 0; i < copies; i++) weighted.push(u);
    }
    const seen = new Set();
    const result = [];
    const shuffled = weighted.sort(() => Math.random() - 0.5);
    for (const u of shuffled) {
        if (!seen.has(u.id)) { seen.add(u.id); result.push(u); }
        if (result.length === n) break;
    }
    return result;
}

function applyUpgrade(upg) {
    switch (upg.id) {
        case 'firerate':    player.fireRate    = Math.max(2, Math.floor(player.fireRate * 0.8)); break;
        case 'damage':      player.damage += 0.5;  break;
        case 'multishot':   if (player.projectiles < 5) player.projectiles++; break;
        case 'heal':        lives = Math.min(lives + 1, player.maxHearts); break;
        case 'darkheart':   player.darkHearts++; player.speed = 4 * (1 + player.darkHearts * 0.05); break;
        case 'shield':      player.shields++;      break;
        case 'penetration': player.pierceCount++;  break;
    }
}

// ─── Utility ──────────────────────────────────────────────────────────────────
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

function bulletOffsets(n) {
    const S = 15 * Math.PI / 180;
    const offsets = [0];
    for (let i = 1; offsets.length < n; i++) {
        offsets.push(i * S);
        if (offsets.length < n) offsets.push(-i * S);
    }
    return offsets;
}

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

// ─── Game state ───────────────────────────────────────────────────────────────
let state = STATES.START;
let frameCount = 0;
let menuEnemies = [];
let player, bullets, enemies, score, lives, spawnTimer, spawnInterval;
let camera = { x: 0, y: 0 };
let xp, level, xpToNext, upgradeChoices;

function initGame() {
    player = {
        x: WORLD_W / 2, y: WORLD_H / 2,
        radius: 18, speed: 4, angle: 0,
        shootCooldown: 0, invincible: 0,
        fireRate:    48,
        projectiles: 1,
        damage:      1,
        pierceCount: 0,
        maxHearts:   3,
        darkHearts:  0,
        shields:     0,
        shieldAngle: 0,
    };
    bullets = []; enemies = [];
    score = 0; lives = 3;
    spawnTimer = 0; spawnInterval = 120;
    xp = 0; level = 1; xpToNext = 60;
    upgradeChoices = [];
    autoFire = settings.autoFireEnabled;
    paused = false;
    state = STATES.PLAYING;
    updateCamera();
}

function updateCamera() {
    const vw = canvas.width / dbg.zoom;
    const vh = canvas.height / dbg.zoom;
    camera.x = clamp(player.x - vw / 2, 0, WORLD_W - vw);
    camera.y = clamp(player.y - vh / 2, 0, WORLD_H - vh);
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
    if (state === STATES.START)    { handleStartTap(t0.clientX, t0.clientY); return; }
    if (state === STATES.DEAD)     { handleDeadTap(t0.clientX, t0.clientY); return; }
    if (state === STATES.SETTINGS) { handleSettingsTap(t0.clientX, t0.clientY); return; }
    if (state === STATES.LEVELUP)  { handleUpgradeTap(t0.clientX, t0.clientY); return; }
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
            xpToNext = Math.floor(xpToNext * 1.25);
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
    const by = canvas.height / 2 + 70;
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
    const panelW = Math.min(320, canvas.width - 48);
    const panelH = 300;
    return { panelX: (canvas.width - panelW) / 2, panelY: (canvas.height - panelH) / 2, panelW, panelH };
}

function handleSettingsTap(cx, cy) {
    const { panelX, panelY, panelW, panelH } = settingsLayout();
    const bw = 90, bh = 34, tx = panelX + panelW - bw - 16;
    if (cx >= tx && cx <= tx + bw && cy >= panelY + 80 && cy <= panelY + 80 + bh) {
        settings.aimMode = settings.aimMode === 'auto' ? 'manual' : 'auto';
        saveSettings(); return;
    }
    if (cx >= tx && cx <= tx + bw && cy >= panelY + 140 && cy <= panelY + 140 + bh) {
        settings.autoFireEnabled = !settings.autoFireEnabled;
        saveSettings(); return;
    }
    const backW = 120, backH = 36, backX = (canvas.width - backW) / 2, backY = panelY + panelH - 55;
    if (cx >= backX && cx <= backX + backW && cy >= backY && cy <= backY + backH) {
        state = STATES.START;
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
    if (!type) {
        const r = Math.random();
        const fastChance = level >= 5 ? Math.min(0.05 * (level - 4), 0.35) : 0;
        if (level >= 10 && r < 0.15) type = 'tank';
        else if (r < 0.15 + fastChance) type = 'fast';
        else type = 'normal';
    }
    const t   = ENEMY_TYPES[type];
    const ang = Math.random() * Math.PI * 2;
    const dist = Math.max(canvas.width, canvas.height) / dbg.zoom * 0.6;
    enemies.push({
        x: clamp(player.x + Math.cos(ang) * dist, 20, WORLD_W - 20),
        y: clamp(player.y + Math.sin(ang) * dist, 20, WORLD_H - 20),
        type, radius: t.radius, speed: t.speed(), hp: t.hp, xpVal: t.xpVal,
        hitFlash: 0, shieldHitCooldown: 0,
    });
}

function shoot() {
    if (player.shootCooldown > 0) return;
    player.shootCooldown = dbg.fireRateOverride ?? player.fireRate;
    for (const offset of bulletOffsets(player.projectiles)) {
        const ang = player.angle + offset;
        bullets.push({
            x: player.x + Math.cos(player.angle) * player.radius,
            y: player.y + Math.sin(player.angle) * player.radius,
            dx: Math.cos(ang) * 10,
            dy: Math.sin(ang) * 10,
            radius: 5, life: 120,
            pierceLeft: player.pierceCount,
            hitEnemies: new Set(),
        });
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
        player.x = clamp(player.x + mx / mlen * player.speed, player.radius, WORLD_W - player.radius);
        player.y = clamp(player.y + my / mlen * player.speed, player.radius, WORLD_H - player.radius);
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
        const count = 2 + Math.floor(level / 2) + (score > 20 ? 2 : 0);
        for (let i = 0; i < count; i++) spawnEnemy();
        if (spawnInterval > 30) spawnInterval = Math.max(30, spawnInterval - 2);
    }

    // Move enemies
    for (const e of enemies) {
        const dx = player.x - e.x, dy = player.y - e.y;
        const len = Math.hypot(dx, dy);
        e.x += dx / len * e.speed;
        e.y += dy / len * e.speed;
        if (e.hitFlash > 0)          e.hitFlash--;
        if (e.shieldHitCooldown > 0) e.shieldHitCooldown--;
    }

    // Enemy separation
    for (let i = 0; i < enemies.length; i++) {
        for (let j = i + 1; j < enemies.length; j++) {
            const a = enemies[i], b = enemies[j];
            const dx = b.x - a.x, dy = b.y - a.y;
            const dist = Math.hypot(dx, dy);
            const minDist = a.radius + b.radius;
            if (dist < minDist && dist > 0) {
                const push = (minDist - dist) / 2;
                const nx = dx / dist * push, ny = dy / dist * push;
                a.x -= nx; a.y -= ny;
                b.x += nx; b.y += ny;
            }
        }
    }

    // Collision phase
    const dead = new Set();

    // Bullet ↔ enemy
    for (const b of bullets) {
        if (b.life <= 0) continue;
        for (const e of enemies) {
            if (dead.has(e) || b.hitEnemies.has(e)) continue;
            if (Math.hypot(b.x - e.x, b.y - e.y) >= b.radius + e.radius) continue;
            b.hitEnemies.add(e);
            e.hp -= player.damage;
            e.hitFlash = 8;
            if (e.hp <= 0) dead.add(e);
            if (b.pierceLeft <= 0) { b.life = 0; break; }
            else b.pierceLeft--;
        }
    }

    // Shield ↔ enemy
    for (let i = 0; i < player.shields; i++) {
        const ang = player.shieldAngle + (i / player.shields) * Math.PI * 2;
        const sx  = player.x + Math.cos(ang) * SHIELD_ORBIT_R;
        const sy  = player.y + Math.sin(ang) * SHIELD_ORBIT_R;
        for (const e of enemies) {
            if (dead.has(e)) continue;
            const dist = Math.hypot(e.x - sx, e.y - sy);
            if (dist >= SHIELD_R + e.radius) continue;
            const pdx = e.x - player.x, pdy = e.y - player.y;
            const pdist = Math.hypot(pdx, pdy);
            if (pdist > 0) {
                const targetDist = SHIELD_ORBIT_R + e.radius + SHIELD_R;
                e.x = player.x + pdx / pdist * targetDist;
                e.y = player.y + pdy / pdist * targetDist;
            }
            if (e.shieldHitCooldown <= 0) {
                e.hp -= SHIELD_DAMAGE;
                e.hitFlash = 8;
                e.shieldHitCooldown = SHIELD_HIT_COOLDOWN;
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

    // Player ↔ enemy
    if (!dbg.godMode && player.invincible === 0) {
        for (const e of enemies) {
            if (Math.hypot(player.x - e.x, player.y - e.y) >= player.radius + e.radius - 4) continue;
            if (player.darkHearts > 0) player.darkHearts--;
            else lives--;
            player.invincible = 90;
            enemies = enemies.filter(en => en !== e);
            if (lives <= 0 && player.darkHearts <= 0) state = STATES.DEAD;
            break;
        }
    }
}
