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
.locate-error{position:absolute;left:54px;bottom:32px;z-index:2;max-width:260px;padding:9px 11px;border-radius:6px;background:#111816;color:#fffdf7;font:700 12px system-ui;box-shadow:0 4px 14px #0004;opacity:0;pointer-events:none;transition:opacity .15s}
.locate-error.visible{opacity:1}
.user-location{width:18px;height:18px;border-radius:50%;background:#2586ff;border:3px solid #fff;box-shadow:0 0 0 7px #2586ff26,0 2px 10px #0005}
.maplibregl-ctrl-logo,.maplibregl-ctrl-attrib{opacity:.72}
</style></head><body><div id="map"></div><div class="locate-error" role="status"></div>
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
const markers={};
let selected=stops[0]?.id;
let userLocationMarker;
function selectStop(id){
  selected=id;
  Object.entries(markers).forEach(([markerId,el])=>el.classList.toggle('selected',markerId===selected));
}
function showLocateError(message='Location unavailable'){
  const error=document.querySelector('.locate-error');
  if(error){
    error.textContent=message;
    error.classList.add('visible');
    window.setTimeout(()=>error.classList.remove('visible'),3500);
  }
}
function updateUserLocation(lat,lon){
  const coords=[lon,lat];
  if(!userLocationMarker){
    const el=document.createElement('div');
    el.className='user-location';
    userLocationMarker=new maplibregl.Marker({element:el,anchor:'center'}).setLngLat(coords).addTo(map);
  } else {
    userLocationMarker.setLngLat(coords);
  }
  map.flyTo({center:coords,zoom:Math.max(map.getZoom(),16),duration:700});
}
function fitTour(duration=0){
  if(!stops.length) return;
  map.fitBounds(
    stops.reduce((b,s)=>b.extend([s.position.lon,s.position.lat]),new maplibregl.LngLatBounds()),
    {padding:{top:145,bottom:210,left:44,right:44},duration}
  );
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
function handleMessage(data){
  if(data?.type==='selectStop') selectStop(data.id);
  if(data?.type==='recenterTour') fitTour(700);
  if(data?.type==='userLocation') updateUserLocation(data.lat,data.lon);
  if(data?.type==='userLocationError') showLocateError(data.message);
}
function handleMessageEvent(event){
  handleMessage(event.data);
  if(typeof event.data==='string') {
    try {
      const data=JSON.parse(event.data);
      handleMessage(data);
    } catch {}
  }
}
window.receiveMapMessage=handleMessage;
window.addEventListener('message',handleMessageEvent);
document.addEventListener('message',handleMessageEvent);
fitTour();
</script></body></html>`;
}
