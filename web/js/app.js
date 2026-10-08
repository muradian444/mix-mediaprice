// Mix Media web · գործարկում, մուտք, մենյու, երթուղիներ
import { $, S, api, clear, h, loader, onLang, setLang, setTheme, t, toast } from './core.js';
import * as home from './sections/home.js';
import * as stores from './sections/stores.js';
import * as contracts from './sections/contracts.js';
import * as plan from './sections/plan.js';
import * as act from './sections/act.js';
import * as kp from './sections/kp.js';
import * as law from './sections/law.js';
import * as techmon from './sections/techmon.js';
import * as quarterly from './sections/quarterly.js';
import * as warehouse from './sections/warehouse.js';
import * as vault from './sections/vault.js';
import * as editor from './sections/editor.js';
import * as voice from './sections/voice.js';
import * as settings from './sections/settings.js';
import { initFixik, setFixikSection } from './sections/fixik.js';

const SECTIONS = [
  { ...home, id: 'home', icon: '🏠', group: null },
  { ...vault, id: 'vault', icon: '👤', group: null },
  { ...stores, id: 'stores', icon: '🏪', group: 'nav.ads' },
  { ...contracts, id: 'contracts', icon: '📄', group: 'nav.docs' },
  { ...plan, id: 'plan', icon: '📊', group: 'nav.docs' },
  { ...act, id: 'act', icon: '🧾', group: 'nav.docs' },
  { ...kp, id: 'kp', icon: '💼', group: 'nav.docs' },
  { ...editor, id: 'editor', icon: '✏️', group: 'nav.docs' },
  { ...techmon, id: 'techmon', icon: '📡', group: 'nav.work' },
  { ...quarterly, id: 'quarterly', icon: '📈', group: 'nav.work' },
  { ...warehouse, id: 'warehouse', icon: '🏷', group: 'nav.work' },
  { ...law, id: 'law', icon: '⚖️', group: 'nav.system' },
  { ...voice, id: 'voice', icon: '🎙', group: 'nav.system' },
  { ...settings, id: 'settings', icon: '⚙️', group: 'nav.system' },
];
const BY_ID = Object.fromEntries(SECTIONS.map(s => [s.id, s]));
S.nav = SECTIONS;
let renderSeq = 0;

/* ---------------------------------------------------------------- մենյու */
function buildNav() {
  const nav = clear($('#nav'));
  let group;
  SECTIONS.forEach(s => {
    if (s.group !== group) {
      group = s.group;
      if (group) nav.append(h('div', { class: 'group', text: t(group) }));
    }
    nav.append(h('button', {
      class: `navitem${S.section === s.id ? ' active' : ''}`,
      dataset: { id: s.id },
      onClick: () => go(s.id),
    }, h('span', { class: 'ic', text: s.icon }), h('span', { text: t('sec.' + s.id) }),
      s.badge ? h('span', { class: 'cnt', text: s.badge() }) : null));
  });
}
function markNav() {
  document.querySelectorAll('.navitem').forEach(b => b.classList.toggle('active', b.dataset.id === S.section));
}

/* ---------------------------------------------------------------- երթուղի */
export function go(id, params) {
  const sec = BY_ID[id] ? id : 'home';
  const hash = `#/${sec}${params ? '?' + new URLSearchParams(params) : ''}`;
  if (location.hash !== hash) { location.hash = hash; return; }
  render(sec, params);
}
function parseHash() {
  const raw = location.hash.replace(/^#\/?/, '');
  const [id, qs] = raw.split('?');
  return { id: BY_ID[id] ? id : 'home', params: Object.fromEntries(new URLSearchParams(qs || '')) };
}
async function render(id, params) {
  const sec = BY_ID[id] || BY_ID.home;
  const seq = ++renderSeq;            // արագ սեղմումների դեպքում հին էջը չի փոխարինում նորին
  S.section = sec.id;
  markNav();
  document.body.classList.remove('nav-open');
  $('#page-title').textContent = t('sec.' + sec.id);
  $('#page-sub').textContent = sec.sub ? sec.sub() : '';
  setFixikSection(sec.id);
  const view = $('#view');
  const slow = setTimeout(() => {
    if (seq === renderSeq) clear(view).append(h('div', { class: 'card skeleton' }, t('word.loading')));
  }, 160);
  try {
    const node = await sec.render(params || {});
    clearTimeout(slow);
    if (seq !== renderSeq) return;
    clear(view).append(node);
    window.scrollTo({ top: 0, behavior: 'instant' });
  } catch (e) {
    clearTimeout(slow);
    if (seq !== renderSeq || e.status === 401) return;
    console.error(e);
    clear(view).append(h('div', { class: 'card' },
      h('h2', { text: '⚠️ ' + (S.lang === 'ru' ? 'Раздел не открылся' : 'Բաժինը չբացվեց') }),
      h('p', { class: 'small', text: String(e.message || e) }),
      h('button', { class: 'btn primary', onClick: () => render(id, params) }, t('btn.refresh'))));
    api('/api/client-error', { method: 'POST', quiet: true, body: { message: `${id}: ${e.message}`, stack: String(e.stack || '') } }).catch(() => {});
  }
}

/* ---------------------------------------------------------------- մուտք */
let waitTimer = null;
function loginScreen(mode = 'login', note = '') {
  $('#shell').hidden = true;
  $('#fixik-btn').hidden = true;
  $('#fixik').hidden = true;
  $('#login').hidden = false;
  $('#login-form').hidden = mode !== 'login';
  $('#register-form').hidden = mode !== 'register';
  $('#wait-box').hidden = mode !== 'wait';
  $('#login-err').textContent = note || '';
  if (mode !== 'wait' && waitTimer) { clearInterval(waitTimer); waitTimer = null; }
  if (mode === 'login') setTimeout(() => $('#login-user').focus(), 50);
}
function waitScreen(info) {
  loginScreen('wait');
  const blocked = info?.state === 'blocked';
  $('#wait-title').textContent = blocked ? 'Մուտքը արգելափակված է / Доступ закрыт' : 'Սպասում ենք հաստատմանը / Ждём подтверждения';
  $('#wait-text').textContent = blocked
    ? 'Դիմեք ադմինին / Обратитесь к администратору.'
    : `Ձեր հարցումը (${info?.user?.login || ''}) ուղարկված է ադմինին: Հաստատելուց հետո էջը կբացվի ինքնաբերաբար: / `
      + `Запрос (${info?.user?.login || ''}) отправлен администратору. После подтверждения страница откроется сама.`;
  $('#wait-ip').textContent = `IP: ${info?.ip || '—'}`;
  if (!blocked && !waitTimer) {
    waitTimer = setInterval(async () => {
      try {
        const me = await api('/api/me', { quiet: true, noauth: true });
        if (me.state === 'active') { clearInterval(waitTimer); waitTimer = null; boot(); }
        else if (me.state === 'none') { clearInterval(waitTimer); waitTimer = null; loginScreen('login'); }
      } catch (e) { /* սերվերը կարող է վերագործարկվել */ }
    }, 4000);
  }
}

async function boot() {
  S.lang = localStorage.getItem('mm_lang') || 'hy';
  S.theme = localStorage.getItem('mm_theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.dataset.theme = S.theme;
  $('#theme-btn').textContent = S.theme === 'dark' ? '☀️' : '🌙';
  document.querySelectorAll('#lang-seg button').forEach(b => b.classList.toggle('on', b.dataset.lang === S.lang));
  let me;
  try {
    me = await api('/api/me', { quiet: true, noauth: true });
  } catch (e) {
    loginScreen('login', e.message);
    return;
  }
  if (me.state === 'pending' || me.state === 'blocked') { waitScreen(me); return; }
  if (me.state !== 'active') { loginScreen('login'); return; }
  try {
    S.meta = await api('/api/meta', { quiet: true });
  } catch (e) {
    if (e.status !== 401) loginScreen('login', e.message);
    return;
  }
  S.user = S.meta.user;
  const prefs = S.user?.prefs || {};
  if (prefs.lang && !localStorage.getItem('mm_lang')) S.lang = prefs.lang;
  if (prefs.theme && !localStorage.getItem('mm_theme')) {
    S.theme = prefs.theme;
    document.documentElement.dataset.theme = S.theme;
  }
  $('#login').hidden = true;
  $('#shell').hidden = false;
  $('#fixik-btn').hidden = false;
  $('#sfoot-company').textContent = S.meta.company?.name || 'Mix Media';
  $('#sfoot-ver').textContent = `v${S.meta.version} · ${S.meta.company?.site || ''}`;
  $('#logout-btn').hidden = false;
  $('#user-name').textContent = S.user?.name || S.user?.login || '';
  $('#user-av').textContent = (S.user?.name || S.user?.login || '?').trim().charAt(0).toUpperCase();
  $('#user-chip').title = `${S.user?.login} · ${S.user?.role === 'admin' ? 'admin' : 'user'} · IP ${S.meta.ip || ''}`;
  document.documentElement.lang = S.lang;
  buildNav();
  initFixik();
  const { id, params } = parseHash();
  render(id, params);
  if (!S.meta.pdf?.ready && !sessionStorage.getItem('mm_pdf_warned')) {
    sessionStorage.setItem('mm_pdf_warned', '1');
    toast(S.lang === 'ru'
      ? 'PDF-конвертер не найден: договоры и АКТ будут в Word (.docx). Печать работает через кнопку «Печать».'
      : 'PDF փոխարկիչ չկա՝ պայմանագիրը և ԱԿՏ-ը կստացվեն Word-ով: Տպելը աշխատում է «Տպել» կոճակով:', 'warn');
  }
}

/* ---------------------------------------------------------------- իրադարձություններ */
window.addEventListener('hashchange', () => { if (!S.meta) return; const { id, params } = parseHash(); render(id, params); });
document.addEventListener('mm:auth', e => {
  const st = e.detail?.state;
  S.meta = null;
  if (st === 'pending' || st === 'blocked') { api('/api/me', { quiet: true, noauth: true }).then(waitScreen).catch(() => loginScreen('login')); return; }
  loginScreen('login', S.lang === 'ru' ? 'Сессия закрыта, войдите снова' : 'Մտեք կրկին / Войдите снова');
});
onLang(() => { if (!S.meta) return; buildNav(); const { id, params } = parseHash(); render(id, params); });

document.addEventListener('DOMContentLoaded', () => {
  $('#burger').addEventListener('click', () => document.body.classList.toggle('nav-open'));
  $('#theme-btn').addEventListener('click', () => setTheme(S.theme === 'dark' ? 'light' : 'dark'));
  document.querySelectorAll('#lang-seg button').forEach(b => b.addEventListener('click', () => setLang(b.dataset.lang)));
  const logout = async () => {
    await api('/api/logout', { method: 'POST', body: {}, quiet: true, noauth: true }).catch(() => {});
    location.hash = '';
    location.reload();
  };
  $('#logout-btn').addEventListener('click', logout);
  $('#wait-logout').addEventListener('click', logout);
  $('#to-register').addEventListener('click', () => loginScreen('register'));
  $('#to-login').addEventListener('click', () => loginScreen('login'));
  $('#login-form').addEventListener('submit', async e => {
    e.preventDefault();
    $('#login-err').textContent = '';
    try {
      loader(true);
      const r = await api('/api/login', { method: 'POST', quiet: true, noauth: true,
        body: { login: $('#login-user').value, password: $('#login-pass').value } });
      $('#login-pass').value = '';
      if (r.state === 'active') boot();
      else waitScreen(await api('/api/me', { quiet: true, noauth: true }));
    } catch (err) {
      $('#login-err').textContent = err.message;
    } finally { loader(false); }
  });
  $('#register-form').addEventListener('submit', async e => {
    e.preventDefault();
    $('#login-err').textContent = '';
    if ($('#reg-pass').value !== $('#reg-pass2').value) {
      $('#login-err').textContent = 'Գաղտնաբառերը չեն համընկնում / Пароли не совпадают';
      return;
    }
    try {
      loader(true);
      await api('/api/register', { method: 'POST', quiet: true, noauth: true, body: {
        name: $('#reg-name').value, login: $('#reg-login').value.trim().toLowerCase(), password: $('#reg-pass').value } });
      waitScreen(await api('/api/me', { quiet: true, noauth: true }));
    } catch (err) {
      $('#login-err').textContent = err.message;
    } finally { loader(false); }
  });
  document.body.addEventListener('click', e => {
    const a = e.target.closest('[data-go]');
    if (a) { e.preventDefault(); go(a.dataset.go); }
  });
  window.addEventListener('error', ev => {
    if (!S.meta) return;
    api('/api/client-error', { method: 'POST', quiet: true,
      body: { message: String(ev.message), stack: `${ev.filename}:${ev.lineno}` } }).catch(() => {});
  });
  window.addEventListener('unhandledrejection', ev => {
    const e = ev.reason;
    if (!S.meta || !e || e.name === 'ApiError' || e.status !== undefined) return;   // API-ի սխալները արդեն ցույց են տրված
    api('/api/client-error', { method: 'POST', quiet: true,
      body: { message: 'promise: ' + String(e.message || e), stack: String(e.stack || '') } }).catch(() => {});
  });
  boot();
});

export function reload() { const { id, params } = parseHash(); render(id, params); }
window.MM = { go, reload, S };
