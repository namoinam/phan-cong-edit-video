// Nam ơi Nam — Landing Page JS

// Navbar scroll
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  navbar.classList.toggle('scrolled', window.scrollY > 40);
}, { passive: true });

// Burger menu — uses separate overlay outside nav stacking context
const burger = document.getElementById('burger');
const mobileMenu = document.getElementById('mobile-menu');
const mobileMenuClose = document.getElementById('mobile-menu-close');

function openMenu() { mobileMenu.classList.add('open'); document.body.style.overflow = 'hidden'; }
function closeMenu() { mobileMenu.classList.remove('open'); document.body.style.overflow = ''; }

burger.addEventListener('click', openMenu);
mobileMenuClose.addEventListener('click', closeMenu);
mobileMenu.querySelectorAll('a').forEach(a => a.addEventListener('click', closeMenu));
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeMenu(); });

// Scroll reveal
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); revealObserver.unobserve(e.target); } });
}, { threshold: 0.12, rootMargin: '0px 0px -50px 0px' });

document.querySelectorAll('.stat-card, .content-card, .collab-card, .channel-card, .trust-item, .about-left, .about-right').forEach(el => {
  el.classList.add('reveal');
  revealObserver.observe(el);
});

// Counter animation
function animateCount(el, target) {
  const isM = target >= 1000000;
  const isK = target >= 1000 && target < 1000000;
  const duration = 1800;
  const start = performance.now();

  function update(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    const val = Math.floor(target * eased);
    if (isM) {
      el.textContent = (val / 1000000).toFixed(1) + 'M';
    } else if (isK) {
      el.textContent = (val / 1000).toFixed(1) + 'K';
    } else {
      el.textContent = val.toLocaleString('vi-VN');
    }
    if (progress < 1) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
}

const counterObserver = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      const el = e.target;
      const target = parseInt(el.dataset.target);
      if (target) animateCount(el, target);
      counterObserver.unobserve(el);
    }
  });
}, { threshold: 0.5 });

document.querySelectorAll('.stat-big[data-target]').forEach(el => counterObserver.observe(el));

// Active nav on scroll
const sections = document.querySelectorAll('section[id]');
window.addEventListener('scroll', () => {
  let current = '';
  sections.forEach(s => { if (window.scrollY >= s.offsetTop - 120) current = s.id; });
  document.querySelectorAll('.nav-links a').forEach(a => {
    a.style.color = a.getAttribute('href') === '#' + current ? '#1456F0' : '';
  });
}, { passive: true });

// =============================================
// SURVEY FORM (DAY 6)
// =============================================
const surveyModal = document.getElementById('survey-modal');

window.handleSurveySubmit = function(event) {
  event.preventDefault();
  
  const name = document.getElementById('surveyName').value;
  const phone = document.getElementById('surveyPhone').value;
  const room = document.getElementById('surveyRoom').value;
  const budget = document.getElementById('surveyBudget').value;
  const trouble = document.getElementById('surveyTrouble').value;
  const interest = document.getElementById('surveyInterest').value;
  const channel = document.getElementById('surveyChannel').value;
  
  const data = {
    name,
    phone,
    room,
    budget,
    trouble,
    interest,
    channel,
    timestamp: new Date().toISOString()
  };
  
  // Save to localStorage
  const existing = JSON.parse(localStorage.getItem('survey_leads') || '[]');
  existing.push(data);
  localStorage.setItem('survey_leads', JSON.stringify(existing));
  
  console.log("Survey submitted successfully:", data);
  
  // Open success modal
  surveyModal.classList.add('open');
};

window.closeSurveyModal = function() {
  surveyModal.classList.remove('open');
  document.getElementById('survey-form').reset();
};
