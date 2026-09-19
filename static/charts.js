new Chart(document.getElementById("confidenceChart"),{
type:"doughnut",
data:{
labels:["Confidence","Remaining"],
datasets:[{
data:[98,2]
}]
}
});

new Chart(document.getElementById("qualityChart"),{
type:"radar",
data:{
labels:["Focus","Blur","Contrast","Brightness","Sharpness"],
datasets:[{
data:[98,95,97,96,99]
}]
}
});

new Chart(document.getElementById("featureChart"),{
type:"bar",
data:{
labels:["CNN","LBP","Gabor","GLCM"],
datasets:[{
data:[98,95,92,97]
}]
}
});

new Chart(document.getElementById("trendChart"),{
type:"line",
data:{
labels:["Capture","Detect","Segment","CNN","Match"],
datasets:[{
data:[90,94,96,98,99]
}]
}
});