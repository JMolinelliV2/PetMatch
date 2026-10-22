// Run only against the disposable production preview. SMTP terminates at its private Mailpit.
import assert from "node:assert/strict";
import {randomUUID} from "node:crypto";
import {readFile} from "node:fs/promises";

assert.equal(process.env.DISPOSABLE_STACK,"mascomatch-prod-smoke","Use only the explicitly disposable preview stack");
assert.equal(process.env.NODE_ENV,"production","Requires the production web image");

const base="http://localhost:3000";
const identity=randomUUID();
const email=`smoke-owner-${identity}@example.test`;
const password="test-only-production-passphrase";
let cookie="";
const cookies=new Map();
function absorb(response){for(const value of response.headers.getSetCookie()){const pair=value.split(";")[0];const at=pair.indexOf("=");cookies.set(pair.slice(0,at),pair.slice(at+1));}cookie=[...cookies].map(([key,value])=>`${key}=${value}`).join("; ");}
const pageEvent={name:"page_view",page:"HOME",event_id:randomUUID()};
const synthetic=await fetch(base+"/api/analytics",{method:"POST",headers:{Origin:"https://mascomatch.com","Content-Type":"application/json","X-MascoMatch-Synthetic":"1"},body:JSON.stringify(pageEvent)});
assert.equal(synthetic.status,204);assert.equal(synthetic.headers.getSetCookie().length,0);
for(let attempt=0;attempt<2;attempt++){
  const view=await fetch(base+"/api/analytics",{method:"POST",headers:{Origin:"https://mascomatch.com","Content-Type":"application/json",...(cookie?{Cookie:cookie}:{})},body:JSON.stringify(pageEvent)});
  assert.equal(view.status,204);absorb(view);
}
assert.ok(cookies.has("mm_visitor")&&cookies.has("mm_visit"));
const visitorBeforeSignup=cookies.get("mm_visitor");
async function request(path,body,method=body?"POST":"GET"){
  const response=await fetch(base+path,{method,headers:{Origin:"https://mascomatch.com",...(cookie?{Cookie:cookie}:{}),...(body?{"Content-Type":"application/json"}:{})},body:body?JSON.stringify(body):undefined});
  const data=await response.json();
  assert.equal(response.ok,true,`${path}: HTTP ${response.status}`);
  return {response,data};
}
const session=await request("/api/session",{mode:"register",email,password,name:"Cuenta sintética de producción"});
assert.equal(session.data.access_token,undefined);
assert.equal(session.data.user.email_verification_required,true);
const header=session.response.headers.get("set-cookie");
assert.match(header,/__Host-mascomatch_session=/);
assert.match(header,/HttpOnly/i);assert.match(header,/Secure/i);assert.match(header,/SameSite=Lax/i);
absorb(session.response);assert.equal(cookies.get("mm_visitor"),visitorBeforeSignup);
assert.equal((await fetch(base+"/api/backend/pets",{method:"POST",headers:{Cookie:cookie,Origin:"https://mascomatch.com","Content-Type":"application/json"},body:JSON.stringify({name:"Sin verificar",species:"dog"})})).status,403);
let code;
for(let attempt=0;attempt<45;attempt++){
  const inbox=await (await fetch("http://mailpit:8025/api/v1/messages")).json();
  const item=inbox.messages.find(item=>item.To.some(target=>target.Address===email));
  if(item){
    const mail=await (await fetch(`http://mailpit:8025/api/v1/message/${item.ID}`)).json();
    code=mail.Text.match(/confirmar-correo\?codigo=([A-Za-z0-9_-]+)/)?.[1];
    if(code)break;
  }
  await new Promise(resolve=>setTimeout(resolve,1000));
}
assert.ok(code,"Confirmation email must arrive at the disposable Mailpit");
await request("/api/account-access/verify-email",{code});
const pet=(await request("/api/backend/pets",{name:"Animal sintético",species:"dog",sex:"female",primary_color:"brown",size:"medium"})).data;
const lost=(await request("/api/backend/lost-cases",{pet_id:pet.id,lost_at:new Date(Date.now()-3600000).toISOString(),latitude:-34.9,longitude:-56.1,description:"Aviso sintético de la prueba de producción",public_location:"Montevideo"})).data;
const form=new FormData();
form.set("owner_type","lost_case");form.set("owner_id",lost.id);
form.set("file",new Blob([await readFile("/app/public/images/dog-hero-generated.jpg")],{type:"image/jpeg"}),"example.jpg");
const upload=await fetch(base+"/api/backend/photos/upload",{method:"POST",headers:{Cookie:cookie,Origin:"https://mascomatch.com"},body:form});
assert.equal(upload.status,201);
const photo=await upload.json();assert.equal(photo.signed_url,undefined);
const dashboard=(await request("/api/account/dashboard")).data;
assert.equal(dashboard.cases.length,1);
const sighting=new FormData();sighting.set("request_id",randomUUID());sighting.set("observed_at",new Date().toISOString());
sighting.set("latitude","-34.901");sighting.set("longitude","-56.101");sighting.set("public_location","Montevideo");
const anonymous=await fetch(base+`/api/sightings/${lost.id}`,{method:"POST",headers:{Origin:"https://mascomatch.com"},body:sighting});
assert.equal(anonymous.status,201);const linked=await anonymous.json();assert.equal(linked.owner_notified,true);
const matches=(await request(`/api/matches/lost-cases/${lost.id}`)).data;
assert.equal(matches.items[0].match.presentation,null,"An unverified linked report is not an AI recommendation view");
const recovered=(await request(`/api/account/lost-cases/${lost.id}`,{status:"FOUND",recovery_reason:"OTHER"},"PATCH")).data;
assert.equal(recovered.status,"FOUND");
assert.equal((await fetch(base+"/api/backend/pets",{method:"POST",headers:{Origin:"https://other.example","Content-Type":"application/json"},body:"{}"})).status,403);
await request("/api/session",undefined,"DELETE");
const after=await request("/api/session");assert.equal(after.data.user,null);
console.log(JSON.stringify({bff_signup:true,unverified_publish_rejected:true,confirmation_email_received:true,email_verified:true,token_not_exposed:true,secure_cookie:true,case_saved:true,photo_saved:true,csrf_rejected:true,logout_revoked:true,analytics_cookie:true,synthetic_views_excluded:true,anonymous_sighting_notified:true,recovery_attributed:true}));
