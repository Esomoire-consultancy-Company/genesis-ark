// Public Door links are navigation hints, never Warden authority.
// This module does not authenticate buyers, confirm bookings or verify River receipts.
const STATES = Object.freeze(["TODAY","PLANNED","FINISHED","CONFIGURED","DELIVERED"]);
const ANCHORS = Object.freeze(["FLOOR_01","ARCH_01","GLAZE_01","KITCHEN_01","BALC_01","LIGHT_01"]);
const SAFE_NAME = /^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$/;
const ALLOWED_LOCALES = ["en","ar","en-IN","en-AE","ar-AE"];

export function interpretUntrustedDoorUrl(rawUrl) {
  const u = new URL(rawUrl);
  if (!["https:","http:"].includes(u.protocol)) throw new Error("Only web entry URLs may be interpreted");
  const p = u.searchParams;
  const stage = p.get("state");
  const anchor = p.get("anchor");
  const locale = p.get("locale");
  const geo = p.get("geo");
  // A URL parameter is never proof of identity, evidence or authorization.
  return Object.freeze({
    navigation_only: true,
    requested_state: STATES.includes(stage) ? stage : "TODAY",
    requested_anchor: ANCHORS.includes(anchor) ? anchor : null,
    locale_hint: ALLOWED_LOCALES.includes(locale) ? locale : "en",
    geo_pack_hint: geo && /^[a-z0-9-]{1,40}$/.test(geo) ? geo : null,
    effective_disclosure: "GUEST",
    admitted: false,
    booking_confirmed: false,
    evidence_verified: false,
    title_transferred: false,
    ignored_authority_inputs: ["buyer","disclosure","river","rights","role","verified","token"].filter(x=>p.has(x))
  });
}

export function buildPublicDoorLink(origin, {place="belgaum",asset="A-1204",state="TODAY",anchor=null,locale="en"}={}) {
  const root=new URL(origin);
  const local=["localhost","127.0.0.1"].includes(root.hostname);
  if(root.protocol!=="https:" && !(local && root.protocol==="http:")) throw new Error("Use HTTPS for publicly shared Door links");
  if(!SAFE_NAME.test(place) || !SAFE_NAME.test(asset)) throw new Error("Invalid place or asset reference");
  if(!STATES.includes(state)) throw new Error("Invalid stage");
  if(anchor!==null && !ANCHORS.includes(anchor)) throw new Error("Invalid anchor");
  const url=new URL("/estate/"+encodeURIComponent(place)+"/"+encodeURIComponent(asset)+"/door",root);
  url.searchParams.set("entry","vsr-door");
  url.searchParams.set("state",state);
  if(anchor!==null) url.searchParams.set("anchor",anchor);
  if(ALLOWED_LOCALES.includes(locale) && locale!=="en") url.searchParams.set("locale",locale);
  return url.toString();
}
