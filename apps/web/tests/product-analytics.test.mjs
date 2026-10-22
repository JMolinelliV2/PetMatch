import test from "node:test";
import assert from "node:assert/strict";
import {pageCategory,viewQualified} from "../lib/product-analytics.ts";
import {analyticsGeo,normalizePlaces} from "../lib/places.ts";

test("las categorías de página descartan parámetros, rutas internas e identificadores sensibles",()=>{
 assert.equal(pageCategory("/?token=private"),"HOME");
 assert.equal(pageCategory("/mapa?email=private@example.test"),"MAP");
 assert.equal(pageCategory("/perdidos/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),"LOST_CASE");
 assert.equal(pageCategory("/admin"),null);
 assert.equal(pageCategory("/api/session"),null);
 assert.equal(pageCategory("/_next/static/test.js"),null);
 assert.equal(pageCategory("/recuperar?codigo=secret"),"OTHER_PUBLIC");
});

test("una vista requiere mitad visible durante un segundo y pestaña visible",()=>{
 assert.equal(viewQualified(.49,true,4000),false);
 assert.equal(viewQualified(.5,true,999),false);
 assert.equal(viewQualified(.5,false,2000),false);
 assert.equal(viewQualified(.5,true,1000),true);
});

test("la zona de analytics no incluye dirección, detalle, coordenadas ni identificadores",()=>{
 const geo=analyticsGeo({label:"Calle privada 123",detail:"Dirección privada",locality:"Calle privada 123",city:"Montevideo",department:"Montevideo",countryCode:"UY",latitude:-34.123456,longitude:-56.123456,source:"search",id:"sensitive"});
 assert.deepEqual(geo,{country:"UY",department:"Montevideo",locality:"Montevideo"});
 assert.deepEqual(analyticsGeo({city:"Calle 123",department:"x@example.test"}),{country:"ZZ",department:"unknown",locality:"unknown"});
});

test("geocodificación conserva ciudad y departamento separados de la dirección",()=>{
 const [place]=normalizePlaces({features:[{geometry:{type:"Point",coordinates:[-56,-34]},properties:{name:"Plaza",city:"Canelones",state:"Canelones",countrycode:"UY"}}]});
 assert.equal(place.city,"Canelones");assert.equal(place.department,"Canelones");
});
