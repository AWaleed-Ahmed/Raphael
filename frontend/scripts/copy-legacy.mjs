import { cp, mkdir } from "node:fs/promises";

const destination = new URL("../public/legacy/", import.meta.url);
await mkdir(destination, { recursive: true });
for (const name of ["console", "direction", "assets"]) {
  await cp(new URL(`../dist/${name}`, import.meta.url), new URL(name, destination), {
    recursive: true,
  });
}
