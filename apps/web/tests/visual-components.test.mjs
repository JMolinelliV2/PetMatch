import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import ts from "typescript";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

const require = createRequire(import.meta.url);
async function compiled(name, imports = {}, sourceFile = new URL(`../app/ui/${name}.tsx`, import.meta.url)) {
  const source = await readFile(sourceFile, "utf8");
  let { outputText } = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
  for (const [specifier, target] of Object.entries({ react: pathToFileURL(require.resolve("react")).href, "react/jsx-runtime": pathToFileURL(require.resolve("react/jsx-runtime")).href, ...imports })) {
    outputText = outputText.replaceAll(JSON.stringify(specifier), JSON.stringify(target));
  }
  return `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`;
}
const pictogram = await compiled("pictogram");
const { Stepper } = await import(await compiled("stepper", { "./pictogram": pictogram }));
const { MatchScore } = await import(await compiled("match-score"));
const { SexSelector } = await import(await compiled("sex-selector", { "./pictogram": pictogram }));
const reportPhotos = await compiled("report-photos", {}, new URL("../lib/report-photos.ts", import.meta.url));
const { PhotoUploader } = await import(await compiled("photo-uploader", { "./pictogram": pictogram, "@/lib/report-photos": reportPhotos }));
const html = (component, props) => renderToStaticMarkup(createElement(component, props));

test("el stepper conserva las tres etapas y comunica la etapa actual", () => {
  const markup = html(Stepper, { steps: ["Mascota", "Fecha y lugar", "Contacto y revisión"], current: 2 });
  assert.equal((markup.match(/<li /g) || []).length, 3);
  assert.match(markup, /aria-current="step"/);
  assert.match(markup, /value="2" max="3"/);
  assert.match(markup, /completado/);
});
test("el selector visual conserva el campo sex y el valor unknown del contrato actual", () => {
  const markup = html(SexSelector);
  assert.match(markup, /<select name="sex"/);
  assert.match(markup, /value="unknown" selected=""/);
  assert.equal((markup.match(/type="radio"/g) || []).length, 3);
});
test("una compatibilidad alta tiene contexto y no se expresa como probabilidad de identidad", () => {
  const markup = html(MatchScore, { score: .92 });
  assert.match(markup, /92%/);
  assert.match(markup, /Compatibilidad alta/);
  assert.doesNotMatch(markup, /probabilidad/i);
});
test("la compatibilidad inferior se presenta para revisión", () => {
  assert.match(html(MatchScore, { score: .71 }), /Para revisar/);
});
test("un score ausente o inválido no produce un porcentaje inventado", () => {
  assert.equal(html(MatchScore, { score: undefined }), "");
  assert.equal(html(MatchScore, { score: NaN }), "");
});
test("el formulario general permite cinco fotos opcionales con los formatos actuales", () => {
  const markup = html(PhotoUploader, { name: "photo" });
  assert.match(markup, /name="photo"/);
  assert.match(markup, /image\/jpeg,image\/png,image\/webp/);
  assert.match(markup, /10 MB/);
  assert.match(markup, /multiple=""/);
  assert.doesNotMatch(markup, /required=""/);
});
test("el avistamiento vinculado conserva el control photos y permite cinco fotos opcionales", () => {
  const markup = html(PhotoUploader, { name: "photos", label: "Fotos", maxFiles: 5 });
  assert.match(markup, /name="photos"/);
  assert.match(markup, /multiple=""/);
  assert.match(markup, /Hasta 5 fotos/);
  assert.doesNotMatch(markup, /required=""/);
});
