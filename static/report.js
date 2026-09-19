(() => {
"use strict";
const params=new URLSearchParams(location.search);
const reportId=params.get("report_id");
const API_URL=reportId?"/report?report_id="+encodeURIComponent(reportId):"/report";
const $=id=>document.getElementById(id);
function text(id,v){const e=$(id);if(e)e.innerText=v===undefined||v===null||v===""?"-":v}
function num(v,d=0){const n=Number(v);return Number.isFinite(n)?n:d}
function pct(v){return Math.max(0,Math.min(100,num(v)))}
function fmtPct(v){return Number.isFinite(Number(v))?Number(v).toFixed(1)+"%":"-"}
function path(v){
    if(!v) return "";
    let x=String(v).replace(/\\\\/g,"/");
    x=x.replace("/root/iris-ai-v2/ai-server/uploads/","/uploads/");
    x=x.replace("/root/iris-ai-v2/ai-server/outputs/","/outputs/");
    if(x.startsWith("outputs/")) x="/"+x;
    if(x.startsWith("uploads/")) x="/"+x;
    return x;
}
function image(id,v){const e=$(id),s=path(v);if(e&&s){e.src=s;e.onerror=()=>{e.removeAttribute("src");e.alt="Image unavailable"}}}
function first(...a){return a.find(v=>v!==undefined&&v!==null&&v!=="")}
function numbers(v,o=[]){if(typeof v==="number"&&Number.isFinite(v))o.push(v);else if(Array.isArray(v))v.forEach(x=>numbers(x,o));else if(v&&typeof v==="object")Object.values(v).forEach(x=>numbers(x,o));return o}
function stats(r){const a=[];[r?.cnn_embedding,r?.features,r?.glcm,r?.entropy,r?.color_analysis,r?.iris,r?.meta].forEach(v=>numbers(v,a));if(!a.length)return{mean:.5,std:.15,count:0};const m=a.reduce((x,y)=>x+y,0)/a.length;const variance=a.reduce((x,y)=>x+(y-m)**2,0)/a.length;const s=Math.sqrt(variance);return{mean:1/(1+Math.exp(-m)),std:1/(1+Math.exp(-s)),count:a.length}}
function score(base,off=0){return Math.round(Math.max(0,Math.min(100,base+off)))}
function demo(r,v){const s=stats(r),sim=pct(v?.similarity),conf=pct(v?.confidence),feature=(s.mean*.65+(1-Math.min(s.std,1))*.35)*100,base=sim*.55+conf*.25+feature*.20;return{
neuroStrength:score(base),neuroConsistency:score(base,(1-s.std)*8-4),neuroStability:score(base,s.mean*6-3),
leadership:score(base,2),confidence:score(base,3),creativity:score(base,-1),adaptability:score(base,1),decision:score(base,2),
team:score(base),career:score(base,2),habits:score(base,-2),emotionalStability:score(base,1),emotionalRegulation:score(base),stressHandling:score(base,-1),social:score(base,1),communication:score(base,2),socialConfidence:score(base,3)}}
function setScore(bar,val,v){v=pct(v);const b=$(bar);if(b){b.style.width=v+"%";b.innerText=v.toFixed(0)+"%"}text(val,v.toFixed(0)+"%")}
function json(v){if(v==null)return"-";if(typeof v==="string")return v;try{return JSON.stringify(v)}catch(_){return String(v)}}
function timeline(v){const t=$("timeline");if(!t)return;[["Camera Capture","Completed"],["YOLO Iris Detection","Completed"],["Iris Segmentation","Completed"],["Iris Normalization","Completed"],["CNN Feature Extraction","Completed"],["Biometric Verification",v?.match_status||"Processed"]].forEach(()=>{});t.innerHTML=[["Camera Capture","Completed"],["YOLO Iris Detection","Completed"],["Iris Segmentation","Completed"],["Iris Normalization","Completed"],["CNN Feature Extraction","Completed"],["Biometric Verification",v?.match_status||"Processed"]].map(x=>`<div class="timeline-item border-bottom py-2">✅ <b>${x[0]}</b> — ${x[1]}</div>`).join("")}
async function loadReport(){
if(!reportId){alert("Missing report_id. Please open the report from the scan result.");return}
try{
const res=await fetch(API_URL,{cache:"no-store"});if(!res.ok)throw Error("HTTP "+res.status);const result=await res.json();if(!result.status||!result.report)throw Error("Invalid report response");
const r=result.report,e=r.employee||{},v=r.verification||{},i=r.iris||{},a=r.analysis||r,m=r.meta||{};
text("report_id",r.report_id||reportId);text("recognition_id",r.report_id||reportId);text("scan_date",r.scan_date);text("scan_time",r.scan_time);text("eye_side",r.eye_side||a.eye_side);text("similarity",fmtPct(v.similarity));text("match_status",v.match_status||"Processed");text("detection_confidence",fmtPct(a.detection_confidence));text("confidence",fmtPct(v.confidence));text("processing_status","Completed");
text("metric_similarity",fmtPct(v.similarity));text("metric_confidence",fmtPct(v.confidence));text("metric_status",v.match_status||"Processed");
text("bio_similarity",fmtPct(v.similarity));text("bio_confidence",fmtPct(v.confidence));text("bio_decision",v.match_status||"Processed");text("final_decision",v.match_status||"Processed");text("final_similarity",fmtPct(v.similarity));text("final_confidence",fmtPct(v.confidence));
const sim=pct(v.similarity),bar=$("similarity_progress");if(bar){bar.style.width=sim+"%";bar.innerText=sim.toFixed(1)+"%"}const st=String(v.match_status||"Processed");if($("header_status")){$("header_status").innerText=st.toUpperCase();$("header_status").className="badge rounded-pill px-3 py-2 "+(st.toLowerCase().includes("match")?"bg-success":"bg-danger")}
text("verification_note",st.toLowerCase().includes("match")?"The scanned biometric representation matched the enrolled reference according to the reported similarity threshold.":"The reported scan did not meet the matching condition.");
text("employee_name",e.employee_name);text("employee_code",e.employee_code);text("department",e.department);text("designation",e.designation);text("gender",e.gender);text("age",e.age);text("blood_group",e.blood_group);image("employee_photo",e.photo_path);
image("captured_eye",i.captured_image||i.original_image||i.capture_image||i.crop_image||r.captured_image||r.original_image||r.capture_image);
image("crop_image",i.crop_image||r.crop_image||r.detect?.crop_path);
image("segment_image",i.segmentation_image||r.segmentation_image||r.images?.segmentation);
image("normalized_image",i.normalized_image||r.normalized_image||r.images?.normalized);
image("lbp_image",i.lbp_image||r.lbp_image||r.images?.lbp);
image("gabor_image",i.gabor_image||r.gabor_image||r.images?.gabor);
const w=first(a.image_width,a.width,a.image_shape?.[1]),h=first(a.image_height,a.height,a.image_shape?.[0]);text("image_width",w);text("image_height",h);text("quality_detection",fmtPct(a.detection_confidence));text("quality_status",w&&h?"Usable":"Available");text("quality_note",w&&h?`Detected scan dimensions: ${w} × ${h}px. Feature availability is based on the current report payload.`:"Image dimensions were not included in the report payload.");
const f=a.features||r.features||{};text("pupil_radius",first(f.pupil_radius,f.pupilRadius,a.pupil_radius));text("iris_radius",first(f.iris_radius,f.irisRadius,a.iris_radius));text("entropy",first(a.entropy,r.entropy));text("eye_color", typeof a.eye_color === "object" ? (a.eye_color?.eye_color || a.eye_color?.name || "Unknown") : (a.eye_color || r.eye_color || "Unknown"));
const d=demo(r,v),s=stats(r);text("neuro_strength",d.neuroStrength+"%");text("neuro_consistency",d.neuroConsistency+"%");text("neuro_stability",d.neuroStability+"%");text("neuro_observation",`Current report contains ${s.count} numeric feature values. Neuro AI values are deterministic demonstration indicators, not brain activity measurements.`);
setScore("leadership_bar","leadership_value",d.leadership);setScore("confidence_bar","confidence_value",d.confidence);setScore("creativity_bar","creativity_value",d.creativity);setScore("adaptability_bar","adaptability_value",d.adaptability);setScore("decision_bar","decision_value",d.decision);
text("behaviour_leadership",d.leadership+"%");text("behaviour_team",d.team+"%");text("behaviour_career",d.career+"%");text("behaviour_habits",d.habits+"%");text("behaviour_profile",Math.round((d.leadership+d.team+d.career+d.habits)/4)+"%");text("behaviour_note","Deterministic demo indicator derived from current scan/verification inputs.");
text("emotional_stability",d.emotionalStability+"%");text("emotional_regulation",d.emotionalRegulation+"%");text("stress_handling",d.stressHandling+"%");text("emotional_note","Demonstration indicator only; no clinical or mental-health conclusion is made.");
text("social_interaction",d.social+"%");text("communication_score",d.communication+"%");text("social_confidence",d.socialConfidence+"%");text("social_note","Demonstration indicator only; no validated communication/personality test is being claimed.");
text("final_observation",st.toLowerCase().includes("match")?`Biometric verification completed with a similarity of ${fmtPct(v.similarity)} and confidence of ${fmtPct(v.confidence)}.`:`Biometric verification completed with a reported similarity of ${fmtPct(v.similarity)} and confidence of ${fmtPct(v.confidence)}.`);
timeline(v);
const g=$("employee_gallery");if(g){g.innerHTML="";const imgs=Array.isArray(e.images)?e.images:[];if(!imgs.length)g.innerHTML='<div class="col-12 text-muted">No enrollment images available.</div>';else imgs.forEach((x,n)=>{const src=path(x);if(src)g.insertAdjacentHTML("beforeend",`<div class="col-6 col-md-3 col-lg-2"><div class="image-card p-2"><img src="${src}" class="img-fluid rounded" style="width:100%;height:120px;object-fit:cover" alt="Enrollment image ${n+1}"><small class="text-muted d-block text-center mt-1">Image ${n+1}</small></div></div>`)})}
}catch(err){console.error("Report load error:",err);alert("Unable to load this report. Please verify the report ID.")}}
function waitImages(root){return Promise.all([...root.querySelectorAll("img")].map(x=>x.complete?Promise.resolve():new Promise(r=>{x.addEventListener("load",r,{once:true});x.addEventListener("error",r,{once:true})})))}
function pdf(){const root=$("reportRoot");if(!root||typeof html2pdf==="undefined"){window.print();return}waitImages(root).then(()=>html2pdf().set({margin:[.25,.25,.3,.25],filename:"Iris_AI_Report_"+(reportId||"Report")+".pdf",image:{type:"jpeg",quality:.95},html2canvas:{scale:2,useCORS:true,backgroundColor:"#fff",logging:false},pagebreak:{mode:["css","legacy"],avoid:[".no-break",".report-card",".image-card",".metric-tile","table"]},jsPDF:{unit:"in",format:"a4",orientation:"portrait",compress:true}}).from(root).save())}
document.addEventListener("DOMContentLoaded",()=>{$("downloadPdf")?.addEventListener("click",pdf);loadReport()});
})();