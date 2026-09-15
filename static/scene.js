import * as THREE from './vendor/three.module.js';

const host = document.querySelector('#sceneBackground');
const stage = document.querySelector('#searchStage');
const toggle = document.querySelector('#motionToggle');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');

// The background owns its render loop; search and charts do not depend on WebGL.
function createScene() {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  renderer.setClearColor(0xe9e9ed);
  host.append(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 50);
  const time = { value: 0 };
  const sphere = new THREE.Mesh(new THREE.SphereGeometry(1.28, 96, 64), new THREE.ShaderMaterial({
    uniforms: { time },
    vertexShader: `
      uniform float time;
      varying vec3 vNormal;
      varying vec3 vPosition;
      varying vec3 vView;
      void main() {
        vec3 p = position;
        float wave = sin(p.y * 4.0 + time * .45) * sin(p.x * 3.0 + p.z * 2.0 + time * .2);
        p += normal * wave * .022;
        vec4 view = modelViewMatrix * vec4(p, 1.0);
        vNormal = normalize(normalMatrix * normal);
        vPosition = p;
        vView = -view.xyz;
        gl_Position = projectionMatrix * view;
      }
    `,
    fragmentShader: `
      uniform float time;
      varying vec3 vNormal;
      varying vec3 vPosition;
      varying vec3 vView;
      void main() {
        vec3 n = normalize(vNormal);
        vec3 eye = normalize(vView);
        float marble = sin(vPosition.y * 12.0 + sin(vPosition.x * 7.0 + time * .18) * 1.1 + sin(vPosition.z * 9.0) * .7);
        n = normalize(n + vec3(marble * .016, marble * .012, 0.0));
        float light = max(dot(n, normalize(vec3(-.7, 1.4, 1.0))), 0.0);
        float rim = pow(1.0 - max(dot(n, eye), 0.0), 3.0);
        vec3 pearl = mix(vec3(.67, .69, .71), vec3(.965, .958, .944), smoothstep(-.3, .85, n.y + light * .3));
        float sheen = pow(max(dot(reflect(-normalize(vec3(-.5,1.2,1.1)), n), eye), 0.0), 24.0);
        pearl += vec3(.11, .10, .08) * sheen;
        pearl += vec3(.033, .007, .012) * sin(vPosition.y * 2.0 + time * .22) * light;
        pearl += marble * .005 * light;
        pearl = mix(pearl, vec3(.92,.93,.95), rim * .65);
        gl_FragColor = vec4(pearl, 1.0);
      }
    `,
  }));
  sphere.position.y = 2.12;
  scene.add(sphere);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(200, 200), new THREE.ShaderMaterial({
    uniforms: { time },
    vertexShader: `varying vec2 point; void main() { point = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
    fragmentShader: `
      uniform float time;
      varying vec2 point;
      void main() {
        float r = length(point);
        float halo = exp(-r*r*.22);
        float ring = sin(r*11.0 - time*.7) * exp(-pow((r-1.4)/.85,2.0)) * .036;
        float shadow = exp(-r*r*1.4) * .075;
        vec3 base = mix(vec3(.914,.914,.929), vec3(.97,.972,.978), halo);
        gl_FragColor = vec4(base + ring - shadow, 1.0);
      }
    `,
  }));
  floor.rotation.x = -Math.PI / 2;
  scene.add(floor);
  const pointer = new THREE.Vector2();
  let paused = reducedMotion.matches;
  let visible = true;
  let frame = 0;
  let previous = 0;
  let elapsed = 0;
  let compact = false;
  function resize() {
    const { width, height } = host.getBoundingClientRect();
    compact = width < 700;
    camera.aspect = width / height;
    camera.position.set(0, compact ? 4.6 : 4.15, compact ? 12.8 : 10.0);
    camera.lookAt(0, compact ? .5 : 1.1, 0);
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
    draw();
  }
  function draw() {
    time.value = elapsed;
    sphere.position.y = (compact ? 2.6 : 2.12) + Math.sin(elapsed * .65) * .09;
    sphere.rotation.y = elapsed * .07 + pointer.x * .12;
    sphere.rotation.z = pointer.y * .045;
    renderer.render(scene, camera);
  }
  function tick(now) {
    elapsed += previous ? Math.min((now - previous) / 1000, .05) : 0;
    previous = now;
    draw();
    frame = requestAnimationFrame(tick);
  }
  function sync() {
    cancelAnimationFrame(frame);
    previous = 0;
    toggle.setAttribute('aria-pressed', String(paused));
    const label = paused ? '播放背景动画' : '暂停背景动画';
    toggle.setAttribute('aria-label', label);
    toggle.title = label;
    toggle.firstElementChild.textContent = paused ? '▷' : 'Ⅱ';
    if (!paused && visible && !document.hidden) frame = requestAnimationFrame(tick);
    else draw();
  }
  toggle.disabled = false;
  toggle.addEventListener('click', () => { paused = !paused; sync(); });
  stage.addEventListener('pointermove', (event) => {
    if (paused) return;
    const rect = stage.getBoundingClientRect();
    pointer.set((event.clientX - rect.left) / rect.width - .5, (event.clientY - rect.top) / rect.height - .5);
  });
  stage.addEventListener('pointerleave', () => pointer.set(0, 0));
  reducedMotion.addEventListener('change', () => { paused = reducedMotion.matches; sync(); });
  document.addEventListener('visibilitychange', sync);
  new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; sync(); }).observe(stage);
  new ResizeObserver(resize).observe(host);
  renderer.domElement.addEventListener('webglcontextlost', (event) => {
    event.preventDefault();
    paused = true;
    sync();
    toggle.disabled = true;
  });
  renderer.domElement.addEventListener('webglcontextrestored', () => { toggle.disabled = false; sync(); });
  resize();
  sync();
}

try { createScene(); } catch (error) {
  toggle.disabled = true;
  host.replaceChildren();
  console.warn('3D background unavailable:', error.message);
}
