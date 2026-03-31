// ─── Draw helpers ─────────────────────────────────────────────────────────────
function drawFloor() {
    const vw = canvas.width / dbg.zoom, vh = canvas.height / dbg.zoom;
    const x0 = Math.floor(camera.x / TILE_SIZE) - 1, x1 = Math.ceil((camera.x + vw) / TILE_SIZE) + 1;
    const y0 = Math.floor(camera.y / TILE_SIZE) - 1, y1 = Math.ceil((camera.y + vh) / TILE_SIZE) + 1;
    for (let tx = x0; tx <= x1; tx++) {
        for (let ty = y0; ty <= y1; ty++) {
            const wx = tx * TILE_SIZE, wy = ty * TILE_SIZE;
            const h  = Math.abs((tx * 73856093) ^ (ty * 19349663)) % 1000;
            const v  = 20 + Math.floor(h / 1000 * 16);
            ctx.fillStyle = `rgb(${v+3},${v+1},${v+6})`;
            ctx.fillRect(wx, wy, TILE_SIZE, TILE_SIZE);
            ctx.fillStyle = 'rgba(0,0,0,0.38)';
            ctx.fillRect(wx, wy, TILE_SIZE, 2);
            ctx.fillRect(wx, wy, 2, TILE_SIZE);
            if (h < 60) { ctx.fillStyle = 'rgba(255,255,255,0.03)'; ctx.fillRect(wx+3, wy+3, TILE_SIZE-6, TILE_SIZE-6); }
        }
    }
}

function drawHeart(x, y, sz, color) {
    ctx.save(); ctx.translate(x, y);
    ctx.beginPath();
    ctx.moveTo(0, sz * 0.3);
    ctx.bezierCurveTo(-sz * 0.5, -sz * 0.3, -sz, sz * 0.1, 0, sz);
    ctx.bezierCurveTo( sz, sz * 0.1,  sz * 0.5, -sz * 0.3, 0, sz * 0.3);
    ctx.fillStyle = color; ctx.fill(); ctx.restore();
}

function roundRect(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x+r, y); ctx.lineTo(x+w-r, y); ctx.quadraticCurveTo(x+w, y, x+w, y+r);
    ctx.lineTo(x+w, y+h-r); ctx.quadraticCurveTo(x+w, y+h, x+w-r, y+h);
    ctx.lineTo(x+r, y+h); ctx.quadraticCurveTo(x, y+h, x, y+h-r);
    ctx.lineTo(x, y+r); ctx.quadraticCurveTo(x, y, x+r, y);
    ctx.closePath();
}

function dimScreen(alpha = 0.72) {
    ctx.fillStyle = `rgba(0,0,0,${alpha})`;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
}

function drawMenuEnemies() {
    ctx.globalAlpha = 0.3;
    for (const e of menuEnemies) {
        const et = ENEMY_TYPES[e.type];
        ctx.beginPath(); ctx.arc(e.x, e.y, e.radius, 0, Math.PI * 2);
        ctx.fillStyle = et.color; ctx.shadowBlur = 8; ctx.shadowColor = et.glow;
        ctx.fill(); ctx.shadowBlur = 0;
    }
    ctx.globalAlpha = 1;
}

function drawPlayerPreview() {
    ctx.globalAlpha = 0.4;
    drawEyePlayer(canvas.width / 2, canvas.height / 2, frameCount * 0.01, false, '#4fc3f7');
    ctx.globalAlpha = 1;
}

function drawEyePlayer(x, y, angle, showBarrel, baseColor) {
    const R = 18;
    ctx.beginPath(); ctx.arc(x, y, R, 0, Math.PI * 2);
    ctx.shadowBlur = 14; ctx.shadowColor = baseColor;
    ctx.strokeStyle = baseColor; ctx.lineWidth = 1.5; ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.beginPath(); ctx.arc(x, y, R, 0, Math.PI * 2);
    ctx.fillStyle = '#ffffff'; ctx.fill();
    ctx.beginPath(); ctx.arc(x, y, 10, 0, Math.PI * 2);
    ctx.fillStyle = baseColor; ctx.fill();
    const px = x + Math.cos(angle) * 3;
    const py = y + Math.sin(angle) * 3;
    ctx.beginPath(); ctx.arc(px, py, 5.5, 0, Math.PI * 2);
    ctx.fillStyle = '#050510'; ctx.fill();
    ctx.beginPath(); ctx.arc(px + 2, py - 2, 1.8, 0, Math.PI * 2);
    ctx.fillStyle = '#ffffff'; ctx.fill();
    if (showBarrel) {
        const bx = x + Math.cos(angle) * R;
        const by = y + Math.sin(angle) * R;
        ctx.save();
        ctx.translate(bx, by); ctx.rotate(angle);
        ctx.beginPath(); ctx.roundRect(0, -1.5, 8, 3, 1.5);
        ctx.fillStyle = baseColor; ctx.fill();
        ctx.restore();
    }
}

// ─── Draw sections ────────────────────────────────────────────────────────────
function drawWorld() {
    ctx.save();
    ctx.scale(dbg.zoom, dbg.zoom);
    ctx.translate(-camera.x, -camera.y);

    drawFloor();

    // Bullets
    for (const b of bullets) {
        ctx.beginPath(); ctx.arc(b.x, b.y, b.radius, 0, Math.PI * 2);
        ctx.fillStyle = '#ffe066'; ctx.shadowBlur = 10; ctx.shadowColor = '#ffe066';
        ctx.fill(); ctx.shadowBlur = 0;
    }

    // Enemies
    for (const e of enemies) {
        const et = ENEMY_TYPES[e.type] || ENEMY_TYPES.normal;
        ctx.beginPath(); ctx.arc(e.x, e.y, e.radius, 0, Math.PI * 2);
        ctx.fillStyle = et.color; ctx.shadowBlur = 12; ctx.shadowColor = et.glow;
        ctx.fill(); ctx.shadowBlur = 0;
        const es = e.radius / 14;
        ctx.fillStyle = '#fff';
        ctx.beginPath(); ctx.arc(e.x-4*es, e.y-3*es, 3*es, 0, Math.PI*2); ctx.arc(e.x+4*es, e.y-3*es, 3*es, 0, Math.PI*2); ctx.fill();
        ctx.fillStyle = '#000';
        ctx.beginPath(); ctx.arc(e.x-4*es, e.y-3*es, 1.5*es, 0, Math.PI*2); ctx.arc(e.x+4*es, e.y-3*es, 1.5*es, 0, Math.PI*2); ctx.fill();
        if (e.type === 'tank') {
            const bw = e.radius * 2.2, bh = 4;
            const bx = e.x - bw/2, by = e.y + e.radius + 4;
            ctx.fillStyle = '#333'; ctx.fillRect(bx, by, bw, bh);
            ctx.fillStyle = '#a855f7'; ctx.fillRect(bx, by, bw * Math.max(0, e.hp / ENEMY_TYPES.tank.hp), bh);
        }
        if (e.hitFlash > 0) {
            ctx.globalAlpha = (e.hitFlash / 8) * 0.75;
            ctx.beginPath(); ctx.arc(e.x, e.y, e.radius, 0, Math.PI * 2);
            ctx.fillStyle = '#ffffff'; ctx.fill();
            ctx.globalAlpha = 1;
        }
    }

    // Shields
    for (let i = 0; i < player.shields; i++) {
        const ang = player.shieldAngle + (i / player.shields) * Math.PI * 2;
        const sx  = player.x + Math.cos(ang) * SHIELD_ORBIT_R;
        const sy  = player.y + Math.sin(ang) * SHIELD_ORBIT_R;
        ctx.beginPath(); ctx.arc(sx, sy, SHIELD_R, 0, Math.PI * 2);
        ctx.fillStyle = '#44aaff'; ctx.shadowBlur = 12; ctx.shadowColor = '#4af';
        ctx.fill(); ctx.shadowBlur = 0;
    }

    // Player
    const blink = player.invincible > 0 && !dbg.godMode && Math.floor(player.invincible / 5) % 2 === 0;
    ctx.globalAlpha = blink ? 0.3 : 1;
    drawEyePlayer(player.x, player.y, player.angle, true, dbg.godMode ? '#ffd700' : '#4fc3f7');
    ctx.globalAlpha = 1;

    ctx.restore();
}

function drawHUD() {
    ctx.fillStyle = '#fff'; ctx.textAlign = 'left';
    ctx.font = 'bold 20px monospace';
    ctx.fillText('SCORE: ' + score, 14, 30);
    if (dbg.godMode) { ctx.fillStyle = '#ffd700'; ctx.font = 'bold 12px monospace'; ctx.fillText('GOD MODE', 14, 48); }

    for (let i = 0; i < player.maxHearts; i++)
        drawHeart(20 + i * 26, 50, 9, i < lives ? '#ff4444' : '#2a2a2a');
    for (let i = 0; i < player.darkHearts; i++) {
        if (player.darkHearts === 3) {
            ctx.shadowBlur = 6 * (0.5 + 0.5 * Math.abs(Math.sin(frameCount * 0.1)));
            ctx.shadowColor = '#8844dd';
        }
        drawHeart(20 + (player.maxHearts + i) * 26, 50, 9, '#8844dd');
        ctx.shadowBlur = 0;
    }

    if (paused) {
        ctx.fillStyle = 'rgba(255,255,255,0.6)'; ctx.textAlign = 'center';
        ctx.font = 'bold 16px monospace';
        ctx.fillText('PAUSED', canvas.width / 2, 24);
    }

    const bw = Math.min(280, canvas.width * 0.55), bh = 13;
    const bx = (canvas.width - bw) / 2, by = canvas.height - 28;
    ctx.fillStyle = 'rgba(0,0,0,0.5)'; ctx.fillRect(bx-1, by-1, bw+2, bh+2);
    ctx.fillStyle = '#111';             ctx.fillRect(bx, by, bw, bh);
    const grad = ctx.createLinearGradient(bx, 0, bx+bw, 0);
    grad.addColorStop(0, '#7b2fff'); grad.addColorStop(1, '#c084fc');
    ctx.fillStyle = grad; ctx.fillRect(bx, by, bw * Math.min(xp / xpToNext, 1), bh);
    ctx.strokeStyle = 'rgba(255,255,255,0.15)'; ctx.lineWidth = 1; ctx.strokeRect(bx, by, bw, bh);
    ctx.fillStyle = '#bbb'; ctx.font = '11px monospace'; ctx.textAlign = 'center';
    ctx.fillText(`LVL ${level}  ${xp} / ${xpToNext} XP`, canvas.width / 2, by - 4);

    const jb = joy.active ? { x: joy.sx, y: joy.sy } : { x: 80, y: canvas.height - 80 };
    ctx.beginPath(); ctx.arc(jb.x, jb.y, JOY_R, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(255,255,255,0.15)'; ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.04)'; ctx.fill();
    ctx.beginPath(); ctx.arc(jb.x + joy.dx, jb.y + joy.dy, 24, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.25)'; ctx.fill();

    if (settings.aimMode !== 'manual') {
        const ajb = aimJoy.active ? { x: aimJoy.sx, y: aimJoy.sy } : { x: canvas.width - 80, y: canvas.height - 80 };
        ctx.beginPath(); ctx.arc(ajb.x, ajb.y, JOY_R, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(255,200,0,0.2)'; ctx.lineWidth = 2; ctx.stroke();
        ctx.fillStyle = 'rgba(255,200,0,0.04)'; ctx.fill();
        ctx.beginPath(); ctx.arc(ajb.x + aimJoy.dx, ajb.y + aimJoy.dy, 24, 0, Math.PI * 2);
        ctx.fillStyle = aimJoy.active ? 'rgba(255,200,0,0.35)' : 'rgba(255,200,0,0.1)'; ctx.fill();
    }
}

function drawStartScreen() {
    ctx.save(); ctx.scale(dbg.zoom, dbg.zoom); drawFloor(); ctx.restore();
    drawMenuEnemies();
    dimScreen(0.65);
    drawPlayerPreview();

    const logoY = canvas.height * 0.32;
    ctx.font = 'bold 80px monospace';
    ctx.shadowBlur = 20; ctx.shadowColor = '#44aaff';
    ctx.fillStyle = '#4fc3f7'; ctx.textAlign = 'left';
    const fullW = ctx.measureText('ZERO').width;
    const zerW  = ctx.measureText('ZER').width;
    const oW    = ctx.measureText('O').width;
    const logoX = canvas.width / 2 - fullW / 2;
    ctx.fillText('ZER', logoX, logoY);
    const pulse = 1 + 0.05 * Math.sin(frameCount * 0.05);
    ctx.save();
    ctx.translate(logoX + zerW + oW / 2, logoY - 28);
    ctx.scale(pulse, pulse);
    ctx.fillText('O', -oW / 2, 28);
    ctx.restore();
    ctx.shadowBlur = 0;

    const btnPulse = 0.4 + 0.6 * (0.5 + 0.5 * Math.sin(frameCount * Math.PI * 2 / 90));
    ctx.globalAlpha = btnPulse;
    const bw = Math.min(260, canvas.width - 48), bh = 52;
    const bx = (canvas.width - bw) / 2, by = canvas.height * 0.62 - bh / 2;
    roundRect(bx, by, bw, bh, 10);
    ctx.fillStyle = 'rgba(0,80,160,0.2)'; ctx.fill();
    ctx.strokeStyle = '#44aaff'; ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = '#4fc3f7'; ctx.font = 'bold 18px monospace'; ctx.textAlign = 'center';
    ctx.fillText('TAP TO START', canvas.width / 2, by + bh / 2 + 6);
    ctx.globalAlpha = 1;

    const gx = canvas.width - 42, gy = canvas.height - 42;
    ctx.beginPath(); ctx.arc(gx, gy, 18, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(60,60,80,0.85)'; ctx.fill();
    ctx.strokeStyle = '#555'; ctx.lineWidth = 1; ctx.stroke();
    ctx.fillStyle = '#aaa'; ctx.font = '17px monospace'; ctx.textAlign = 'center';
    ctx.fillText('⚙', gx, gy + 6);
}

function drawSettingsScreen() {
    ctx.save(); ctx.scale(dbg.zoom, dbg.zoom); drawFloor(); ctx.restore();
    drawMenuEnemies();
    dimScreen(0.82);

    const { panelX, panelY, panelW, panelH } = settingsLayout();
    roundRect(panelX, panelY, panelW, panelH, 12);
    ctx.fillStyle = 'rgba(8,8,20,0.97)'; ctx.fill();
    ctx.strokeStyle = '#444'; ctx.lineWidth = 1; ctx.stroke();

    ctx.fillStyle = '#4fc3f7'; ctx.font = 'bold 20px monospace'; ctx.textAlign = 'center';
    ctx.fillText('SETTINGS', canvas.width / 2, panelY + 36);
    ctx.strokeStyle = '#333'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(panelX + 16, panelY + 50); ctx.lineTo(panelX + panelW - 16, panelY + 50); ctx.stroke();

    const bw = 90, bh = 34, tx = panelX + panelW - bw - 16;
    const toggles = [
        { label: 'AIMING',    val: settings.aimMode === 'auto' ? 'AUTO' : 'MANUAL', active: settings.aimMode === 'auto',  y: panelY + 80  },
        { label: 'AUTO FIRE', val: settings.autoFireEnabled ? 'ON' : 'OFF',          active: settings.autoFireEnabled,    y: panelY + 140 },
    ];
    for (const tog of toggles) {
        ctx.fillStyle = '#ccc'; ctx.font = '14px monospace'; ctx.textAlign = 'left';
        ctx.fillText(tog.label, panelX + 16, tog.y + bh / 2 + 5);
        roundRect(tx, tog.y, bw, bh, 6);
        ctx.fillStyle = tog.active ? '#44aaff' : 'rgba(0,0,0,0)'; ctx.fill();
        ctx.strokeStyle = '#44aaff'; ctx.lineWidth = 2; ctx.stroke();
        ctx.fillStyle = tog.active ? '#001020' : '#44aaff';
        ctx.font = 'bold 13px monospace'; ctx.textAlign = 'center';
        ctx.fillText(tog.val, tx + bw / 2, tog.y + bh / 2 + 5);
    }

    const backW = 120, backH = 36, backX = (canvas.width - backW) / 2, backY = panelY + panelH - 55;
    roundRect(backX, backY, backW, backH, 6);
    ctx.fillStyle = 'rgba(60,60,80,0.8)'; ctx.fill();
    ctx.strokeStyle = '#555'; ctx.lineWidth = 1; ctx.stroke();
    ctx.fillStyle = '#aaa'; ctx.font = 'bold 13px monospace'; ctx.textAlign = 'center';
    ctx.fillText('← BACK', canvas.width / 2, backY + backH / 2 + 5);
}

function drawLevelUpOverlay() {
    dimScreen();
    ctx.textAlign = 'center';
    ctx.fillStyle = '#c084fc'; ctx.font = 'bold 30px monospace';
    ctx.fillText('LEVEL UP!', canvas.width / 2, canvas.height / 2 - 145);
    ctx.fillStyle = '#888'; ctx.font = '15px monospace';
    ctx.fillText('Tap to choose an upgrade', canvas.width / 2, canvas.height / 2 - 115);
    for (const [i, upg] of upgradeChoices.entries()) {
        const c = cardRects()[i];
        roundRect(c.x, c.y, c.w, c.h, 10);
        ctx.fillStyle = 'rgba(25,15,45,0.97)'; ctx.fill();
        ctx.strokeStyle = '#7b2fff'; ctx.lineWidth = 2; ctx.stroke();
        ctx.fillStyle = '#ddb8ff'; ctx.font = 'bold 15px monospace'; ctx.textAlign = 'center';
        ctx.fillText(upg.name, c.x + c.w / 2, c.y + 38);
        ctx.fillStyle = '#888'; ctx.font = '12px monospace';
        upg.desc.split('\n').forEach((line, li) => ctx.fillText(line, c.x + c.w / 2, c.y + 66 + li * 18));
    }
}

function drawGameOverOverlay() {
    dimScreen(0.75);
    ctx.textAlign = 'center';
    ctx.fillStyle = '#ff4444'; ctx.font = 'bold 44px monospace';
    ctx.fillText('GAME OVER', canvas.width / 2, canvas.height / 2 - 48);
    ctx.fillStyle = '#fff'; ctx.font = '26px monospace';
    ctx.fillText('Score: ' + score, canvas.width / 2, canvas.height / 2 + 8);
    ctx.fillStyle = '#aaa'; ctx.font = '18px monospace';
    ctx.fillText('Reached level ' + level, canvas.width / 2, canvas.height / 2 + 38);
    const btns = deathBtnRects();
    const labels = ['PLAY AGAIN', 'MAIN MENU'];
    for (let i = 0; i < btns.length; i++) {
        const b = btns[i];
        roundRect(b.x, b.y, b.w, b.h, 8);
        ctx.fillStyle = i === 0 ? 'rgba(0,80,160,0.4)' : 'rgba(60,20,20,0.4)'; ctx.fill();
        ctx.strokeStyle = i === 0 ? '#44aaff' : '#ff4444'; ctx.lineWidth = 2; ctx.stroke();
        ctx.fillStyle = i === 0 ? '#4fc3f7' : '#ff6666';
        ctx.font = 'bold 14px monospace'; ctx.textAlign = 'center';
        ctx.fillText(labels[i], b.x + b.w / 2, b.y + b.h / 2 + 5);
    }
}

// ─── Main draw ────────────────────────────────────────────────────────────────
function draw() {
    ctx.fillStyle = '#0a0a0f';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    if (state === STATES.START)    { drawStartScreen(); return; }
    if (state === STATES.SETTINGS) { drawSettingsScreen(); return; }
    drawWorld();
    drawHUD();
    if (state === STATES.LEVELUP) drawLevelUpOverlay();
    if (state === STATES.DEAD)    drawGameOverOverlay();
}

// ─── Loop ─────────────────────────────────────────────────────────────────────
const enemyCountEl = document.getElementById('enemy-count');
function updateMenuEnemies() {
    for (const e of menuEnemies) {
        e.x += e.vx; e.y += e.vy;
        if (e.x < e.radius || e.x > canvas.width - e.radius)  { e.vx *= -1; e.x = clamp(e.x, e.radius, canvas.width - e.radius); }
        if (e.y < e.radius || e.y > canvas.height - e.radius) { e.vy *= -1; e.y = clamp(e.y, e.radius, canvas.height - e.radius); }
    }
}
function loop() {
    frameCount++;
    if (state === STATES.START || state === STATES.SETTINGS) updateMenuEnemies();
    update(); draw();
    if (debugPanel.style.display !== 'none') enemyCountEl.textContent = enemies ? enemies.length : 0;
    requestAnimationFrame(loop);
}
initMenuEnemies();
loop();
