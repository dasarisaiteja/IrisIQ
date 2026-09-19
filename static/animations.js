// =========================================
// IRIS AI LANDING PAGE ANIMATIONS
// Part - 1
// =========================================

// Navbar Scroll Effect

const navbar = document.querySelector(".navbar");

window.addEventListener("scroll", () => {

    if (window.scrollY > 50) {

        navbar.style.background = "rgba(11,19,43,.95)";
        navbar.style.backdropFilter = "blur(15px)";
        navbar.style.boxShadow = "0 10px 35px rgba(0,0,0,.25)";
        navbar.style.padding = "12px 0";

    }
    else {

        navbar.style.background = "#0b132b";
        navbar.style.boxShadow = "none";
        navbar.style.padding = "18px 0";

    }

});

// =========================================
// Smooth Scroll
// =========================================

document.querySelectorAll('a[href^="#"]').forEach(anchor => {

    anchor.addEventListener("click", function (e) {

        e.preventDefault();

        const target = document.querySelector(
            this.getAttribute("href")
        );

        if (target) {

            target.scrollIntoView({

                behavior: "smooth"

            });

        }

    });

});

// =========================================
// Counter Animation
// =========================================

const counters = document.querySelectorAll(".counter");

const counterObserver = new IntersectionObserver(entries => {

    entries.forEach(entry => {

        if (!entry.isIntersecting)
            return;

        const counter = entry.target;

        const target = Number(counter.dataset.target);

        let count = 0;

        const speed = target / 120;

        const update = () => {

            count += speed;

            if (count < target) {

                counter.innerHTML = Math.floor(count);

                requestAnimationFrame(update);

            }
            else {

                counter.innerHTML = target;

            }

        };

        update();

        counterObserver.unobserve(counter);

    });

});

counters.forEach(c => counterObserver.observe(c));

// =========================================
// Reveal Animation
// =========================================

const revealItems = document.querySelectorAll(

    ".feature-card,.tech-card,.step-box,.contact-box"

);

const revealObserver = new IntersectionObserver(entries => {

    entries.forEach(entry => {

        if (entry.isIntersecting) {

            entry.target.style.opacity = "1";

            entry.target.style.transform = "translateY(0px)";

        }

    });

}, {

    threshold: .15

});

revealItems.forEach(item => {

    item.style.opacity = "0";

    item.style.transform = "translateY(60px)";

    item.style.transition = ".7s";

    revealObserver.observe(item);

});

// =========================================
// Hero Image Parallax
// =========================================

const hero = document.querySelector(".hero-image");

window.addEventListener("mousemove", e => {

    if (!hero)
        return;

    const x = (window.innerWidth / 2 - e.pageX) / 40;

    const y = (window.innerHeight / 2 - e.pageY) / 40;

    hero.style.transform =
        `translate(${x}px,${y}px)`;

});

// =========================================
// Floating Animation
// =========================================

setInterval(() => {

    if (!hero)
        return;

    hero.animate([

        {

            transform: "translateY(0px)"

        },

        {

            transform: "translateY(-15px)"

        },

        {

            transform: "translateY(0px)"

        }

    ], {

        duration: 4000

    });

}, 4000);

// =========================================
// Button Ripple Effect
// =========================================

document.querySelectorAll(".btn").forEach(btn => {

    btn.addEventListener("click", function (e) {

        const ripple = document.createElement("span");

        ripple.style.position = "absolute";

        ripple.style.width = "20px";

        ripple.style.height = "20px";

        ripple.style.borderRadius = "50%";

        ripple.style.background = "rgba(255,255,255,.5)";

        ripple.style.left =

            e.offsetX + "px";

        ripple.style.top =

            e.offsetY + "px";

        ripple.style.transform =

            "translate(-50%,-50%)";

        ripple.style.animation =

            "ripple .7s linear";

        this.appendChild(ripple);

        setTimeout(() => {

            ripple.remove();

        }, 700);

    });

});

console.log("Animations Loaded");
// =========================================
// PART - 2
// Premium Animations
// =========================================

// Mouse Glow

const glow = document.createElement("div");

glow.style.position = "fixed";
glow.style.width = "250px";
glow.style.height = "250px";
glow.style.borderRadius = "50%";
glow.style.background =
"radial-gradient(circle,rgba(0,212,255,.25),transparent 70%)";
glow.style.pointerEvents = "none";
glow.style.zIndex = "0";
glow.style.transition = ".08s";

document.body.appendChild(glow);

window.addEventListener("mousemove", e => {

    glow.style.left = (e.pageX - 125) + "px";
    glow.style.top = (e.pageY - 125) + "px";

});

// =========================================
// Technology Cards
// =========================================

document.querySelectorAll(".tech-card").forEach(card => {

    card.addEventListener("mouseenter", () => {

        card.style.transform =
        "translateY(-15px) rotateY(10deg) scale(1.05)";

        card.style.boxShadow =
        "0 25px 50px rgba(13,110,253,.35)";

    });

    card.addEventListener("mouseleave", () => {

        card.style.transform = "";

        card.style.boxShadow = "";

    });

});

// =========================================
// Feature Cards
// =========================================

document.querySelectorAll(".feature-card").forEach(card => {

    card.addEventListener("mouseenter", () => {

        card.style.transform =
        "translateY(-15px) scale(1.05)";

    });

    card.addEventListener("mouseleave", () => {

        card.style.transform = "";

    });

});

// =========================================
// Floating Icons
// =========================================

document.querySelectorAll(".feature-card i").forEach(icon => {

    icon.animate([

        { transform:"translateY(0px)" },

        { transform:"translateY(-12px)" },

        { transform:"translateY(0px)" }

    ],{

        duration:2500,

        iterations:Infinity

    });

});

// =========================================
// Hero Background Animation
// =========================================

const heroSection = document.querySelector(".hero-section");

let angle = 120;

setInterval(()=>{

    angle++;

    if(heroSection){

        heroSection.style.background =
        `linear-gradient(${angle}deg,#eef7ff,#dcefff,#ffffff)`;

    }

},120);

// =========================================
// Scroll Progress
// =========================================

const progress = document.createElement("div");

progress.style.position="fixed";
progress.style.left="0";
progress.style.top="0";
progress.style.height="5px";
progress.style.background="#00d4ff";
progress.style.width="0%";
progress.style.zIndex="99999";

document.body.appendChild(progress);

window.addEventListener("scroll",()=>{

    const total =
    document.documentElement.scrollHeight -
    window.innerHeight;

    const current =
    (window.scrollY/total)*100;

    progress.style.width=current+"%";

});
// ================= Statistics Counter =================

window.addEventListener("load", () => {

    const stats = document.querySelectorAll(".bg-primary .display-4");

    const values = [
        { end: 99.8, suffix: "%" },
        { end: 0.8, suffix: "s" },
        { end: 5000, suffix: "+" },
        { end: 24, suffix: "/7" }
    ];

    stats.forEach((item, index) => {

        let current = 0;
        const target = values[index].end;
        const increment = target / 80;

        function animate() {

            current += increment;

            if (current < target) {

                if (target >= 1000) {

                    item.innerHTML = Math.floor(current);

                }
                else {

                    item.innerHTML = current.toFixed(1);

                }

                requestAnimationFrame(animate);

            }
            else {

                item.innerHTML = target + values[index].suffix;

            }

        }

        item.innerHTML = "0";

        animate();

    });

});
// =========================================
// Back To Top
// =========================================

const topBtn=document.createElement("button");

topBtn.innerHTML="↑";

topBtn.style.position="fixed";
topBtn.style.right="25px";
topBtn.style.bottom="25px";
topBtn.style.width="55px";
topBtn.style.height="55px";
topBtn.style.border="none";
topBtn.style.borderRadius="50%";
topBtn.style.background="#0d6efd";
topBtn.style.color="#fff";
topBtn.style.fontSize="22px";
topBtn.style.cursor="pointer";
topBtn.style.display="none";
topBtn.style.zIndex="999";

document.body.appendChild(topBtn);

window.addEventListener("scroll",()=>{

    if(window.scrollY>400){

        topBtn.style.display="block";

    }
    else{

        topBtn.style.display="none";

    }

});

topBtn.onclick=()=>{

    window.scrollTo({

        top:0,

        behavior:"smooth"

    });

};

// =========================================
// Button Hover Pulse
// =========================================

document.querySelectorAll(".btn").forEach(btn=>{

    btn.addEventListener("mouseenter",()=>{

        btn.animate([

            {transform:"scale(1)"},

            {transform:"scale(1.08)"},

            {transform:"scale(1)"}

        ],{

            duration:600

        });

    });

});

// =========================================
// Hero Text Fade
// =========================================

const heroTitle=document.querySelector(".display-3");

if(heroTitle){

    heroTitle.animate([

        {

            opacity:0,

            transform:"translateY(60px)"

        },

        {

            opacity:1,

            transform:"translateY(0px)"

        }

    ],{

        duration:1500

    });

}

console.log("Premium Animations Loaded");