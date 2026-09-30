/**
 * El JS que baja el tablero al abrir la app (§11.6): el archivo principal más los que
 * index.html precarga (modulepreload). La salida de Vite los lista por separado, así que
 * mirar solo "index-….js" subestima el peso. Se corre después de `npm run build`.
 */
import { readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";

const LIMITE_KB = 150;
const html = readFileSync("dist/index.html", "utf8");
const archivos = [...html.matchAll(/(?:src|href)="\/(assets\/[^"]+\.js)"/g)].map((m) => m[1]);

let total = 0;
for (const archivo of archivos) {
  const kb = gzipSync(readFileSync(`dist/${archivo}`), { level: 9 }).length / 1000;
  total += kb;
  console.log(`${archivo.padEnd(40)} ${kb.toFixed(1).padStart(6)} kB gzip`);
}
console.log(`JS inicial: ${total.toFixed(1)} kB gzip (límite ${LIMITE_KB} kB)`);
if (total > LIMITE_KB) {
  console.error("Supera el límite: revisa qué entró al chunk inicial.");
  process.exit(1);
}
