import test from "node:test";
import assert from "node:assert/strict";
import { dogTraits, lostDate, sexLabel, speciesLabel } from "../lib/lost-dogs.ts";
import { placeAtMapPoint } from "../lib/places.ts";

test("el pin guarda el punto nuevo sin conservar la dirección o precisión del GPS anterior", () => {
  const point = placeAtMapPoint(-34.79123, -55.95456);
  assert.equal(point.latitude, -34.79123);
  assert.equal(point.longitude, -55.95456);
  assert.equal(point.source, "map");
  assert.equal(point.label, "Punto elegido en el mapa");
  assert.equal(point.locality, undefined);
  assert.equal(point.accuracyMeters, undefined);
});

test("las características públicas usan etiquetas en español y omiten datos desconocidos", () => {
  assert.deepEqual(dogTraits({ breed: "unknown", sex: "unknown", size: "medium", primary_color: "brown" }), ["Mediano", "Marrón"]);
  assert.deepEqual(dogTraits({ breed: "unknown", sex: "unknown", size: "unknown", primary_color: "unknown" }), []);
});

test("el sexo declarado se muestra con etiquetas en español", () => {
  assert.equal(sexLabel("male"), "Macho");
  assert.equal(sexLabel("female"), "Hembra");
  assert.equal(sexLabel("unknown"), "No indicado");
  assert.deepEqual(dogTraits({ breed: "unknown", sex: "female", size: "medium", primary_color: "white" }), ["Hembra", "Mediano", "Blanco"]);
});

test("las fechas del aviso son legibles y toleran datos inválidos", () => {
  assert.match(lostDate("2026-10-07T15:00:00Z"), /2026/);
  assert.equal(lostDate("invalid"), "Fecha no indicada");
});

test("cada aviso identifica perros y gatos y señala las especies históricas fuera de alcance", () => {
  for (const [species, label] of Object.entries({ dog: "Perro", cat: "Gato" })) {
    assert.equal(speciesLabel(species), label);
  }
  for (const species of ["rabbit", "bird", "other", "unknown", ""]) {
    assert.equal(speciesLabel(species), "Especie fuera del alcance actual");
  }
});
