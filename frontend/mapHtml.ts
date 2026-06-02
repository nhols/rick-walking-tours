type Stop = {
  id: string;
  order: number;
  title: string;
  position: { lat: number; lon: number };
};

type Tour = {
  map: { center: { lat: number; lon: number } };
  stops: Stop[];
};

export function mapHtml(tour: Tour) {
  const stops = JSON.stringify(tour.stops);
  const center = JSON.stringify([tour.map.center.lon, tour.map.center.lat]);

  return `<!doctype html>
<html><head>
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<link href="https://unpkg.com/maplibre-gl@5.9.0/dist/maplibre-gl.css" rel="stylesheet">
<style>
html,body,#map{height:100%;margin:0;background:#eef1ed}
.marker{width:34px;height:34px;border-radius:17px;background:#111816;color:#fffdf7;border:3px solid #fffdf7;display:flex;align-items:center;justify-content:center;font:900 15px system-ui;box-shadow:0 4px 12px #0003}
.marker.selected{width:42px;height:42px;border-radius:21px;background:#c94738}
.maplibregl-ctrl-logo,.maplibregl-ctrl-attrib{opacity:.72}
</style></head><body><div id="map"></div>
<script src="https://unpkg.com/maplibre-gl@5.9.0/dist/maplibre-gl.js"></script>
<script>
const stops=${stops};
const map=new maplibregl.Map({
  container:'map',
  center:${center},
  zoom:15.1,
  attributionControl:true,
  style:'https://tiles.openfreemap.org/styles/bright'
});
map.addControl(new maplibregl.GeolocateControl({positionOptions:{enableHighAccuracy:true},trackUserLocation:true}),'bottom-left');
const markers={};
let selected=stops[0]?.id;
function selectStop(id){
  selected=id;
  Object.entries(markers).forEach(([markerId,el])=>el.classList.toggle('selected',markerId===selected));
}
stops.forEach(stop=>{
  const el=document.createElement('button');
  markers[stop.id]=el;
  el.className='marker';
  el.textContent=stop.order;
  el.onclick=()=>{selectStop(stop.id);window.ReactNativeWebView?.postMessage(stop.id);parent.postMessage({type:'selectStop',id:stop.id},'*')};
  new maplibregl.Marker({element:el,anchor:'center'}).setLngLat([stop.position.lon,stop.position.lat]).addTo(map);
});
selectStop(selected);
window.addEventListener('message',event=>{
  if(event.data?.type==='selectStop') selectStop(event.data.id);
  if(typeof event.data==='string') {
    try {
      const data=JSON.parse(event.data);
      if(data.type==='selectStop') selectStop(data.id);
    } catch {}
  }
});
map.fitBounds(stops.reduce((b,s)=>b.extend([s.position.lon,s.position.lat]),new maplibregl.LngLatBounds()),{padding:{top:145,bottom:210,left:44,right:44},duration:0});
</script></body></html>`;
}
