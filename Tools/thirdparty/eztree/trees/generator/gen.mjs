// Headless ez-tree -> glTF 2.0 exporter.  node gen.mjs <config.json> <outdir>
// config: [{ id, preset, height, overrides:{...deep...}, leafType?, barkType? }]
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { Tree } from './lib/index.js';
import { loadPreset } from './lib/presets/index.js';

const [cfgPath, outDir] = process.argv.slice(2);
const cfg = JSON.parse(readFileSync(cfgPath, 'utf8'));
mkdirSync(outDir, { recursive: true });

function deepMerge(t, s) {
  for (const k of Object.keys(s)) {
    if (s[k] && typeof s[k] === 'object' && !Array.isArray(s[k]) && t[k] && typeof t[k] === 'object') deepMerge(t[k], s[k]);
    else t[k] = s[k];
  }
  return t;
}
const srgbToLin = (c) => (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
function hexToLinear(h) {
  return [(h >> 16) & 255, (h >> 8) & 255, h & 255].map((v) => srgbToLin(v / 255)).concat([1]);
}

const report = [];
for (const item of cfg) {
  const opts = loadPreset(item.preset);
  if (item.overrides) deepMerge(opts, item.overrides);
  const tree = new Tree();
  tree.options.copy(opts);
  if (item.overrides && item.overrides.seed !== undefined) tree.options.seed = item.overrides.seed;
  tree.generate();
  const o = tree.options;
  const B = tree.branches, L = tree.leaves;
  const hasLeaves = L.indices.length > 0 && !item.noLeaves;

  // bounds of everything for scaling to target height (y-up)
  const all = hasLeaves ? B.verts.concat(L.verts) : B.verts;
  let minY = Infinity, maxY = -Infinity;
  for (let i = 1; i < all.length; i += 3) { minY = Math.min(minY, all[i]); maxY = Math.max(maxY, all[i]); }
  const s = item.height / (maxY - Math.min(0, minY));

  const sx = o.bark.textureScale.x, sy = o.bark.textureScale.y;
  const prims = [];
  const bufs = [];
  let byteOffset = 0;
  const bufferViews = [], accessors = [];
  function addAccessor(arr, type, comp, target, minmax) {
    const typed = comp === 5126 ? new Float32Array(arr) : new Uint32Array(arr);
    const buf = Buffer.from(typed.buffer);
    const pad = (4 - (buf.length % 4)) % 4;
    bufferViews.push({ buffer: 0, byteOffset, byteLength: buf.length, target });
    bufs.push(buf); if (pad) bufs.push(Buffer.alloc(pad));
    byteOffset += buf.length + pad;
    const n = { SCALAR: 1, VEC2: 2, VEC3: 3 }[type];
    const acc = { bufferView: bufferViews.length - 1, componentType: comp, count: arr.length / n, type };
    if (minmax) {
      const mn = Array(n).fill(Infinity), mx = Array(n).fill(-Infinity);
      for (let i = 0; i < arr.length; i++) { const c = i % n; mn[c] = Math.min(mn[c], arr[i]); mx[c] = Math.max(mx[c], arr[i]); }
      acc.min = mn; acc.max = mx;
    }
    accessors.push(acc);
    return accessors.length - 1;
  }
  const scaled = (v) => v.map((x) => x * s);
  // bark
  const buv = [];
  for (let i = 0; i < B.uvs.length; i += 2) { buv.push(B.uvs[i] * sx, B.uvs[i + 1] / sy); }
  prims.push({
    attributes: {
      POSITION: addAccessor(scaled(B.verts), 'VEC3', 5126, 34962, true),
      NORMAL: addAccessor(B.normals, 'VEC3', 5126, 34962),
      TEXCOORD_0: addAccessor(buv, 'VEC2', 5126, 34962),
    },
    indices: addAccessor(B.indices, 'SCALAR', 5125, 34963),
    material: 0,
  });
  if (hasLeaves) {
    prims.push({
      attributes: {
        POSITION: addAccessor(scaled(L.verts), 'VEC3', 5126, 34962, true),
        NORMAL: addAccessor(L.normals, 'VEC3', 5126, 34962),
        TEXCOORD_0: addAccessor(L.uvs.map((v, i) => (i % 2 ? 1 - v : v)), 'VEC2', 5126, 34962),
      },
      indices: addAccessor(L.indices, 'SCALAR', 5125, 34963),
      material: 1,
    });
  }
  const bark = item.barkType || o.bark.type;
  const leaf = item.leafType || o.leaves.type;
  const images = [
    { uri: `textures/${bark}_color_1k.jpg` },
    { uri: `textures/${bark}_normal_1k.jpg` },
    { uri: `textures/${bark}_orm_1k.png` },
  ];
  const materials = [{
    name: `MI_EzBark_${bark}`,
    pbrMetallicRoughness: {
      baseColorTexture: { index: 0 }, baseColorFactor: hexToLinear(item.barkTint ?? o.bark.tint),
      metallicRoughnessTexture: { index: 2 }, metallicFactor: 0, roughnessFactor: 1,
    },
    normalTexture: { index: 1 },
    occlusionTexture: { index: 2 },
  }];
  if (hasLeaves) {
    images.push({ uri: `textures/${leaf}_color.png` });
    materials.push({
      name: `MI_EzLeaves_${leaf}`,
      pbrMetallicRoughness: { baseColorTexture: { index: 3 }, baseColorFactor: hexToLinear(item.leafTint ?? o.leaves.tint), metallicFactor: 0, roughnessFactor: 0.8 },
      alphaMode: 'MASK', alphaCutoff: o.leaves.alphaTest ?? 0.5, doubleSided: true,
    });
  }
  const textures = images.map((_, i) => ({ sampler: 0, source: i }));
  const bin = Buffer.concat(bufs);
  const gltf = {
    asset: { version: '2.0', generator: 'ez-tree 1.1.0 (headless, Duel Academy Island tools)',
      extras: { generator: '@dgreenheck/ez-tree@1.1.0 (MIT)', preset: item.preset, overrides: item.overrides || {}, seed: o.seed, scale: s } },
    scene: 0, scenes: [{ nodes: [0] }],
    nodes: [{ name: item.id, mesh: 0 }],
    meshes: [{ name: item.id, primitives: prims }],
    materials, textures, images,
    samplers: [{ magFilter: 9729, minFilter: 9987, wrapS: 10497, wrapT: 10497 }],
    buffers: [{ uri: `${item.id}.bin`, byteLength: bin.length }],
    bufferViews, accessors,
  };
  writeFileSync(`${outDir}/${item.id}.bin`, bin);
  writeFileSync(`${outDir}/${item.id}.gltf`, JSON.stringify(gltf, null, 1));
  const tris = (B.indices.length + (hasLeaves ? L.indices.length : 0)) / 3;
  report.push({ id: item.id, tris, barkTris: B.indices.length / 3, leafTris: hasLeaves ? L.indices.length / 3 : 0, height: item.height, scale: s, bark, leaf });
  console.log(JSON.stringify(report[report.length - 1]));
}
writeFileSync(`${outDir}/_report.json`, JSON.stringify(report, null, 1));
