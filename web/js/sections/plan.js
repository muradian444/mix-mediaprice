// 📊 Մեդիա պլան՝ 6 քայլ, հասցեների ՈՐՈՆՈՒՄ, MP3 Drive-ից կամ ֆայլով
// + 📷 լրացում լուսանկարից/ֆայլից + պահված մեդիա պլանի բացում («✏️ Изменить»)
import { S, api, clear, clientSelect, debounce, emptyBox, field, filesResult, h, highlight,
  loader, modal, nextMonthRange, nf, photoButton, promptDlg, steps, t, toIso, toast } from '../core.js';

export const sub = () => S.lang === 'ru' ? 'Сетка выходов, адреса и ролики → PDF'
  : 'Հեռարձակման ցանց, հասցեներ և հոլովակներ → PDF';

const P = { client: '', start: '', end: '', picked: new Map(), slots: [], clips: [], assign: {}, step: 0, nets: [] };

const PHOTO_FIELDS = [
  { key: 'client', label: 'Customer (client) company name' },
  { key: 'start', type: 'date', label: 'Broadcast period start date' },
  { key: 'end', type: 'date', label: 'Broadcast period end date' },
  { key: 'times', label: 'Broadcast schedule', hint: "either a range like '9:20-23:50/30' (first-last/interval in minutes) or a list like '9:00, 13:00, 18:30'" },
  { key: 'addresses', type: 'list', label: 'Shop addresses where the ad plays', hint: 'one address per item; keep street and house number' },
  { key: 'clips', type: 'list', label: 'Audio clip names / titles' },
];

export async function render() {
  const L = S.lang === 'ru' ? 1 : 0;
  P.nets = await api('/api/networks');
  if (!P.start) { const [a, b] = nextMonthRange(); P.start = a; P.end = b; }
  const root = h('div');
  const bar = h('div');
  const body = h('div');
  const photo = photoButton({ section: 'Media plan (audio advertising schedule in shops)', fields: PHOTO_FIELDS,
    match: 'addresses', note: 'Media plan, order, e-mail or list from the customer.',
    onResult: res => { applyPhoto(res, L); draw(); } });
  const reset = h('button', { class: 'btn sm ghost', onClick: () => {
    Object.assign(P, { client: '', picked: new Map(), slots: [], clips: [], assign: {}, step: 0 });
    const [a, b] = nextMonthRange(); P.start = a; P.end = b; draw();
  } }, '🧹 ' + (L ? 'Новый' : 'Նոր'));
  root.append(h('div', { class: 'row', style: 'margin-bottom:12px' }, bar, h('div', { class: 'spacer' }), photo, reset), body);
  const NAMES = L
    ? ['Клиент', 'Период', 'Адреса', 'Часы', 'Ролики', 'Проверка']
    : ['Հաճախորդ', 'Ժամանակահատված', 'Հասցեներ', 'Ժամեր', 'Հոլովակներ', 'Ստուգում'];

  function draw() {
    clear(bar).append(steps(NAMES, P.step, i => { P.step = i; draw(); }));
    clear(body).append([stepClient, stepPeriod, stepAddr, stepTimes, stepClips, stepSummary][P.step](L, draw));
  }
  if (S.prefill?.section === 'plan') {
    applySaved(S.prefill.data || {}, L);
    S.prefill = null;
  }
  draw();
  return root;
}

/* առաջին չլրացված քայլը */
function firstMissing() {
  if (!P.client.trim()) return 0;
  if (!P.start || !P.end) return 1;
  if (![...P.picked.values()].some(s => s.size)) return 2;
  if (!P.slots.length) return 3;
  if (!P.clips.length) return 4;
  return 5;
}
function pick(ni, ai) {
  if (!P.picked.has(ni)) P.picked.set(ni, new Set());
  P.picked.get(ni).add(ai);
}
function addClip(name, extra = {}) {
  const nm = String(name || '').trim();
  if (!nm || P.clips.some(c => c.name === nm)) return;
  P.clips.push({ n: P.clips.length + 1, name: nm, file: extra.file || '', link: extra.link || null });
}
function unmatchedDlg(list, L) {
  if (!list?.length) return;
  modal({ title: '📍 ' + (L ? 'Не нашёл в списке сетей' : 'Չգտա ցանցերի ցուցակում'),
    body: h('div', {}, h('p', { class: 'small muted', text: L
      ? 'Эти адреса не совпали с адресами в «Настройках». Добавьте их в нужную сеть (шаг «Адреса» → сеть → «➕ Новый адрес») или выберите вручную.'
      : 'Այս հասցեները չհամընկան «Կարգավորումների» հասցեների հետ: Ավելացրեք դրանք ցանցում («Հասցեներ» քայլ → ցանց → «➕ Նոր հասցե») կամ ընտրեք ձեռքով:' }),
    h('textarea', { rows: String(Math.min(12, list.length + 1)), readonly: true }, list.join('\n'))) });
}

/* 📷 արդյունքը՝ մեդիա պլանում */
function applyPhoto(res, L) {
  const v = res.values || {};
  if (v.client) P.client = v.client;
  if (toIso(v.start)) P.start = toIso(v.start);
  if (toIso(v.end)) P.end = toIso(v.end);
  if (res.slots?.length) P.slots = res.slots;
  (res.matched || []).forEach(m => pick(m.net, m.addr));
  (v.clips || []).forEach(c => addClip(c));
  P.clips.forEach(c => { if (!P.assign[c.n]) P.assign[c.n] = 'all'; });
  P.step = firstMissing();
  if (res.matched?.length) toast(`📍 ${L ? 'Найдено адресов' : 'Գտնված հասցեներ'}: ${res.matched.length}`);
  unmatchedDlg(res.unmatched, L);
}

/* ✏️ պահված մեդիա պլան (PDF-ի մեջ պահված տվյալներ) */
function applySaved(d, L) {
  const norm = s => String(s || '').toLowerCase().replace(/[\s.,«»"'()\-–—/․]+/g, '');
  Object.assign(P, { client: d.client || '', picked: new Map(), slots: d.slots || [], clips: [], assign: {} });
  if (toIso(d.start)) P.start = toIso(d.start);
  if (toIso(d.end)) P.end = toIso(d.end);
  const missing = [];
  const keyOf = {};
  (d.addresses || []).forEach(a => {
    const want = norm(a.addr);
    let hit = null;
    const nets = a.net ? P.nets.filter(n => norm(n.name) === norm(a.net)) : [];
    for (const n of (nets.length ? nets : P.nets)) {
      const ai = n.addresses.findIndex(x => norm(x) === want);
      if (ai >= 0) { hit = [n.index, ai, n.name, n.addresses[ai]]; break; }
    }
    if (hit) { pick(hit[0], hit[1]); keyOf[`${a.net}|${a.addr}`] = `${hit[2]}|${hit[3]}`; }
    else missing.push(a.net ? `${a.addr} (${a.net})` : a.addr);
  });
  (d.clips || []).forEach(c => addClip(c.name, c));
  const total = (d.addresses || []).length;
  P.clips.forEach(c => {
    const using = (d.addresses || []).filter(a => (a.clips || [1]).includes(c.n));
    P.assign[c.n] = !total || using.length === total ? 'all'
      : using.map(a => keyOf[`${a.net}|${a.addr}`]).filter(Boolean);
    if (Array.isArray(P.assign[c.n]) && !P.assign[c.n].length) P.assign[c.n] = 'all';
  });
  P.step = firstMissing();
  toast(L ? 'Медиаплан открыт: измените нужное и создайте заново' : 'Մեդիա պլանը բացվեց՝ փոխեք և ստեղծեք նորից');
  unmatchedDlg(missing, L);
}

function navRow(L, draw, { next = true, nextLabel, disabled, onNext } = {}) {
  return h('div', { class: 'row', style: 'margin-top:14px' },
    P.step > 0 ? h('button', { class: 'btn', onClick: () => { P.step--; draw(); } }, '← ' + t('btn.back')) : null,
    h('div', { class: 'spacer' }),
    next ? h('button', { class: 'btn primary', disabled: !!disabled,
      onClick: () => { if (onNext && onNext() === false) return; P.step++; draw(); } },
    (nextLabel || t('btn.next')) + ' →') : null);
}

/* ------------------------------------------------ 1. հաճախորդ */
function stepClient(L, draw) {
  const { wrap, input } = clientSelect(P.client);
  input.addEventListener('input', () => { P.client = input.value; });
  const card = h('div', { class: 'card' },
    h('h2', { text: '👤 ' + t('word.client') }), h('div', { class: 'gradline' }),
    field(L ? 'Выберите из списка или впишите нового' : 'Ընտրեք ցանկից կամ մուտքագրեք նորը', wrap));
  card.append(navRow(L, draw, { onNext: () => {
    if (!P.client.trim()) { toast(L ? 'Укажите клиента' : 'Լրացրեք հաճախորդը', 'err'); return false; }
  } }));
  return card;
}

/* ------------------------------------------------ 2. ժամանակահատված */
function stepPeriod(L, draw) {
  const s = h('input', { type: 'date', value: P.start });
  const e = h('input', { type: 'date', value: P.end });
  const info = h('div', { class: 'badge plain' });
  const upd = () => {
    P.start = s.value; P.end = e.value;
    const d = days();
    info.textContent = d > 0 ? `${d} ${t('word.days')}` : '—';
    info.className = 'badge ' + (d > 0 && d <= MAX_DAYS ? 'ok' : 'err');
  };
  s.addEventListener('change', upd); e.addEventListener('change', upd);
  const quick = h('button', { class: 'btn sm' }, L ? 'Следующий месяц' : 'Հաջորդ ամիս');
  quick.addEventListener('click', () => { const [a, b] = nextMonthRange(); s.value = a; e.value = b; upd(); });
  // +N ամիս սկզբից (օր.՝ 01.10 → 31.12)
  const plus = n => h('button', { class: 'btn sm', onClick: () => {
    const a = s.value ? new Date(s.value) : new Date();
    const b = new Date(a.getFullYear(), a.getMonth() + n, a.getDate() - 1);
    const iso = d => `-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    s.value = iso(a); e.value = iso(b); upd();
  } }, n === 12 ? (L ? '1 год' : '1 տարի') : `+${n} ${L ? 'мес' : 'ամիս'}`);
  const card = h('div', { class: 'card' },
    h('h2', { text: '📅 ' + t('word.period') }), h('div', { class: 'gradline' }),
    h('div', { class: 'grid c2' }, field(t('word.start'), s), field(t('word.end'), e)),
    h('div', { class: 'row' }, quick, plus(2), plus(3), plus(6), plus(12), info,
      h('span', { class: 'tiny muted', text: L ? 'Любой срок — сколько укажете (график по месяцам)' : 'Ցանկացած ժամկետ (գրաֆիկը՝ ըստ ամիսների)' })));
  upd();
  card.append(navRow(L, draw, { onNext: () => {
    const d = days();
    if (d <= 0) { toast(L ? 'Дата окончания раньше начала' : 'Ավարտը սկզբից շուտ է', 'err'); return false; }
    if (d > MAX_DAYS) { toast(L ? 'Слишком длинный период (больше 5 лет)' : 'Շատ երկար ժամանակահատված (5 տարուց ավել)', 'err'); return false; }
  } }));
  return card;
}
const MAX_DAYS = 1830;   // 5 տարի՝ միայն սխալ մուտքագրումից պաշտպանություն
const days = () => {
  if (!P.start || !P.end) return 0;
  return Math.floor((new Date(P.end) - new Date(P.start)) / 86400000) + 1;
};

/* ------------------------------------------------ 3. հասցեներ + ՈՐՈՆՈՒՄ */
function stepAddr(L, draw) {
  const card = h('div', { class: 'card' });
  const counter = h('span', { class: 'badge', text: '0' });
  const q = h('input', { type: 'search', placeholder: (L ? 'Поиск адреса: улица, дом, сеть…'
    : 'Որոնել հասցե՝ փողոց, շենք, ցանց…') });
  const results = h('div');
  const openNets = new Set();

  const total = () => [...P.picked.values()].reduce((a, s) => a + s.size, 0);
  const upd = () => {
    counter.textContent = `${t('word.selected')}: ${total()}`;
    counter.className = 'badge ' + (total() ? 'ok' : 'warn');
  };
  const toggle = (ni, ai, on) => {
    if (!P.picked.has(ni)) P.picked.set(ni, new Set());
    const set = P.picked.get(ni);
    on ? set.add(ai) : set.delete(ai);
    if (!set.size) P.picked.delete(ni);
    upd();
  };
  const row = (ni, ai, addr, netName, needle) => {
    const on = P.picked.get(ni)?.has(ai) || false;
    const cb = h('input', { type: 'checkbox', checked: on });
    cb.addEventListener('change', () => { toggle(ni, ai, cb.checked); li.classList.toggle('sel', cb.checked); });
    const li = h('label', { class: 'li' + (on ? ' sel' : '') }, cb,
      h('div', { class: 't' }, h('b', { html: highlight(addr, needle) }),
        netName ? h('div', { class: 's', html: highlight(netName, needle) }) : null));
    return li;
  };

  async function search() {
    const needle = q.value.trim();
    clear(results);
    if (needle.length >= 2) {
      let rows = [];
      try { rows = await api(`/api/addresses/search?q=${encodeURIComponent(needle)}`, { quiet: true }); } catch (e) { rows = []; }
      const head = h('div', { class: 'row', style: 'margin-bottom:8px' },
        h('span', { class: 'badge plain', text: `${t('word.found')}: ${rows.length}` }),
        rows.length ? h('button', { class: 'btn sm' }, '☑️ ' + t('btn.all')) : null);
      if (rows.length) head.lastChild.addEventListener('click', () => {
        rows.forEach(r => toggle(r.net, r.addr, true)); search();
      });
      results.append(head);
      const list = h('div', { class: 'list scroll' });
      rows.forEach(r => list.append(row(r.net, r.addr, r.address, r.net_name, needle)));
      if (!rows.length) list.append(emptyBox(L ? 'Ничего не найдено' : 'Ոչինչ չգտնվեց', '🔍'));
      results.append(list);
      return;
    }
    // ցանցերով (ակորդեոն)
    P.nets.forEach(n => {
      const picked = P.picked.get(n.index)?.size || 0;
      const open = openNets.has(n.index);
      const head = h('div', { class: 'li', style: 'cursor:pointer;background:var(--card-2)' },
        h('span', { text: open ? '▾' : '▸' }),
        h('div', { class: 't' }, h('b', { text: n.name }),
          h('div', { class: 's', text: `${n.addresses.length} ${L ? 'адресов' : 'հասցե'}` })),
        picked ? h('span', { class: 'badge ok', text: String(picked) }) : null);
      head.addEventListener('click', e => {
        if (e.target.closest('button')) return;
        open ? openNets.delete(n.index) : openNets.add(n.index); search();
      });
      const all = h('button', { class: 'btn sm ghost' }, picked === n.addresses.length ? t('btn.none') : t('btn.all'));
      all.addEventListener('click', e => {
        e.stopPropagation();
        if (picked === n.addresses.length) P.picked.delete(n.index);
        else P.picked.set(n.index, new Set(n.addresses.map((_, i) => i)));
        upd(); search();
      });
      head.append(all);
      const group = h('div', { class: 'list', style: 'margin-bottom:8px' }, head);
      if (open) {
        n.addresses.forEach((a, ai) => group.append(row(n.index, ai, a, '', '')));
        const add = h('button', { class: 'li', style: 'cursor:pointer;color:var(--violet);font-weight:600;border:0;background:var(--card);width:100%;text-align:left' },
          '➕ ' + (L ? 'Новый адрес в эту сеть' : 'Նոր հասցե այս ցանցում'));
        add.addEventListener('click', async () => {
          const txt = await promptDlg(L ? 'Адреса (каждый с новой строки)' : 'Հասցեներ (յուրաքանչյուրը նոր տողից)',
            { textarea: true, title: n.name });
          if (!txt) return;
          const res = await api(`/api/networks/${n.index}/addresses`, { method: 'POST', body: { text: txt } });
          toast(`${t('btn.add')}: ${res.added}` + (res.skipped ? ` · ${L ? 'повторы' : 'կրկնվող'}: ${res.skipped}` : ''));
          P.nets = await api('/api/networks');
          res.indexes.forEach(i => toggle(n.index, i, true));
          S.meta.addresses_total = (S.meta.addresses_total || 0) + res.added;
          search();
        });
        group.append(add);
      }
      results.append(group);
    });
  }
  q.addEventListener('input', debounce(search, 200));

  card.append(h('div', { class: 'card-head' }, h('h2', { text: '📍 ' + t('word.addresses') }),
    h('div', { class: 'right' }, counter,
      h('button', { class: 'btn sm ghost', onClick: () => { P.picked.clear(); upd(); search(); } }, '🧹 ' + t('btn.none')),
      h('button', { class: 'btn sm ghost', onClick: () => window.open('/print/addresses', '_blank') }, '🖨'))),
    h('div', { class: 'search', style: 'margin-bottom:10px' }, q), results);
  upd(); search();
  card.append(navRow(L, draw, { onNext: () => {
    if (!total()) { toast(L ? 'Выберите хотя бы один адрес' : 'Ընտրեք գոնե մեկ հասցե', 'err'); return false; }
  } }));
  return card;
}

/* ------------------------------------------------ 4. ժամեր */
function stepTimes(L, draw) {
  const card = h('div', { class: 'card' });
  const info = h('span', { class: 'badge', text: P.slots.length ? `${P.slots.length}` : '0' });
  const custom = h('input', { type: 'text', placeholder: '10:00-22:00/30' });
  const preview = h('div', { class: 'small muted', style: 'margin-top:8px' });
  const show = () => {
    info.textContent = `${P.slots.length} ${L ? 'выходов/день' : 'հեռարձակում/օր'}`;
    info.className = 'badge ' + (P.slots.length ? 'ok' : 'warn');
    preview.textContent = P.slots.join(' · ');
  };
  const setSlots = async text => {
    try {
      const r = await api('/api/plan/times', { method: 'POST', body: { text }, quiet: true });
      P.slots = r.slots; show();
    } catch (e) { toast(e.message, 'err'); }
  };
  const presets = h('div', { class: 'grid c2' }, ...(S.meta.presets || []).map(p =>
    h('button', { class: 'pick', onClick: () => setSlots(p) },
      h('div', { class: 'pico' }, '🕒'),
      h('div', {}, h('div', { class: 'pt', text: p.replace('/', ' · ') }),
        h('div', { class: 'pd', text: L ? 'готовый график' : 'պատրաստի եթերացանկ' })))));
  const apply = h('button', { class: 'btn' }, t('btn.save'));
  apply.addEventListener('click', () => setSlots(custom.value));
  custom.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); setSlots(custom.value); } });
  card.append(h('div', { class: 'card-head' }, h('h2', { text: '🕒 ' + t('word.times') }), h('div', { class: 'right' }, info)),
    presets, h('div', { class: 'hr' }),
    field(L ? 'Свой график' : 'Ձեր եթերացանկը', h('div', { class: 'inline' }, custom, apply),
      { hint: L ? '10:00-22:00/30 — с 10:00 до 22:00 каждые 30 мин · или 9:00, 13:00, 18:30'
        : '10:00-22:00/30՝ 10:00-ից 22:00՝ յուրաքանչյուր 30 րոպեն մեկ · կամ 9:00, 13:00, 18:30' }),
    preview);
  show();
  card.append(navRow(L, draw, { onNext: () => {
    if (!P.slots.length) { toast(L ? 'Выберите часы' : 'Ընտրեք ժամերը', 'err'); return false; }
  } }));
  return card;
}

/* ------------------------------------------------ 5. հոլովակներ */
function stepClips(L, draw) {
  const card = h('div', { class: 'card' });
  const list = h('div');
  const renumber = () => P.clips.forEach((c, i) => { c.n = i + 1; });
  const drawList = () => {
    clear(list);
    if (!P.clips.length) list.append(emptyBox(L ? 'Добавьте ролик' : 'Ավելացրեք հոլովակ', '🎬'));
    P.clips.forEach((c, i) => {
      const name = h('input', { type: 'text', value: c.name, placeholder: L ? 'Название ролика' : 'Հոլովակի անվանումը' });
      name.addEventListener('input', () => { c.name = name.value; });
      list.append(h('div', { class: 'card', style: 'padding:12px;margin-bottom:10px;background:var(--card-2)' },
        h('div', { class: 'row' },
          h('span', { class: 'badge plain', text: `N°${i + 1}` }),
          h('div', { style: 'flex:1;min-width:180px' }, name),
          c.link ? h('a', { class: 'btn sm', href: c.link, target: '_blank' }, '▶ MP3') : h('span', { class: 'tiny muted', text: L ? 'без ссылки' : 'առանց հղման' }),
          h('button', { class: 'btn sm danger', onClick: () => { P.clips.splice(i, 1); renumber(); drawList(); } }, '🗑')),
        c.file ? h('div', { class: 'tiny muted', style: 'margin-top:6px', text: '🎵 ' + c.file }) : null));
    });
  };
  const addManual = h('button', { class: 'btn' }, '✍️ ' + (L ? 'Добавить вручную' : 'Ավելացնել ձեռքով'));
  addManual.addEventListener('click', async () => {
    const nm = await promptDlg(L ? 'Название ролика' : 'Հոլովակի անվանումը', { placeholder: 'Նոր Տուն-Ֆոնդիտալ' });
    if (!nm) return;
    P.clips.push({ n: P.clips.length + 1, name: nm, file: '', link: null }); drawList();
  });
  const addDrive = h('button', { class: 'btn' }, '☁️ ' + (L ? 'Из Google Drive' : 'Google Drive-ից'));
  addDrive.addEventListener('click', () => drivePicker(L, drawList));
  const upl = h('input', { type: 'file', accept: '.mp3,audio/mpeg', style: 'display:none' });
  upl.addEventListener('change', async () => {
    if (!upl.files.length) return;
    const fd = new FormData(); fd.append('file', upl.files[0]);
    loader(true, L ? 'Загружаю MP3…' : 'Բեռնում եմ MP3-ը…');
    try {
      const r = await api('/api/plan/clip-upload', { method: 'POST', form: fd });
      P.clips.push({ n: P.clips.length + 1, name: r.name.replace(/\.mp3$/i, ''), file: r.name, link: r.link || r.local });
      if (!r.link) toast(L ? 'Ссылка Drive не создана — в плане будет локальная ссылка' : 'Drive հղում չստացվեց՝ պլանում կլինի տեղական հղումը', 'warn');
      drawList();
    } finally { loader(false); upl.value = ''; }
  });
  const addFile = h('button', { class: 'btn' }, '⬆️ ' + (L ? 'Загрузить MP3' : 'Բեռնել MP3'));
  addFile.addEventListener('click', () => upl.click());
  const addLink = h('button', { class: 'btn' }, '🔗 ' + (L ? 'По ссылке' : 'Հղումով'));
  addLink.addEventListener('click', async () => {
    const link = await promptDlg(L ? 'Ссылка на MP3 (Google Drive)' : 'MP3-ի հղում (Google Drive)');
    if (!link) return;
    const nm = await promptDlg(L ? 'Название ролика' : 'Հոլովակի անվանումը');
    if (!nm) return;
    P.clips.push({ n: P.clips.length + 1, name: nm, file: 'Google Drive MP3', link });
    drawList();
  });
  card.append(h('div', { class: 'card-head' }, h('h2', { text: '🎬 ' + t('word.clips') }),
    h('div', { class: 'right' }, addManual, addFile, addDrive, addLink, upl)), list);
  drawList();
  card.append(navRow(L, draw, { onNext: () => {
    if (!P.clips.length) { toast(L ? 'Добавьте хотя бы один ролик' : 'Ավելացրեք գոնե մեկ հոլովակ', 'err'); return false; }
    if (P.clips.some(c => !String(c.name).trim())) { toast(L ? 'У каждого ролика должно быть название' : 'Ամեն հոլովակ պետք է ունենա անվանում', 'err'); return false; }
    P.clips.forEach(c => { if (!P.assign[c.n]) P.assign[c.n] = 'all'; });
  } }));
  return card;
}

async function drivePicker(L, after) {
  loader(true, L ? 'Читаю Google Drive…' : 'Կարդում եմ Google Drive-ը…');
  let data;
  try { data = await api('/api/drive/mp3'); } catch (e) { loader(false); return; } finally { loader(false); }
  const list = h('div', { class: 'list scroll' });
  const q = h('input', { type: 'search', placeholder: t('word.search') + '…' });
  const draw = () => {
    clear(list);
    const needle = q.value.trim().toLowerCase();
    const rows = data.files.filter(f => !needle || f.name.toLowerCase().includes(needle));
    if (!rows.length) list.append(emptyBox(L ? 'MP3 не найдены' : 'MP3 չգտնվեց', '🎵'));
    rows.forEach(f => {
      const play = h('audio', { controls: true, preload: 'none', src: `/api/drive/mp3/${f.id}?name=${encodeURIComponent(f.name)}`,
        style: 'height:32px;max-width:190px' });
      const pick = h('button', { class: 'btn sm primary' }, '✅');
      pick.addEventListener('click', () => {
        P.clips.push({ n: P.clips.length + 1, name: f.name.replace(/\.mp3$/i, ''), file: f.name, link: f.link });
        toast('＋ ' + f.name); after();
      });
      list.append(h('div', { class: 'li' }, h('div', { class: 't' }, h('b', { text: f.name })), play, pick));
    });
  };
  q.addEventListener('input', draw); draw();
  modal({ title: '☁️ Google Drive · MP3', wide: true,
    body: h('div', {}, h('div', { class: 'search', style: 'margin-bottom:10px' }, q),
      h('div', { class: 'tiny muted', style: 'margin-bottom:8px', text: data.folder }), list) });
}

/* ------------------------------------------------ 6. ամփոփում */
function stepSummary(L, draw) {
  const card = h('div', { class: 'card' });
  const addrRows = [];
  P.picked.forEach((set, ni) => set.forEach(ai => {
    const net = P.nets.find(n => n.index === ni);
    if (net) addrRows.push({ net: net.name, addr: net.addresses[ai], clips: [] });
  }));
  const multi = P.clips.length > 1;
  addrRows.forEach(a => {
    a.clips = P.clips.filter(c => {
      const v = P.assign[c.n];
      return v === 'all' || (Array.isArray(v) && v.includes(`${a.net}|${a.addr}`));
    }).map(c => c.n);
    if (!a.clips.length) a.clips = [P.clips[0]?.n || 1];
  });
  const byNet = {};
  addrRows.forEach(a => { byNet[a.net] = (byNet[a.net] || 0) + 1; });
  const total = days() * P.slots.length * addrRows.length;

  card.append(h('h2', { text: '📋 ' + (L ? 'Проверьте данные' : 'Ստուգեք տվյալները') }), h('div', { class: 'gradline' }),
    h('div', { class: 'grid c4', style: 'margin-bottom:14px' },
      kv(t('word.client'), P.client), kv(t('word.days'), nf(days())),
      kv(t('word.addresses'), nf(addrRows.length)), kv(L ? 'Выходов/день' : 'Հեռարձակում/օր', nf(P.slots.length))),
    h('div', { class: 'tile', style: 'margin-bottom:14px' },
      h('div', { class: 'k', text: L ? 'Всего выходов' : 'Ընդամենը հեռարձակում' }),
      h('div', { class: 'v', text: nf(total) }),
      h('div', { class: 'n', text: `${nf(days())} × ${nf(addrRows.length)} × ${nf(P.slots.length)}` })),
    h('div', { class: 'grid c2' },
      h('div', {}, h('h3', { text: t('word.networks') }),
        h('div', { class: 'list scroll sm' }, ...Object.entries(byNet).map(([n, c]) =>
          h('div', { class: 'li' }, h('div', { class: 't' }, h('b', { text: n })), h('span', { class: 'badge', text: String(c) }))))),
      h('div', {}, h('h3', { text: t('word.clips') }),
        h('div', { class: 'list scroll sm' }, ...P.clips.map(c =>
          h('div', { class: 'li' }, h('span', { class: 'badge plain', text: String(c.n) }),
            h('div', { class: 't' }, h('b', { text: c.name })),
            multi ? h('button', { class: 'btn sm ghost', onClick: () => assignDlg(c, addrRows, L, draw) },
              P.assign[c.n] === 'all' ? (L ? 'все адреса' : 'բոլոր հասցեները') : (L ? 'выбранные' : 'ընտրված')) : null))))));

  const result = h('div');
  const seal = h('input', { type: 'checkbox', checked: P.seal !== false });
  seal.addEventListener('change', () => { P.seal = seal.checked; });
  const make = h('button', { class: 'btn primary' }, '✅ ' + (L ? 'Создать медиаплан' : 'Ստեղծել մեդիա պլան'));
  make.addEventListener('click', async () => {
    loader(true, L ? 'Готовлю PDF…' : 'PDF-ը պատրաստվում է…');
    try {
      const res = await api('/api/plan/create', { method: 'POST', body: {
        client: P.client, start: P.start, end: P.end, slots: P.slots,
        addresses: addrRows, clips: P.clips.map(c => ({ n: c.n, name: c.name, file: c.file, link: c.link })),
        seal: seal.checked,
      } });
      clear(result).append(filesResult(res.files));
      toast(t('msg.ready'));
      S.meta.clients = await api('/api/clients', { quiet: true }).catch(() => S.meta.clients);
      result.scrollIntoView({ behavior: 'smooth' });
    } catch (e) { /* toast-ը արդեն ցույց է տրվել */ } finally { loader(false); }
  });
  card.append(h('div', { class: 'row', style: 'margin-top:16px' },
    h('button', { class: 'btn', onClick: () => { P.step--; draw(); } }, '← ' + t('btn.back')),
    h('label', { class: 'row tight small', style: 'margin-left:12px' }, seal,
      L ? '✍️ Подпись и печать Mix Media в конце' : '✍️ Միքս Մեդիա-ի ստորագրություն և կնիք վերջում'),
    h('div', { class: 'spacer' }), make));
  return h('div', {}, card, result);
}

function assignDlg(clip, addrRows, L, draw) {
  const cur = P.assign[clip.n];
  const sel = new Set(Array.isArray(cur) ? cur : addrRows.map(a => `${a.net}|${a.addr}`));
  const list = h('div', { class: 'list scroll' }, ...addrRows.map(a => {
    const key = `${a.net}|${a.addr}`;
    const cb = h('input', { type: 'checkbox', checked: sel.has(key) });
    cb.addEventListener('change', () => cb.checked ? sel.add(key) : sel.delete(key));
    return h('label', { class: 'li' }, cb, h('div', { class: 't' }, h('b', { text: a.addr }), h('div', { class: 's', text: a.net })));
  }));
  modal({ title: `🎬 ${clip.name} · ${t('word.addresses')}`, wide: true, body: list, actions: [
    { label: L ? 'Все адреса' : 'Բոլոր հասցեները', onClick: () => { P.assign[clip.n] = 'all'; draw(); } },
    { label: t('btn.save'), primary: true, onClick: () => {
      if (!sel.size) { toast(L ? 'Выберите адреса' : 'Ընտրեք հասցեները', 'err'); return false; }
      P.assign[clip.n] = sel.size === addrRows.length ? 'all' : [...sel]; draw();
    } }] });
}

const kv = (k, v) => h('div', { class: 'tile plain' }, h('div', { class: 'k', text: k }), h('div', { class: 'v', text: v }));
