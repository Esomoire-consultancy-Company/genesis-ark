// R0.6 fixture is deliberately non-admissible.
// REAL deployments must supply a verified server-controlled asset registry.
export const a1204Registry = Object.freeze({
  asset_ref:"A-1204",resource_ref:"ESTATE:UNVERIFIED:A-1204",
  door_ref:"VSR:BELGAUM:A-1204:DOOR",
  room_ref:"VSR:BELGAUM:A-1204:ROOM",
  status:"DRAFT_UNVERIFIED",
  live_enabled:false,
  max_disclosure:"GUEST",
  states:["TODAY","PLANNED","FINISHED","CONFIGURED","DELIVERED"],
  anchors:["FLOOR_01","ARCH_01","GLAZE_01","KITCHEN_01","BALC_01","LIGHT_01"]
});
export const a1204DraftRegistry={
  async get(id){return id==="A-1204"?a1204Registry:null;}
};
