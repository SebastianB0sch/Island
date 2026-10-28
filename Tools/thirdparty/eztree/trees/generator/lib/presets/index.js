import { readFileSync } from 'node:fs';
import TreeOptions from '../options.js';
const names = { 'Ash Small':'ash_small','Ash Medium':'ash_medium','Ash Large':'ash_large','Aspen Small':'aspen_small','Aspen Medium':'aspen_medium','Aspen Large':'aspen_large','Bush 1':'bush_1','Bush 2':'bush_2','Bush 3':'bush_3','Oak Small':'oak_small','Oak Medium':'oak_medium','Oak Large':'oak_large','Pine Small':'pine_small','Pine Medium':'pine_medium','Pine Large':'pine_large','Trellis':'trellis' };
export const TreePreset = {};
for (const [k, f] of Object.entries(names)) TreePreset[k] = JSON.parse(readFileSync(new URL('./' + f + '.json', import.meta.url)));
export function loadPreset(name) {
  const preset = TreePreset[name];
  return preset ? structuredClone(preset) : new TreeOptions();
}
