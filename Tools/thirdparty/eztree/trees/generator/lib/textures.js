import * as THREE from 'three';
// Headless stub: records which texture would be used instead of loading images.
export function getBarkTexture(barkType, fileType, scale = { x: 1, y: 1 }) {
  const t = new THREE.Texture();
  t.userData = { kind: 'bark', barkType, fileType, scale };
  return t;
}
export function getLeafTexture(leafType) {
  const t = new THREE.Texture();
  t.userData = { kind: 'leaf', leafType };
  return t;
}
