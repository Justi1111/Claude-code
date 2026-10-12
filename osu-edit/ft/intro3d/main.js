// Stylized 3D intro: chibi FlyingTuna in a tuna hood. Everything is a pure function of time t
// (window.renderAt), so frames can be rendered one by one at any fps.
import * as THREE from 'three';

const W = 1920, H = 1080;
const BEAT = 60 / 189, BAR = BEAT * 4;
const qs = new URLSearchParams(location.search);
const SHOW_TEXT = qs.get('text') !== '0';

// ---------- helpers ----------
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, t) => a + (b - a) * t;
const seg = (t, a, b) => clamp((t - a) / (b - a));
const smooth = (t) => { t = clamp(t); return t * t * (3 - 2 * t); };
const easeOutCubic = (t) => 1 - Math.pow(1 - clamp(t), 3);
const easeInCubic = (t) => Math.pow(clamp(t), 3);
const easeInOut = (t) => { t = clamp(t); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
const easeOutBack = (t, s = 1.8) => { t = clamp(t); const c = s + 1; return 1 + c * Math.pow(t - 1, 3) + s * Math.pow(t - 1, 2); };
// decaying pulse after time t0
const pulse = (t, t0, len = 0.25) => (t < t0 || t > t0 + len) ? 0 : Math.pow(1 - (t - t0) / len, 2);
function mulberry(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const noise = (t, f, ph) => Math.sin(t * f + ph) * 0.6 + Math.sin(t * f * 2.31 + ph * 1.7) * 0.3 + Math.sin(t * f * 4.13 + ph * 0.3) * 0.1;

// ---------- renderer / scene ----------
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.outputColorSpace = THREE.SRGBColorSpace;
document.getElementById('wrap').prepend(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(35, W / H, 0.05, 300);

function gradTex(steps) {
  const d = new Uint8Array(steps.length * 4);
  steps.forEach((v, i) => { d[i * 4] = d[i * 4 + 1] = d[i * 4 + 2] = v; d[i * 4 + 3] = 255; });
  const t = new THREE.DataTexture(d, steps.length, 1, THREE.RGBAFormat);
  t.minFilter = t.magFilter = THREE.NearestFilter; t.generateMipmaps = false; t.needsUpdate = true;
  return t;
}
const GRAD = gradTex([120, 200, 255]);
const toon = (hex, extra = {}) => new THREE.MeshToonMaterial({ color: new THREE.Color(hex), gradientMap: GRAD, ...extra });

function outlineMat(px = 4, hex = '#15121a') {
  return new THREE.ShaderMaterial({
    uniforms: { px: { value: px }, res: { value: new THREE.Vector2(W, H) }, color: { value: new THREE.Color(hex) } },
    vertexShader: `uniform float px; uniform vec2 res;
      void main(){
        vec4 clip = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        vec3 n = normalize(normalMatrix * normal);
        vec2 d = (projectionMatrix * vec4(n, 0.0)).xy;
        float l = length(d); d = l > 1e-5 ? d / l : vec2(0.0);
        clip.xy += d * px * 2.0 / res * clip.w;
        gl_Position = clip;
      }`,
    fragmentShader: `uniform vec3 color; void main(){ gl_FragColor = vec4(color, 1.0); }`,
    side: THREE.BackSide,
  });
}

function addMesh(parent, geo, mat, o = {}) {
  const m = new THREE.Mesh(geo, mat);
  if (o.pos) m.position.set(...o.pos);
  if (o.rot) m.rotation.set(...o.rot);
  if (o.scale) m.scale.set(...o.scale);
  parent.add(m);
  if (o.outline) m.add(new THREE.Mesh(geo, outlineMat(o.outline)));
  return m;
}

function canvasTex(w, h, draw) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
  return t;
}
function radialTex(stops, size = 512) {
  return canvasTex(size, size, (g, w, h) => {
    const r = g.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2);
    for (const [o, c] of stops) r.addColorStop(o, c);
    g.fillStyle = r; g.fillRect(0, 0, w, h);
  });
}

// ---------- palette ----------
const C = {
  skin: '#fadcc9', hair: '#6a4436', hoodie: '#2c2b35', pants: '#22212a', shoe: '#ededf2',
  hood: '#5b83d3', hoodIn: '#2e4889', hoodRim: '#4b72c6', string: '#f4f4f6',
};

// ---------- environment ----------
const bg = new THREE.Mesh(new THREE.SphereGeometry(120, 48, 24), new THREE.ShaderMaterial({
  side: THREE.BackSide, depthWrite: false,
  uniforms: { top: { value: new THREE.Color('#1a2348') }, bot: { value: new THREE.Color('#06060c') }, k: { value: 0 } },
  vertexShader: 'varying vec3 vP; void main(){ vP = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `uniform vec3 top; uniform vec3 bot; uniform float k; varying vec3 vP;
    void main(){ float h = vP.y * 0.5 + 0.5; vec3 c = mix(bot, top, smoothstep(0.42, 0.9, h)) * k; gl_FragColor = vec4(c, 1.0);
    #include <colorspace_fragment>
    }`,
}));
scene.add(bg);

const glowTex = radialTex([[0, 'rgba(255,255,255,1)'], [0.35, 'rgba(255,255,255,0.35)'], [1, 'rgba(255,255,255,0)']]);
const glowPink = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: '#ff4f9e', transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, opacity: 0 }));
glowPink.position.set(-1.3, 1.9, -3.5); glowPink.scale.set(7, 7, 1); scene.add(glowPink);
const glowBlue = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: '#3f7dff', transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, opacity: 0 }));
glowBlue.position.set(1.6, 1.2, -3.2); glowBlue.scale.set(7.5, 7.5, 1); scene.add(glowBlue);

const floorTex = radialTex([[0, 'rgba(70,90,160,0.55)'], [0.45, 'rgba(40,50,100,0.25)'], [1, 'rgba(10,10,20,0)']]);
const floor = new THREE.Mesh(new THREE.CircleGeometry(6, 64), new THREE.MeshBasicMaterial({ map: floorTex, transparent: true, depthWrite: false, opacity: 0 }));
floor.rotation.x = -Math.PI / 2; scene.add(floor);
const poolTex = radialTex([[0, 'rgba(190,210,255,0.9)'], [0.5, 'rgba(150,170,255,0.35)'], [1, 'rgba(120,140,255,0)']]);
const pool = new THREE.Mesh(new THREE.CircleGeometry(1.7, 64), new THREE.MeshBasicMaterial({ map: poolTex, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, opacity: 0 }));
pool.rotation.x = -Math.PI / 2; pool.position.y = 0.003; scene.add(pool);
const shadowTex = radialTex([[0, 'rgba(0,0,0,0.75)'], [0.6, 'rgba(0,0,0,0.35)'], [1, 'rgba(0,0,0,0)']]);
const shadow = new THREE.Mesh(new THREE.CircleGeometry(0.75, 48), new THREE.MeshBasicMaterial({ map: shadowTex, transparent: true, depthWrite: false }));
shadow.rotation.x = -Math.PI / 2; shadow.position.y = 0.006; scene.add(shadow);

const coneMat = new THREE.ShaderMaterial({
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.BackSide,
  uniforms: { k: { value: 0 }, col: { value: new THREE.Color('#9db5ff') } },
  vertexShader: 'varying float vY; varying vec3 vN; varying vec3 vV; void main(){ vY = position.y; vec4 mv = modelViewMatrix * vec4(position,1.0); vN = normalize(normalMatrix*normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }',
  fragmentShader: `uniform float k; uniform vec3 col; varying float vY; varying vec3 vN; varying vec3 vV;
    void main(){ float f = smoothstep(2.6, -2.6, vY); float edge = pow(abs(dot(vN, vV)), 1.5);
    gl_FragColor = vec4(col * f * (0.35 + 0.65 * edge) * 0.2 * k, 1.0);
    #include <colorspace_fragment>
    }`,
});
const cone = new THREE.Mesh(new THREE.ConeGeometry(1.75, 5.2, 48, 1, true), coneMat);
cone.position.set(0, 2.6, 0); scene.add(cone);

const hemi = new THREE.HemisphereLight('#d7defc', '#2a2134', 0);
scene.add(hemi);
const key = new THREE.DirectionalLight('#ffffff', 0);
key.position.set(-3, 5, 6); scene.add(key);
const rimL = new THREE.DirectionalLight('#ff6fb0', 0);
rimL.position.set(4, 3, -4); scene.add(rimL);
const rimB = new THREE.DirectionalLight('#5f8dff', 0);
rimB.position.set(-4, 2.5, -3); scene.add(rimB);

// ---------- character ----------
const chibi = new THREE.Group();
scene.add(chibi);
const body = new THREE.Group(); // squash/stretch pivot at the feet
chibi.add(body);

for (const sx of [-1, 1]) {
  addMesh(body, new THREE.CapsuleGeometry(0.12, 0.2, 8, 16), toon(C.pants), { pos: [sx * 0.15, 0.3, 0], outline: 3 });
  addMesh(body, new THREE.SphereGeometry(1, 24, 16), toon(C.shoe), { pos: [sx * 0.16, 0.09, 0.07], scale: [0.15, 0.095, 0.22], outline: 3 });
}
{
  const pts = [[0.0, 0.34], [0.33, 0.36], [0.41, 0.46], [0.42, 0.6], [0.38, 0.78], [0.31, 0.93], [0.2, 1.03], [0.0, 1.07]];
  addMesh(body, new THREE.LatheGeometry(pts.map(([r, y]) => new THREE.Vector2(r, y)), 48), toon(C.hoodie), { outline: 4 });
  // kangaroo pocket
  addMesh(body, new THREE.SphereGeometry(1, 32, 16), toon('#25242d'), { pos: [0, 0.53, 0.36], scale: [0.24, 0.1, 0.06], outline: 2 });
  for (const sx of [-1, 1]) {
    addMesh(body, new THREE.CylinderGeometry(0.017, 0.017, 0.25, 8), toon(C.string), { pos: [sx * 0.075, 0.86, 0.33], rot: [-0.46, 0, sx * 0.06], outline: 2 });
    addMesh(body, new THREE.SphereGeometry(0.027, 12, 8), toon(C.string), { pos: [sx * 0.08, 0.745, 0.385], outline: 2 });
  }
}
function makeArm(side) {
  const pivot = new THREE.Group();
  pivot.position.set(side * 0.29, 0.92, 0.02);
  body.add(pivot);
  addMesh(pivot, new THREE.CapsuleGeometry(0.095, 0.24, 8, 16), toon(C.hoodie), { pos: [0, -0.19, 0], outline: 4 });
  addMesh(pivot, new THREE.SphereGeometry(0.085, 20, 14), toon(C.skin), { pos: [0, -0.39, 0.01], outline: 3 });
  return pivot;
}
const armL = makeArm(-1), armR = makeArm(1);

const head = new THREE.Group();
head.position.set(0, 1.5, 0);
body.add(head);
const headS = new THREE.Group();
headS.scale.set(1, 0.94, 0.93);
head.add(headS);
addMesh(headS, new THREE.SphereGeometry(0.62, 64, 48), toon(C.skin, { emissive: new THREE.Color('#3a2620') }), { outline: 3 });

// face decal: a front cap of a slightly bigger sphere carrying a 2D face texture
const FW = 1.9, FH = 1.6, FR = 0.626;
const FACE_U = FR * FW, FACE_V = FR * FH; // world units covered by the texture (approx.)
function faceTexture(kind) {
  return canvasTex(1024, 1024, (g) => {
    const X = (fx) => 512 + fx / FACE_U * 1024, Y = (fy) => 512 - fy / FACE_V * 1024;
    const sx = 1024 / FACE_U, sy = 1024 / FACE_V;
    const ell = (cx, cy, rx, ry) => { g.beginPath(); g.ellipse(X(cx), Y(cy), rx * sx, ry * sy, 0, 0, Math.PI * 2); };
    const line = (pts, w, col) => {
      g.beginPath(); g.moveTo(X(pts[0][0]), Y(pts[0][1]));
      for (const [a, b] of pts.slice(1)) g.lineTo(X(a), Y(b));
      g.lineWidth = w * sy; g.strokeStyle = col; g.lineCap = 'round'; g.lineJoin = 'round'; g.stroke();
    };
    // blush
    for (const s of [-1, 1]) {
      const cx = X(s * 0.3), cy = Y(-0.16);
      const r = g.createRadialGradient(cx, cy, 0, cx, cy, 0.085 * sx);
      r.addColorStop(0, 'rgba(255,120,140,0.75)'); r.addColorStop(1, 'rgba(255,120,140,0)');
      g.save(); g.translate(cx, cy); g.scale(1, 0.55); g.translate(-cx, -cy);
      g.fillStyle = r; g.beginPath(); g.arc(cx, cy, 0.085 * sx, 0, Math.PI * 2); g.fill(); g.restore();
      for (let k = -1; k <= 1; k++) line([[s * 0.3 + k * 0.028 - 0.008, -0.145], [s * 0.3 + k * 0.028 + 0.008, -0.175]], 0.007, 'rgba(230,90,110,0.8)');
    }
    const ink = '#1b1212';
    for (const s of [-1, 1]) {
      const ex = s * 0.215, ey = -0.01;
      if (kind === 'normal') {
        ell(ex, ey, 0.092, 0.128);
        const gr = g.createLinearGradient(0, Y(ey + 0.13), 0, Y(ey - 0.13));
        gr.addColorStop(0, '#24140f'); gr.addColorStop(0.55, '#4a2a1f'); gr.addColorStop(1, '#a3674a');
        g.fillStyle = gr; g.fill();
        ell(ex, ey - 0.012, 0.05, 0.07); g.fillStyle = '#140b09'; g.fill();
        // lash line
        g.beginPath(); g.ellipse(X(ex), Y(ey), 0.1 * sx, 0.136 * sy, 0, Math.PI * 1.08, Math.PI * 1.92);
        g.lineWidth = 0.03 * sy; g.strokeStyle = ink; g.lineCap = 'round'; g.stroke();
        line([[ex + s * 0.088, ey + 0.07], [ex + s * 0.125, ey + 0.1]], 0.022, ink);
        // highlights
        ell(ex - 0.03, ey + 0.045, 0.034, 0.046); g.fillStyle = '#ffffff'; g.fill();
        ell(ex + 0.035, ey - 0.062, 0.016, 0.018); g.fill();
      } else if (kind === 'blink') {
        g.beginPath(); g.ellipse(X(ex), Y(ey - 0.01), 0.085 * sx, 0.05 * sy, 0, Math.PI * 0.1, Math.PI * 0.9);
        g.lineWidth = 0.026 * sy; g.strokeStyle = ink; g.lineCap = 'round'; g.stroke();
      } else if (kind === 'happy') {
        // > <
        const o = s * 0.075;
        line([[ex - o, ey + 0.07], [ex + o, ey], [ex - o, ey - 0.07]], 0.032, ink);
      } else if (kind === 'shock') {
        ell(ex, ey, 0.105, 0.125); g.fillStyle = '#ffffff'; g.fill();
        g.lineWidth = 0.022 * sy; g.strokeStyle = ink; g.stroke();
        ell(ex, ey, 0.03, 0.036); g.fillStyle = ink; g.fill();
      }
    }
    // mouth
    if (kind === 'shock') {
      ell(0, -0.27, 0.055, 0.07); g.fillStyle = '#7d2433'; g.fill(); g.lineWidth = 0.012 * sy; g.strokeStyle = ink; g.stroke();
      ell(0, -0.31, 0.034, 0.022); g.fillStyle = '#ee7586'; g.fill();
    } else {
      const big = kind === 'happy' ? 1.35 : 1;
      const w = 0.07 * big, d = 0.075 * big, my = -0.245;
      g.beginPath();
      g.moveTo(X(-w), Y(my));
      g.quadraticCurveTo(X(0), Y(my + 0.012), X(w), Y(my));
      g.quadraticCurveTo(X(w * 0.9), Y(my - d * 1.1), X(0), Y(my - d));
      g.quadraticCurveTo(X(-w * 0.9), Y(my - d * 1.1), X(-w), Y(my));
      g.closePath(); g.fillStyle = '#7d2433'; g.fill();
      g.save(); g.clip(); ell(0, my - d * 0.95, w * 0.75, d * 0.5); g.fillStyle = '#ee7586'; g.fill(); g.restore();
      g.lineWidth = 0.012 * sy; g.strokeStyle = ink; g.stroke();
      if (kind === 'happy') { // little fang
        g.beginPath(); g.moveTo(X(-w * 0.55), Y(my + 0.003)); g.lineTo(X(-w * 0.38), Y(my - 0.03)); g.lineTo(X(-w * 0.22), Y(my + 0.003));
        g.closePath(); g.fillStyle = '#ffffff'; g.fill();
      }
    }
  });
}
const FACES = {};
const faceMat = new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false });
const face = new THREE.Mesh(new THREE.SphereGeometry(FR, 64, 48, Math.PI / 2 - FW / 2, FW, Math.PI / 2 - FH / 2, FH), faceMat);
headS.add(face);

// hair
const hairMat = toon(C.hair);
const spike = (() => {
  const pts = [];
  for (let i = 24; i >= 0; i--) { const s = i / 24; pts.push(new THREE.Vector2(Math.pow(Math.sin(Math.PI * s), 0.75), 1 - 2 * s)); }
  return new THREE.LatheGeometry(pts, 16);
})();
function strand(angle, elev, len, wid, tilt, depth = 0.085, back = -0.3) {
  const g = new THREE.Group(); g.rotation.y = angle; head.add(g);
  const r = 0.6;
  addMesh(g, spike, hairMat, { pos: [0, r * Math.sin(elev) * 0.94, r * Math.cos(elev) * 0.93 + 0.03], rot: [back, 0, tilt], scale: [wid, len, depth], outline: 3 });
}
{
  // hair cap so the gaps between bangs show hair, not skin
  const cap = new THREE.SphereGeometry(0.632, 64, 32, 0, Math.PI * 2, 0, 1.05);
  addMesh(headS, cap, hairMat, { rot: [0.32, 0, 0], outline: 0 });
}
[[-0.8, 0.4, 0.2, 0.15, 0.45], [-0.5, 0.47, 0.22, 0.16, 0.22], [-0.2, 0.5, 0.24, 0.16, 0.12], [0.08, 0.5, 0.22, 0.16, -0.14],
 [0.36, 0.49, 0.23, 0.16, -0.05], [0.6, 0.45, 0.21, 0.15, -0.3], [0.86, 0.38, 0.19, 0.14, -0.5]]
  .forEach(([a, e, l, w, t]) => strand(a, e, l, w, t, 0.1, -0.42));
strand(-1.06, 0.05, 0.3, 0.13, 0.1, 0.09, -0.08);
strand(-0.33, 0.66, 0.2, 0.15, 0.3, 0.1, -0.7);
strand(0.25, 0.68, 0.2, 0.15, -0.25, 0.1, -0.72);
strand(1.06, 0.05, 0.3, 0.13, -0.1, 0.09, -0.08);
function taperTube(curve, r0, r1, segs = 48, radial = 12) {
  const geo = new THREE.TubeGeometry(curve, segs, 1, radial, false);
  const pos = geo.attributes.position, v = new THREE.Vector3();
  for (let i = 0; i <= segs; i++) {
    const u = i / segs, c = curve.getPointAt(u), r = lerp(r0, r1, Math.pow(u, 1.3));
    for (let j = 0; j <= radial; j++) {
      const k = i * (radial + 1) + j;
      v.fromBufferAttribute(pos, k).sub(c).normalize().multiplyScalar(r).add(c);
      pos.setXYZ(k, v.x, v.y, v.z);
    }
  }
  geo.computeVertexNormals();
  return geo;
}
{
  const curve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(0.0, 0.46, 0.52), new THREE.Vector3(0.03, 0.68, 0.58), new THREE.Vector3(0.14, 0.86, 0.55),
    new THREE.Vector3(0.27, 0.86, 0.5), new THREE.Vector3(0.31, 0.76, 0.46),
  ]);
  addMesh(head, taperTube(curve, 0.055, 0.012), hairMat, { outline: 3 });
}

// hood (tuna head)
const hood = new THREE.Group();
hood.position.set(0, 0.17, -0.12);
hood.scale.set(1, 1.08, 1.04);
head.add(hood);
const HR = 0.95, TH0 = 0.7;
{
  const shell = new THREE.SphereGeometry(HR, 64, 48, 0, Math.PI * 2, TH0, Math.PI - TH0);
  shell.rotateX(Math.PI / 2);
  hood.add(new THREE.Mesh(shell, toon(C.hood)));
  hood.add(new THREE.Mesh(shell, toon(C.hoodIn, { side: THREE.BackSide })));
  hood.add(new THREE.Mesh(new THREE.SphereGeometry(HR + 0.004, 64, 48), outlineMat(5))); // silhouette line only
  addMesh(hood, new THREE.TorusGeometry(HR * Math.sin(TH0), 0.05, 18, 72), toon(C.hood), { pos: [0, 0, HR * Math.cos(TH0)], outline: 0 });
  const black = new THREE.MeshBasicMaterial({ color: '#141218' }), white = new THREE.MeshBasicMaterial({ color: '#ffffff' });
  for (const s of [-1, 1]) {
    const d = new THREE.Vector3(s * 0.43, 0.76, 0.48).normalize();
    const e = new THREE.Group(); e.position.copy(d.clone().multiplyScalar(HR + 0.006)); e.lookAt(d.clone().multiplyScalar(10)); hood.add(e);
    const sz = 0.15;
    e.add(new THREE.Mesh(new THREE.CircleGeometry(sz * 1.14, 40), black));
    const w = new THREE.Mesh(new THREE.CircleGeometry(sz, 40), white); w.position.z = 0.002; e.add(w);
    const p = new THREE.Mesh(new THREE.CircleGeometry(sz * 0.64, 40), black); p.position.set(s * sz * 0.08, -sz * 0.06, 0.004); e.add(p);
    const h = new THREE.Mesh(new THREE.CircleGeometry(sz * 0.2, 20), white); h.position.set(-s * sz * 0.18, sz * 0.22, 0.006); e.add(h);
  }
  // little curl on top + dorsal fin
  const curl = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-0.02, 0.83, 0.05), new THREE.Vector3(-0.04, 0.98, 0.1), new THREE.Vector3(0.05, 1.08, 0.08),
    new THREE.Vector3(0.14, 1.03, 0.02), new THREE.Vector3(0.1, 0.95, -0.02),
  ]);
  addMesh(hood, taperTube(curl, 0.05, 0.02), toon(C.hoodRim), { outline: 3 });
  addMesh(hood, spike, toon(C.hood), { pos: [0, 0.55, -0.8], rot: [-0.9, 0, 0], scale: [0.05, 0.32, 0.24], outline: 3 });
  // tail fin at the back and small side fins, so it reads as a fish from the side
  for (const s of [-1, 1]) {
    addMesh(hood, spike, toon(C.hoodRim), { pos: [0, -0.28 + s * 0.16, -1.08], rot: [-1.57 + s * 0.55, 0, 0], scale: [0.05, 0.26, 0.15], outline: 3 });
    addMesh(hood, spike, toon(C.hoodRim), { pos: [s * 0.9, -0.38, 0.05], rot: [0.3, 0, s * 2.2], scale: [0.04, 0.2, 0.12], outline: 3 });
  }
}

// ---------- osu! hit circles ----------
const LILITA = "'Lilita', sans-serif";
function hitTex(col, num) {
  return canvasTex(256, 256, (g) => {
    const c = 128;
    const r = g.createRadialGradient(c, c - 20, 10, c, c, 104);
    r.addColorStop(0, col.light); r.addColorStop(1, col.dark);
    g.beginPath(); g.arc(c, c, 100, 0, Math.PI * 2); g.fillStyle = r; g.fill();
    g.lineWidth = 16; g.strokeStyle = '#ffffff'; g.stroke();
    g.beginPath(); g.arc(c, c, 110, 0, Math.PI * 2); g.lineWidth = 5; g.strokeStyle = 'rgba(20,18,26,0.9)'; g.stroke();
    g.font = `120px ${LILITA}`; g.textAlign = 'center'; g.textBaseline = 'middle';
    g.lineWidth = 12; g.strokeStyle = 'rgba(20,18,26,0.85)'; g.strokeText(String(num), c, c + 6);
    g.fillStyle = '#ffffff'; g.fillText(String(num), c, c + 6);
  });
}
function ringTex(col) {
  return canvasTex(256, 256, (g) => {
    g.beginPath(); g.arc(128, 128, 116, 0, Math.PI * 2); g.lineWidth = 9; g.strokeStyle = col; g.stroke();
  });
}
const t300 = canvasTex(256, 128, (g) => {
  g.font = `96px ${LILITA}`; g.textAlign = 'center'; g.textBaseline = 'middle';
  g.lineWidth = 12; g.strokeStyle = '#15121a'; g.strokeText('300', 128, 68);
  g.fillStyle = '#72c8ff'; g.fillText('300', 128, 68);
});
const COMBO = [
  { light: '#ff9cc8', dark: '#ff3f93', ring: '#ff7ab5' },
  { light: '#9cc8ff', dark: '#3e7dff', ring: '#86b8ff' },
];
const HITS = [2.54, 3.81, 5.079, 6.032, 7.619, 8.889, 10.159, 10.318, 10.952, 11.111, 11.429, 12.54, 12.698, 13.492, 13.651, 13.809,
  14.127, 15.238, 16.191, 16.349, 16.508, 17.143, 17.778, 18.413, 18.73];
const circles = [];
{
  const rnd = mulberry(1906);
  let combo = 0, colIdx = 0, prev = null;
  HITS.forEach((ht, i) => {
    if (i > 0 && ht - HITS[i - 1] > 0.6) { combo = 0; colIdx ^= 1; }
    combo += 1;
    const col = COMBO[colIdx];
    let x, y, z;
    for (let tries = 0; ; tries++) { x = (rnd() * 2 - 1) * 3.1; y = 0.5 + rnd() * 2.6; z = -2.6 + rnd() * 3.2; const far = !prev || Math.hypot(x - prev[0], y - prev[1]) > 1.5 || tries > 50; if ((Math.abs(x) > 1.15 || z < -1.8) && far) break; }
    prev = [x, y];
    const grp = new THREE.Group(); grp.position.set(x, y, z); scene.add(grp);
    const mk = (map, blend) => new THREE.Sprite(new THREE.SpriteMaterial({ map, transparent: true, depthWrite: false, opacity: 0, blending: blend || THREE.NormalBlending }));
    const disc = mk(hitTex(col, combo)), ring = mk(ringTex(col.ring)), burst = mk(hitTex(col, ''), THREE.AdditiveBlending), judge = mk(t300);
    grp.add(ring, disc, burst, judge);
    circles.push({ ht, grp, disc, ring, burst, judge, size: 0.62 + rnd() * 0.18 });
  });
}
function updateCircles(t) {
  const pre = BEAT * 2.2;
  for (const c of circles) {
    const dt = t - c.ht, s = c.size;
    const vis = t > c.ht - pre && t < c.ht + 0.7;
    c.grp.visible = vis;
    if (!vis) continue;
    if (dt < 0) {
      const p = 1 + dt / pre; // 0..1
      c.disc.material.opacity = smooth(p * 1.6); c.disc.scale.set(s, s, 1);
      const rs = s * (1 + 1.6 * (1 - p)); c.ring.scale.set(rs, rs, 1); c.ring.material.opacity = smooth(p * 2);
      c.burst.material.opacity = 0; c.judge.material.opacity = 0;
    } else {
      const p = dt / 0.32;
      c.disc.material.opacity = 0; c.ring.material.opacity = 0;
      const bs = s * (1 + 0.55 * easeOutCubic(p)); c.burst.scale.set(bs, bs, 1); c.burst.material.opacity = clamp(1 - p) * 0.9;
      const jp = dt / 0.7; c.judge.material.opacity = clamp(1 - Math.pow(jp, 3)) * (dt < 0.05 ? dt / 0.05 : 1);
      c.judge.scale.set(s * 0.62, s * 0.31, 1); c.judge.position.y = s * 0.62 + 0.15 * easeOutCubic(jp);
    }
  }
}

// ---------- sparkles ----------
const starTex = canvasTex(256, 256, (g) => {
  const c = 128, R = 112, r = 26;
  g.beginPath();
  for (let i = 0; i < 8; i++) { const a = i * Math.PI / 4 - Math.PI / 2, rr = i % 2 ? r : R; g.lineTo(c + Math.cos(a) * rr, c + Math.sin(a) * rr); }
  g.closePath(); g.fillStyle = '#ffd338'; g.fill(); g.lineWidth = 8; g.strokeStyle = '#e39a12'; g.stroke();
});
const SPARK_BURSTS = [[10.159, 7], [11.429, 3], [16.191, 4], [16.508, 6]];
const sparks = [];
{
  const rnd = mulberry(77);
  for (const [t0, n] of SPARK_BURSTS) for (let i = 0; i < n; i++) {
    const a = rnd() * Math.PI * 2, rad = 0.85 + rnd() * 0.75;
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: starTex, transparent: true, depthWrite: false, opacity: 0 }));
    sp.userData = { t0: t0 + rnd() * 0.12, x: Math.cos(a) * rad, y: 1.55 + Math.sin(a) * rad * 0.8, z: 0.35 + rnd() * 0.4, s: 0.16 + rnd() * 0.16, rot: rnd() * 6, life: 0.9 + rnd() * 0.6 };
    scene.add(sp); sparks.push(sp);
  }
}
function updateSparks(t, chibiPos) {
  for (const sp of sparks) {
    const u = sp.userData, dt = t - u.t0;
    if (dt < 0 || dt > u.life) { sp.visible = false; continue; }
    sp.visible = true;
    const p = dt / u.life;
    const sc = u.s * Math.sin(Math.PI * Math.min(1, p * 1.15)) * (1 + 0.25 * Math.sin(dt * 18));
    sp.scale.set(sc, sc, 1);
    sp.material.rotation = u.rot + dt * 1.5;
    sp.material.opacity = 1;
    sp.position.set(chibiPos.x + u.x * (1 + 0.15 * p), u.y + 0.1 * p, chibiPos.z + u.z);
  }
}

// ---------- speed lines (2D overlay) ----------
const speedCv = document.getElementById('speed');
{
  const g = speedCv.getContext('2d'), rnd = mulberry(5);
  for (let i = 0; i < 140; i++) {
    const a = rnd() * Math.PI * 2, r0 = 380 + rnd() * 260, r1 = 1300;
    const w = 2 + rnd() * 9;
    const cx = 960, cy = 540;
    g.beginPath();
    g.moveTo(cx + Math.cos(a) * r0, cy + Math.sin(a) * r0);
    g.lineTo(cx + Math.cos(a + w / r1) * r1, cy + Math.sin(a + w / r1) * r1);
    g.lineTo(cx + Math.cos(a - w / r1) * r1, cy + Math.sin(a - w / r1) * r1);
    g.closePath(); g.fillStyle = 'rgba(255,255,255,0.85)'; g.fill();
  }
}

// ---------- text overlays ----------
const T = (id) => document.getElementById(id);
const txt = { dateLbl: T('t_date_lbl'), date: T('t_date'), kr: T('t_kr'), title: T('t_title'), rankLbl: T('t_rank_lbl'), rank: T('t_rank') };
function place(el, cx, cy, scale, rot, op) {
  const w = el.offsetWidth, h = el.offsetHeight;
  el.style.transform = `translate(${cx - w / 2}px, ${cy - h / 2}px) rotate(${rot}deg) scale(${scale})`;
  el.style.opacity = op;
}
function popIn(t, t0, t1) { // scale + opacity for a pop-in at t0, fade-out ending at t1
  if (t < t0 || t > t1) return [0, 0];
  const s = 0.35 + 0.65 * easeOutBack(seg(t, t0, t0 + 0.26));
  const o = Math.min(seg(t, t0, t0 + 0.08), 1 - seg(t, t1 - 0.3, t1));
  return [s, o];
}
function updateText(t) {
  if (!SHOW_TEXT) { for (const el of Object.values(txt)) el.style.opacity = 0; return; }
  let [s, o] = popIn(t, 5.97, 9.6);
  place(txt.dateLbl, 420, 300, s, -4, o);
  [s, o] = popIn(t, 5.97, 9.6);
  place(txt.date, 420, 395 + 6 * Math.sin(t * 2.2), s, -4, o);
  // title slam at the first big hit of the intro
  if (t >= 10.159 && t < 15.0) {
    const p = seg(t, 10.159, 10.159 + 0.24);
    const sc = lerp(2.3, 1, easeOutBack(p, 1.2)) * (1 + 0.04 * pulse(t, 11.429, 0.2) + 0.04 * pulse(t, 13.492, 0.2));
    const op = Math.min(seg(t, 10.159, 10.2), 1 - seg(t, 14.6, 15.0));
    place(txt.title, 960, 880, sc, lerp(-9, -3, easeOutCubic(p)), op);
    const [ks, ko] = popIn(t, 10.952, 15.0);
    place(txt.kr, 960, 735, ks, -3, ko);
  } else { txt.title.style.opacity = 0; txt.kr.style.opacity = 0; }
  [s, o] = popIn(t, 17.51, 19.05);
  place(txt.rankLbl, 1450, 300, s, 4, o);
  [s, o] = popIn(t, 17.51, 19.05);
  place(txt.rank, 1450, 400 + 6 * Math.sin(t * 2.6), s, 4, o);
}

// ---------- camera path ----------
const CAMK = [ // t, angle(deg), radius, height, lookY
  [0.0, -2, 10.8, 1.85, 1.22], [5.08, -9, 8.4, 1.6, 1.26], [10.159, 9, 7.5, 1.5, 1.3],
  [15.238, 19, 6.9, 1.45, 1.32], [19.048, 6, 4.6, 1.62, 1.5], [20.4, 5, 4.45, 1.62, 1.52],
];
function camAt(t) {
  let i = 0;
  while (i < CAMK.length - 2 && t > CAMK[i + 1][0]) i++;
  const p0 = CAMK[Math.max(0, i - 1)], p1 = CAMK[i], p2 = CAMK[i + 1], p3 = CAMK[Math.min(CAMK.length - 1, i + 2)];
  const u = clamp((t - p1[0]) / (p2[0] - p1[0]));
  const cr = (a, b, c, d) => 0.5 * ((2 * b) + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u + (-a + 3 * b - 3 * c + d) * u * u * u);
  return [1, 2, 3, 4].map((k) => cr(p0[k], p1[k], p2[k], p3[k]));
}

// ---------- main update ----------
const BLINKS = [3.9, 8.25, 15.55];
let LUNGE = 0;
const headPos = new THREE.Vector3();
const fade = T('fade');
window.renderAt = function (t) {
  // lights & environment
  const lightOn = smooth(seg(t, 0.75, 1.6));
  const preLight = 0.18 * smooth(seg(t, 0.0, 0.7));
  const L = Math.max(lightOn, preLight);
  key.intensity = 1.55 * L + 0.6 * pulse(t, 10.159, 0.35) + 0.5 * pulse(t, 16.191, 0.3) + 0.6 * pulse(t, 16.508, 0.35);
  hemi.intensity = 0.75 * L;
  rimL.intensity = 1.5 * smooth(seg(t, 2.5, 4.5)) + 1.5 * pulse(t, 10.159, 0.4);
  rimB.intensity = 1.6 * smooth(seg(t, 5.0, 7.0));
  bg.material.uniforms.k.value = 0.25 + 0.75 * smooth(seg(t, 0.8, 3.0));
  glowPink.material.opacity = 0.42 * smooth(seg(t, 2.5, 5.0)) + 0.25 * pulse(t, 10.159, 0.5) + 0.2 * pulse(t, 16.508, 0.5);
  glowBlue.material.opacity = 0.38 * smooth(seg(t, 5.0, 8.0)) + 0.15 * pulse(t, 11.429, 0.4);
  floor.material.opacity = smooth(seg(t, 1.0, 3.0));
  pool.material.opacity = 0.75 * lightOn;
  coneMat.uniforms.k.value = lightOn * (1 - 0.6 * smooth(seg(t, 15.2, 19.0)));
  fade.style.opacity = 1 - smooth(seg(t, 0.0, 0.5));

  // character pose
  LUNGE = 0;
  let faceKind = 'normal';
  if (BLINKS.some((b) => t >= b && t < b + 0.13)) faceKind = 'blink';
  const waving = t >= 10.159 && t < 12.9;
  if (waving) faceKind = 'happy';
  const shock = t >= 19.048;
  if (shock) faceKind = 'shock';
  faceMat.map = FACES[faceKind];

  const breath = Math.sin(t * Math.PI * 2 * 0.45);
  let nod = 0;
  if (t > 10.0 && t < 19.0) { const bt = (t - 10.159) / BEAT; const ph = bt - Math.floor(bt); nod = 0.05 * Math.pow(1 - ph, 3); }
  head.rotation.set(-nod + 0.03 * noise(t, 0.7, 1), 0.06 * noise(t, 0.45, 2) + (waving ? 0.12 : 0), 0.05 * noise(t, 0.6, 3) + (waving ? -0.06 : 0));
  body.scale.set(1 + 0.008 * breath, 1 - 0.012 * breath, 1 + 0.008 * breath);
  body.rotation.set(0, 0, 0);
  chibi.position.set(0, 0, 0);
  chibi.rotation.set(0, 0.12 * Math.sin(t * 0.35), 0);

  // arms
  armL.rotation.set(0.05, 0, -0.32 - 0.03 * breath);
  armR.rotation.set(0.05, 0, 0.32 + 0.03 * breath);
  if (waving) {
    const up = smooth(seg(t, 10.159, 10.4)) * (1 - smooth(seg(t, 12.55, 12.9)));
    const wv = Math.sin((t - 10.159) / (BEAT * 2) * Math.PI * 2);
    armR.rotation.set(0.15 * up, 0, lerp(0.32, 2.55 + 0.32 * wv, up));
  }
  // shock + lunge at the camera
  if (shock) {
    const [ang, rad, hh] = camAt(t);
    const a = ang * Math.PI / 180;
    const camPos = new THREE.Vector3(Math.sin(a) * rad, hh, Math.cos(a) * rad);
    const crouch = smooth(seg(t, 19.048, 19.4)) * (1 - easeOutCubic(seg(t, 19.5, 19.62)));
    body.scale.set(1 + 0.07 * crouch, 1 - 0.12 * crouch, 1 + 0.07 * crouch);
    const lp = easeInCubic(seg(t, 19.52, 20.02));
    const headWorld = new THREE.Vector3(0, 1.5, 0);
    const dir = camPos.clone().sub(headWorld);
    const dist = dir.length(); dir.normalize();
    const travel = (dist - 1.38) * lp;
    chibi.position.copy(dir.multiplyScalar(travel));
    chibi.position.y += 0.35 * Math.sin(Math.PI * clamp(lp * 1.1)) * (1 - lp);
    chibi.rotation.set(0.3 * Math.sin(Math.PI * lp) - 0.1 * crouch, a * lp, 0);
    LUNGE = lp;
    const armsUp = smooth(seg(t, 19.1, 19.35));
    armL.rotation.set(-0.4 * armsUp, 0, lerp(-0.32, -2.3, armsUp));
    armR.rotation.set(-0.4 * armsUp, 0, lerp(0.32, 2.3, armsUp));
    head.rotation.x -= 0.12 * crouch;
  }
  shadow.position.set(chibi.position.x, 0.006, chibi.position.z);
  const sh = clamp(1 - chibi.position.y * 1.2) * (1 - seg(chibi.position.length(), 0.5, 2.5));
  shadow.scale.set(1, 1, 1); shadow.material.opacity = sh;

  // camera
  const [ang, rad, hh, lookY] = camAt(t);
  const a = ang * Math.PI / 180;
  let shakeAmp = 0.004 + 0.03 * pulse(t, 10.159, 0.3) + 0.025 * pulse(t, 16.191, 0.25) + 0.035 * pulse(t, 16.508, 0.3) + (shock ? 0.012 + 0.03 * seg(t, 19.5, 20.0) : 0);
  camera.position.set(Math.sin(a) * rad + shakeAmp * noise(t, 37, 1), hh + shakeAmp * noise(t, 41, 2), Math.cos(a) * rad);
  chibi.updateMatrixWorld(true); head.getWorldPosition(headPos);
  const lk = smooth(LUNGE);
  camera.lookAt(lerp(0, headPos.x, lk) + shakeAmp * 0.5 * noise(t, 29, 4), lerp(lookY, headPos.y - 0.05, lk), lerp(0, headPos.z, lk));
  camera.fov = 35 - 3.5 * pulse(t, 10.159, 0.35) - 2.2 * pulse(t, 16.191, 0.3) - 3.0 * pulse(t, 16.508, 0.35);
  camera.updateProjectionMatrix();

  updateCircles(t);
  updateSparks(t, chibi.position);
  updateText(t);
  const sl = shock ? smooth(seg(t, 19.45, 19.65)) : 0;
  speedCv.style.opacity = sl * 0.9;
  speedCv.style.transform = `rotate(${(Math.floor(t * 30) % 7) * 1.7}deg) scale(${1 + 0.04 * ((Math.floor(t * 30) % 3))})`;

  if (window.CAM) { camera.position.set(...window.CAM.p); camera.lookAt(...window.CAM.l); camera.fov = window.CAM.f || 35; camera.updateProjectionMatrix(); }
  renderer.render(scene, camera);
};

await document.fonts.load(`120px ${LILITA}`);
await document.fonts.load("900 72px 'KR'");
for (const k of ['normal', 'blink', 'happy', 'shock']) FACES[k] = faceTexture(k);
for (const c of circles) { /* textures were drawn before the font finished loading: redraw */
  c.disc.material.map.dispose();
}
// rebuild hit textures now that the font is ready
{
  let combo = 0, colIdx = 0;
  HITS.forEach((ht, i) => {
    if (i > 0 && ht - HITS[i - 1] > 0.6) { combo = 0; colIdx ^= 1; }
    combo += 1;
    const tex = hitTex(COMBO[colIdx], combo);
    circles[i].disc.material.map = tex; circles[i].burst.material.map = hitTex(COMBO[colIdx], '');
    circles[i].disc.material.needsUpdate = true; circles[i].burst.material.needsUpdate = true;
  });
}
t300.image.getContext('2d').clearRect(0, 0, 256, 128);
{
  const g = t300.image.getContext('2d');
  g.font = `96px ${LILITA}`; g.textAlign = 'center'; g.textBaseline = 'middle';
  g.lineWidth = 12; g.strokeStyle = '#15121a'; g.strokeText('300', 128, 68);
  g.fillStyle = '#72c8ff'; g.fillText('300', 128, 68);
  t300.needsUpdate = true;
}
window.renderAt(0);
window.READY = true;
