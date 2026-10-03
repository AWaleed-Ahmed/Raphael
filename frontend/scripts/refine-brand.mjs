// Materialize the selected, licensed type and icon assets. Run from frontend.
import fs from 'node:fs';
const publicDir = 'public';
fs.mkdirSync(`${publicDir}/fonts`, { recursive: true });
fs.mkdirSync(`${publicDir}/licenses`, { recursive: true });
for (const [pkg, file, name] of [
  ['@fontsource-variable/instrument-sans', 'instrument-sans-latin-wght-normal.woff2', 'instrument-sans'],
  ['@fontsource-variable/newsreader', 'newsreader-latin-wght-italic.woff2', 'newsreader-italic'],
  ['@fontsource/ibm-plex-mono', 'ibm-plex-mono-latin-400-normal.woff2', 'ibm-plex-mono'],
]) {
  fs.copyFileSync(`node_modules/${pkg}/files/${file}`, `${publicDir}/fonts/${name}.woff2`);
  fs.copyFileSync(`node_modules/${pkg}/LICENSE`, `${publicDir}/licenses/${name}.txt`);
}
const names = ['arrow-up-right','arrow-right','arrow-down','arrows-left-right','arrow-counter-clockwise','pause','play','check','warning','plus','minus','list','shield-check','git-pull-request','stack','cube','crosshair','file-code','magnifying-glass','fingerprint','arrow-elbow-down-right','arrow-up'];
const symbols = names.map(name => {
  const svg = fs.readFileSync(`node_modules/@phosphor-icons/core/assets/light/${name}-light.svg`, 'utf8');
  return `<symbol id="${name}" viewBox="0 0 256 256">${svg.replace(/^<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '')}</symbol>`;
});
fs.writeFileSync(`${publicDir}/icons.svg`, `<svg xmlns="http://www.w3.org/2000/svg">${symbols.join('')}</svg>`);
fs.copyFileSync('node_modules/@phosphor-icons/core/LICENSE', `${publicDir}/licenses/phosphor.txt`);
